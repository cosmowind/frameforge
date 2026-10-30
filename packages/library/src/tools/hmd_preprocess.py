#!/usr/bin/env python
"""HMD preprocessor: splitStereo + ffmpeg → left.mp4 only

Usage:
    python hmd_preprocess.py <session_folder>

Output (configurable via env HMD_CACHE_ROOT, default <project>/hmd_cache/):
    <CACHE_ROOT>/<session_basename>/.hmd_process.json    (status file)
    <CACHE_ROOT>/<session_basename>/left.h265 + left.mp4
    [<CACHE_ROOT>/<session_basename>/right.h265 + right.mp4]  (optional, if env HMD_PROCESS_BOTH_EYES=1)

This is the SERVER-side counterpart to hmd-decode.js. It runs splitStereo
via Node.js + ffmpeg in a background thread, so the browser can use
native <video src="left.mp4"> playback (no WebCodecs/canvas overhead).

NOTE (2026-06-17): by default only the left-eye stream is generated because
the left eye alone is enough to understand what the video is about, and
skipping the right-eye ffmpeg step roughly halves preprocessing time.
Set env var HMD_PROCESS_BOTH_EYES=1 to enable both eyes (e.g. for stereo
inspection / measurement workflows).
"""
import json
import os
import sys
import time
import threading

# ── Path utilities, decode & transcode operations (split into _ops module) ──
try:
    from hmd_preprocess_ops import (  # noqa: F401 – re-exported for callers
        STATUS_FILE, FRAME_RATE,
        _project_root, get_cache_root, _extract_date_from_path,
        get_output_dir, get_status_path, get_mp4_path, get_h265_path,
        _get_folder_lock, write_status, list_parts, check_done, _both_eyes,
        run_python_decode, run_node_decode, ffmpeg_to_mp4, ffmpeg_to_h264_mp4,
    )
except ImportError:
    from tools.hmd_preprocess_ops import (
        STATUS_FILE, FRAME_RATE,
        _project_root, get_cache_root, _extract_date_from_path,
        get_output_dir, get_status_path, get_mp4_path, get_h265_path,
        _get_folder_lock, write_status, list_parts, check_done, _both_eyes,
        run_python_decode, run_node_decode, ffmpeg_to_mp4, ffmpeg_to_h264_mp4,
    )


def process_mp4_only(folder):
    """仅编码：从已有的 left.h265 生成 left.mp4。

    前提：left.h265 已存在（由 tools.hmd_fast 或其他方式生成）。
    不会重新解码 HMD 文件。
    成功后删除 left.h265 并写入 .hmd_process.json。

    Returns:
        dict: {"left_mp4": path, "right_mp4": path or None}
    """
    left_h265 = get_h265_path(folder, "left")
    if not os.path.isfile(left_h265):
        raise FileNotFoundError(f"left.h265 not found (run fast preprocess first): {left_h265}")

    os.makedirs(get_output_dir(folder), exist_ok=True)

    # 尝试从 fast status 读取帧数/时长
    fast_status_file = os.path.join(get_output_dir(folder), ".hmd_fast.json")
    left_frames = 0
    duration_sec = 0.0
    if os.path.isfile(fast_status_file):
        try:
            with open(fast_status_file, "r", encoding="utf-8") as f:
                fs = json.load(f)
            left_frames = fs.get("left_frames", 0)
            duration_sec = fs.get("duration_sec", 0.0)
        except Exception:
            pass

    started_at = _status_started(folder)
    write_status(folder, {
        "status": "processing",
        "stage": "muxing-mp4",
        "progress": 90,
        "started_at": started_at,
    })

    left_mp4 = get_mp4_path(folder, "left")
    ffmpeg_to_mp4(left_h265, left_mp4)

    # 删除中间的 .h265 文件
    if os.path.isfile(left_h265):
        try:
            os.remove(left_h265)
        except OSError:
            pass

    # 检查是否也有 right.h265
    both = _both_eyes()
    right_mp4_path = None
    if both:
        right_h265 = get_h265_path(folder, "right")
        if os.path.isfile(right_h265):
            write_status(folder, {
                "status": "processing",
                "stage": "muxing-right",
                "progress": 95,
                "started_at": started_at,
            })
            right_mp4 = get_mp4_path(folder, "right")
            ffmpeg_to_mp4(right_h265, right_mp4)
            if os.path.isfile(right_h265):
                try:
                    os.remove(right_h265)
                except OSError:
                    pass
            right_mp4_path = "right.mp4"

    if not duration_sec and left_frames > 0:
        duration_sec = left_frames / FRAME_RATE

    session_basename = os.path.basename(os.path.normpath(folder))
    left_mp4_name = f"{session_basename}.mp4"

    status_done = {
        "status": "done",
        "progress": 100,
        "stage": "done",
        "left_frames": left_frames,
        "right_frames": 0,
        "duration_sec": duration_sec,
        "left_mp4": left_mp4_name,
        "finished_at": time.time(),
    }
    if right_mp4_path:
        status_done["right_mp4"] = f"{session_basename}_right.mp4"
    write_status(folder, status_done)

    return {"left_mp4": left_mp4, "right_mp4": right_mp4_path}


