from flask import Blueprint, jsonify, request, send_file, Response, stream_with_context, make_response
from config import *
from config import USE_PG, DATABASE_DSN
import os
import sys
import json
import threading
import time
from datetime import datetime
import subprocess
import logging

from config import USE_PG
from utils.path_utils import is_local_status
if USE_PG:
    from models.pg_store import read_csv
else:
    from models.csv_store import read_csv
from services.upload_config_service import _load_upload_options
from services.upload_execution_service import _generate_upload_runner
from services.upload_service import _is_hmd_session
logger = logging.getLogger(__name__)

bp = Blueprint("upload", __name__)


def _resolve_row_range(row_range_str, data_len):
    """Parse 'xx-xx' range string into list of 0-based indices. Returns empty list if invalid."""
    if not row_range_str:
        return []
    try:
        parts = row_range_str.strip().split("-")
        if len(parts) != 2:
            return []
        start = int(parts[0].strip()) - 1  # 1-based → 0-based
        end = int(parts[1].strip()) - 1
        if start < 0 or end < 0 or start > end:
            return []
        end = min(end, data_len - 1)
        return list(range(start, end + 1))
    except (ValueError, IndexError):
        return []


@bp.route("/api/upload-options")
def get_upload_options():
    """返回上传表单的枚举选项数据（国家、场景分类等）"""
    return jsonify(_load_upload_options())


@bp.route("/api/export", methods=["POST"])
def export_txt():
    body = request.get_json()
    selected_cols = body.get("columns", [])  # list of column keys in order
    selected_rows = body.get("rows", [])    # list of row indices
    row_range = body.get("rowRange", "")     # "xx-xx" range string
    separator = body.get("separator", ".")   # default "."

    if not selected_cols:
        return jsonify({"error": "请选择至少一列"}), 400

    data = read_csv()

    # Resolve row selection
    row_indices = set(selected_rows)
    if row_range:
        range_indices = _resolve_row_range(row_range, len(data))
        row_indices.update(range_indices)

    if row_indices:
        data = [data[i] for i in sorted(row_indices) if 0 <= i < len(data)]

    lines = []
    for row in data:
        for col in selected_cols:
            lines.append(str(row.get(col, "")).strip())

    content = "\n".join(lines)
    response = make_response(content)
    response.headers["Content-Type"] = "text/plain; charset=utf-8"
    response.headers["Content-Disposition"] = "attachment; filename=export.txt"
    return response


# ── 上传后清理函数 ──


@bp.route("/api/upload-generate", methods=["POST"])
def upload_generate():
    """Generate _upload_now.py + _upload_now.cmd scripts to disk."""
    body = request.get_json()
    row_indices = body.get("rows", [])
    row_range = body.get("rowRange", "")
    selected_only = body.get("selectedOnly", True)
    delete_after_upload = body.get("deleteAfterUpload", False)

    data = read_csv()

    # Resolve row selection
    selected = set(row_indices)
    if row_range:
        range_indices = _resolve_row_range(row_range, len(data))
        selected.update(range_indices)

    if selected and selected_only:
        videos_with_idx = [(i, data[i]) for i in sorted(selected) if 0 <= i < len(data)]
    else:
        videos_with_idx = [(i, row) for i, row in enumerate(data)]

    # Filter to local videos only
    videos = [(i, v) for i, v in videos_with_idx if v.get("location_status") == "thisPC_local"]

    if not videos:
        return jsonify({"error": "没有可上传的本地视频"}), 400

    # Separate already-uploaded vs pending
    already_uploaded = []
    pending = []
    for i, v in videos:
        vid_path = v.get("path", "").strip()
        marker_ok = vid_path and os.path.isfile(vid_path + ".uploaded")
        csv_ok = v.get("uploaded", "").strip() == "Yes"
        if csv_ok or marker_ok:
            already_uploaded.append((i, v))
        else:
            pending.append((i, v))

    # Build video metadata list
    video_list = []
    for idx, video in pending:
        video_path = video.get("path", "").strip()
        if not video_path or not os.path.isfile(video_path):
            continue
        label = video.get("extra_description", "").strip() or ""
        notes = video.get("extra_description", "").strip()
        file_type = video.get("file_type", "").strip()
        video_list.append({
            "path": video_path,
            "csv_index": idx,
            "label": label,
            "notes": notes,
            "file_type": file_type,
        })

    if not video_list and not already_uploaded:
        return jsonify({"error": "选中的视频文件均不存在"}), 400

    # Paths for upload scripts
    parts_dir = os.path.join(UPLOAD_PKG_DIR, "parts")
    os.makedirs(parts_dir, exist_ok=True)
    cookie_file = os.path.join(UPLOAD_PKG_DIR, "cookie.txt")
    upload_py = os.path.join(UPLOAD_PKG_DIR, "upload.py")

    # Generate the runner .py
    runner_code = _generate_upload_runner(video_list, already_uploaded, upload_py, cookie_file, parts_dir, delete_after_upload=delete_after_upload)
    runner_py_path = os.path.join(ROOT_DIR, "_upload_now.py")
    with open(runner_py_path, "w", encoding="utf-8") as f:
        f.write(runner_code)

    # Generate the .cmd launcher
    python_exe = sys.executable
    cmd_content = f'@echo off\r\n"{python_exe}" "{runner_py_path}"\r\npause\r\n'
    cmd_path = os.path.join(ROOT_DIR, "_upload_now.cmd")
    with open(cmd_path, "w", encoding="ascii") as f:
        f.write(cmd_content)

    return jsonify({
        "ok": True,
        "pending": len(video_list),
        "skippedAlready": len(already_uploaded),
        "skippedNames": [os.path.basename(v.get("path", "")) for _, v in already_uploaded],
        "cmdPath": cmd_path,
        "pyPath": runner_py_path,
        "message": f"共 {len(videos)} 个视频，其中 {len(already_uploaded)} 个已上传跳过，{len(video_list)} 个待上传。"
    })



