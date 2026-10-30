#!/usr/bin/env python
"""HMD fast preprocess -- path helpers and status I/O."""

import glob
import json
import os
import threading
import time

STATUS_FILE = ".hmd_fast.json"
FRAME_RATE = 30  # assumed fps (HMD container does not carry frame rate)


# ── Path utilities (consistent with hmd_preprocess.py) ──

def _project_root():
    """Return the video-sort-package project root (parent of src/).

    __file__ = <root>/src/tools/hmd_fast/path_utils.py
    向上 4 层 dirname 才是 project root
    """
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def get_cache_root():
    return os.environ.get("HMD_CACHE_ROOT") or os.path.join(_project_root(), "runtime", "hmd_cache")


def _extract_date_from_path(path):
    """Extract date directory name (MMDD format) from source path, return 'YYYY-MM-DD' or 'unknown'.

    Path example: D:\\videos\\0619\\hmd\\4aa45c_session_00000 -> '2026-06-19'
    Strategy: find the first 4-digit directory name in path as date.
    """
    import datetime as _dt
    parts = os.path.normpath(path).split(os.sep)
    for part in reversed(parts):
        if len(part) == 4 and part.isdigit():
            month = part[:2]
            day = part[2:]
            year = _dt.datetime.now().year
            return f"{year}-{month}-{day}"
    return "unknown"


def get_output_dir(source_folder):
    """Cache directory: <CACHE_ROOT>/<date>/<session_basename>/

    Uses date prefix to avoid file overwrites from same-name sessions on different dates.
    """
    date_key = _extract_date_from_path(source_folder)
    basename = os.path.basename(os.path.normpath(source_folder))
    return os.path.join(get_cache_root(), date_key, basename)


def get_status_path(source_folder):
    return os.path.join(get_output_dir(source_folder), STATUS_FILE)


def get_video_basename(source_folder, eye="left"):
    """Return video file base name (without path and extension).

    Naming rule: {session_basename} or {session_basename}_right
    """
    session_basename = os.path.basename(os.path.normpath(source_folder))
    if eye == "right":
        return f"{session_basename}_right"
    return session_basename


def get_h265_path(source_folder, eye="left"):
    assert eye in ("left", "right"), eye
    basename = get_video_basename(source_folder, eye)
    new_path = os.path.join(get_output_dir(source_folder), f"{basename}.h265")
    old_path = os.path.join(get_output_dir(source_folder), f"{eye}.h265")
    # If old-name file exists, prefer old path (backward compat with existing cache)
    if os.path.isfile(old_path) and not os.path.isfile(new_path):
        return old_path
    return new_path


def get_mp4_path(source_folder, eye="left"):
    assert eye in ("left", "right"), eye
    basename = get_video_basename(source_folder, eye)
    new_path = os.path.join(get_output_dir(source_folder), f"{basename}.mp4")
    old_path = os.path.join(get_output_dir(source_folder), f"{eye}.mp4")
    # If old-name file exists, prefer old path (backward compat with existing cache)
    if os.path.isfile(old_path) and not os.path.isfile(new_path):
        return old_path
    return new_path


def get_frames_dir(source_folder):
    return os.path.join(get_output_dir(source_folder), "frames")


def list_parts(folder):
    return sorted(glob.glob(os.path.join(folder, "part_*.hmd")))


def check_fast_done(folder):
    """Whether fast preprocess is complete.

    Must satisfy all: status=done, cover exists, preview frames exist.
    Video source must have at least mp4 or h265 (mp4 preferred; h265 is auto-cleaned after preprocess).
    h265 alone does not count as done, to avoid skipping frame/cover retries.
    """
    sp = get_status_path(folder)
    h265_ok = os.path.isfile(get_h265_path(folder))
    mp4_ok = os.path.isfile(get_mp4_path(folder, "left")) and os.path.getsize(get_mp4_path(folder, "left")) > 0
    video_ok = mp4_ok or h265_ok  # at least one of mp4 or h265 must exist
    cover_path = os.path.join(get_output_dir(folder), "cover.jpg")
    cover_ok = os.path.isfile(cover_path) and os.path.getsize(cover_path) > 0
    frames_ok = check_frames_done(folder)
    all_files_ok = video_ok and cover_ok and frames_ok

    if not os.path.isfile(sp):
        # Backward compat: video+cover+preview frames must all be present
        return all_files_ok
    try:
        with open(sp, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("status") != "done":
            return False
        # status=done but files incomplete -> not really done, needs retry
        if not all_files_ok:
            return False
        return True
    except Exception:
        return all_files_ok


def check_frames_done(folder, num_frames=6):
    """Check whether 6 preview frames have been generated."""
    frames_dir = get_frames_dir(folder)
    if not os.path.isdir(frames_dir):
        return False
    jpgs = [f for f in os.listdir(frames_dir) if f.endswith('.jpg') and f.startswith('frame_')]
    return len(jpgs) >= num_frames


# ── Status read/write (atomic writes, avoids concurrent conflicts) ──
_folder_locks = {}
_folder_locks_lock = threading.Lock()


def _get_folder_lock(folder):
    with _folder_locks_lock:
        if folder not in _folder_locks:
            _folder_locks[folder] = threading.Lock()
        return _folder_locks[folder]


def write_status(folder, status):
    path = get_status_path(folder)
    os.makedirs(get_output_dir(folder), exist_ok=True)
    lock = _get_folder_lock(folder)
    with lock:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(status, f, ensure_ascii=False, indent=2)
        for attempt in range(5):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                time.sleep(0.1 * (attempt + 1))
        try:
            os.unlink(tmp)
        except OSError:
            pass
        with open(path, "w", encoding="utf-8") as f:
            json.dump(status, f, ensure_ascii=False, indent=2)


def read_status(folder):
    path = get_status_path(folder)
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
