from flask import Blueprint, jsonify, request
from config import *
import os
import sys
import json
import subprocess
import logging

from config import USE_PG
if USE_PG:
    from models.pg_store import read_csv
else:
    from models.csv_store import read_csv
from services.upload_service import _is_hmd_session
logger = logging.getLogger(__name__)

bp = Blueprint('auto_upload', __name__)


@bp.route("/api/auto-upload-start", methods=["POST"])
def auto_upload_start():
    """启动自动上传（在后台 subprocess 中运行 auto_upload.py）
    支持 paths 列表（推荐）或 row_indices 数组（批量上传）"""
    body = request.get_json(silent=True) or {}
    paths = body.get("paths")
    if paths:
        # 通过 path 查找对应的行索引
        rows = read_csv()
        row_indices = []
        for path in paths:
            norm_target = os.path.normpath(path).replace("\\", "/")
            found = False
            for i, r in enumerate(rows):
                row_path = os.path.normpath(r.get("path", "")).replace("\\", "/")
                if row_path == norm_target or row_path.lower() == norm_target.lower():
                    row_indices.append(i)
                    found = True
                    break
            if not found:
                return jsonify({"error": f"未找到路径: {path}"}), 400
    else:
        row_indices = body.get("row_indices") or ([body.get("row_index")] if body.get("row_index") is not None else None)
    delete_after_upload = body.get("deleteAfterUpload", False)
    keep_thumbs = body.get("keepThumbs", False)

    if not row_indices:
        return jsonify({"error": "缺少 paths 或 row_indices 或 row_index 参数"}), 400

    rows = read_csv()
    skipped = []
    video_names = []

    for idx in row_indices:
        if idx < 0 or idx >= len(rows):
            return jsonify({"error": f"行索引 {idx} 超出范围（共 {len(rows)} 行）"}), 400
        if rows[idx].get("uploaded", "").strip() == "Yes":
            skipped.append(idx)
            continue
        video_path = rows[idx].get("path", "").strip()
        if not video_path:
            return jsonify({"error": f"行 {idx} 视频路径为空"}), 400
        is_hmd = _is_hmd_session(video_path)
        if is_hmd:
            if not os.path.isdir(video_path):
                return jsonify({"error": f"行 {idx} HMD 目录不存在: {video_path}"}), 400
        else:
            if not os.path.isfile(video_path):
                return jsonify({"error": f"行 {idx} 视频文件不存在: {video_path}"}), 400
        video_names.append(os.path.basename(video_path))

    # 过滤掉已上传的
    effective_indices = [i for i in row_indices if i not in skipped]
    if not effective_indices:
        return jsonify({"error": "所有视频均已标记为上传完成"}), 400

    # ★ 校验关键上传参数是否已填写
    missing = []
    for idx in effective_indices:
        r = rows[idx]
        cid = (r.get("recorder_id") or "").strip()
        tid = (r.get("task_id") or "").strip()
        eid = (r.get("env_id") or "").strip()
        missing_fields = []
        if not cid:
            missing_fields.append("录制员ID")
        if not tid:
            missing_fields.append("Task ID")
        if not eid:
            missing_fields.append("环境ID")
        if missing_fields:
            name = os.path.basename(r.get("path", "").strip())
            missing.append(f"行{idx + 1}「{name}」缺少: {', '.join(missing_fields)}")
    if missing:
        return jsonify({
            "error": "以下视频的上传参数不完整，请先填写后重试",
            "details": missing,
            "hint": "可双击对应行，在 recorder_id / task_id / env_id 列中填写"
        }), 400

    auto_upload_py = os.path.join(SRC_DIR, "auto_upload.py")

    # 启动 subprocess（不等待完成）
    try:
        cmd_args = [sys.executable, auto_upload_py, "--pipeline", "--row-index"] + \
                   [str(idx) for idx in effective_indices]
        if delete_after_upload:
            cmd_args.append("--delete-local")
        if keep_thumbs:
            cmd_args.append("--keep-thumbs")
        proc = subprocess.Popen(
            cmd_args,
            cwd=SRC_DIR,
        )
        # 把 PID 写入文件，方便后续查询状态
        pid_file = os.path.join(RUNTIME_DIR, "auto_upload.pid")
        with open(pid_file, "w") as f:
            f.write(str(proc.pid))

        return jsonify({
            "ok": True,
            "pid": proc.pid,
            "count": len(effective_indices),
            "video_names": video_names,
            "skipped": skipped,
            "message": f"已启动批量上传: {len(effective_indices)} 个视频（跳过 {len(skipped)} 个已上传）",
        })

    except Exception as e:
        return jsonify({"error": f"启动上传进程失败: {str(e)}"}), 500



@bp.route("/api/auto-upload-status", methods=["GET"])
def auto_upload_status():
    """查询当前自动上传进程状态"""
    pid_file = os.path.join(RUNTIME_DIR, "auto_upload.pid")
    if not os.path.isfile(pid_file):
        return jsonify({"running": False, "status": "idle"})

    try:
        with open(pid_file, "r") as f:
            pid = int(f.read().strip())
    except Exception:
        return jsonify({"running": False, "status": "idle"})

    # 检查进程是否存活
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x0400, False, pid)  # PROCESS_QUERY_INFORMATION
        if handle:
            kernel32.CloseHandle(handle)
            return jsonify({"running": True, "pid": pid, "status": "running"})
    except Exception:
        pass

    # 进程已退出，清理 pid 文件
    try:
        os.remove(pid_file)
    except Exception:
        pass
    return jsonify({"running": False, "status": "completed"})



@bp.route("/api/auto-upload-progress", methods=["GET"])
def auto_upload_progress():
    """读取 auto_upload.py 写入的进度 JSON 文件"""
    progress_file = os.path.join(RUNTIME_DIR, "data", "auto_upload_progress.json")
    # 检查进程状态
    pid_file = os.path.join(RUNTIME_DIR, "auto_upload.pid")
    running = False
    if os.path.isfile(pid_file):
        try:
            with open(pid_file, "r") as f:
                pid = int(f.read().strip())
            import ctypes as _ct
            kernel32 = _ct.windll.kernel32
            handle = kernel32.OpenProcess(0x0400, False, pid)
            if handle:
                running = True
                kernel32.CloseHandle(handle)
        except Exception:
            pass
    if os.path.isfile(progress_file):
        try:
            with open(progress_file, "r", encoding="utf-8") as f:
                progress = json.load(f)
            progress["running"] = running
            return jsonify(progress)
        except Exception:
            pass
    return jsonify({"status": "unknown", "running": running, "message": ""})
