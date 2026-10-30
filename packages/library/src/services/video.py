"""视频/缩略图服务：缩略图生成、视频帧提取、HMD 抽帧等纯逻辑。

提取自 app.py — S9（services/video.py），不含 Flask 依赖。
"""
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import threading

from config import (
    THUMBNAILS_DIR, THUMB_WIDTH, THUMB_HEIGHT, THUMB_SEEK_TRY, LUMA_MIN,
    THUMB_MAX_CONCURRENT, _PLACEHOLDER_THUMB_PATH,
)
from utils.path_utils import get_hmd_cache_dir as _get_hmd_cache_dir
from config import USE_PG
from models.cache import is_registered_path as _is_registered_path_cached
if USE_PG:
    from models.pg_store import read_csv
else:
    from models.csv_store import read_csv
from .lazy_loader import (
    _update_preprocess_status,
    _get_hmd_preprocess, _get_hmd_fast_preprocess,
    _get_video_frames_helper,
)

# ── 运行时锁/信号量 ──
_thumb_lock = threading.Lock()
_thumb_semaphore = threading.Semaphore(THUMB_MAX_CONCURRENT)


# ═══════════════════════════════════════════════════════════════════
#  路径校验 & 缓存指纹
# ═══════════════════════════════════════════════════════════════════

def _is_registered_video_path(path):
    """Path must exist in video_manager.csv — whitelist against arbitrary read.
    优先使用缓存索引 O(1)，缓存未就绪时回退到全表扫描。"""
    if not path or not os.path.isabs(path):
        return False
    # 快速路径：缓存索引
    if _is_registered_path_cached(path):
        return True
    # 回退：缓存未就绪时走全表扫描（首次调用等场景）
    norm = os.path.normpath(path).lower()
    for r in read_csv():
        rp = os.path.normpath(r.get("path", "")).lower()
        if rp == norm:
            return True
    return False


def _thumb_cache_key(path, validate_staleness=False):
    """Stable cache key from absolute path + mtime + size（防止 copy2 保留 mtime 导致冲突）。

    Args:
        path: 文件或目录路径
        validate_staleness: 若为 True，返回 (key, current_fingerprint)，
            调用方可比对 fingerprint 判断缓存是否过期。
    """
    try:
        mtime = int(os.path.getmtime(path))
    except OSError:
        mtime = 0
    try:
        if os.path.isfile(path):
            size = os.path.getsize(path)
        elif os.path.isdir(path):
            total_size = 0
            file_count = 0
            for dirpath, _, filenames in os.walk(path):
                file_count += len(filenames)
                for fn in filenames:
                    try:
                        total_size += os.path.getsize(os.path.join(dirpath, fn))
                    except OSError:
                        pass
            size = (file_count << 40) | (total_size & ((1 << 40) - 1))
        else:
            size = 0
    except OSError:
        size = 0

    fingerprint = f"{path}|{mtime}|{size}"
    key = hashlib.sha1(fingerprint.encode("utf-8", errors="replace")).hexdigest()[:24]

    if validate_staleness:
        return key, fingerprint
    return key


def _write_fingerprint(fp_path, fingerprint):
    """原子写入指纹文件（避免并发冲突）。"""
    try:
        tmp = fp_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(fingerprint)
        os.replace(tmp, fp_path)
    except OSError:
        pass


