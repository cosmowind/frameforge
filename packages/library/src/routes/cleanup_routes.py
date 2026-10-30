"""cleanup_routes — cache cleanup and preprocess overview endpoints."""

import os
import shutil

from flask import Blueprint, jsonify, request

from config import RUNTIME_DIR, THUMBNAILS_DIR
from config import USE_PG
from utils.path_utils import is_local_status
if USE_PG:
    from models.pg_store import read_csv
else:
    from models.csv_store import read_csv
from services.lazy_loader import (
    _PREPROCESS_LOCK, _PREPROCESS_STATUS, _update_preprocess_status,
)
from services.video import _thumb_cache_key
from routes.data_helpers import _extract_date_from_path

bp = Blueprint("cleanup", __name__)


# ─────────────────────────────────────────────────────────────────
# Clean orphan cache
# ─────────────────────────────────────────────────────────────────

@bp.route("/api/clean-orphan-cache", methods=["POST"])
def clean_orphan_cache():
    """Clean hmd_cache dirs and thumbnails with no corresponding CSV record."""
    rows = read_csv()
    registered_paths = set()
    registered_hmd_keys = set()
    registered_hmd_basenames = set()
    for r in rows:
        vp = os.path.normpath(r.get("path", "")).lower()
        if vp:
            registered_paths.add(vp)
        if r.get("file_type", "") == "hmd":
            rpath = r.get("path", "")
            base = os.path.basename(os.path.normpath(rpath)).lower()
            registered_hmd_basenames.add(base)
            date_key = _extract_date_from_path(rpath)
            registered_hmd_keys.add((date_key, base))

    hmd_cache_root = os.path.join(RUNTIME_DIR, "hmd_cache")
    cleaned_caches = 0
    if os.path.isdir(hmd_cache_root):
        for date_dir in os.listdir(hmd_cache_root):
            date_path = os.path.join(hmd_cache_root, date_dir)
            if not os.path.isdir(date_path):
                continue
            for session_dir in os.listdir(date_path):
                session_path = os.path.join(date_path, session_dir)
                if not os.path.isdir(session_path):
                    continue
                key = (date_dir, session_dir.lower())
                if key not in registered_hmd_keys and session_dir.lower() not in registered_hmd_basenames:
                    try:
                        shutil.rmtree(session_path)
                        cleaned_caches += 1
                    except Exception:
                        pass
            try:
                remaining = [d for d in os.listdir(date_path) if os.path.isdir(os.path.join(date_path, d))]
                if not remaining:
                    os.rmdir(date_path)
            except Exception:
                pass

    cleaned_thumbs = 0
    kept_thumbs = 0
    if os.path.isdir(THUMBNAILS_DIR):
        for fname in os.listdir(THUMBNAILS_DIR):
            if not fname.lower().endswith(".jpg"):
                continue
            fpath = os.path.join(THUMBNAILS_DIR, fname)
            if not os.path.isfile(fpath):
                continue
            matched = False
            for vp in registered_paths:
                try:
                    if _thumb_cache_key(vp) == os.path.splitext(fname)[0]:
                        matched = True
                        break
                except Exception:
                    pass
            if matched:
                kept_thumbs += 1
            else:
                try:
                    os.unlink(fpath)
                    cleaned_thumbs += 1
                except Exception:
                    pass

    return jsonify({
        "ok": True, "cleaned_caches": cleaned_caches,
        "cleaned_thumbs": cleaned_thumbs, "kept_thumbs": kept_thumbs,
    })


# ─────────────────────────────────────────────────────────────────
# Clean uploaded cache
# ─────────────────────────────────────────────────────────────────

@bp.route("/api/clean-uploaded-cache", methods=["POST"])
def clean_uploaded_cache():
    """清理已上传视频的源文件与缓存（preview/execute 模式）。"""
    body = request.get_json(silent=True) or {}
    mode = body.get("mode", "preview")
    rows = read_csv()
    uploaded = [r for r in rows if r.get("uploaded", "").strip().lower() == "yes"]
    if not uploaded:
        return jsonify({
            "ok": True, "mode": mode,
            "deleted_count": 0, "total_freed_mb": 0, "errors": [],
            "total_videos": 0, "videos": [], "summary": {},
        })
    if mode == "preview":
        scan_result = _scan_uploaded_cache(rows, os.path.join(RUNTIME_DIR, "hmd_cache"))
        return jsonify({
            "ok": True, "mode": "preview",
            "total_videos": scan_result["total_videos"],
            "videos": scan_result["videos"],
            "summary": scan_result["summary"],
        })
    deleted_count, total_freed_mb, errors_list = _execute_clean_uploaded_cache(rows)
    return jsonify({
        "ok": True, "mode": "execute",
        "deleted_count": deleted_count, "total_freed_mb": total_freed_mb,
        "errors": errors_list,
    })


