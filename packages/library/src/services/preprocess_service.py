"""
预处理状态管理服务。
管理缩略图/帧/HMD预处理的状态跟踪、概览聚合、后台自动预热。
"""

import json
import os
import sys
import threading
import time

from config import THUMBNAILS_DIR, USE_PG
if USE_PG:
    from models.pg_store import read_csv
else:
    from models.csv_store import read_csv
from services.lazy_loader import (
    _PREPROCESS_STATUS, _PREPROCESS_LOCK, _update_preprocess_status,
    _get_hmd_preprocess, _get_hmd_fast_preprocess,
)
from services.video import _ensure_thumbnail, _thumb_cache_key
from utils.path_utils import get_hmd_cache_dir as _get_hmd_cache_dir
from utils.path_utils import parse_location_status as _parse_location_status


def init_preprocess_status_from_rows(rows):
    """根据 CSV rows 初始化预处理状态跟踪（在扫描完成后调用）。"""
    hmd_pre = _get_hmd_preprocess()
    hmd_fast = _get_hmd_fast_preprocess()
    for r in rows:
        vp = r.get("path", "")
        if not vp:
            continue
        ftype = r.get("file_type", "")
        # Thumbnail
        key = _thumb_cache_key(vp)
        thumb_path = os.path.join(THUMBNAILS_DIR, f"{key}.jpg")
        if os.path.isfile(thumb_path) and os.path.getsize(thumb_path) > 0:
            _update_preprocess_status(vp, thumb="done", thumb_progress=100)
        elif ftype == "hmd" and hmd_fast:
            cover_path = os.path.join(hmd_fast.get_output_dir(vp), "cover.jpg")
            if os.path.isfile(cover_path) and os.path.getsize(cover_path) > 0:
                _update_preprocess_status(vp, thumb="done", thumb_progress=100)
            else:
                _update_preprocess_status(vp, thumb="pending", thumb_progress=0)
        else:
            _update_preprocess_status(vp, thumb="pending", thumb_progress=0)
        # Duration
        if (r.get("duration_sec") or "").strip():
            _update_preprocess_status(vp, duration="done")
        else:
            _update_preprocess_status(vp, duration="pending")
        # Frames
        key = _thumb_cache_key(vp)
        frames_dir = os.path.join(THUMBNAILS_DIR, "frames", key)
        if os.path.isdir(frames_dir):
            frame_files = [f for f in os.listdir(frames_dir) if f.endswith('.jpg')]
            if len(frame_files) >= 6:
                _update_preprocess_status(vp, frames="done", frames_progress=100)
            else:
                _update_preprocess_status(vp, frames="pending", frames_progress=0)
        elif ftype == "hmd" and hmd_fast:
            hmd_frames_dir = hmd_fast.get_frames_dir(vp)
            if os.path.isdir(hmd_frames_dir):
                frame_files = [f for f in os.listdir(hmd_frames_dir) if f.endswith('.jpg')]
                if len(frame_files) >= 6:
                    _update_preprocess_status(vp, frames="done", frames_progress=100)
                else:
                    _update_preprocess_status(vp, frames="pending", frames_progress=0)
            else:
                _update_preprocess_status(vp, frames="pending", frames_progress=0)
        else:
            _update_preprocess_status(vp, frames="pending", frames_progress=0)
        # HMD preprocess status
        if ftype == "hmd":
            _sync_hmd_preprocess_status(vp, hmd_pre, hmd_fast)
        else:
            _update_preprocess_status(vp, hmd_preprocess="n/a")