def _read_fingerprint(fp_path):
    """读取指纹文件内容，失败返回 None。"""
    try:
        with open(fp_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════
#  缩略图生成（MP4 / HMD）
# ═══════════════════════════════════════════════════════════════════

def _ffmpeg_avg_luma(video_path, at_sec):
    """Extract a tiny grayscale frame and compute its mean luma (0-255).
    Used to detect 'all-black' thumbnails so we can retry at a different offset."""
    tmp = tempfile.NamedTemporaryFile(suffix=".pgm", delete=False)
    tmp.close()
    try:
        r = subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-ss", f"{at_sec:.2f}",
                "-i", video_path,
                "-vframes", "1",
                "-vf", "scale=64:36,format=gray",
                "-f", "image2",
                tmp.name,
            ],
            capture_output=True, encoding="utf-8", errors="replace", timeout=10,
        )
        if r.returncode != 0 or not os.path.isfile(tmp.name) or os.path.getsize(tmp.name) == 0:
            return None
        with open(tmp.name, "rb") as f:
            data = f.read()
        idx1 = data.index(b"\n", 0) + 1
        idx2 = data.index(b"\n", idx1) + 1
        idx3 = data.index(b"\n", idx2) + 1
        pixels = data[idx3:]
        if not pixels:
            return None
        return sum(pixels) / len(pixels)
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return None
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def _generate_mp4_thumbnail(video_path, out_path):
    """Run ffmpeg to extract a single frame as JPEG.
    Smart seek: tries multiple offsets, picks the first non-black frame.
    Returns True on success.

    Filter note: the old `pad=...:(ow-iw)/2:(oh-ih)/2:black` triggers
    "Padded dimensions cannot be smaller than input dimensions" when the
    input scales to exactly 240x135 (e.g. 1920x1080 source). Use plain
    `scale=W:H:force_original_aspect_ratio=decrease` — aspect-preserving
    and avoids the pad-math edge case.
    """
    vf = f"scale={THUMB_WIDTH}:{THUMB_HEIGHT}:force_original_aspect_ratio=decrease"
    for at in THUMB_SEEK_TRY:
        try:
            r = subprocess.run(
                [
                    "ffmpeg", "-y", "-loglevel", "error",
                    "-ss", f"{at:.2f}",
                    "-i", video_path,
                    "-vframes", "1",
                    "-vf", vf,
                    "-q:v", "5",
                    out_path,
                ],
                capture_output=True, encoding="utf-8", errors="replace", timeout=20,
            )
            if r.returncode != 0 or not os.path.isfile(out_path) or os.path.getsize(out_path) == 0:
                continue
            luma = _ffmpeg_avg_luma(video_path, at)
            if luma is None or luma >= LUMA_MIN:
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            continue
    return os.path.isfile(out_path) and os.path.getsize(out_path) > 0


def _generate_hmd_thumbnail(session_dir, out_path):
    """Generate thumbnail for a HMD session directory.
    Uses the preprocessed left.mp4 / left.h265 in hmd_cache/<basename>/.
    Returns True on success.

    Priority chain: cover.jpg (fast preprocess) → mp4 → h265 → frames/*.jpg.
    Raw .hmd fallback removed — thumbnails must come from preprocess output.
    Each candidate is tried in order; if one fails (e.g. corrupt mp4),
    the next candidate is attempted.
    """
    cache = _get_hmd_cache_dir(session_dir)

    # ── Priority 0: cover.jpg from fast preprocess (instant copy) ──
    cover_path = os.path.join(cache, "cover.jpg")
    if os.path.isfile(cover_path) and os.path.getsize(cover_path) > 0:
        try:
            shutil.copy2(cover_path, out_path)
            if os.path.isfile(out_path) and os.path.getsize(out_path) > 0:
                return True
        except Exception:
            pass

    # ── Build ordered candidate list ──
    candidates = []
    session_basename = os.path.basename(os.path.normpath(session_dir))

    # 1) mp4 (fully processed) — 新命名 + 旧命名兼容
    for name in (
        f"{session_basename}.mp4",
        f"{session_basename}_right.mp4",
        "left.mp4",
        "right.mp4",
    ):
        candidates.append(("mp4", os.path.join(cache, name)))
    # 2) h265 raw streams (preprocessed but not mp4-converted)
    for name in (
        f"{session_basename}.h265",
        f"{session_basename}_right.h265",
        "left.h265",
        "right.h265",
    ):
        candidates.append(("h265", os.path.join(cache, name)))

    # 3) Try first frame jpg from frames/ dir (instant, no ffmpeg)
    frames_dir = os.path.join(cache, "frames")
    if os.path.isdir(frames_dir):
        try:
            jpgs = sorted([f for f in os.listdir(frames_dir) if f.endswith('.jpg')])
            if jpgs:
                shutil.copy2(os.path.join(frames_dir, jpgs[0]), out_path)
                if os.path.isfile(out_path) and os.path.getsize(out_path) > 0:
                    return True
        except Exception:
            pass

    # 4-5) Raw .hmd 回退已移除。
    # 缩略图应按规范跟随预处理产出（cover.jpg / mp4 / h265 / frames），
    # 不再对原始 .hmd 裸流直接跑 ffmpeg，避免无意义的错误日志。
    # 未预处理的 HMD session 应走预处理管道后再生成缩略图。

    # ── Try each candidate in order ──
    for _kind, src in candidates:
        if not os.path.isfile(src):
            continue
        if _generate_mp4_thumbnail(src, out_path):
            return True
        print(f"[thumb] ffmpeg failed on {_kind}: {src}", flush=True)

    return False