def _scan_uploaded_cache(rows, hmd_cache_root):
    """扫描所有已上传视频可删除的文件列表（预览模式）。"""
    uploaded_rows = [(i, r) for i, r in enumerate(rows)
                     if r.get("uploaded", "").strip().lower() == "yes"]
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
        if vpath:
            if ftype == "hmd" and os.path.isdir(vpath):
                src_size = 0
                try:
                    for root_dir, dirs, files in os.walk(vpath):
                        for fn in files:
                            fp = os.path.join(root_dir, fn)
                            try:
                                src_size += os.path.getsize(fp)
                            except Exception:
                                pass
                except Exception:
                    src_size = 0
                if src_size > 0:
                    items.append({
                        "category": "源文件(HMD分片)",
                        "path": vpath,
                        "size_bytes": src_size,
                        "size_mb": round(src_size / (1024 * 1024), 2),
                        "exists": True,
                    })
                    summary["source_count"] += 1
                    summary["source_size_mb"] += round(src_size / (1024 * 1024), 2)
                    video_total += src_size
        date_key = _extract_date_from_path(vpath)
        session_name = os.path.basename(vpath.rstrip("\\/"))
        cache_dir = os.path.join(hmd_cache_root, date_key, session_name)
        if os.path.isdir(cache_dir):
            _sn = session_name
            _all_vf = (f"{_sn}.mp4", f"{_sn}_right.mp4", f"{_sn}.h265", f"{_sn}_right.h265",
                       "left.mp4", "right.mp4", "left.h265", "right.h265")
            for vf in _all_vf:
                vp = os.path.join(cache_dir, vf)
                if os.path.isfile(vp):
                    sz = os.path.getsize(vp)
                    is_h265 = vf.endswith(".h265")
                    items.append({
                        "category": "预览视频(H265)" if is_h265 else "预览视频(MP4)",
                        "path": vp,
                        "size_bytes": sz,
                        "size_mb": round(sz / (1024 * 1024), 2),
                        "exists": True,
                    })
                    if is_h265:
                        summary["preview_h265_count"] += 1
                        summary["preview_h265_size_mb"] += round(sz / (1024 * 1024), 2)
                    else:
                        summary["preview_mp4_count"] += 1
                        summary["preview_mp4_size_mb"] += round(sz / (1024 * 1024), 2)
                    video_total += sz
            frames_dir = os.path.join(cache_dir, "frames")
            if os.path.isdir(frames_dir):
                try:
                    for f in os.listdir(frames_dir):
                        if f.lower().endswith(".jpg"):
                            fp = os.path.join(frames_dir, f)
                            sz = os.path.getsize(fp)
                            items.append({
                                "category": "预览帧",
                                "path": fp,
                                "size_bytes": sz,
                                "size_mb": round(sz / (1024 * 1024), 2),
                                "exists": True,
                            })
                            summary["preview_frames_file_count"] += 1
                            summary["preview_frames_size_mb"] += round(sz / (1024 * 1024), 2)
                            video_total += sz
                except Exception:
                    pass
            status_files = ("hmd_process.json", "hmd_fast.json")
            for sf in status_files:
                sp = os.path.join(cache_dir, sf)
                if os.path.isfile(sp):
                    sz = os.path.getsize(sp)
                    items.append({
                        "category": "预处理状态",
                        "path": sp,
                        "size_bytes": sz,
                        "size_mb": round(sz / (1024 * 1024), 2),
                        "exists": True,
                    })
                    summary["preprocess_status_count"] += 1
                    video_total += sz
        if items:
            videos.append({"csv_index": csv_idx, "path": vpath, "items": items,
                           "total_bytes": video_total,
                           "total_mb": round(video_total / (1024 * 1024), 2)})
            summary["total_size_mb"] += round(video_total / (1024 * 1024), 2)
    return {"videos": videos, "summary": summary}


def _execute_clean_uploaded_cache(rows):
    """执行已上传视频的缓存文件删除。"""
    scan_result = _scan_uploaded_cache(rows, os.path.join(RUNTIME_DIR, "hmd_cache"))
    deleted_count = 0
    total_freed_mb = 0.0
    errors_list = []
    for video in scan_result["videos"]:
        for item in video["items"]:
            try:
                if os.path.isfile(item["path"]):
                    os.unlink(item["path"])
                    deleted_count += 1
                    total_freed_mb += item["size_mb"]
            except Exception as e:
                errors_list.append(f"{item['path']}: {e}")
    return deleted_count, round(total_freed_mb, 2), errors_list


# ─────────────────────────────────────────────────────────────────
# Preprocess overview
# ─────────────────────────────────────────────────────────────────

@bp.route("/api/preprocess-overview")
def preprocess_overview():
    """Return overview of all videos' preprocessing status."""
    return jsonify(_get_preprocess_overview())


@bp.route("/api/preprocess-overview/enable-tracking", methods=["POST"])
def enable_preprocess_tracking():
    """Enable background status tracking for all local videos."""
    rows = read_csv()
    enabled = 0
    for r in rows:
        vp = r.get("path", "")
        if not vp or not is_local_status(r.get("location_status")):
            continue
        with _PREPROCESS_LOCK:
            if vp not in _PREPROCESS_STATUS:
                _PREPROCESS_STATUS[vp] = {}
        ftype = r.get("file_type", "")
        kind = ftype if ftype in ("mp4", "hmd") else "mp4"
        key = _thumb_cache_key(vp)
        thumb_path = os.path.join(THUMBNAILS_DIR, f"{key}.jpg")
        if os.path.isfile(thumb_path) and os.path.getsize(thumb_path) > 0:
            _update_preprocess_status(vp, thumb="done", thumb_progress=100)
        else:
            _update_preprocess_status(vp, thumb="pending", thumb_progress=0)
        from services.data_service import read_hmd_duration_from_status as _read_hmd_duration_from_status
        if kind == "hmd":
            dur = _read_hmd_duration_from_status(vp)
            if dur:
                _update_preprocess_status(vp, duration=dur)
                try:
                    _update_preprocess_status(vp, duration_sec=int(round(float(dur))))
                except Exception:
                    pass
        enabled += 1
    return jsonify({"ok": True, "enabled": enabled})


def _get_preprocess_overview():
    """返回所有视频的预处理概览，同时主动同步 HMD status 文件到内存状态。
    委托给 preprocess_service.get_preprocess_overview() 以保持逻辑统一。
    """
    from services.preprocess_service import get_preprocess_overview as _svc_overview
    return _svc_overview()