def _sync_hmd_preprocess_status(vp, hmd_pre, hmd_fast):
    """同步单个 HMD session 的预处理状态。"""
    fast_done = False
    if hmd_fast:
        fast_status = hmd_fast.get_status_path(vp)
        if os.path.isfile(fast_status):
            try:
                with open(fast_status, "r", encoding="utf-8") as f:
                    st_data = json.load(f)
                s = st_data.get("status", "unknown")
                _update_preprocess_status(vp, hmd_preprocess=s,
                                          hmd_progress=st_data.get("progress", 0),
                                          hmd_stage=st_data.get("stage", ""))
                if s == "done":
                    fast_done = True
            except Exception:
                _update_preprocess_status(vp, hmd_preprocess="unknown")
        elif os.path.isfile(hmd_fast.get_h265_path(vp)):
            _update_preprocess_status(vp, hmd_preprocess="done",
                                      hmd_progress=100, hmd_stage="fast-done")
            fast_done = True
    if not fast_done and hmd_pre:
        status_file = hmd_pre.get_status_path(vp)
        if os.path.isfile(status_file):
            try:
                with open(status_file, "r", encoding="utf-8") as f:
                    st_data = json.load(f)
                s = st_data.get("status", "unknown")
                _update_preprocess_status(vp, hmd_preprocess=s,
                                          hmd_progress=st_data.get("progress", 0),
                                          hmd_stage=st_data.get("stage", ""))
            except Exception:
                _update_preprocess_status(vp, hmd_preprocess="unknown")
        elif os.path.isdir(hmd_pre.get_output_dir(vp)):
            if os.path.isfile(hmd_pre.get_mp4_path(vp, "left")):
                _update_preprocess_status(vp, hmd_preprocess="done", hmd_progress=100, hmd_stage="done")
            elif os.path.isfile(hmd_pre.get_h265_path(vp, "left")):
                _update_preprocess_status(vp, hmd_preprocess="done",
                                          hmd_progress=100, hmd_stage="h265-ready")
            else:
                _update_preprocess_status(vp, hmd_preprocess="pending", hmd_progress=0, hmd_stage="")
        else:
            _update_preprocess_status(vp, hmd_preprocess="pending", hmd_progress=0, hmd_stage="")
    if not fast_done and not hmd_pre:
        cache_dir = _get_hmd_cache_dir(vp)
        status_file = os.path.join(cache_dir, ".hmd_process.json")
        if os.path.isfile(status_file):
            try:
                with open(status_file, "r", encoding="utf-8") as f:
                    st_data = json.load(f)
                s = st_data.get("status", "unknown")
                _update_preprocess_status(vp, hmd_preprocess=s,
                                          hmd_progress=st_data.get("progress", 0),
                                          hmd_stage=st_data.get("stage", ""))
            except Exception:
                _update_preprocess_status(vp, hmd_preprocess="unknown")
        elif os.path.isdir(cache_dir):
            has_output = any(
                os.path.isfile(os.path.join(cache_dir, f"{eye}.{ext}"))
                for eye in ("left", "right") for ext in ("mp4", "h265")
            )
            if has_output:
                _update_preprocess_status(vp, hmd_preprocess="done", hmd_progress=100, hmd_stage="done")
            else:
                _update_preprocess_status(vp, hmd_preprocess="pending", hmd_progress=0, hmd_stage="")
        else:
            _update_preprocess_status(vp, hmd_preprocess="pending", hmd_progress=0, hmd_stage="")


def get_preprocess_overview():
    """返回所有视频的预处理概览。同时主动同步 HMD status 文件到 _PREPROCESS_STATUS。"""
    rows = read_csv()
    hmd_pre = _get_hmd_preprocess()
    hmd_fast = _get_hmd_fast_preprocess()

    overview = {
        "total": 0,
        "thumb": {"done": 0, "processing": 0, "pending": 0, "error": 0},
        "frames": {"done": 0, "processing": 0, "pending": 0, "error": 0},
        "hmd_preprocess": {"done": 0, "processing": 0, "pending": 0, "error": 0, "n/a": 0},
        "duration": {"done": 0, "pending": 0},
        "items": [],
    }

    # 主动同步 HMD status
    for r in rows:
        if r.get("file_type", "") != "hmd":
            continue
        vp = r.get("path", "")
        if not vp:
            continue
        _sync_hmd_preprocess_status(vp, hmd_pre, hmd_fast)

    with _PREPROCESS_LOCK:
        status_snapshot = dict(_PREPROCESS_STATUS)
    for r in rows:
        vp = r.get("path", "")
        if not vp:
            continue
        overview["total"] += 1
        st = status_snapshot.get(vp, {})
        item = {
            "path": vp,
            "file_type": r.get("file_type", ""),
            "uploaded": r.get("uploaded", ""),
            "location_status": r.get("location_status", ""),
            "duration_sec": r.get("duration_sec", ""),
            "thumb": st.get("thumb", "pending"),
            "thumb_progress": st.get("thumb_progress", 0),
            "frames": st.get("frames", "pending"),
            "frames_progress": st.get("frames_progress", 0),
            "hmd_preprocess": st.get("hmd_preprocess", ""),
            "hmd_progress": st.get("hmd_progress", 0),
            "hmd_stage": st.get("hmd_stage", ""),
        }
        overview["items"].append(item)
        # 统计
        t = item["thumb"]
        overview["thumb"][t if t in overview["thumb"] else "pending"] += 1
        f = item["frames"]
        overview["frames"][f if f in overview["frames"] else "pending"] += 1
        if r.get("file_type", "") == "hmd":
            u = item["hmd_preprocess"] or "pending"
            overview["hmd_preprocess"][u if u in overview["hmd_preprocess"] else "pending"] += 1
        dur = (r.get("duration_sec") or "").strip()
        if dur:
            overview["duration"]["done"] += 1
        else:
            overview["duration"]["pending"] += 1
    return overview


