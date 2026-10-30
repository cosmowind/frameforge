#!/usr/bin/env python
"""HMD fast preprocess -- orchestrators and async queue."""

import os
import sys
import threading
import time

from tools.hmd_fast.path_utils import (
    FRAME_RATE,
    get_output_dir, get_status_path, get_h265_path, get_mp4_path,
    get_frames_dir, list_parts, check_fast_done, check_frames_done,
    write_status, read_status,
)
from tools.hmd_fast.media_ops import (
    run_decode, get_h265_duration, remux_h265_to_mp4, ensure_mp4,
    get_mp4_duration, extract_frames_from_h265, extract_frames_from_mp4,
    generate_cover_from_h265, generate_cover_from_mp4,
)


# ── Main flow ──

def process_fast(folder, extract_frames=True, extract_cover=True):
    """Fast preprocess main entry.

    1. Decode HMD -> left.h265
    2. Fast remux h265 -> mp4 (stream copy, seconds-level)
    3. Extract 6 preview frames from mp4 (using container index, very fast)
    4. Generate cover thumbnail from mp4 (input seek, very fast)
    """
    basename = os.path.basename(os.path.normpath(folder))
    print(f"[decode+frames+cover] {basename}")
    parts = list_parts(folder)
    if not parts:
        raise FileNotFoundError(f"No part_*.hmd files in {folder}")

    out_dir = get_output_dir(folder)
    os.makedirs(out_dir, exist_ok=True)

    left_h265 = get_h265_path(folder, "left")
    left_mp4 = get_mp4_path(folder, "left")
    started_at = time.time()

    # ── Stage 1: decode ──
    # If left.h265 already exists and size > 0, skip decode
    need_decode = True
    if os.path.isfile(left_h265) and os.path.getsize(left_h265) > 0:
        # Already have h265, try to recover frame count from status file
        existing = read_status(folder)
        if existing and existing.get("left_frames", 0) > 0:
            left_frames = existing["left_frames"]
            right_frames = existing.get("right_frames", 0)
            need_decode = False

    if need_decode:
        basename = os.path.basename(os.path.normpath(folder))
        print(f"    decoding HMD -> left.h265 for {basename} ...")
        write_status(folder, {
            "status": "processing",
            "stage": "decode+split",
            "progress": 0,
            "started_at": started_at,
        })

        left_frames, right_frames = run_decode(
            folder, left_h265,
            status_cb=lambda s: write_status(folder, {
                "status": "processing",
                "stage": s["stage"],
                "progress": s["progress"],
                "started_at": started_at,
            }),
        )

        write_status(folder, {
            "status": "processing",
            "stage": "decoded",
            "progress": 80,
            "left_frames": left_frames,
            "right_frames": right_frames,
            "started_at": started_at,
        })
        print(f"    decode done: {left_frames} frames, {right_frames} right")
    else:
        write_status(folder, {
            "status": "processing",
            "stage": "decoded",
            "progress": 80,
            "left_frames": left_frames,
            "right_frames": right_frames,
            "started_at": started_at,
        })

    # Calculate duration
    duration_sec = left_frames / FRAME_RATE

    # ── Stage 1.5: fast remux mp4 (stream copy, seconds-level) ──
    if not os.path.isfile(left_mp4) or os.path.getsize(left_mp4) == 0:
        print(f"    remux h265 -> mp4 ...", flush=True)
        t_remux = time.time()
        try:
            remux_h265_to_mp4(left_h265, left_mp4)
            print(f"    remux done ({time.time()-t_remux:.1f}s)", flush=True)
        except Exception as e:
            print(f"    remux failed: {e}, will use h265 as fallback", flush=True)

    # Choose video source: prefer mp4 (has container index, fast seek), fallback h265
    video_src = left_mp4 if (os.path.isfile(left_mp4) and os.path.getsize(left_mp4) > 0) else left_h265
    use_mp4 = (video_src == left_mp4)

    # ── Stage 2: extract frames ──
    frames_count = 0
    if extract_frames and not check_frames_done(folder):
        write_status(folder, {
            "status": "processing",
            "stage": "extracting-frames",
            "progress": 88,
            "left_frames": left_frames,
            "right_frames": right_frames,
            "duration_sec": duration_sec,
            "started_at": started_at,
        })

        frames_dir = get_frames_dir(folder)
        if use_mp4:
            frame_results = extract_frames_from_mp4(
                video_src, frames_dir, duration_sec,
                num_frames=6, width=320
            )
        else:
            frame_results = extract_frames_from_h265(
                video_src, frames_dir, duration_sec,
                num_frames=6, width=320
            )
        frames_count = len(frame_results)
    else:
        frames_dir = get_frames_dir(folder)
        if os.path.isdir(frames_dir):
            frames_count = len([f for f in os.listdir(frames_dir) if f.endswith('.jpg')])

    # ── Stage 3: cover ──
    cover_ok = False
    if extract_cover:
        write_status(folder, {
            "status": "processing",
            "stage": "generating-cover",
            "progress": 95,
            "left_frames": left_frames,
            "right_frames": right_frames,
            "duration_sec": duration_sec,
            "frames_count": frames_count,
            "started_at": started_at,
        })

        # Cover saved in hmd_cache/<session>/cover.jpg
        cover_path = os.path.join(out_dir, "cover.jpg")
        if use_mp4:
            cover_ok = generate_cover_from_mp4(video_src, cover_path)
        else:
            cover_ok = generate_cover_from_h265(video_src, cover_path)

    # ── Done ──
    status_done = {
        "status": "done",
        "progress": 100,
        "stage": "done",
        "left_frames": left_frames,
        "right_frames": right_frames,
        "duration_sec": round(duration_sec, 1),
        "frames_count": frames_count,
        "cover_ok": cover_ok,
        "mp4_ready": use_mp4,
        "finished_at": time.time(),
    }
    write_status(folder, status_done)

    # ── Delete .h265 after preprocess to save disk space ──
    if use_mp4 and os.path.isfile(left_mp4) and os.path.getsize(left_mp4) > 0:
        if os.path.isfile(left_h265):
            try:
                h265_size_mb = os.path.getsize(left_h265) / (1024 * 1024)
                os.unlink(left_h265)
                print(f"    [cleanup] deleted left.h265 ({h265_size_mb:.1f} MB freed)", flush=True)
            except OSError as e:
                print(f"    [cleanup] failed to delete left.h265: {e}", flush=True)

    return status_done