@bp.route("/api/upload-run-cmd", methods=["POST"])
def upload_run_cmd():
    """Launch _upload_now.cmd in a separate visible terminal window and log output."""
    cmd_path = os.path.join(ROOT_DIR, "_upload_now.cmd")
    if not os.path.isfile(cmd_path):
        return jsonify({"error": "上传脚本不存在，请先生成上传脚本"}), 400

    # Create logs directory
    logs_dir = os.path.join(RUNTIME_DIR, "logs")
    os.makedirs(logs_dir, exist_ok=True)

    # Log file name with timestamp
    log_name = f"upload_cmd_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_path = os.path.join(logs_dir, log_name)

    try:
        # Build a wrapper .cmd that runs _upload_now.py with --log-file
        # so output shows in the cmd window AND is saved to log file
        wrapper_cmd_path = os.path.join(ROOT_DIR, "_upload_now_wrapper.cmd")
        python_exe = sys.executable
        runner_py = os.path.join(ROOT_DIR, "_upload_now.py")

        # _upload_now.py supports --log-file to tee output to both screen and log
        wrapper_content = (
            '@echo off\r\n'
            'chcp 65001 >nul\r\n'
            'echo ============================================================\r\n'
            'echo   Video Upload - publish.example.com\r\n'
            'echo ============================================================\r\n'
            'echo Start: %date% %time%\r\n'
            'echo Log: ' + log_path + '\r\n'
            'echo ============================================================\r\n'
            'echo.\r\n'
            '"{python}" "{runner}" --log-file "{log}"\r\n'
            'echo.\r\n'
            'echo ============================================================\r\n'
            'echo   Upload Finished - %date% %time%\r\n'
            'echo   Log saved to: ' + log_path + '\r\n'
            'echo ============================================================\r\n'
            'pause\r\n'
        ).format(python=python_exe, runner=runner_py, log=log_path)
        # Write with utf-8 BOM so cmd.exe handles CJK paths properly
        with open(wrapper_cmd_path, "w", encoding="utf-8-sig") as f:
            f.write(wrapper_content)

        # Launch cmd window using start (opens a new visible window)
        # start "title" /D cwd "path" — title must be first quoted arg
        proc = subprocess.Popen(
            f'cmd /c start "Video Upload" /D "{ROOT_DIR}" "{wrapper_cmd_path}"',
            shell=True,
        )

        return jsonify({
            "ok": True,
            "pid": proc.pid,
            "logFile": log_path,
            "message": "上传窗口已打开，运行结果将记录到日志文件"
        })

    except Exception as e:
        return jsonify({"error": f"启动上传窗口失败: {str(e)}"}), 500



