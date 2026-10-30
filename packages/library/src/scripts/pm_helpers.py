#!/usr/bin/env python
"""
pm_helpers.py - preprocess_manager 的工具函数拆分。

包含：CSV 管理、session 状态检查、通用工具函数。
"""
import os
import sys
import csv
import json
import datetime
import subprocess
import argparse

# 项目路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src", "tools"))

from config import CSV_PATH, RUNTIME_DIR, THUMBNAILS_DIR

PM_CSV = os.path.join(RUNTIME_DIR, "preprocess_manager.csv")
PM_FIELDS = [
    "pm_id", "video_id", "session_path", "session_name",
    "status", "has_h265", "has_frames", "has_cover", "has_mp4",
    "frames_count", "cache_dir",
    "mp4_path", "cover_path", "h265_path", "frames_dir",
    "progress_pct", "error_msg",
    "fast_stage", "mp4_stage",
    "created_at", "started_at", "finished_at",
]

# 估算速度（秒/session，经验值）
EST_FAST_SEC = 30      # 快速预处理（解码+抽帧+封面）
EST_MP4_SEC = 60       # mp4 编码


# ───────────────────────────────────────────────────────────────
# 工具函数
# ───────────────────────────────────────────────────────────────

def now_iso():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_args():
    parser = argparse.ArgumentParser(description="HMD 预处理管理器")
    parser.add_argument("--dry-run", action="store_true", help="只扫描不处理")
    parser.add_argument("--fast-only", action="store_true", help="只做 fast 预处理，不生成 mp4")
    parser.add_argument("--force", action="store_true", help="强制重跑已完成的项目")
    parser.add_argument("--skip-extra-desc", metavar="VAL",
                        help="跳过 video_manager 中 extra_description 等于指定值的 session（可多次指定）")
    return parser.parse_args()


def ensure_pm_csv():
    """确保管理 CSV 存在。"""
    os.makedirs(os.path.dirname(PM_CSV), exist_ok=True)
    if not os.path.isfile(PM_CSV):
        with open(PM_CSV, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=PM_FIELDS)
            writer.writeheader()


def read_pm_csv():
    """读取管理 CSV，返回 {session_path: row}"""
    rows = {}
    if os.path.isfile(PM_CSV):
        with open(PM_CSV, "r", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                rows[r["session_path"]] = r
    return rows


def write_pm_csv(rows):
    """全量写入管理 CSV。"""
    with open(PM_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=PM_FIELDS)
        writer.writeheader()
        for r in rows.values():
            writer.writerow(r)


def read_video_csv():
    """读取 video_manager.csv，返回 [{index, path, file_type, ...}]"""
    rows = []
    if os.path.isfile(CSV_PATH):
        with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
            for i, r in enumerate(csv.DictReader(f)):
                rows.append({"index": i, **r})
    return rows


def get_local_hmd_sessions(video_rows):
    """从 video_manager.csv 提取本地 HMD session。"""
    sessions = []
    for r in video_rows:
        if r.get("file_type", "").strip().lower() == "hmd":
            path = r.get("path", "").strip()
            loc = r.get("location_status", "").strip()
            if path and loc.endswith('_local'):
                sessions.append(r)
    return sessions


# ───────────────────────────────────────────────────────────────
# 状态检查（从 hmd_cache 实际检查，不依赖内存状态）
# ───────────────────────────────────────────────────────────────

def get_hmd_fast():
    try:
        from tools import hmd_fast as uf
        return uf
    except ImportError:
        return None


def get_hmd():
    try:
        import hmd_preprocess as up
        return up
    except ImportError:
        return None


def _extract_date_from_path(path):
    parts = os.path.normpath(path).split(os.sep)
    for part in reversed(parts):
        if len(part) == 4 and part.isdigit():
            month, day = part[:2], part[2:]
            year = datetime.datetime.now().year
            return f"{year}-{month}-{day}"
    return "unknown"


def get_cache_dir(session_path):
    """计算 hmd_cache 目录路径。"""
    from tools import hmd_fast as uf
    return uf.get_output_dir(session_path)


def check_session_actual_state(session_path):
    """从 hmd_cache 目录实际检查 session 的文件状态。"""
    from tools import hmd_fast as uf
    cache = uf.get_output_dir(session_path)
    base = os.path.basename(os.path.normpath(session_path))

    # 新旧命名兼容
    _h265_new = os.path.join(cache, f"{base}.h265")
    _h265_old = os.path.join(cache, "left.h265")
    h265_path = _h265_new if os.path.isfile(_h265_new) else (_h265_old if os.path.isfile(_h265_old) else "")
    _mp4_new = os.path.join(cache, f"{base}.mp4")
    _mp4_old = os.path.join(cache, "left.mp4")
    mp4_path = _mp4_new if os.path.isfile(_mp4_new) else (_mp4_old if os.path.isfile(_mp4_old) else "")
    cover_path = os.path.join(cache, "cover.jpg")
    frames_dir = os.path.join(cache, "frames")

    has_h265 = bool(h265_path and os.path.isfile(h265_path) and os.path.getsize(h265_path) > 0)
    has_mp4 = bool(mp4_path and os.path.isfile(mp4_path) and os.path.getsize(mp4_path) > 0)
    has_cover = os.path.isfile(cover_path) and os.path.getsize(cover_path) > 0
    frames_count = 0
    if os.path.isdir(frames_dir):
        frames_count = len([f for f in os.listdir(frames_dir) if f.endswith(".jpg")])
    has_frames = frames_count >= 6

    # 读取状态文件
    fast_status = None
    proc_status = None
    fast_sp = os.path.join(cache, ".hmd_fast.json")
    proc_sp = os.path.join(cache, ".hmd_process.json")
    if os.path.isfile(fast_sp):
        try:
            with open(fast_sp, "r", encoding="utf-8") as f:
                fast_status = json.load(f)
        except Exception:
            pass
    if os.path.isfile(proc_sp):
        try:
            with open(proc_sp, "r", encoding="utf-8") as f:
                proc_status = json.load(f)
        except Exception:
            pass

    return {
        "cache_dir": cache,
        "h265_path": h265_path,
        "mp4_path": mp4_path,
        "cover_path": cover_path,
        "frames_dir": frames_dir,
        "has_h265": has_h265,
        "has_mp4": has_mp4,
        "has_cover": has_cover,
        "has_frames": has_frames,
        "frames_count": frames_count,
        "fast_status": fast_status,
        "proc_status": proc_status,
    }


def mp4_is_playable(mp4_path):
    """用 ffprobe 验证 mp4 是否可播放。"""
    if not mp4_path or not os.path.isfile(mp4_path):
        return False
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error",
             "-show_entries", "format=duration,nb_streams:stream=codec_name",
             "-of", "json", mp4_path],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=20,
        )
        if r.returncode != 0:
            return False
        data = json.loads(r.stdout)
        # 新旧 ffprobe 版本兼容：streams 可能为空但 stream_groups 有数据，或 streams 直接有数据
        streams = data.get("streams") or data.get("stream_groups") or []
        if not streams:
            return False
        # 只要 ffprobe 成功解析出流信息（duration/nb_streams/codec），文件就是可播放的
        fmt = data.get("format", {})
        return bool(fmt.get("duration") or fmt.get("nb_streams"))
    except Exception:
        return False