# ── Frames only (prefer mp4, fallback h265) ──

def process_frames_only(folder, num_frames=6, width=320):
    """Extract preview frames from video. Prefer mp4 (has container index), fallback to h265.

    Suitable for when h265 already exists (e.g. produced by hmd_preprocess.py).
    """
    basename = os.path.basename(os.path.normpath(folder))
    print(f"[frames] {basename}")

    # Prefer mp4, fast-remux if not present
    try:
        video_src = ensure_mp4(folder, "left")
        use_mp4 = True
        print(f"  using mp4")
    except (FileNotFoundError, RuntimeError):
        video_src = get_h265_path(folder, "left")
        use_mp4 = False
        if not os.path.isfile(video_src):
            raise FileNotFoundError(f"left.h265 not found: {video_src}")
        print(f"  using h265 (mp4 not available)")

    # Read duration from existing status file
    existing = read_status(folder)
    if existing and existing.get("duration_sec", 0) > 0:
        duration_sec = existing["duration_sec"]
    else:
        # Fallback: probe with ffprobe or assume 30fps
        print(f"  probing duration ...")
        if use_mp4:
            ffprobe_dur = get_mp4_duration(video_src)
        else:
            ffprobe_dur = get_h265_duration(video_src)
        if ffprobe_dur:
            duration_sec = ffprobe_dur
            print(f"  duration: {duration_sec:.1f}s (ffprobe)")
        else:
            # Read from .hmd_process.json (hmd_preprocess.py status)
            import json as _json
            proc_status = os.path.join(get_output_dir(folder), ".hmd_process.json")
            if os.path.isfile(proc_status):
                try:
                    with open(proc_status, "r") as f:
                        ps = _json.load(f)
                    duration_sec = ps.get("duration_sec", 30)
                except Exception:
                    duration_sec = 30
            else:
                duration_sec = 30
            print(f"  duration: {duration_sec:.1f}s (estimated)")

    frames_dir = get_frames_dir(folder)
    os.makedirs(frames_dir, exist_ok=True)

    print(f"  extracting {num_frames} frames ...")
    t0 = time.time()
    if use_mp4:
        results = extract_frames_from_mp4(
            video_src, frames_dir, duration_sec,
            num_frames=num_frames, width=width
        )
    else:
        results = extract_frames_from_h265(
            video_src, frames_dir, duration_sec,
            num_frames=num_frames, width=width
        )
    elapsed = time.time() - t0

    # Update status file
    existing = read_status(folder) or {}
    existing["frames_count"] = len(results)
    existing["stage"] = "frames-extracted" if existing.get("status") == "done" else existing.get("stage", "")
    write_status(folder, existing)

    print(f"  -> {len(results)}/{num_frames} frames ({elapsed:.1f}s)")
    return results