@bp.route("/api/upload-batch", methods=["POST"])
def upload_batch():
    """Prepare upload list and return a session ID for SSE streaming"""
    body = request.get_json()
    row_indices = body.get("rows", [])
    row_range = body.get("rowRange", "")
    selected_only = body.get("selectedOnly", True)
    delete_after_upload = body.get("deleteAfterUpload", False)

    data = read_csv()

    # Resolve row selection
    selected = set(row_indices)
    if row_range:
        range_indices = _resolve_row_range(row_range, len(data))
        selected.update(range_indices)

    if selected and selected_only:
        videos_with_idx = [(i, data[i]) for i in sorted(selected) if 0 <= i < len(data)]
    else:
        videos_with_idx = [(i, row) for i, row in enumerate(data)]

    # Filter to local videos only
    videos = [(i, v) for i, v in videos_with_idx if v.get("location_status") == "thisPC_local"]

    if not videos:
        return jsonify({"error": "没有可上传的本地视频"}), 400

    # Separate already-uploaded vs pending
    already_uploaded = []
    pending = []
    for i, v in videos:
        vid_path = v.get("path", "").strip()
        marker_ok = vid_path and os.path.isfile(vid_path + ".uploaded")
        csv_ok = v.get("uploaded", "").strip() == "Yes"
        if csv_ok or marker_ok:
            already_uploaded.append((i, v))
        else:
            pending.append((i, v))

    # Build video metadata list
    video_list = []
    for idx, video in pending:
        video_path = video.get("path", "").strip()
        if not video_path or not os.path.isfile(video_path):
            continue
        label = video.get("extra_description", "").strip() or ""
        notes = video.get("extra_description", "").strip()
        video_list.append({
            "path": video_path,
            "csv_index": idx,
            "label": label,
            "notes": notes,
        })

    if not video_list and not already_uploaded:
        return jsonify({"error": "选中的视频文件均不存在"}), 400

    # Generate a session ID for this upload batch
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + str(os.urandom(4).hex())

    # Store session info
    _upload_sessions[session_id] = {
        "videos": video_list,
        "already_uploaded": already_uploaded,
        "status": "ready",
        "delete_after_upload": delete_after_upload,
        "progress": {"done": 0, "total": len(video_list), "current": ""},
        "results": [],
    }

    return jsonify({
        "ok": True,
        "sessionId": session_id,
        "total": len(videos),
        "pending": len(video_list),
        "skippedAlready": len(already_uploaded),
        "skippedNames": [os.path.basename(v.get("path", "")) for _, v in already_uploaded],
        "message": f"共 {len(videos)} 个视频，其中 {len(already_uploaded)} 个已上传跳过，{len(video_list)} 个待上传。"
    })


# ── Upload session storage & SSE ──
_upload_sessions = {}  # session_id -> session info dict
_upload_lock = threading.Lock()



@bp.route("/api/upload-run", methods=["POST"])
def upload_run():
    """Start the upload process for a prepared session (returns SSE stream)"""
    body = request.get_json()
    session_id = body.get("sessionId", "")

    if session_id not in _upload_sessions:
        return jsonify({"error": "无效的上传会话，请重新生成"}), 400

    session = _upload_sessions[session_id]
    if session["status"] == "running":
        return jsonify({"error": "上传已在运行中"}), 409

    video_list = session["videos"]
    if not video_list:
        return jsonify({"error": "没有待上传的视频"}), 400

    # Paths
    parts_dir = os.path.join(UPLOAD_PKG_DIR, "parts")
    os.makedirs(parts_dir, exist_ok=True)
    cookie_file = os.path.join(UPLOAD_PKG_DIR, "cookie.txt")
    upload_py = os.path.join(UPLOAD_PKG_DIR, "upload.py")

    # Create logs directory
    logs_dir = os.path.join(RUNTIME_DIR, "logs")
    os.makedirs(logs_dir, exist_ok=True)

    # Mark as running
    with _upload_lock:
        session["status"] = "running"


@bp.route("/api/upload-status", methods=["GET"])
def upload_status():
    """Get status of an upload session"""
    session_id = request.args.get("sessionId", "")
    if session_id not in _upload_sessions:
        return jsonify({"error": "会话不存在"}), 404
    session = _upload_sessions[session_id]
    return jsonify({
        "status": session["status"],
        "progress": session["progress"],
        "results": session.get("results", {}),
    })



@bp.route("/api/upload-cancel", methods=["POST"])
def upload_cancel():
    """Cancel a running upload session"""
    body = request.get_json()
    session_id = body.get("sessionId", "")
    if session_id not in _upload_sessions:
        return jsonify({"error": "会话不存在"}), 404
    with _upload_lock:
        session = _upload_sessions[session_id]
        session["status"] = "cancelled"
    return jsonify({"ok": True})