def _get_placeholder_thumb():
    """Return path to a tiny neutral placeholder JPEG (240×135 gray).
    Generated once via ffmpeg at first call; reused thereafter.
    Never returns None on error (404-safe fallback)."""
    if os.path.isfile(_PLACEHOLDER_THUMB_PATH) and os.path.getsize(_PLACEHOLDER_THUMB_PATH) > 0:
        return _PLACEHOLDER_THUMB_PATH
    try:
        r = subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-f", "lavfi",
                "-i", "color=c=0x444444:s=240x135:d=0.1",
                "-vframes", "1",
                _PLACEHOLDER_THUMB_PATH,
            ],
            capture_output=True, encoding="utf-8", errors="replace", timeout=10,
        )
        if r.returncode == 0 and os.path.isfile(_PLACEHOLDER_THUMB_PATH):
            return _PLACEHOLDER_THUMB_PATH
    except Exception:
        pass
    try:
        _write_minimal_jpeg(_PLACEHOLDER_THUMB_PATH)
        if os.path.isfile(_PLACEHOLDER_THUMB_PATH):
            return _PLACEHOLDER_THUMB_PATH
    except Exception:
        pass
    return None


def _write_minimal_jpeg(path):
    """Write an ultra-minimal valid 1×1 gray JPEG as last-resort placeholder."""
    buf = bytearray()
    buf += b'\xff\xd8'
    buf += b'\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
    buf += b'\xff\xdb\x00\x43\x00'
    qt = [16,11,10,16,24,40,51,61,12,12,14,19,26,58,60,55,
          14,13,16,24,40,57,69,56,14,17,22,29,51,87,80,62,
          18,22,37,56,68,109,103,77,24,35,55,64,81,104,113,92,
          49,64,78,87,103,121,120,101,72,92,95,98,112,100,103,99]
    buf += bytes(qt)
    buf += b'\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00'
    buf += b'\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b'
    buf += b'\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04\x04\x00\x00\x01\x7d\x01\x02\x03\x00\x04\x11\x05\x12\x21\x31\x41\x06\x13\x51\x61\x07\x22\x71\x14\x32\x81\x91\xa1\x08\x23\x42\xb1\xc1\x15\x52\xd1\xf0\x24\x33\x62\x72\x82\x09\x0a\x16\x17\x18\x19\x1a\x25\x26\x27\x28\x29\x2a\x34\x35\x36\x37\x38\x39\x3a\x43\x44\x45\x46\x47\x48\x49\x4a\x53\x54\x55\x56\x57\x58\x59\x5a\x63\x64\x65\x66\x67\x68\x69\x6a\x73\x74\x75\x76\x77\x78\x79\x7a\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa'
    buf += b'\xff\xda\x00\x08\x01\x01\x00\x00\x3f\x00\x7b\xf9\xff'
    buf += b'\xff\xd9'
    with open(path, "wb") as f:
        f.write(buf)


# ═══════════════════════════════════════════════════════════════════
#  HMD 抽帧
# ═══════════════════════════════════════════════════════════════════