def process_folder(folder):
    """Full pipeline: parse + split + ffmpeg → left.mp4 (and optionally right.mp4).

    Default mode (env HMD_PROCESS_BOTH_EYES unset/0/false):
      - Decodes splitStereo → left.h265 only (skip right decoding in Node)
      - ffmpeg left.h265 → left.mp4
      - Skips right.mp4 entirely
      - ~50% faster than both-eyes mode

    Both-eyes mode (env HMD_PROCESS_BOTH_EYES=1):
      - Decodes both, muxes both

    NOTE: This is the LEGACY full pipeline (kept for reference).
    Prefer tools.hmd_fast + process_mp4_only() for split-stage workflow.
    """
    parts = list_parts(folder)
    if not parts:
        raise FileNotFoundError(f"No part_*.hmd files in {folder}")

    # Ensure output dir exists
    os.makedirs(get_output_dir(folder), exist_ok=True)

    write_status(folder, {
        "status": "processing",
        "stage": "starting",
        "progress": 0,
        "started_at": time.time(),
    })

    left_h265 = get_h265_path(folder, "left")
    left_mp4 = get_mp4_path(folder, "left")
    both = _both_eyes()
    right_h265 = get_h265_path(folder, "right") if both else None
    right_mp4 = get_mp4_path(folder, "right") if both else None

    # ── 智能跳过：如果 left.h265 已存在（由 tools.hmd_fast 生成），跳过解码 ──
    h265_exists = os.path.isfile(left_h265) and os.path.getsize(left_h265) > 0
    if h265_exists:
        # 尝试从 fast status 恢复帧数信息
        fast_status_file = os.path.join(get_output_dir(folder), ".hmd_fast.json")
        left_frames = 0
        right_frames = 0
        if os.path.isfile(fast_status_file):
            try:
                with open(fast_status_file, "r", encoding="utf-8") as f:
                    fs = json.load(f)
                left_frames = fs.get("left_frames", 0)
                right_frames = fs.get("right_frames", 0)
            except Exception:
                pass
        print(f"[hmd] left.h265 already exists ({os.path.getsize(left_h265)} bytes), skipping decode → mp4 only", file=sys.stderr)
    else:
        # 1) Python: parse + splitStereo → left.h265 (+ right.h265 if both_eyes)
        #    (Pure-Python bypasses Node.js ArrayBuffer memory limit)
        py_error = None
        node_error = None
        try:
            left_frames, right_frames = run_python_decode(
                parts, left_h265, right_h265,
                status_cb=lambda s: write_status(folder, {
                    "status": "processing", "stage": s["stage"],
                    "progress": s["progress"] * 0.85,
                    "started_at": _status_started(folder),
                }),
            )
        except Exception as e:
            py_error = str(e)
            print(f"[hmd] Python decode failed, falling back to Node.js: {py_error}", file=sys.stderr)
            # Fallback to Node.js
            try:
                left_frames, right_frames = run_node_decode(
                    parts, left_h265, right_h265,
                    status_cb=lambda s: write_status(folder, {
                        "status": "processing", "stage": s["stage"],
                        "progress": s["progress"] * 0.85,
                        "started_at": _status_started(folder),
                    }),
                )
            except Exception as e2:
                node_error = str(e2)
                # Both failed: write detailed error to status file
                raise RuntimeError(
                    f"Both Python and Node.js decode failed.\n"
                    f"Python error: {py_error}\n"
                    f"Node.js error: {node_error}"
                ) from e2

    # 2) ffmpeg: left.h265 → left.mp4
    write_status(folder, {
        "status": "processing", "stage": "muxing-left",
        "progress": 88, "started_at": _status_started(folder),
    })
    ffmpeg_to_mp4(left_h265, left_mp4)
    # 删除中间的 .h265 文件，只保留 .mp4
    if os.path.isfile(left_h265):
        try:
            os.remove(left_h265)
        except OSError:
            pass

    # 3) ffmpeg: right.h265 → right.mp4 (only if both_eyes)
    if both and right_h265 and right_mp4:
        write_status(folder, {
            "status": "processing", "stage": "muxing-right",
            "progress": 94, "started_at": _status_started(folder),
        })
        ffmpeg_to_mp4(right_h265, right_mp4)
        # 删除中间的 .h265 文件
        if os.path.isfile(right_h265):
            try:
                os.remove(right_h265)
            except OSError:
                pass

    # 4) Done
    duration_sec = left_frames / FRAME_RATE
    session_basename = os.path.basename(os.path.normpath(folder))
    status_done = {
        "status": "done",
        "progress": 100,
        "stage": "done",
        "left_frames": left_frames,
        "right_frames": right_frames if both else 0,
        "duration_sec": duration_sec,
        "left_mp4": f"{session_basename}.mp4",
        "finished_at": time.time(),
    }
    if both:
        status_done["right_mp4"] = f"{session_basename}_right.mp4"
    write_status(folder, status_done)


