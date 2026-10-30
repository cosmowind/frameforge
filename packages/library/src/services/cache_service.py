import os
import json
import glob
import re
import shutil
from datetime import datetime
from typing import Optional, Dict, List, Any
from config import *


def _scan_uploaded_cache(rows, hmd_cache_root):
    """扫描所有已上传视频可删除的文件列表（预览模式，不实际删除）。

    Returns:
        dict with keys: videos (list of per-video items), summary (aggregated stats)
    """
    uploaded_rows = [(i, r) for i, r in enumerate(rows) if r.get("uploaded", "").strip().lower() == "yes"]

    videos = []
    summary = {
        "source_count": 0, "source_size_mb": 0,
        "preview_mp4_count": 0, "preview_mp4_size_mb": 0,
        "preview_h265_count": 0, "preview_h265_size_mb": 0,
        "preview_frames_file_count": 0, "preview_frames_size_mb": 0,
        "preprocess_status_count": 0,
        "total_size_mb": 0,
    }

    for csv_idx, r in uploaded_rows:
        vpath = os.path.normpath(r.get("path", ""))
        ftype = r.get("file_type", "").strip().lower()
        items = []
        video_total = 0

        # ── 1) 源文件 ──
        if vpath:
            if ftype == "hmd" and os.path.isdir(vpath):
                src_size = 0
                try:
                    for root, dirs, files in os.walk(vpath):
                        for fn in files:
                            fp = os.path.join(root, fn)
                            try:
                                src_size += os.path.getsize(fp)
                            except Exception:
                                pass
                except Exception:
                    src_size = 0
                items.append({
                    "category": "源文件(HMD分片)",
                    "path": vpath,
                    "size_bytes": src_size,
                    "size_mb": round(src_size / (1024 * 1024), 2),
                    "exists": True,
                })
                video_total += src_size
                summary["source_count"] += 1
                summary["source_size_mb"] += items[-1]["size_mb"]

            elif ftype == "mp4" and os.path.isfile(vpath):
                try:
                    src_size = os.path.getsize(vpath)
                except Exception:
                    src_size = 0
                items.append({
                    "category": "源文件(MP4)",
                    "path": vpath,
                    "size_bytes": src_size,
                    "size_mb": round(src_size / (1024 * 1024), 2),
                    "exists": True,
                })
                video_total += src_size
                summary["source_count"] += 1
                summary["source_size_mb"] += items[-1]["size_mb"]

            elif vpath and not os.path.exists(vpath):
                # 源文件已不存在
                items.append({
                    "category": "源文件",
                    "path": vpath,
                    "size_bytes": 0,
                    "size_mb": 0,
                    "exists": False,
                    "note": "文件已不存在（可能已清理）",
                })

        # ── 2) hmd_cache 中的预览文件 ──
        session_name = os.path.basename(vpath.rstrip("\\/")) if vpath else ""
        date_key = _extract_date_from_path(vpath) if vpath else "unknown"
        cache_dir = os.path.join(hmd_cache_root, date_key, session_name)

        if os.path.isdir(cache_dir):
            # 预览 mp4（新旧命名兼容）
            _sname = session_name
            _mp4_patterns = (
                f"{_sname}.mp4", f"{_sname}_right.mp4",
                "left.mp4", "right.mp4",
            )
            for video_file in _mp4_patterns:
                vf = os.path.join(cache_dir, video_file)
                if os.path.isfile(vf):
                    try:
                        sz = os.path.getsize(vf)
                    except Exception:
                        sz = 0
                    items.append({
                        "category": "预览mp4",
                        "path": vf,
                        "size_bytes": sz,
                        "size_mb": round(sz / (1024 * 1024), 2),
                        "exists": True,
                    })
                    video_total += sz
                    summary["preview_mp4_count"] += 1
                    summary["preview_mp4_size_mb"] += items[-1]["size_mb"]

            # 预览 h265
            for h265_file in ("left.h265", "right.h265"):
                vf = os.path.join(cache_dir, h265_file)
                if os.path.isfile(vf):
                    try:
                        sz = os.path.getsize(vf)
                    except Exception:
                        sz = 0
                    items.append({
                        "category": "预览h265",
                        "path": vf,
                        "size_bytes": sz,
                        "size_mb": round(sz / (1024 * 1024), 2),
                        "exists": True,
                    })
                    video_total += sz
                    summary["preview_h265_count"] += 1
                    summary["preview_h265_size_mb"] += items[-1]["size_mb"]

            # 预览帧 frames/
            frames_dir = os.path.join(cache_dir, "frames")
            if os.path.isdir(frames_dir):
                frame_count = 0
                frame_size = 0
                try:
                    for fn in os.listdir(frames_dir):
                        fp = os.path.join(frames_dir, fn)
                        if os.path.isfile(fp):
                            try:
                                frame_size += os.path.getsize(fp)
                                frame_count += 1
                            except Exception:
                                pass
                except Exception:
                    pass
                if frame_count > 0:
                    items.append({
                        "category": "预览帧",
                        "path": frames_dir,
                        "file_count": frame_count,
                        "size_bytes": frame_size,
                        "size_mb": round(frame_size / (1024 * 1024), 2),
                        "exists": True,
                    })
                    video_total += frame_size
                    summary["preview_frames_file_count"] += frame_count
                    summary["preview_frames_size_mb"] += items[-1]["size_mb"]

            # preprocess_status.json
            status_file = os.path.join(cache_dir, "preprocess_status.json")
            if os.path.isfile(status_file):
                try:
                    sz = os.path.getsize(status_file)
                except Exception:
                    sz = 0
                items.append({
                    "category": "预处理状态文件",
                    "path": status_file,
                    "size_bytes": sz,
                    "size_mb": round(sz / (1024 * 1024), 2),
                    "exists": True,
                })
                summary["preprocess_status_count"] += 1

        summary["total_size_mb"] += round(video_total / (1024 * 1024), 2)

        if items:
            videos.append({
                "csv_index": csv_idx,
                "display_path": vpath,
                "file_type": ftype,
                "session_name": session_name,
                "items": items,
                "total_size_mb": round(video_total / (1024 * 1024), 2),
            })

    summary["total_size_mb"] = round(summary["total_size_mb"], 2)
    return {"videos": videos, "summary": summary, "total_videos": len(videos)}