def _extract_hmd_frames(session_dir, output_dir, num_frames=6, width=320):
    """Extract multiple frames from HMD video at even intervals.

    Args:
        session_dir: Path to HMD session directory
        output_dir: Directory to save extracted frames
        num_frames: Number of frames to extract (default 6)
        width: Width of extracted frames (height auto)

    Returns:
        list of (timestamp_sec, frame_path) tuples, or empty list on failure
    """
    cache = _get_hmd_cache_dir(session_dir)
    session_basename = os.path.basename(os.path.normpath(session_dir))

    candidates = [
        os.path.join(cache, f"{session_basename}.mp4"),
        os.path.join(cache, f"{session_basename}.h265"),
        os.path.join(cache, f"{session_basename}_right.mp4"),
        os.path.join(cache, "left.mp4"),
        os.path.join(cache, "left.h265"),
        os.path.join(cache, "right.mp4"),
    ]
    if os.path.isdir(session_dir):
        for fn in sorted(os.listdir(session_dir)):
            if fn.startswith("part_") and fn.endswith(".hmd"):
                candidates.append(os.path.join(session_dir, fn))
                break

    src = next((c for c in candidates if os.path.isfile(c)), None)
    if not src:
        return []

    # Get video duration — 优先从状态文件读取（避免 ffprobe 逐帧解析 h265 流）
    duration = None

    hmd_fast = _get_hmd_fast_preprocess()
    if hmd_fast:
        fast_status = hmd_fast.get_status_path(session_dir)
        if os.path.isfile(fast_status):
            try:
                with open(fast_status, "r", encoding="utf-8") as f:
                    fs = json.load(f)
                if fs.get("duration_sec", 0) > 0:
                    duration = fs["duration_sec"]
            except Exception:
                pass

    if duration is None:
        hmd_pre = _get_hmd_preprocess()
        if hmd_pre:
            proc_status = hmd_pre.get_status_path(session_dir)
            if os.path.isfile(proc_status):
                try:
                    with open(proc_status, "r", encoding="utf-8") as f:
                        ps = json.load(f)
                    if ps.get("duration_sec", 0) > 0:
                        duration = ps["duration_sec"]
                except Exception:
                    pass

    if duration is None:
        try:
            r = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", src],
                capture_output=True, encoding="utf-8", errors="replace", timeout=10
            )
            if r.returncode == 0 and r.stdout.strip():
                duration = float(r.stdout.strip())
        except (subprocess.TimeoutExpired, ValueError, Exception):
            pass

    if duration is None or duration <= 0:
        duration = 30.0

    if duration < 1.0:
        duration = 1.0
    safe_duration = max(0.5, duration - 0.5)
    timestamps = [safe_duration * (i + 1) / num_frames for i in range(num_frames)]

    os.makedirs(output_dir, exist_ok=True)
    results = []
    vf = f"scale={width}:-1:force_original_aspect_ratio=decrease"

    for i, ts in enumerate(timestamps):
        out_path = os.path.join(output_dir, f"frame_{i:02d}.jpg")
        try:
            r = subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error",
                 "-ss", f"{ts:.2f}",
                 "-i", src,
                 "-vframes", "1",
                 "-vf", vf,
                 "-q:v", "5",
                 out_path],
                capture_output=True, encoding="utf-8", errors="replace", timeout=15
            )
            if r.returncode == 0 and os.path.isfile(out_path) and os.path.getsize(out_path) > 0:
                results.append((ts, out_path))
        except (subprocess.TimeoutExpired, Exception):
            continue

    return results


def _is_hmd_session(p):
    """Check if path is a HMD session (file or directory)."""
    if p.lower().endswith(".hmd"):
        return True
    if os.path.isdir(p):
        if os.path.isfile(os.path.join(p, "metadata.json")):
            return True
        try:
            if any(f.endswith(".hmd") for f in os.listdir(p)):
                return True
        except Exception:
            pass
        cache_dir = _get_hmd_cache_dir(p)
        if os.path.isdir(cache_dir):
            try:
                if any(f.endswith((".mp4", ".h265")) for f in os.listdir(cache_dir)):
                    return True
            except Exception:
                pass
    return False


# ═══════════════════════════════════════════════════════════════════
#  缩略图/帧 确保调度（防过期 + 并发安全）
# ═══════════════════════════════════════════════════════════════════

def _ensure_thumbnail(path, kind):
    """Return cache file path; create on demand. Returns None if generation fails.
    Updates _PREPROCESS_STATUS[path]["thumb"] along the way.

    防过期：缓存 key 包含文件大小指纹，源文件变化时自动重新生成。
    """
    key, fp = _thumb_cache_key(path, validate_staleness=True)
    cache_path = os.path.join(THUMBNAILS_DIR, f"{key}.jpg")
    fp_path = cache_path + ".fp"

    if os.path.isfile(cache_path) and os.path.getsize(cache_path) > 0:
        stored_fp = _read_fingerprint(fp_path)
        if stored_fp and stored_fp == fp:
            _update_preprocess_status(path, thumb="done", thumb_progress=100)
            return cache_path
        try:
            os.unlink(cache_path)
            if os.path.isfile(fp_path):
                os.unlink(fp_path)
        except OSError:
            pass

    _update_preprocess_status(path, thumb="processing", thumb_progress=10)
    with _thumb_semaphore:
        with _thumb_lock:
            if os.path.isfile(cache_path) and os.path.getsize(cache_path) > 0:
                stored_fp = _read_fingerprint(fp_path)
                if stored_fp and stored_fp == fp:
                    _update_preprocess_status(path, thumb="done", thumb_progress=100)
                    return cache_path

            _update_preprocess_status(path, thumb_progress=30)
            ok = False
            if kind == "mp4":
                if _generate_mp4_thumbnail(path, cache_path):
                    ok = True
            elif kind == "hmd":
                if _generate_hmd_thumbnail(path, cache_path):
                    ok = True
            if ok:
                _write_fingerprint(fp_path, fp)
                _update_preprocess_status(path, thumb="done", thumb_progress=100)
                return cache_path
            else:
                _update_preprocess_status(path, thumb="error", thumb_progress=0)
                return None
    return None


