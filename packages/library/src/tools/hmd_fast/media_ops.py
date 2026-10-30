#!/usr/bin/env python
"""HMD fast preprocess -- decode, remux, frame extraction, cover generation."""

import os
import re
import subprocess
import sys
import threading
import shutil

from tools.hmd_fast.path_utils import (
    FRAME_RATE, list_parts,
)


# ── 找到 ffmpeg 二进制 ──
# 系统 PATH 没有 ffmpeg，但项目自带一份在 D:/sp/dev/video-sort-package/tools/ffmpeg/bin
# 如果 ffmpeg 已经在 PATH 上（其他位置），优先用系统的
def _find_ffmpeg():
    """查找 ffmpeg 可执行文件路径，找不到返回 None"""
    # 1) PATH 中查找
    p = shutil.which("ffmpeg")
    if p:
        return p
    # 2) 项目自带
    candidates = [
        r"D:\sp\dev\video-sort-package\tools\ffmpeg\bin\ffmpeg.exe",
        r"D:\sp\tools\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


FFMPEG_BIN = _find_ffmpeg()


# ── Core: decode HMD -> left.h265 ──

def run_decode(folder, left_h265, status_cb, decode_timeout=3600):
    """Call hmd_decode_py.py subprocess to decode HMD and split left/right eyes, outputting left.h265.

    Args:
        folder: HMD session folder path
        left_h265: output left.h265 path
        status_cb: progress callback
        decode_timeout: max seconds for the entire decode (default 1 hour)

    Returns:
        (left_frames, right_frames) -- left/right eye frame counts
    """
    parts = list_parts(folder)
    if not parts:
        raise FileNotFoundError(f"No part_*.hmd files in {folder}")

    # Estimate HEVC size from part files for timeout scaling
    total_part_size = sum(os.path.getsize(p) for p in parts)
    # HEVC extraction from HMD is ~50% overhead, so temp file ~1.5x total parts
    # For very large sessions (> 5GB parts), increase timeout proportionally
    if total_part_size > 5 * 1024 * 1024 * 1024:  # > 5 GB
        decode_timeout = max(decode_timeout, int(total_part_size / (50 * 1024 * 1024)))  # ~50MB/s
        print(f"      [large session: {total_part_size/1024/1024/1024:.1f} GB parts, "
              f"timeout={decode_timeout/60:.0f}min]", flush=True)

    script = os.path.join(os.path.dirname(os.path.dirname(__file__)), "hmd_decode_py.py")
    cmd = [sys.executable, script, left_h265]
    cmd.extend(parts)  # only output left eye (no right_out arg)

    env = os.environ.copy()
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace", env=env
    )

    # Read stdout in a thread so we can enforce timeout
    output_lines = []

    def _read_stdout():
        try:
            for line in proc.stdout:
                output_lines.append(line)
        except Exception:
            pass

    reader = threading.Thread(target=_read_stdout, daemon=True)
    reader.start()

    try:
        reader.join(timeout=decode_timeout)
        if reader.is_alive():
            proc.kill()
            proc.wait()
            raise TimeoutError(
                f"HMD decode timed out after {decode_timeout/60:.0f}min "
                f"(parts: {total_part_size/1024/1024/1024:.1f} GB). "
                f"Session may be too large to decode efficiently."
            )

        # Process captured output lines
        last_progress = 0
        last_printed = 0
        for line in output_lines:
            line = line.strip()
            m = re.match(r"PROGRESS:([\d.]+)", line)
            if m:
                pct = float(m.group(1))
                if pct > last_progress:
                    last_progress = pct
                    status_cb({"progress": pct * 0.80, "stage": "decode+split"})
                # Print progress every 10%
                pct10 = int(pct / 10)
                if pct10 > last_printed:
                    last_printed = pct10
                    print(f"      decode {int(pct)}% ...", flush=True)
            elif line.startswith("DONE:"):
                parts_info = line[5:].split(":")
                return int(parts_info[0]), int(parts_info[1])

        # If we get here, stdout closed without DONE
        proc.wait()
        if proc.returncode != 0:
            stderr = proc.stderr.read()
            raise RuntimeError(f"HMD decode failed (exit {proc.returncode}): {stderr[:500]}")
        raise RuntimeError("HMD decode completed without DONE marker")
    finally:
        pass


# ── Get duration from h265 (using ffprobe) ──

