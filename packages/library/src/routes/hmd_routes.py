"""hmd_routes — HMD session management: scan, preprocess, file serving, duration, register."""

import glob
import json
import os
import urllib.parse

from flask import Blueprint, jsonify, request, send_file

from config import RUNTIME_DIR, SESSION_MARKER, USE_PG
if USE_PG:
    from models.pg_store import get_fieldnames, read_csv, write_csv
else:
    from models.csv_store import get_fieldnames, read_csv, write_csv
from services.lazy_loader import (
    _get_hmd_fast_preprocess, _get_hmd_preprocess,
)
from services.video import _extract_hmd_frames, _is_registered_video_path
from utils.format_utils import get_hmd_date as _get_hmd_date
from utils.path_utils import get_hmd_cache_dir as _get_hmd_cache_dir

bp = Blueprint("hmd", __name__)


# ─────────────────────────────────────────────────────────────────
# Helpers (private to this module)
# ─────────────────────────────────────────────────────────────────

def _scan_hmd_sessions(directory):
    """List HMD session subdirs under directory (folders with part_*.hmd + metadata.json)."""
    sessions = []
    err = None
    try:
        for root, dirs, files in os.walk(directory):
            has_parts = any(f.startswith("part_") and f.endswith(".hmd") for f in files)
            has_meta = "metadata.json" in files
            if has_parts and has_meta:
                parts = sorted(glob.glob(os.path.join(root, "part_*.hmd")))
                total = sum(os.path.getsize(p) for p in parts)
                meta = None
                try:
                    with open(os.path.join(root, "metadata.json"), "r", encoding="utf-8") as f:
                        meta = json.load(f)
                except Exception:
                    pass
                sessions.append({
                    "folder": root,
                    "parts": [os.path.basename(p) for p in parts],
                    "total_size": total,
                    "metadata": meta,
                })
                dirs[:] = []
    except Exception as e:
        err = str(e)
    return sessions, err


def _scan_data_sessions(directory):
    """List Data session subdirs (session.json or metadata.json without part_*.hmd)."""
    sessions = []
    err = None
    try:
        for root, dirs, files in os.walk(directory):
            has_parts = any(f.startswith("part_") and f.endswith(".hmd") for f in files)
            has_session_json = "session.json" in files
            has_meta = "metadata.json" in files
            is_data = (has_session_json or has_meta) and not has_parts
            if is_data:
                config_path = os.path.join(root, "session.json") if has_session_json else os.path.join(root, "metadata.json")
                dev_short = ""
                hostname = ""
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    dev = None
                    if "devices" in meta:
                        dev = (meta.get("devices") or [{}])[0]
                    elif "device" in meta:
                        dev = meta.get("device") or {}
                    elif "device_id" in meta:
                        dev_id = meta.get("device_id", "") or ""
                        dev_short = dev_id[-6:] if dev_id else ""
                    if dev:
                        dev_id = dev.get("identity", {}).get("device_id", "") or ""
                        if not dev_id and "device_id" in dev:
                            dev_id = dev.get("device_id", "") or ""
                        dev_short = dev_id[-6:] if dev_id else ""
                        hostname = dev.get("identity", {}).get("hostname", "") or ""
                        if not hostname and "hostname" in dev:
                            hostname = dev.get("hostname", "") or ""
                except Exception:
                    pass
                data_files = [f for f in files if f not in ("session.json", "metadata.json")]
                sessions.append({
                    "folder": root,
                    "files": data_files,
                    "file_count": len(data_files),
                    "total_size": sum(os.path.getsize(os.path.join(root, f))
                                      for f in data_files if os.path.isfile(os.path.join(root, f))),
                    "device_short": dev_short,
                    "hostname": hostname,
                })
                dirs[:] = []
    except Exception as e:
        err = str(e)
    return sessions, err


# ─────────────────────────────────────────────────────────────────
# Scan
# ─────────────────────────────────────────────────────────────────