# ── Cover generation (prefer mp4, fallback h265) ──

def process_cover_only(folder):
    """Generate cover from video. Prefer mp4 (input seek very fast), fallback to h265."""
    basename = os.path.basename(os.path.normpath(folder))
    print(f"[cover] {basename}")

    # Prefer mp4, fast-remux if not present
    try:
        video_src = ensure_mp4(folder, "left")
        use_mp4 = True
        print(f"  using mp4")
    except (FileNotFoundError, RuntimeError):
        video_src = get_h265_path(folder, "left")
        use_mp4 = False
        if not os.path.isfile(video_src):
            raise FileNotFoundError(f"left.h265 not found: {video_src}")
        print(f"  using h265 (mp4 not available)")

    out_dir = get_output_dir(folder)
    cover_path = os.path.join(out_dir, "cover.jpg")
    print(f"  generating cover ...")
    t0 = time.time()
    if use_mp4:
        ok = generate_cover_from_mp4(video_src, cover_path)
    else:
        ok = generate_cover_from_h265(video_src, cover_path)
    elapsed = time.time() - t0

    existing = read_status(folder) or {}
    existing["cover_ok"] = ok
    write_status(folder, existing)
    print(f"  -> {'OK' if ok else 'FAIL'} ({elapsed:.1f}s)")
    return ok


# ── Two-stage parallel preprocess queue ──
# Stage 1: decode + remux mp4 (main thread, time-consuming)
# Stage 2: extract frames + cover (sub-thread, seconds-level, parallel with Stage 1)
# Flow: Stage1 worker decode+remux -> push to Stage2 queue -> Stage2 worker frames+cover

# ── Stage 1 queue ──
_queue = []
_active_folder = None
_queue_lock = threading.Lock()
_queue_cv = threading.Condition(_queue_lock)
_worker_thread = None
_worker_started = False

# ── Stage 2 queue (frame extraction + cover) ──
_stage2_queue = []
_stage2_active = None
_stage2_lock = threading.Lock()
_stage2_cv = threading.Condition(_stage2_lock)
_stage2_thread = None
_stage2_started = False


def _stage2_worker_func():
    """Stage 2 worker thread: extract frames + generate cover from mp4."""
    global _stage2_active
    while True:
        with _stage2_cv:
            while not _stage2_queue:
                _stage2_cv.wait()
            folder = _stage2_queue.pop(0)
            _stage2_active = folder
        try:
            _do_stage2(folder)
        except Exception as e:
            print(f"[stage2] error {os.path.basename(folder)}: {e}", file=sys.stderr)
            try:
                existing = read_status(folder) or {}
                existing["status"] = "error"
                existing["stage"] = "stage2-error"
                existing["error"] = str(e)
                existing["finished_at"] = time.time()
                write_status(folder, existing)
            except Exception:
                pass
        finally:
            with _stage2_cv:
                _stage2_active = None


def _ensure_stage2():
    """Lazy-start Stage 2 worker thread."""
    global _stage2_thread, _stage2_started
    with _stage2_cv:
        if not _stage2_started:
            _stage2_thread = threading.Thread(target=_stage2_worker_func, daemon=True)
            _stage2_thread.start()
            _stage2_started = True


def _push_stage2(folder):
    """Push folder into Stage 2 queue (frame extraction + cover)."""
    _ensure_stage2()
    with _stage2_cv:
        if folder in _stage2_queue:
            return
        if _stage2_active == folder:
            return
        _stage2_queue.append(folder)
        _stage2_cv.notify()