def get_h265_duration(h265_path):
    """Use ffprobe to get raw h265 stream duration (seconds).

    Note: raw h265 stream has no container duration; ffprobe parses frames to calculate.
    For long videos may be slow (~few seconds); as fallback use frame_count/30.
    """
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", h265_path],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30
        )
        if r.returncode == 0 and r.stdout.strip():
            return float(r.stdout.strip())
    except (subprocess.TimeoutExpired, ValueError, Exception):
        pass
    return None


# ── H.265 -> MP4 fast remux (stream copy, seconds-level) ──

def remux_h265_to_mp4(h265_path, mp4_path):
    """Remux raw H.265 stream to MP4 container (-c:v copy, no re-encoding).

    Remux speed ~400 MB/s, 736MB file ~1.7 seconds.
    MP4 container supports fast seek (input seek), greatly improving subsequent frame/cover extraction.
    """
    ffmpeg = FFMPEG_BIN or "ffmpeg"
    cmd = [
        ffmpeg, "-y", "-loglevel", "error",
        "-i", h265_path,
        "-c:v", "copy", "-tag:v", "hvc1",
        "-f", "mp4", "-movflags", "+faststart",
        mp4_path
    ]
    p = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                       text=True, encoding="utf-8", errors="replace", timeout=120)
    if p.returncode != 0:
        raise RuntimeError(f"remux failed: {p.stderr[-300:]}")
    if not os.path.isfile(mp4_path) or os.path.getsize(mp4_path) == 0:
        raise RuntimeError("remux produced empty file")


def ensure_mp4(source_folder, eye="left"):
    """Ensure mp4 file exists; if not, fast-remux from h265."""
    from tools.hmd_fast.path_utils import get_mp4_path as _get_mp4, get_h265_path as _get_h265
    mp4_path = _get_mp4(source_folder, eye)
    if os.path.isfile(mp4_path) and os.path.getsize(mp4_path) > 0:
        return mp4_path
    h265_path = _get_h265(source_folder, eye)
    if not os.path.isfile(h265_path) or os.path.getsize(h265_path) <= 0:
        raise FileNotFoundError(f"h265 not found: {h265_path}")
    remux_h265_to_mp4(h265_path, mp4_path)
    return mp4_path


# ── Get duration from MP4 (using ffprobe, seconds-level) ──