@bp.route("/api/hmd/scan", methods=["POST"])
def scan_hmd_dir():
    """Scan a directory for HMD sessions."""
    data = request.get_json(silent=True) or {}
    directory = (data.get("directory") or "").strip()
    if not directory or not os.path.isdir(directory):
        return jsonify({"error": "目录不存在"}), 400
    sessions, err = _scan_hmd_sessions(directory)
    return jsonify({"sessions": sessions, "count": len(sessions), "error": err})


@bp.route("/api/data/scan", methods=["POST"])
def scan_data_dir():
    """Scan a directory for Data sessions."""
    data = request.get_json(silent=True) or {}
    directory = (data.get("directory") or "").strip()
    if not directory or not os.path.isdir(directory):
        return jsonify({"error": "目录不存在"}), 400
    sessions, err = _scan_data_sessions(directory)
    return jsonify({"sessions": sessions, "count": len(sessions), "error": err})


# ─────────────────────────────────────────────────────────────────
# File serving
# ─────────────────────────────────────────────────────────────────

@bp.route("/api/hmd/file")
def serve_hmd_file():
    """Stream a single .hmd file (used by frontend WebCodecs fetcher)."""
    path = request.args.get("path", "")
    if not path:
        return "Missing path", 400
    if not path.lower().endswith(".hmd"):
        return "Forbidden: only .hmd allowed", 403
    parent = os.path.normpath(os.path.dirname(path))
    if not _is_registered_video_path(parent):
        return "Forbidden: parent folder not in video_manager.csv", 403
    if not os.path.isfile(path):
        return "File not found", 404
    return send_file(path, mimetype="application/octet-stream", conditional=True)