def _do_stage2(folder):
    """Stage 2 actual work: extract frames + generate cover + write final status."""
    basename = os.path.basename(os.path.normpath(folder))
    print(f"[stage2:frames+cover] {basename}", flush=True)

    # Read Stage 1 status (duration etc.)
    status = read_status(folder) or {}
    duration_sec = status.get("duration_sec", 30)
    left_frames = status.get("left_frames", 0)

    # Choose video source
    mp4_path = get_mp4_path(folder, "left")
    h265_path = get_h265_path(folder, "left")
    if os.path.isfile(mp4_path) and os.path.getsize(mp4_path) > 0:
        video_src = mp4_path
        use_mp4 = True
    else:
        video_src = h265_path
        use_mp4 = False

    # Extract frames
    frames_dir = get_frames_dir(folder)
    if not check_frames_done(folder):
        write_status(folder, {**status, "status": "processing", "stage": "extracting-frames", "progress": 92})
        if use_mp4:
            frame_results = extract_frames_from_mp4(video_src, frames_dir, duration_sec, num_frames=6, width=320)
        else:
            frame_results = extract_frames_from_h265(video_src, frames_dir, duration_sec, num_frames=6, width=320)
        frames_count = len(frame_results)
        print(f"    frames: {frames_count}/6", flush=True)
    else:
        frames_dir = get_frames_dir(folder)
        frames_count = len([f for f in os.listdir(frames_dir) if f.endswith('.jpg')]) if os.path.isdir(frames_dir) else 0

    # Cover
    cover_ok = False
    cover_path = os.path.join(get_output_dir(folder), "cover.jpg")
    if not (os.path.isfile(cover_path) and os.path.getsize(cover_path) > 0):
        write_status(folder, {**status, "status": "processing", "stage": "generating-cover", "progress": 96})
        if use_mp4:
            cover_ok = generate_cover_from_mp4(video_src, cover_path)
        else:
            cover_ok = generate_cover_from_h265(video_src, cover_path)
        print(f"    cover: {'OK' if cover_ok else 'FAIL'}", flush=True)
    else:
        cover_ok = True

    # Write final status
    write_status(folder, {
        "status": "done",
        "progress": 100,
        "stage": "done",
        "left_frames": left_frames,
        "right_frames": status.get("right_frames", 0),
        "duration_sec": round(duration_sec, 1),
        "frames_count": frames_count,
        "cover_ok": cover_ok,
        "mp4_ready": True,
        "finished_at": time.time(),
    })
    print(f"    [stage2 done] {basename}", flush=True)

    # ── Delete .h265 raw stream after preprocess to save disk space ──
    # Condition: mp4 ready (playable), preview frames generated, cover generated
    if use_mp4 and os.path.isfile(mp4_path) and os.path.getsize(mp4_path) > 0:
        h265_path = get_h265_path(folder, "left")
        if os.path.isfile(h265_path):
            try:
                h265_size_mb = os.path.getsize(h265_path) / (1024 * 1024)
                os.unlink(h265_path)
                print(f"    [cleanup] deleted {basename}/left.h265 ({h265_size_mb:.1f} MB freed)", flush=True)
            except OSError as e:
                print(f"    [cleanup] failed to delete left.h265: {e}", flush=True)


# ── Stage 1 core function: decode + remux only ──

def process_decode_and_remux(folder):
    """Stage 1: decode HMD -> left.h265, then stream-copy remux to left.mp4.

    Does not extract frames or cover (delegated to Stage 2 for parallel processing).
    Returns (duration_sec, left_frames).
    """
    basename = os.path.basename(os.path.normpath(folder))
    print(f"[stage1:decode+remux] {basename}")
    parts = list_parts(folder)
    if not parts:
        raise FileNotFoundError(f"No part_*.hmd files in {folder}")

    out_dir = get_output_dir(folder)
    os.makedirs(out_dir, exist_ok=True)

    left_h265 = get_h265_path(folder, "left")
    left_mp4 = get_mp4_path(folder, "left")
    started_at = time.time()

    # ── Decode ──
    need_decode = True
    if os.path.isfile(left_h265) and os.path.getsize(left_h265) > 0:
        existing = read_status(folder)
        if existing and existing.get("left_frames", 0) > 0:
            left_frames = existing["left_frames"]
            right_frames = existing.get("right_frames", 0)
            need_decode = False

    if need_decode:
        print(f"    decoding HMD -> left.h265 ...", flush=True)
        write_status(folder, {
            "status": "processing",
            "stage": "decode+split",
            "progress": 0,
            "started_at": started_at,
        })
        left_frames, right_frames = run_decode(
            folder, left_h265,
            status_cb=lambda s: write_status(folder, {
                "status": "processing",
                "stage": s["stage"],
                "progress": s["progress"],
                "started_at": started_at,
            }),
        )
        print(f"    decode done: {left_frames} frames", flush=True)
    else:
        print(f"    h265 exists, skip decode ({left_frames} frames)", flush=True)

    write_status(folder, {
        "status": "processing",
        "stage": "decoded",
        "progress": 80,
        "left_frames": left_frames,
        "right_frames": right_frames,
        "started_at": started_at,
    })

    duration_sec = left_frames / FRAME_RATE

    # ── Remux mp4 ──
    if not os.path.isfile(left_mp4) or os.path.getsize(left_mp4) == 0:
        print(f"    remux h265 -> mp4 ...", flush=True)
        t_remux = time.time()
        try:
            remux_h265_to_mp4(left_h265, left_mp4)
            print(f"    remux done ({time.time()-t_remux:.1f}s)", flush=True)
        except Exception as e:
            print(f"    remux failed: {e}", flush=True)
    else:
        print(f"    mp4 exists, skip remux", flush=True)

    mp4_ready = os.path.isfile(left_mp4) and os.path.getsize(left_mp4) > 0

    # Write intermediate status
    write_status(folder, {
        "status": "stage1-done",
        "stage": "stage1-done",
        "progress": 90,
        "left_frames": left_frames,
        "right_frames": right_frames,
        "duration_sec": round(duration_sec, 1),
        "mp4_ready": mp4_ready,
        "started_at": started_at,
    })

    return duration_sec, left_frames