def get_mp4_duration(mp4_path):
    """Use ffprobe to get mp4 container duration. MP4 has full timestamps, returns instantly."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", mp4_path],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
        )
        if r.returncode == 0 and r.stdout.strip():
            return float(r.stdout.strip())
    except (subprocess.TimeoutExpired, ValueError, Exception):
        pass
    return None


# ── Extract frames from h265 ──

def extract_frames_from_h265(h265_path, frames_dir, duration_sec, num_frames=6, width=320):
    """Extract N preview frames from h265 raw stream.

    Strategy:
    1. Use select filter for single-pass extraction (most efficient)
    2. On timeout or insufficient frames, fall back to per-frame output seek (compatible with low-spec machines/long videos)

    Raw H.265 stream has no container timestamps, must use output seek (-ss after -i) or select filter.

    Returns:
        list of (timestamp_sec, frame_path) tuples
    """
    if duration_sec < 1.0:
        duration_sec = 1.0
    # Safe offset: avoid seeking to end causing decode failure
    safe_duration = max(0.5, duration_sec - 0.5)
    timestamps = [safe_duration * (i + 1) / num_frames for i in range(num_frames)]

    os.makedirs(frames_dir, exist_ok=True)

    # Clear old frames (avoid residual interference with counting)
    for old in os.listdir(frames_dir):
        if old.startswith("frame_") and old.endswith(".jpg"):
            try:
                os.remove(os.path.join(frames_dir, old))
            except OSError:
                pass

    # ── Plan A: select filter (single pass) ──
    # Timeout estimated from video duration: h265 decode ~200x realtime, with margin
    select_timeout = max(60, int(duration_sec / 100) + 30)
    frame_nums = [int(ts * FRAME_RATE) for ts in timestamps]
    select_parts = [f"eq(n,{fn})" for fn in frame_nums]
    select_expr = "+".join(select_parts)

    vf = f"select='{select_expr}',scale={width}:-1:force_original_aspect_ratio=decrease"
    out_pattern = os.path.join(frames_dir, "frame_%02d.jpg")

    print(f"      ffmpeg select filter (timeout {select_timeout}s) ...", flush=True)
    try:
        subprocess.run(
            [FFMPEG_BIN or "ffmpeg", "-y", "-loglevel", "error",
             "-r", f"{FRAME_RATE}",
             "-i", h265_path,
             "-vf", vf,
             "-vsync", "vfr",
             "-q:v", "5",
             out_pattern],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
            timeout=select_timeout
        )
    except (subprocess.TimeoutExpired, Exception):
        pass

    # Collect results from select plan
    results = _collect_frame_results(frames_dir, timestamps, safe_duration, num_frames)
    if len(results) >= num_frames:
        return results

    # ── Plan B: per-frame output seek (fallback) ──
    print(f"      select got {len(results)}/{num_frames}, falling back to per-frame seek ...", flush=True)
    # Clean up partial frames from select, ensure no residuals
    for old in os.listdir(frames_dir):
        if old.startswith("frame_") and old.endswith(".jpg"):
            try:
                os.remove(os.path.join(frames_dir, old))
            except OSError:
                pass

    vf_fallback = f"scale={width}:-1:force_original_aspect_ratio=decrease"
    for i, ts in enumerate(timestamps):
        out_path = os.path.join(frames_dir, f"frame_{i:02d}.jpg")
        print(f"      frame {i+1}/{num_frames} @ {ts:.1f}s ...", flush=True)
        try:
            subprocess.run(
                [FFMPEG_BIN or "ffmpeg", "-y", "-loglevel", "error",
                 "-r", f"{FRAME_RATE}",
                 "-i", h265_path,
                 "-ss", f"{ts:.2f}",
                 "-vframes", "1",
                 "-vf", vf_fallback,
                 "-q:v", "5",
                 out_path],
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace",
                timeout=max(60, int(duration_sec / 50) + 10)
            )
        except (subprocess.TimeoutExpired, Exception):
            continue

    return _collect_frame_results(frames_dir, timestamps, safe_duration, num_frames)


def _collect_frame_results(frames_dir, timestamps, safe_duration, num_frames):
    """Collect generated frames from frames directory, sorted by filename mapped to timestamps."""
    results = []
    jpgs = sorted([f for f in os.listdir(frames_dir)
                   if f.startswith("frame_") and f.endswith(".jpg")])
    for i, fname in enumerate(jpgs):
        out_path = os.path.join(frames_dir, fname)
        if os.path.getsize(out_path) > 0:
            ts = timestamps[i] if i < len(timestamps) else (i + 1) * safe_duration / num_frames
            results.append((ts, out_path))
    return results


# ── Extract frames from MP4 (using container index, input seek is very fast) ──

def extract_frames_from_mp4(mp4_path, frames_dir, duration_sec, num_frames=6, width=320):
    """Quickly extract N preview frames from MP4 container.

    Leverages MP4 container moov index, using input seek (-ss before -i),
    2-5x faster than output seeking from raw H.265 stream.

    Returns:
        list of (timestamp_sec, frame_path) tuples
    """
    if duration_sec < 1.0:
        duration_sec = 1.0
    safe_duration = max(0.5, duration_sec - 0.5)
    timestamps = [safe_duration * (i + 1) / num_frames for i in range(num_frames)]

    os.makedirs(frames_dir, exist_ok=True)

    # Clear old frames
    for old in os.listdir(frames_dir):
        if old.startswith("frame_") and old.endswith(".jpg"):
            try:
                os.remove(os.path.join(frames_dir, old))
            except OSError:
                pass

    vf = f"scale={width}:-1:force_original_aspect_ratio=decrease"
    results = []

    for i, ts in enumerate(timestamps):
        out_path = os.path.join(frames_dir, f"frame_{i:02d}.jpg")
        try:
            subprocess.run(
                [FFMPEG_BIN or "ffmpeg", "-y", "-loglevel", "error",
                 "-ss", f"{ts:.2f}",           # input seek (before -i, fast on mp4)
                 "-i", mp4_path,
                 "-vframes", "1",
                 "-vf", vf,
                 "-q:v", "5",
                 out_path],
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace",
                timeout=max(30, int(duration_sec / 100) + 10)
            )
            if os.path.isfile(out_path) and os.path.getsize(out_path) > 0:
                results.append((ts, out_path))
        except (subprocess.TimeoutExpired, Exception):
            continue

    return results


# ── Generate cover thumbnail (grab frame 1) ──

def generate_cover_from_h265(h265_path, out_path, width=240, height=135):
    """Grab a frame from h265 stream as cover.

    Raw H.265 stream has no container timestamps, must use output seek (-ss after -i)
    to decode frame-by-frame to target position.
    For early offsets (0.5s~10s) decode volume is small, speed is acceptable.

    Smart frame seeking: tries multiple offsets, skips black frames.
    Returns True on success.
    """
    vf = f"scale={width}:{height}:force_original_aspect_ratio=decrease"
    LUMA_MIN = 30  # brightness threshold

    for at in [0.5, 1.0, 2.0, 3.0, 5.0, 10.0]:
        try:
            r = subprocess.run(
                [FFMPEG_BIN or "ffmpeg", "-y", "-loglevel", "error",
                 "-r", f"{FRAME_RATE}",
                 "-i", h265_path,
                 "-ss", f"{at:.2f}",
                 "-vframes", "1",
                 "-vf", vf,
                 "-q:v", "5",
                 out_path],
                capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=30
            )
            if r.returncode != 0 or not os.path.isfile(out_path) or os.path.getsize(out_path) == 0:
                continue
            # Brightness detection
            luma = _ffmpeg_avg_luma(h265_path, at)
            if luma is None or luma >= LUMA_MIN:
                return True
        except (subprocess.TimeoutExpired, Exception):
            continue
    return os.path.isfile(out_path) and os.path.getsize(out_path) > 0


def _ffmpeg_avg_luma(video_path, at_sec):
    """Use ffmpeg to extract a single grayscale frame, calculate average brightness."""
    import tempfile
    tmp = tempfile.NamedTemporaryFile(suffix=".pgm", delete=False)
    tmp.close()
    try:
        r = subprocess.run(
            [FFMPEG_BIN or "ffmpeg", "-y", "-loglevel", "error",
             "-r", f"{FRAME_RATE}",
             "-i", video_path,
             "-ss", f"{at_sec:.2f}",
             "-vframes", "1",
             "-vf", "scale=64:36,format=gray",
             "-f", "image2", tmp.name],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=10
        )
        if r.returncode != 0 or not os.path.isfile(tmp.name) or os.path.getsize(tmp.name) == 0:
            return None
        with open(tmp.name, "rb") as f:
            data = f.read()
        # PGM: pixel data after 3rd newline
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


# ── Generate cover from MP4 (using input seek, very fast) ──

def generate_cover_from_mp4(mp4_path, out_path, width=240, height=135):
    """Grab a frame from MP4 container as cover.

    Leverages MP4 container moov index, using input seek (-ss before -i),
    4-5x faster and more reliable than output seeking from raw H.265 stream.
    Smart frame seeking: tries multiple offsets, skips black frames.
    Returns True on success.
    """
    vf = f"scale={width}:{height}:force_original_aspect_ratio=decrease"
    LUMA_MIN = 30

    for at in [0.5, 1.0, 2.0, 3.0, 5.0, 10.0]:
        try:
            r = subprocess.run(
                [FFMPEG_BIN or "ffmpeg", "-y", "-loglevel", "error",
                 "-ss", f"{at:.2f}",              # input seek, fast on mp4
                 "-i", mp4_path,
                 "-vframes", "1",
                 "-vf", vf,
                 "-q:v", "5",
                 out_path],
                capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=15
            )
            if r.returncode != 0 or not os.path.isfile(out_path) or os.path.getsize(out_path) == 0:
                continue
            # Brightness detection
            luma = _ffmpeg_avg_luma_mp4(mp4_path, at)
            if luma is None or luma >= LUMA_MIN:
                return True
        except (subprocess.TimeoutExpired, Exception):
            continue
    return os.path.isfile(out_path) and os.path.getsize(out_path) > 0


def _ffmpeg_avg_luma_mp4(mp4_path, at_sec):
    """Same as _ffmpeg_avg_luma but uses input seek (mp4 fast seek)."""
    import tempfile
    tmp = tempfile.NamedTemporaryFile(suffix=".pgm", delete=False)
    tmp.close()
    try:
        r = subprocess.run(
            [FFMPEG_BIN or "ffmpeg", "-y", "-loglevel", "error",
             "-ss", f"{at_sec:.2f}",          # input seek
             "-i", mp4_path,
             "-vframes", "1",
             "-vf", "scale=64:36,format=gray",
             "-f", "image2", tmp.name],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=10
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