def _status_started(folder):
    """Read started_at from existing status to preserve it across updates."""
    p = get_status_path(folder)
    if os.path.isfile(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f).get("started_at")
        except Exception:
            pass
    return time.time()


# ─── Serial queue: one worker thread processes folders one by one ───
# This avoids parallel Node.js/ffmpeg processes fighting for RAM/CPU,
# and lets already-processed videos become viewable immediately.
_queue = []          # list of folder paths waiting to be processed
_active_folder = None  # folder currently being processed
_queue_lock = threading.Lock()
_queue_cv = threading.Condition(_queue_lock)
_worker_thread = None
_worker_started = False


def _worker():
    """Singleton worker thread: pops folders from _queue and processes them
    one at a time. Finished folders are removed from _active when done."""
    global _active_folder
    while True:
        with _queue_cv:
            while not _queue:
                _queue_cv.wait()
            folder = _queue.pop(0)
            _active_folder = folder

        try:
            process_folder(folder)
        except Exception as e:
            write_status(folder, {
                "status": "error",
                "error": str(e),
                "finished_at": time.time(),
            })
        finally:
            with _queue_cv:
                _active_folder = None


def _ensure_worker():
    global _worker_thread, _worker_started
    with _queue_cv:
        if not _worker_started:
            _worker_thread = threading.Thread(target=_worker, daemon=True)
            _worker_thread.start()
            _worker_started = True


def start_async(folder):
    """Enqueue a folder for serial processing. Returns immediately.

    If the folder is already done, or currently being processed, or already
    queued, this is a no-op.
    """
    _ensure_worker()

    with _queue_cv:
        # Skip if already done
        if check_done(folder):
            return
        # Skip if currently processing
        if _active_folder == folder:
            return
        # Skip if already in queue
        if folder in _queue:
            return
        _queue.append(folder)
        _queue_cv.notify()


def get_queue_info():
    """Return queue status for the API layer.

    Returns:
        active_folder: str | None  – folder currently being processed
        queue:         list[str]    – folders waiting in line
    """
    with _queue_cv:
        return {
            "active_folder": _active_folder,
            "queue": list(_queue),
        }


# ─── CLI ───
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python hmd_preprocess.py <session_folder>")
        sys.exit(1)
    folder = sys.argv[1]
    process_folder(folder)
    print(f"OK: {folder}/left.mp4 + right.mp4 ready")