def _worker():
    """Stage 1 worker thread: decode + remux, then push to Stage 2 queue."""
    global _active_folder
    while True:
        with _queue_cv:
            while not _queue:
                _queue_cv.wait()
            folder = _queue.pop(0)
            _active_folder = folder

        try:
            process_decode_and_remux(folder)
            # Stage 1 done, push to Stage 2 (parallel frames+cover)
            _push_stage2(folder)
        except Exception as e:
            write_status(folder, {
                "status": "error",
                "error": str(e),
                "finished_at": time.time(),
            })
            print(f"[stage1] error {os.path.basename(folder)}: {e}", file=sys.stderr)
        finally:
            with _queue_cv:
                _active_folder = None


def _ensure_worker():
    """Lazy-start Stage 1 worker thread (also pre-starts Stage 2)."""
    global _worker_thread, _worker_started
    with _queue_cv:
        if not _worker_started:
            _worker_thread = threading.Thread(target=_worker, daemon=True)
            _worker_thread.start()
            _worker_started = True
    # Also ensure Stage 2 thread is started
    _ensure_stage2()


def start_async(folder):
    """Add folder to two-stage preprocess queue (Stage 1 -> Stage 2).

    Smart routing:
      - Already done -> skip
      - h265+mp4 ready (only needs frames/cover) -> push directly to Stage2
      - Otherwise -> push to Stage1 (decode+remux), then auto Stage2

    Returns immediately, non-blocking.
    """
    _ensure_worker()

    # Already done -> skip
    if check_fast_done(folder):
        return

    # Currently processing or queued in Stage2 -> skip
    with _stage2_cv:
        if folder == _stage2_active or folder in _stage2_queue:
            return

    # Currently processing or queued in Stage1 -> skip
    with _queue_cv:
        if folder == _active_folder or folder in _queue:
            return

    # Smart routing: if h265+mp4 both exist, only need Stage2
    h265_path = get_h265_path(folder, "left")
    mp4_path = get_mp4_path(folder, "left")
    has_h265 = os.path.isfile(h265_path) and os.path.getsize(h265_path) > 0
    has_mp4 = os.path.isfile(mp4_path) and os.path.getsize(mp4_path) > 0
    has_cover = os.path.isfile(os.path.join(get_output_dir(folder), "cover.jpg"))
    has_frames = check_frames_done(folder)

    if has_h265 and has_mp4:
        # Already have h265+mp4 -> push directly to Stage2 (frames+cover)
        print(f"[fast] {os.path.basename(folder)} -> stage2 (h265+mp4 ready)", flush=True)
        _push_stage2(folder)
        return

    # Need full Stage1 -> Stage2
    with _queue_cv:
        _queue.append(folder)
        _queue_cv.notify()


def get_queue_info():
    """Return queue status (including Stage 2)."""
    with _queue_cv:
        s1_info = {
            "active_folder": _active_folder,
            "queue": list(_queue),
        }
    with _stage2_cv:
        s2_info = {
            "stage2_active": _stage2_active,
            "stage2_queue": list(_stage2_queue),
        }
    return {**s1_info, **s2_info}
