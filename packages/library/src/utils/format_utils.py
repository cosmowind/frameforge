# ────────────────────────────────────────────────────────────────
# format_utils.py — 格式化/解析/日期提取纯工具函数
# 拆分自 app.py（S2）
# ────────────────────────────────────────────────────────────────

import os
import subprocess
from datetime import datetime


def fmt_duration(seconds):
    """Format seconds as M:SS or H:MM:SS string."""
    if not seconds or seconds <= 0:
        return ""
    s = int(seconds)
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    if h > 0:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m}:{sec:02d}"


def parse_duration_to_sec(s):
    """Parse 'H:MM:SS' or 'M:SS' back to integer seconds. Returns 0 on failure."""
    if not s:
        return 0
    try:
        parts = [int(p) for p in str(s).strip().split(":")]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        return parts[0]
    except (ValueError, TypeError):
        return 0


def get_file_date(filepath):
    """Get MP4 file's true recording date as YYYY-MM-DD string.

    Priority (fix for wrong ctime on Windows — ctime = copy-time, not recording-time):
    1) ffprobe creation_time tag (exact recording timestamp from camera)
    2) os.path.getmtime (preserved by copy2 from SD card; DJI/GoPro set this correctly)
    3) os.path.getctime (fallback; on Windows this is the file's creation/copy time)
    4) today's date (last resort)
    """
    # 1) ffprobe creation_time
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries",
             "format_tags=creation_time",
             "-of", "default=noprint_wrappers=1:nokey=1", filepath],
            capture_output=True, text=True, timeout=10,
        )
        tag = proc.stdout.strip()
        if tag:
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S",
                        "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
                try:
                    clean = tag.rstrip("Z").split(".")[0] if "T" in tag else tag
                    return datetime.strptime(clean, fmt).strftime("%Y-%m-%d")
                except ValueError:
                    continue
            date_part = tag.split("T")[0].split(" ")[0]
            if len(date_part) == 10 and date_part[4] == '-' and date_part[7] == '-':
                return date_part
    except Exception:
        pass

    # 2) mtime (preserved from source SD card by copy2)
    try:
        mtime = os.path.getmtime(filepath)
        dt = datetime.fromtimestamp(mtime)
        if dt.year >= 2000:
            return dt.strftime("%Y-%m-%d")
    except Exception:
        pass

    # 3) ctime (fallback; Windows copy-time, not recording-time)
    try:
        return datetime.fromtimestamp(os.path.getctime(filepath)).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")


def get_hmd_date(session_folder, metadata=None, dest_dir=None):
    """Get HMD session's original recording date.

    HMD embedded devices lack a real-time clock (RTC); all file timestamps
    default to 2021-01-01 (Linux epoch). metadata.json's start_time is empty
    and start_time_unix is a monotonic clock value (~22s), not a wall-clock.

    Priority:
    1) metadata.json start_time (if non-empty ISO string)
    2) Destination directory name date (e.g. /media\\0615 → year-MM-DD)
    3) Directory mtime (if >= year 2020, may reflect meaningful time)
    4) Today's date (fallback)
    """
    if metadata:
        start_time = metadata.get("start_time", "")
        if start_time and isinstance(start_time, str) and len(start_time) >= 10:
            date_part = start_time.split("T")[0].split(" ")[0]
            if len(date_part) == 10 and date_part[4] == '-' and date_part[7] == '-':
                return date_part

    # Destination directory name (e.g. "0615" → MMDD)
    if dest_dir:
        dir_name = os.path.basename(os.path.normpath(dest_dir))
        if len(dir_name) == 4 and dir_name.isdigit():
            month = dir_name[:2]
            day = dir_name[2:]
            year = datetime.now().year
            return f"{year}-{month}-{day}"

    # Directory mtime (skip embedded device default 2021-01-01)
    try:
        mtime = os.path.getmtime(session_folder)
        dt = datetime.fromtimestamp(mtime)
        if dt.year >= 2020:
            return dt.strftime("%Y-%m-%d")
    except Exception:
        pass

    return datetime.now().strftime("%Y-%m-%d")