def _ensure_frames(path, kind, num_frames=6, width=320):
    """Return frames directory path; create frames on demand.

    防过期：通过指纹文件校验源文件是否变化。
    """
    key, fp = _thumb_cache_key(path, validate_staleness=True)
    frames_dir = os.path.join(THUMBNAILS_DIR, 'frames', key)
    fp_path = os.path.join(frames_dir, '.fingerprint')

    if os.path.isdir(frames_dir):
        existing_frames = [f for f in os.listdir(frames_dir) if f.endswith('.jpg')]
        if len(existing_frames) >= num_frames:
            stored_fp = _read_fingerprint(fp_path)
            if stored_fp and stored_fp == fp:
                _update_preprocess_status(path, frames="done", frames_progress=100)
                return frames_dir
            try:
                for fn in os.listdir(frames_dir):
                    if fn.startswith('.fingerprint'):
                        continue
                    os.unlink(os.path.join(frames_dir, fn))
            except OSError:
                pass

    _update_preprocess_status(path, frames="processing", frames_progress=10)

    try:
        os.makedirs(frames_dir, exist_ok=True)

        if kind == "mp4":
            helper = _get_video_frames_helper()
            if not helper:
                _update_preprocess_status(path, frames="error", frames_progress=0)
                return None
            _update_preprocess_status(path, frames_progress=30)
            results = helper.extract_video_frames(path, frames_dir, num_frames=num_frames, width=width)
            if results and len(results) > 0:
                _write_fingerprint(fp_path, fp)
                _update_preprocess_status(path, frames="done", frames_progress=100)
                return frames_dir
            else:
                _update_preprocess_status(path, frames="error", frames_progress=0)
                return None

        elif kind == "hmd":
            hmd_fast = _get_hmd_fast_preprocess()
            hmd_pre = _get_hmd_preprocess()
            has_source = False

            if hmd_fast:
                h265_path = hmd_fast.get_h265_path(path, "left")
                if os.path.isfile(h265_path) and os.path.getsize(h265_path) > 0:
                    has_source = True
            if not has_source and hmd_pre:
                left_mp4 = hmd_pre.get_mp4_path(path, "left")
                if os.path.isfile(left_mp4):
                    has_source = True

            if not has_source:
                cache_dir = _get_hmd_cache_dir(path)
                session_bn = os.path.basename(os.path.normpath(path))
                for src_name in (
                    f"{session_bn}.h265", f"{session_bn}.mp4", f"{session_bn}_right.mp4",
                    "left.h265", "left.mp4", "right.mp4",
                ):
                    if os.path.isfile(os.path.join(cache_dir, src_name)):
                        has_source = True
                        break

            if not has_source:
                _update_preprocess_status(path, frames="pending", frames_progress=0)
                return None

            _update_preprocess_status(path, frames_progress=30)
            results = _extract_hmd_frames(path, frames_dir, num_frames=num_frames, width=width)
            if results and len(results) > 0:
                _write_fingerprint(fp_path, fp)
                _update_preprocess_status(path, frames="done", frames_progress=100)
                return frames_dir
            else:
                _update_preprocess_status(path, frames="error", frames_progress=0)
                return None
        else:
            _update_preprocess_status(path, frames="error", frames_progress=0)
            return None

    except Exception as e:
        print(f"[frames] Error extracting frames for {path}: {e}", file=sys.stderr)
        _update_preprocess_status(path, frames="error", frames_progress=0)
        return None