@bp.route("/api/hmd/info")
def hmd_info():
    """List parts + metadata for a session folder."""
    folder = request.args.get("path", "").strip()
    if not folder or not os.path.isdir(folder):
        return jsonify({"error": "目录不存在"}), 400
    if not _is_registered_video_path(folder):
        return jsonify({"error": "Forbidden: folder not in video_manager.csv"}), 403
    meta_path = os.path.join(folder, SESSION_MARKER)
    meta = None
    if os.path.isfile(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            meta = None
    parts = sorted(glob.glob(os.path.join(folder, "part_*.hmd")))
    out = []
    total_size = 0
    for p in parts:
        sz = os.path.getsize(p)
        total_size += sz
        out.append({"name": os.path.basename(p), "size": sz})
    return jsonify({"folder": folder, "parts": out, "total_size": total_size, "metadata": meta})


@bp.route("/api/hmd/raw")
def hmd_raw():
    """Stream a single .hmd part file."""
    folder = request.args.get("path", "").strip()
    fname = request.args.get("file", "").strip()
    if not folder or not fname:
        return "Missing params", 400
    if not _is_registered_video_path(folder):
        return "Forbidden: folder not in video_manager.csv", 403
    safe = os.path.basename(fname)
    if not safe or not safe.lower().endswith(".hmd"):
        return "Forbidden", 403
    full = os.path.join(folder, safe)
    if not os.path.isfile(full):
        return "Not found", 404
    return send_file(full, mimetype="application/octet-stream", conditional=True)


# ─────────────────────────────────────────────────────────────────
# Preprocessing
# ─────────────────────────────────────────────────────────────────

@bp.route("/api/hmd/process", methods=["POST"])
def hmd_process_start():
    """Kick off background preprocessing (fast / mp4 / full)."""
    hmd_preprocess = _get_hmd_preprocess()
    hmd_fast = _get_hmd_fast_preprocess()
    if not hmd_preprocess and not hmd_fast:
        return jsonify({"error": "hmd_preprocess 模块未加载"}), 500
    body = request.get_json(silent=True) or {}
    folder = (body.get("folder") or "").strip()
    mode = (body.get("mode") or "fast").strip()
    if not folder or not os.path.isdir(folder):
        return jsonify({"error": "Folder not found"}), 404
    if not glob.glob(os.path.join(folder, "part_*.hmd")):
        return jsonify({"error": "No part_*.hmd files"}), 404

    if hmd_preprocess and os.path.isfile(hmd_preprocess.get_mp4_path(folder, "left")):
        try:
            status_file = hmd_preprocess.get_status_path(folder)
            with open(status_file, "r", encoding="utf-8") as f:
                return jsonify({"status": "done", "mode": "full", **json.load(f)})
        except Exception:
            return jsonify({"status": "done"})

    if mode == "fast":
        if not hmd_fast:
            return jsonify({"error": "hmd_fast 模块未加载"}), 500
        if hmd_fast.check_fast_done(folder):
            return jsonify({"status": "done", "mode": "fast"})
        hmd_fast.start_async(folder)
        return jsonify({"status": "processing", "mode": "fast", "started": True}), 202
    elif mode == "mp4":
        if not hmd_preprocess:
            return jsonify({"error": "hmd_preprocess 模块未加载"}), 500
        h265_path = hmd_preprocess.get_h265_path(folder, "left")
        if not os.path.isfile(h265_path) or os.path.getsize(h265_path) == 0:
            return jsonify({"error": "left.h265 not ready (run fast preprocess first)", "status": "h265_missing"}), 400
        hmd_preprocess.start_async(folder)
        return jsonify({"status": "processing", "mode": "mp4", "started": True}), 202
    elif mode == "full":
        if not hmd_preprocess:
            return jsonify({"error": "hmd_preprocess 模块未加载"}), 500
        hmd_preprocess.start_async(folder)
        return jsonify({"status": "processing", "mode": "full", "started": True}), 202
    else:
        return jsonify({"error": f"Unknown mode: {mode}"}), 400


@bp.route("/api/hmd/process-batch", methods=["POST"])
def hmd_process_batch():
    """Enqueue a batch of HMD sessions for serial processing."""
    hmd_preprocess = _get_hmd_preprocess()
    if not hmd_preprocess:
        return jsonify({"error": "hmd_preprocess 模块未加载"}), 500
    body = request.get_json(silent=True) or {}
    folders = body.get("folders") or []
    if not isinstance(folders, list):
        return jsonify({"error": "folders 必须是 list"}), 400
    queued = 0
    skipped = 0
    for folder in folders:
        if not isinstance(folder, str):
            continue
        folder = folder.strip()
        if not folder or not os.path.isdir(folder):
            continue
        if not glob.glob(os.path.join(folder, "part_*.hmd")):
            continue
        if os.path.isfile(hmd_preprocess.get_mp4_path(folder, "left")):
            skipped += 1
            continue
        try:
            hmd_preprocess.start_async(folder)
            queued += 1
        except Exception as e:
            print(f"[hmd batch] {folder}: {e}", file=sys.stderr)
    return jsonify({"ok": True, "queued": queued, "skipped": skipped}), 202


@bp.route("/api/hmd/retry", methods=["POST"])
def hmd_process_retry():
    """Retry failed preprocessing for a folder."""
    hmd_preprocess = _get_hmd_preprocess()
    if not hmd_preprocess:
        return jsonify({"error": "hmd_preprocess 模块未加载"}), 500
    body = request.get_json(silent=True) or {}
    folder = (body.get("folder") or "").strip()
    if not folder:
        return jsonify({"error": "folder required"}), 400
    hmd_preprocess.start_async(folder)
    return jsonify({"status": "processing", "started": True}), 202


@bp.route("/api/hmd/process-status")
def hmd_process_status():
    """Poll status of preprocessing jobs (fast + full)."""
    folder = request.args.get("folder", "")
    if not folder:
        return jsonify({"error": "Missing folder"}), 400
    hmd_pre = _get_hmd_preprocess()
    hmd_fast = _get_hmd_fast_preprocess()
    if not hmd_pre and not hmd_fast:
        return jsonify({"error": "hmd_preprocess module not loaded"}), 500

    in_fast_queue = False
    is_fast_active = False
    fast_qinfo = None
    if hmd_fast:
        fast_qinfo = hmd_fast.get_queue_info()
        in_fast_queue = folder in fast_qinfo["queue"]
        is_fast_active = folder == fast_qinfo["active_folder"]

    in_mp4_queue = False
    is_mp4_active = False
    mp4_qinfo = None
    if hmd_pre:
        mp4_qinfo = hmd_pre.get_queue_info()
        in_mp4_queue = folder in mp4_qinfo["queue"]
        is_mp4_active = folder == mp4_qinfo["active_folder"]

    fast_status_file = None
    if hmd_fast:
        fast_status_file = hmd_fast.get_status_path(folder)
    if fast_status_file and os.path.isfile(fast_status_file):
        try:
            with open(fast_status_file, "r", encoding="utf-8") as f:
                status = json.load(f)
            status["fast_queue"] = "active" if is_fast_active else ("queued" if in_fast_queue else "none")
            status["mp4_queue"] = "active" if is_mp4_active else ("queued" if in_mp4_queue else "none")
            return jsonify(status)
        except Exception as e:
            status = {"status": "unknown", "error": str(e)}
    elif is_fast_active:
        status = {"status": "processing", "stage": "starting", "progress": 0,
                  "fast_queue": "active", "mp4_queue": "none"}
    elif in_fast_queue:
        if fast_qinfo:
            queue_pos = fast_qinfo["queue"].index(folder) + 1
            status = {"status": "pending", "stage": "queued-fast", "progress": 0,
                      "queue_position": queue_pos, "queue_total": len(fast_qinfo["queue"]),
                      "fast_queue": "queued", "mp4_queue": "none"}
        else:
            status = {"status": "pending", "stage": "queued-fast", "progress": 0}
    elif hmd_pre:
        status_file = hmd_pre.get_status_path(folder)
        if os.path.isfile(status_file):
            try:
                with open(status_file, "r", encoding="utf-8") as f:
                    status = json.load(f)
            except Exception as e:
                status = {"status": "unknown", "error": str(e)}
        elif is_mp4_active:
            status = {"status": "processing", "stage": "starting", "progress": 0}
        elif in_mp4_queue:
            if mp4_qinfo:
                queue_pos = mp4_qinfo["queue"].index(folder) + 1
                status = {"status": "pending", "stage": "queued-mp4", "progress": 0,
                          "queue_position": queue_pos, "queue_total": len(mp4_qinfo["queue"])}
            else:
                status = {"status": "pending", "stage": "queued-mp4", "progress": 0}
        else:
            return jsonify({"error": "No status", "status": "unknown"}), 404
        if status.get("status") == "processing" and not is_mp4_active and not in_mp4_queue:
            if not os.path.isfile(hmd_pre.get_mp4_path(folder, "left")):
                status["status"] = "error"
                status["error"] = status.get("error") or "Processing interrupted (stale state)"
    else:
        return jsonify({"error": "No status", "status": "unknown"}), 404

    if "fast_queue" not in status:
        status["fast_queue"] = "none"
    if "mp4_queue" not in status:
        status["mp4_queue"] = "none"
    return jsonify(status)


@bp.route("/api/hmd/queue-status")
def hmd_queue_status():
    """Return both serial processing queue states (fast + mp4)."""
    hmd_pre = _get_hmd_preprocess()
    hmd_fast = _get_hmd_fast_preprocess()
    result = {"fast": {"active_folder": None, "queue": []},
              "mp4": {"active_folder": None, "queue": []}}
    if hmd_fast:
        result["fast"] = hmd_fast.get_queue_info()
    if hmd_pre:
        result["mp4"] = hmd_pre.get_queue_info()
    return jsonify(result)


# ─────────────────────────────────────────────────────────────────
# MP4 serving
# ─────────────────────────────────────────────────────────────────

@bp.route("/api/hmd/mp4")
def hmd_serve_mp4():
    """Serve preprocessed left.mp4 / right.mp4 with HTTP Range."""
    folder = request.args.get("folder", "")
    eye = request.args.get("eye", "")
    if folder:
        folder = folder.replace("/", os.sep).replace("\\", os.sep)
    if not folder or eye not in ("left", "right"):
        return "Bad request", 400
    hmd_pre = _get_hmd_preprocess()
    if not hmd_pre:
        return "hmd_preprocess module not loaded", 500
    full = os.path.normpath(hmd_pre.get_mp4_path(folder, eye))
    cache_dir = os.path.normpath(hmd_pre.get_output_dir(folder))
    if not full.startswith(cache_dir):
        return "Forbidden", 403
    if not os.path.isfile(full):
        return "Not found", 404
    response = send_file(full, mimetype="video/mp4", conditional=True)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Range"
    return response


# ─────────────────────────────────────────────────────────────────
# Frames
# ─────────────────────────────────────────────────────────────────

@bp.route("/api/hmd/frames")
def hmd_get_frames():
    """Extract and return multiple preview frames from HMD video."""
    folder = request.args.get("folder", "")
    if folder:
        folder = folder.replace("/", os.sep).replace("\\", os.sep)
    if not folder or not os.path.isdir(folder):
        return jsonify({"error": "Invalid folder path"}), 400
    cache_dir = _get_hmd_cache_dir(folder)
    frames_dir = os.path.join(cache_dir, "frames")
    frame_count = len([f for f in os.listdir(frames_dir) if f.endswith(".jpg")]) if os.path.isdir(frames_dir) else 0
    if frame_count < 6:
        try:
            _extract_hmd_frames(folder, frames_dir, num_frames=6, width=320)
        except Exception as e:
            return jsonify({"error": f"Frame extraction failed: {str(e)}"}), 500
    if not os.path.isdir(frames_dir):
        return jsonify({"frames": []})
    frame_files = sorted([f for f in os.listdir(frames_dir) if f.endswith(".jpg")])
    frames = []
    for f in frame_files:
        frames.append({
            "url": f"/api/hmd/frame?folder={urllib.parse.quote(folder)}&file={urllib.parse.quote(f)}",
            "file": f,
        })
    return jsonify({"frames": frames})


@bp.route("/api/hmd/open", methods=["POST"])
def hmd_open_system_player():
    """Open HMD preview video (MP4 only) with system default player.

    注意：只打开 mp4，不再 fallback 到 h265。
    原因：h265/HEVC 大多数系统播放器不兼容（需要额外安装 HEVC codec），
    打开后用户看到的可能是"无法播放"。正确做法：要求预处理必须成功生成 mp4。
    """
    body = request.get_json(silent=True) or {}
    folder = (body.get("folder") or "").strip()
    if folder:
        folder = folder.replace("/", os.sep).replace("\\", os.sep)
    if not folder:
        return jsonify({"error": "无效的文件夹路径"}), 400
    cache_dir = _get_hmd_cache_dir(folder)
    session_bn = os.path.basename(os.path.normpath(folder))
    # 只查找 mp4（不再 fallback h265）
    for name in (
        f"{session_bn}.mp4", "left.mp4",
        f"{session_bn}_right.mp4", "right.mp4",
    ):
        candidate = os.path.join(cache_dir, name)
        if os.path.isfile(candidate):
            video_path = candidate
            break
    else:
        video_path = None
    if not video_path:
        return jsonify({
            "error": "MP4 预览视频尚未生成，请先完成 HMD 预处理（h265 视频不能直接用系统播放器打开）",
            "hint": "回到视频管理页 → ⏳ 预处理 → 全部预热"
        }), 404
    try:
        os.startfile(video_path)
        return jsonify({"ok": True, "path": video_path})
    except Exception as e:
        return jsonify({"error": f"打开播放器失败: {str(e)}"}), 500


@bp.route("/api/hmd/frame")
def hmd_serve_frame():
    """Serve a specific frame image from HMD cache."""
    folder = request.args.get("folder", "")
    file = request.args.get("file", "")
    if folder:
        folder = folder.replace("/", os.sep).replace("\\", os.sep)
    if not folder or not file:
        return "Bad request", 400
    if not file.endswith(".jpg"):
        return "Forbidden", 403
    cache_dir = _get_hmd_cache_dir(folder)
    frame_path = os.path.join(cache_dir, "frames", file)
    if not os.path.isfile(frame_path):
        return "Frame not found", 404
    return send_file(frame_path, mimetype="image/jpeg", conditional=True)


# ─────────────────────────────────────────────────────────────────
# Duration & registration
# ─────────────────────────────────────────────────────────────────

@bp.route("/api/hmd/duration", methods=["POST"])
def set_hmd_duration():
    """Client-side callback: write parsed duration (sec) back into video_manager.csv."""
    body = request.get_json(silent=True) or {}
    session_path = (body.get("sessionPath") or "").strip()
    try:
        seconds = int(body.get("seconds", 0) or 0)
    except (TypeError, ValueError):
        return jsonify({"error": "seconds 必须为整数"}), 400
    if not session_path:
        return jsonify({"error": "缺少 sessionPath"}), 400
    rows = read_csv()
    updated = 0
    for r in rows:
        if r.get("path", "").strip() == session_path:
            r["duration_sec"] = str(seconds)
            updated += 1
    if updated:
        write_csv(rows)
    return jsonify({"ok": True, "updated": updated})


@bp.route("/api/hmd/register", methods=["POST"])
def register_hmd_session():
    """Add a single HMD session as a row in video_manager.csv."""
    import datetime
    body = request.get_json(silent=True) or {}
    session_path = (body.get("sessionPath") or "").strip()
    if not session_path or not os.path.isdir(session_path):
        return jsonify({"error": "sessionPath 不存在"}), 400
    meta_path = os.path.join(session_path, SESSION_MARKER)
    if not os.path.isfile(meta_path):
        return jsonify({"error": "该目录不是合法 HMD session（缺 metadata.json）"}), 400
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
    except Exception as e:
        return jsonify({"error": f"解析 metadata.json 失败: {e}"}), 400
    parts = sorted(glob.glob(os.path.join(session_path, "part_*.hmd")))
    if not parts:
        return jsonify({"error": "session 目录内未找到 part_*.hmd"}), 400
    dev = (meta.get("devices") or [{}])[0]
    dev_id = dev.get("identity", {}).get("device_id", "") or ""
    device_short = dev_id[-6:] if dev_id else ""
    file_date = _get_hmd_date(session_path, meta)
    rows = read_csv()
    existing_map = {r.get("path", ""): r for r in rows}
    if session_path in existing_map:
        return jsonify({"ok": True, "existed": True, "path": session_path})
    fieldnames = get_fieldnames()
    new_row = {fn: "" for fn in fieldnames}
    new_row["path"] = session_path
    new_row["file_type"] = "hmd"
    new_row["location_status"] = "local"
    new_row["scan_date"] = datetime.datetime.now().strftime("%Y-%m-%d")
    new_row["original_history_date"] = file_date
    new_row["device_id"] = body.get("deviceId") or device_short
    new_row["recorder_id"] = body.get("recorderId", "")
    new_row["task_id"] = body.get("taskId", "")
    new_row["uploaded"] = "No"
    duration_sec = body.get("durationSec")
    if duration_sec:
        try:
            new_row["duration_sec"] = str(int(duration_sec))
        except (TypeError, ValueError):
            pass
    rows.append(new_row)
    write_csv(rows)
    return jsonify({"ok": True, "path": session_path, "row": new_row})