def auto_warm_all(rows):
    """扫描后/启动时自动排队预热缩略图和 HMD 预处理（非阻塞）。

    跳过规则（遵循文件生命周期）：
      - uploaded=Yes 的已上传视频 → 跳过
      - location_status=history 的历史视频（源文件已删除）→ 跳过
      - HMD 源目录不存在或无 part_*.hmd → 跳过
    """
    hmd_fast = _get_hmd_fast_preprocess()

    # Phase 1: 快速预处理
    if hmd_fast:
        for row in rows:
            if row.get("file_type") != "hmd":
                continue
            folder = row.get("path", "")
            if not folder:
                continue
            # 遵循文件生命周期：跳过已上传视频
            if (row.get("uploaded") or "").strip() == "Yes":
                continue
            # 跳过历史视频（源文件已删除，无法预处理）
            _, state = _parse_location_status((row.get("location_status") or "").strip())
            if state == "history":
                continue
            # 源目录不存在或无 HMD 分片 → 跳过
            if not os.path.isdir(folder) or not any(
                f.startswith("part_") and f.endswith(".hmd")
                for f in (os.listdir(folder) if os.path.isdir(folder) else [])
            ):
                continue
            # 已完成 → 跳过
            if hmd_fast.check_fast_done(folder):
                continue
            try:
                hmd_fast.start_async(folder)
            except Exception as e:
                print(f"[auto-warm HMD fast] {folder}: {e}", file=sys.stderr)

    # Phase 2: 缩略图生成（仅本地MP4文件）
    for row in rows:
        path = row.get("path", "")
        if not path or not os.path.isfile(path):
            continue
        # 跳过已上传视频
        if (row.get("uploaded") or "").strip() == "Yes":
            continue
        # 跳过历史视频
        _, state = _parse_location_status((row.get("location_status") or "").strip())
        if state == "history":
            continue
        ext = os.path.splitext(path)[1].lower()
        if ext not in (".mp4", ".avi", ".mov", ".mkv", ".mpg", ".mpeg"):
            continue
        key = _thumb_cache_key(path)
        thumb_path = os.path.join(THUMBNAILS_DIR, f"{key}.jpg")
        if os.path.isfile(thumb_path) and os.path.getsize(thumb_path) > 0:
            continue
        def _bg(p=path):
            try:
                _ensure_thumbnail(p, "mp4")
            except Exception as e:
                print(f"[auto-warm thumb] {p}: {e}", file=sys.stderr)
        threading.Thread(target=_bg, daemon=True).start()


def _startup_auto_warm():
    """后台线程：Flask 启动后自动预热 CSV 中待处理项。"""
    time.sleep(3)
    try:
        rows = read_csv()
        if rows:
            print(f"[startup auto-warm] Found {len(rows)} rows in CSV, checking pending items...",
                  file=sys.stderr)
            auto_warm_all(rows)
    except Exception as e:
        print(f"[startup auto-warm failed] {e}", file=sys.stderr)


