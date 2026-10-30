import csv
import io
import json
import os
import queue
import re
import requests
import subprocess
import sys
import threading
import time
from datetime import datetime
from flask import Flask, Response, jsonify, request, send_file, make_response, stream_with_context

app = Flask(__name__)

# 兼容 PyInstaller 打包：sys._MEIPASS 是临时解压目录，exe 实际路径用 sys.argv[0]
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "video_manager.csv")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
ARCHIVE_DIR = os.path.join(BASE_DIR, "archive")
UPLOAD_PKG_DIR = os.path.join(BASE_DIR, "vendor-upload-pkg")

# Default fieldnames with new fields for local/history management
DEFAULT_FIELDNAMES = [
    "path", "location_status", "scan_date", "original_history_date",
    "work_content_cn", "work_content_en", "category", "recorder",
    "upload_feasibility", "uploaded", "extra_description", "score", "duration"
]

# Default upload config from .env
UPLOAD_CONFIG = {
    "country": "CN",
    "region": "Shanghai",
    "recorder": "lingxu zhou",
    "category": "industrial_manufacturing",
    "subcategory": "mfg_other",
}


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def get_fieldnames():
    config = load_config()
    return config.get("fieldnames", DEFAULT_FIELDNAMES)


def get_fieldnames_cached():
    """Get fieldnames, cached at request time so config changes take effect."""
    return get_fieldnames()


def _get_video_duration(filepath):
    """Get video duration as formatted string HH:MM:SS using ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", filepath],
            capture_output=True, text=True, timeout=15,
        )
        seconds = float(result.stdout.strip())
        if seconds <= 0:
            return ""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h}:{m:02d}:{s:02d}" if h > 0 else f"{m}:{s:02d}"
    except Exception:
        return ""


def _get_file_date(filepath):
    """Get file creation date as YYYY-MM-DD string."""
    try:
        ts = os.path.getctime(filepath)
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")


def read_csv():
    if not os.path.exists(CSV_PATH):
        return []
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return [row for row in reader]


def write_csv(rows):
    import shutil as _shutil
    fieldnames = get_fieldnames()
    # 写入前自动备份（仅保留最近 10 个备份）
    try:
        backup_dir = os.path.join(BASE_DIR, "csv_backups")
        os.makedirs(backup_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"video_manager_{ts}.csv")
        if os.path.exists(CSV_PATH) and os.path.getsize(CSV_PATH) > 0:
            _shutil.copy2(CSV_PATH, backup_path)
            backups = sorted(os.listdir(backup_dir))
            while len(backups) > 10:
                os.remove(os.path.join(backup_dir, backups[0]))
                backups.pop(0)
    except Exception:
        pass  # 备份失败不阻塞写入
    # 原子写入：先写临时文件，再 rename
    tmp_path = CSV_PATH + ".tmp"
    with open(tmp_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp_path, CSV_PATH)  # 原子替换


@app.route("/")
def index():
    return send_file("templates/index.html")


@app.route("/api/config", methods=["GET", "POST"])
def handle_config():
    if request.method == "GET":
        return jsonify(load_config())
    config = request.get_json()
    existing = load_config()
    # Merge: only update keys that are provided (partial save)
    for key in ["scanDirectory", "fieldnames", "columnLabels", "columnTypes", "columnVisibility",
                "columnWidths", "columnOrder", "sortColumn", "sortDirection"]:
        if key in config:
            existing[key] = config[key]
    # 同步 scanDirectory → deviceMonitor.destinationBase
    if "scanDirectory" in config:
        if "deviceMonitor" not in existing:
            existing["deviceMonitor"] = {}
        existing["deviceMonitor"]["destinationBase"] = config["scanDirectory"]
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    return jsonify({"ok": True})


@app.route("/api/data")
def get_data():
    return jsonify(read_csv())


@app.route("/api/scan", methods=["POST"])
def scan_directory():
    data = request.get_json()
    directory = data.get("directory", "").strip()
    if not directory or not os.path.isdir(directory):
        return jsonify({"error": "目录不存在"}), 400

    mp4_files = []
    for root, _dirs, files in os.walk(directory):
        for fname in files:
            if fname.lower().endswith(".mp4"):
                mp4_files.append(os.path.join(root, fname))

    mp4_set = set(mp4_files)
    existing = read_csv()
    existing_map = {row["path"]: row for row in existing}

    # Update existing rows: check if file exists locally or not, keep scan_date unchanged
    # Also fill in duration for existing local videos if it's empty
    for path, row in existing_map.items():
        if os.path.isfile(path):
            row["location_status"] = "local"
            if not row.get("duration", "").strip():
                row["duration"] = _get_video_duration(path)
        else:
            row["location_status"] = "history"
        # Do NOT update scan_date for existing rows

    # Add new files from scanned directory (use file creation date, don't overwrite existing records)
    for mp4_path in sorted(mp4_files):
        if mp4_path not in existing_map:
            row = {fn: "" for fn in DEFAULT_FIELDNAMES}
            row["path"] = mp4_path
            row["location_status"] = "local"
            row["scan_date"] = _get_file_date(mp4_path)
            row["uploaded"] = "No"
            row["duration"] = _get_video_duration(mp4_path)
            existing_map[mp4_path] = row

    # Sort by scan_date asc, then path
    result = sorted(existing_map.values(), key=lambda r: (r.get("scan_date", ""), r.get("path", "")))

    write_csv(result)
    return jsonify({"count": len(result), "data": result})


@app.route("/api/merge-history", methods=["POST"])
def merge_history():
    """Merge all historical CSV files into archive/video_manager_history.csv"""
    os.makedirs(ARCHIVE_DIR, exist_ok=True)

    all_history_files = [
        "video_manager0517-1.csv", "video_manager0517-2.csv", "video_manager0517-3.csv",
        "video_manager0518-1.csv", "video_manager0519-1.csv", "video_manager0520.csv",
        "video_manager-bak.csv", "video_manager - 副本.csv"
    ]

    merged = {}  # path -> row, keep latest by scan_date

    for hist_file in all_history_files:
        hist_path = os.path.join(BASE_DIR, hist_file)
        if not os.path.exists(hist_path):
            continue

        hist_date = parse_history_date_from_filename(hist_file)

        try:
            with open(hist_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    path = row.get("path", "").strip()
                    if not path:
                        continue

                    # Build full row with all fields
                    full_row = {fn: "" for fn in DEFAULT_FIELDNAMES}
                    for key, val in row.items():
                        if key in DEFAULT_FIELDNAMES:
                            full_row[key] = val

                    # Determine location_status based on file existence
                    if os.path.isfile(path):
                        full_row["location_status"] = "local"
                    else:
                        full_row["location_status"] = "history"

                    # Set dates
                    full_row["scan_date"] = hist_date
                    if full_row["location_status"] == "history":
                        full_row["original_history_date"] = hist_date

                    # Deduplicate: keep record with latest scan_date
                    if path in merged:
                        existing_date = merged[path].get("scan_date", "")
                        if hist_date > existing_date:
                            merged[path] = full_row
                    else:
                        merged[path] = full_row
        except Exception as e:
            print(f"Error reading {hist_file}: {e}")
            continue

    # Write merged history
    history_path = os.path.join(ARCHIVE_DIR, "video_manager_history.csv")
    with open(history_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=DEFAULT_FIELDNAMES)
        writer.writeheader()
        for row in sorted(merged.values(), key=lambda r: (r.get("scan_date", ""), r.get("path", ""))):
            writer.writerow(row)

    # Move historical files to archive
    for hist_file in all_history_files:
        src = os.path.join(BASE_DIR, hist_file)
        dst = os.path.join(ARCHIVE_DIR, hist_file)
        if os.path.exists(src) and not os.path.exists(dst):
            os.rename(src, dst)

    return jsonify({
        "ok": True,
        "merged_count": len(merged),
        "history_file": history_path
    })


def parse_history_date_from_filename(filename):
    """Parse date from historical CSV filename like video_manager0517-1.csv -> 2026-05-17"""
    match = re.search(r'(\d{2})(\d{2})', filename)
    if match:
        month, day = match.groups()
        year = datetime.now().year
        try:
            return datetime(year, int(month), int(day)).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return datetime.now().strftime("%Y-%m-%d")


@app.route("/api/delete", methods=["POST"])
def delete_records():
    """Delete records by indices from video_manager.csv. Auto-backup before write."""
    body = request.get_json()
    indices = body.get("indices", [])
    if not indices or not isinstance(indices, list):
        return jsonify({"error": "请提供要删除的行索引列表"}), 400

    rows = read_csv()
    removed = []
    kept = []
    for i, row in enumerate(rows):
        if i in indices:
            removed.append({"index": i, "path": row.get("path", "")})
        else:
            kept.append(row)

    if not removed:
        return jsonify({"error": "未找到可删除的记录"}), 404

    write_csv(kept)
    return jsonify({
        "ok": True,
        "deleted": len(removed),
        "remaining": len(kept),
        "deleted_paths": [r["path"] for r in removed]
    })


@app.route("/api/save", methods=["POST"])
def save_data():
    rows = request.get_json()
    if not isinstance(rows, list):
        return jsonify({"error": "Invalid data format", "type": str(type(rows))}), 400
    fieldnames = get_fieldnames()
    cleaned = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        cleaned_row = {}
        for fn in fieldnames:
            val = row.get(fn, "") if isinstance(row, dict) else ""
            cleaned_row[fn] = str(val).strip()
        cleaned.append(cleaned_row)
    write_csv(cleaned)
    return jsonify({"ok": True, "count": len(cleaned)})


@app.route("/api/video")
def serve_video():
    path = request.args.get("path", "")
    if not path or not os.path.isfile(path):
        return "File not found", 404

    file_size = os.path.getsize(path)
    range_header = request.headers.get("Range")

    if range_header:
        # Parse Range header: bytes=start-end
        range_spec = range_header.replace("bytes=", "")
        parts = range_spec.split("-")
        start = int(parts[0])
        end = int(parts[1]) if parts[1] else file_size - 1

        if start >= file_size:
            return "Range not satisfiable", 416

        end = min(end, file_size - 1)
        length = end - start + 1

        with open(path, "rb") as f:
            f.seek(start)
            data = f.read(length)

        resp = Response(data, 206, mimetype="video/mp4")
        resp.headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        resp.headers["Accept-Ranges"] = "bytes"
        resp.headers["Content-Length"] = length
        return resp

    return send_file(path, mimetype="video/mp4")


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


@app.route("/api/export", methods=["POST"])
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


@app.route("/api/upload-generate", methods=["POST"])
def upload_generate():
    """Generate _upload_now.py + _upload_now.cmd scripts to disk."""
    body = request.get_json()
    row_indices = body.get("rows", [])
    row_range = body.get("rowRange", "")
    selected_only = body.get("selectedOnly", True)

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
    videos = [(i, v) for i, v in videos_with_idx if v.get("location_status") == "local"]

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
        label = video.get("work_content_en", "").strip() or video.get("work_content_cn", "").strip()
        notes = video.get("extra_description", "").strip()
        video_list.append({
            "path": video_path,
            "csv_index": idx,
            "label": label,
            "notes": notes,
        })

    if not video_list and not already_uploaded:
        return jsonify({"error": "选中的视频文件均不存在"}), 400

    # Paths for upload scripts
    parts_dir = os.path.join(UPLOAD_PKG_DIR, "parts")
    os.makedirs(parts_dir, exist_ok=True)
    cookie_file = os.path.join(UPLOAD_PKG_DIR, "cookie.txt")
    upload_py = os.path.join(UPLOAD_PKG_DIR, "upload.py")

    # Generate the runner .py
    runner_code = _generate_upload_runner(video_list, already_uploaded, upload_py, cookie_file, parts_dir)
    runner_py_path = os.path.join(BASE_DIR, "_upload_now.py")
    with open(runner_py_path, "w", encoding="utf-8") as f:
        f.write(runner_code)

    # Generate the .cmd launcher
    python_exe = sys.executable
    cmd_content = f'@echo off\r\n"{python_exe}" "{runner_py_path}"\r\npause\r\n'
    cmd_path = os.path.join(BASE_DIR, "_upload_now.cmd")
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


@app.route("/api/upload-run-cmd", methods=["POST"])
def upload_run_cmd():
    """Launch _upload_now.cmd in a separate visible terminal window and log output."""
    cmd_path = os.path.join(BASE_DIR, "_upload_now.cmd")
    if not os.path.isfile(cmd_path):
        return jsonify({"error": "上传脚本不存在，请先生成上传脚本"}), 400

    # Create logs directory
    logs_dir = os.path.join(BASE_DIR, "logs")
    os.makedirs(logs_dir, exist_ok=True)

    # Log file name with timestamp
    log_name = f"upload_cmd_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_path = os.path.join(logs_dir, log_name)

    try:
        # Build a wrapper .cmd that runs _upload_now.py with --log-file
        # so output shows in the cmd window AND is saved to log file
        wrapper_cmd_path = os.path.join(BASE_DIR, "_upload_now_wrapper.cmd")
        python_exe = sys.executable
        runner_py = os.path.join(BASE_DIR, "_upload_now.py")

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
            f'cmd /c start "Video Upload" /D "{BASE_DIR}" "{wrapper_cmd_path}"',
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


@app.route("/api/upload-batch", methods=["POST"])
def upload_batch():
    """Prepare upload list and return a session ID for SSE streaming"""
    body = request.get_json()
    row_indices = body.get("rows", [])
    row_range = body.get("rowRange", "")
    selected_only = body.get("selectedOnly", True)

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
    videos = [(i, v) for i, v in videos_with_idx if v.get("location_status") == "local"]

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
        label = video.get("work_content_en", "").strip() or video.get("work_content_cn", "").strip()
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


@app.route("/api/upload-run", methods=["POST"])
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
    logs_dir = os.path.join(BASE_DIR, "logs")
    os.makedirs(logs_dir, exist_ok=True)

    # Mark as running
    with _upload_lock:
        session["status"] = "running"

    def generate():
        """SSE generator: run upload.py for each video and yield progress events."""
        import shutil as _shutil
        
        log_path = os.path.join(logs_dir, f"upload_{session_id}.log")
        log_fh = open(log_path, "w", encoding="utf-8")
        
        def emit(event_type, data):
            """Send SSE event."""
            payload = json.dumps(data, ensure_ascii=False)
            log_fh.write(f"[{datetime.now().strftime('%H:%M:%S')}] SSE:{event_type}: {payload}\n")
            log_fh.flush()
            return f"event: {event_type}\ndata: {payload}\n\n"

        try:
            yield emit("start", {"sessionId": session_id, "total": len(video_list)})
            log_fh.write(f"[{datetime.now().strftime('%H:%M:%S')}] === Upload session {session_id} started ===\n")
            log_fh.write(f"[{datetime.now().strftime('%H:%M:%S')}] {len(video_list)} videos to upload\n")
            log_fh.flush()

            success = 0
            skipped = 0
            failed = 0

            for idx, video in enumerate(video_list, 1):
                video_path = video["path"]
                csv_index = video["csv_index"]
                basename = os.path.basename(video_path)

                with _upload_lock:
                    session["progress"]["current"] = basename
                    session["progress"]["done"] = idx - 1

                yield emit("progress", {
                    "index": idx,
                    "total": len(video_list),
                    "file": basename,
                    "path": video_path,
                    "status": "uploading",
                })

                # Check file exists
                if not os.path.isfile(video_path):
                    yield emit("progress", {
                        "index": idx,
                        "total": len(video_list),
                        "file": basename,
                        "path": video_path,
                        "status": "error",
                        "message": "文件不存在",
                    })
                    failed += 1
                    continue

                # Check marker
                marker = video_path + ".uploaded"
                if os.path.isfile(marker):
                    yield emit("progress", {
                        "index": idx,
                        "total": len(video_list),
                        "file": basename,
                        "path": video_path,
                        "status": "skipped",
                        "message": "本地标记已上传",
                    })
                    # Sync CSV
                    rows = read_csv()
                    if csv_index < len(rows) and rows[csv_index].get("uploaded", "").strip() != "Yes":
                        rows[csv_index]["uploaded"] = "Yes"
                        rows[csv_index]["location_status"] = "local"
                        write_csv(rows)
                    skipped += 1
                    continue

                # Check CSV uploaded field
                rows = read_csv()
                if csv_index < len(rows) and rows[csv_index].get("uploaded", "").strip() == "Yes":
                    yield emit("progress", {
                        "index": idx,
                        "total": len(video_list),
                        "file": basename,
                        "path": video_path,
                        "status": "skipped",
                        "message": "CSV已标记上传",
                    })
                    try:
                        with open(marker, "w") as f:
                            f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    except Exception:
                        pass
                    skipped += 1
                    continue

                # Build upload.py command
                cmd = [
                    sys.executable, upload_py,
                    "--file", video_path,
                    "--country", UPLOAD_CONFIG["country"],
                    "--region", UPLOAD_CONFIG["region"],
                    "--recorder", UPLOAD_CONFIG["recorder"],
                    "--category", UPLOAD_CONFIG["category"],
                    "--subcategory", UPLOAD_CONFIG["subcategory"],
                    "--cookie-file", cookie_file,
                    "--parts-dir", parts_dir,
                ]
                if video.get("label"):
                    cmd += ["--label", video["label"]]
                if video.get("notes"):
                    cmd += ["--notes", video["notes"]]

                log_fh.write(f"[{datetime.now().strftime('%H:%M:%S')}] [{idx}/{len(video_list)}] {basename}\n")
                log_fh.write(f"[{datetime.now().strftime('%H:%M:%S')}] CMD: {' '.join(cmd)}\n")
                log_fh.flush()

                yield emit("log", {
                    "index": idx,
                    "file": basename,
                    "line": f"[{idx}/{len(video_list)}] 开始上传: {basename}",
                })

                t0 = time.time()
                try:
                    proc = subprocess.Popen(
                        cmd,
                        cwd=os.path.dirname(upload_py),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        bufsize=1,
                    )
                    
                    # Stream subprocess output line by line
                    for line in proc.stdout:
                        line = line.rstrip()
                        if line:
                            log_fh.write(f"[{datetime.now().strftime('%H:%M:%S')}] {line}\n")
                            log_fh.flush()
                            yield emit("log", {
                                "index": idx,
                                "file": basename,
                                "line": line,
                            })
                    
                    proc.wait()
                    elapsed = time.time() - t0

                    if proc.returncode == 0:
                        # Mark as uploaded in CSV
                        rows = read_csv()
                        if csv_index < len(rows):
                            rows[csv_index]["uploaded"] = "Yes"
                            rows[csv_index]["location_status"] = "local"
                            write_csv(rows)
                        # Write marker file
                        try:
                            with open(marker, "w") as f:
                                f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                        except Exception:
                            pass

                        yield emit("progress", {
                            "index": idx,
                            "total": len(video_list),
                            "file": basename,
                            "path": video_path,
                            "status": "done",
                            "message": f"上传成功 (耗时 {elapsed:.0f}s)",
                        })
                        success += 1
                    else:
                        yield emit("progress", {
                            "index": idx,
                            "total": len(video_list),
                            "file": basename,
                            "path": video_path,
                            "status": "error",
                            "message": f"上传失败 (exit code: {proc.returncode}, 耗时 {elapsed:.0f}s)",
                        })
                        failed += 1

                except Exception as e:
                    elapsed = time.time() - t0
                    log_fh.write(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: {e}\n")
                    log_fh.flush()
                    yield emit("progress", {
                        "index": idx,
                        "total": len(video_list),
                        "file": basename,
                        "path": video_path,
                        "status": "error",
                        "message": f"进程错误: {str(e)}",
                    })
                    failed += 1

                with _upload_lock:
                    session["progress"]["done"] = idx

            # Done
            with _upload_lock:
                session["status"] = "done"
                session["results"] = {"success": success, "skipped": skipped, "failed": failed}

            log_fh.write(f"[{datetime.now().strftime('%H:%M:%S')}] === Upload session {session_id} completed: success={success} skipped={skipped} failed={failed} ===\n")
            log_fh.flush()

            yield emit("complete", {
                "success": success,
                "skipped": skipped,
                "failed": failed,
                "total": len(video_list),
                "logFile": log_path,
            })

        except GeneratorExit:
            with _upload_lock:
                session["status"] = "cancelled"
            log_fh.write(f"[{datetime.now().strftime('%H:%M:%S')}] === Upload session {session_id} cancelled ===\n")
        except Exception as e:
            with _upload_lock:
                session["status"] = "error"
            log_fh.write(f"[{datetime.now().strftime('%H:%M:%S')}] FATAL: {e}\n")
            yield emit("error", {"message": str(e)})
        finally:
            log_fh.close()

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/api/upload-status", methods=["GET"])
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


@app.route("/api/upload-cancel", methods=["POST"])
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


def _escape_py_str(s):
    """Escape string for use in Python code. Returns repr() or sanitised version."""
    return repr(s)


def _generate_upload_runner(video_list, already_uploaded, upload_py, cookie_file, parts_dir):
    """Generate self-contained Python upload runner script as a string."""
    video_data = []
    for v in video_list:
        video_data.append({
            "path": v["path"],
            "csv_index": v["csv_index"],
            "label": v["label"],
            "notes": v["notes"],
        })

    import json as _json
    videos_json = _json.dumps(video_data, ensure_ascii=False, indent=4)

    already_json = _json.dumps(
        [{"name": os.path.basename(v.get("path", "")), "csv_index": idx}
         for idx, v in already_uploaded],
        ensure_ascii=False, indent=4
    ) if already_uploaded else "[]"

    upload_cfg_json = _json.dumps(UPLOAD_CONFIG, ensure_ascii=False)

    runner_code = f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auto-generated upload runner — do NOT edit manually.
Double-click _upload_now.cmd to run in a visible terminal window.
"""
import csv, json, os, subprocess, sys, time, shutil
from datetime import datetime
from pathlib import Path

# ── Config (auto-generated) ──
UPLOAD_PY = {repr(upload_py)}
COOKIE_FILE = {repr(cookie_file)}
PARTS_DIR = {repr(parts_dir)}
CSV_PATH = {repr(CSV_PATH)}
UPLOAD_CFG = {upload_cfg_json}
VIDEOS = {videos_json}
ALREADY_UPLOADED = {already_json}

# ── Log file support ──
LOG_FILE = None
def tee_print(*args, **kwargs):
    """Print to both stdout and log file (if set)."""
    msg = " ".join(str(a) for a in args)
    # flush stdout first so real-time output works
    print(msg, **kwargs, flush=True)
    if LOG_FILE:
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as lf:
                lf.write(msg + "\\n")
        except Exception:
            pass

# Parse optional --log-file argument
_args = sys.argv[1:]
if len(_args) >= 2 and _args[0] == "--log-file":
    LOG_FILE = _args[1]
    tee_print = tee_print  # already defined


def _get_fieldnames():
    """Dynamic: read fieldnames from existing CSV to avoid dropping columns."""
    if os.path.exists(CSV_PATH):
        try:
            with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                if reader.fieldnames:
                    return list(reader.fieldnames)
        except Exception:
            pass
    # Fallback
    return ['path', 'location_status', 'scan_date', 'original_history_date',
            'work_content_cn', 'work_content_en', 'category', 'recorder',
            'upload_feasibility', 'uploaded', 'extra_description', 'score', 'duration']


def read_csv():
    if not os.path.exists(CSV_PATH):
        return []
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return [row for row in reader]


def write_csv(rows):
    # Backup before write
    try:
        backup_dir = os.path.join(os.path.dirname(CSV_PATH), "csv_backups")
        os.makedirs(backup_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, "video_manager_" + ts + ".csv")
        if os.path.exists(CSV_PATH) and os.path.getsize(CSV_PATH) > 0:
            shutil.copy2(CSV_PATH, backup_path)
    except Exception:
        pass
    fieldnames = _get_fieldnames()
    with open(CSV_PATH, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def mark_uploaded(csv_index):
    """Update video_manager.csv: set uploaded=Yes for the given row index."""
    rows = read_csv()
    if 0 <= csv_index < len(rows):
        rows[csv_index]["uploaded"] = "Yes"
        rows[csv_index]["location_status"] = "local"
        write_csv(rows)
        return True
    return False


def check_file(video_path):
    """Check if the video file still exists on disk."""
    return os.path.isfile(video_path)


def marker_path(video_path):
    """Return the marker file path for a given video (alongside the video file)."""
    return video_path + ".uploaded"


def has_marker(video_path):
    """Check if the marker file exists, indicating the video was already uploaded."""
    return os.path.isfile(marker_path(video_path))


def write_marker(video_path):
    """Write a marker file to record that this video has been uploaded."""
    with open(marker_path(video_path), "w") as f:
        f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


tee_print("=" * 65)
tee_print("  视频批量上传工具")
tee_print("  publish.example.com Vendor Upload")
tee_print("=" * 65)

if ALREADY_UPLOADED:
    tee_print(f"\\n  [跳过] 以下已标记上传完成:")
    for v in ALREADY_UPLOADED:
        tee_print(f"    - {{v['name']}} (行 #{{v['csv_index']+1}})")

tee_print(f"\\n  [待上传] 共 {{len(VIDEOS)}} 个视频")
tee_print("=" * 65)

success = 0
skipped = 0
failed = 0

for idx, video in enumerate(VIDEOS, 1):
    video_path = video["path"]
    csv_index = video["csv_index"]
    basename = os.path.basename(video_path)

    tee_print(f"\\n\\n>>> [{{idx}}/{{len(VIDEOS)}}] {{basename}}")
    tee_print(f"    路径: {{video_path}}")

    # Check if file exists
    if not check_file(video_path):
        tee_print(f"    ✗ 文件不存在，跳过")
        failed += 1
        continue

    # Dedup ①: check local marker file (written after successful upload)
    if has_marker(video_path):
        tee_print(f"    ↷ 本地标记已上传，跳过")
        # Also sync CSV state
        current_rows = read_csv()
        if csv_index < len(current_rows) and current_rows[csv_index].get("uploaded", "").strip() != "Yes":
            mark_uploaded(csv_index)
        skipped += 1
        continue

    # Dedup ②: check CSV uploaded field
    current_rows = read_csv()
    if csv_index < len(current_rows) and current_rows[csv_index].get("uploaded", "").strip() == "Yes":
        tee_print(f"    ↷ CSV已标记上传，跳过")
        # Also write marker to prevent future re-checks
        try:
            write_marker(video_path)
        except Exception:
            pass
        skipped += 1
        continue

    # Build upload.py command
    cmd = [
        sys.executable, UPLOAD_PY,
        "--file", video_path,
        "--country", UPLOAD_CFG["country"],
        "--region", UPLOAD_CFG["region"],
        "--recorder", UPLOAD_CFG["recorder"],
        "--category", UPLOAD_CFG["category"],
        "--subcategory", UPLOAD_CFG["subcategory"],
        "--cookie-file", COOKIE_FILE,
        "--parts-dir", PARTS_DIR,
    ]
    if video.get("label"):
        cmd += ["--label", video["label"]]
    if video.get("notes"):
        cmd += ["--notes", video["notes"]]

    # Run upload.py in its own working directory
    # Capture output line-by-line so it shows on screen AND goes to log
    tee_print(f"    开始上传...")
    t0 = time.time()
    proc = subprocess.Popen(
        cmd,
        cwd=os.path.dirname(UPLOAD_PY),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    for line in proc.stdout:
        line = line.rstrip("\\n\\r")
        if line:
            tee_print(line)
    proc.wait()
    result_rc = proc.returncode

    elapsed = time.time() - t0
    if result_rc == 0:
        mark_uploaded(csv_index)
        write_marker(video_path)
        tee_print(f"    ✓ 上传成功！(耗时 {{elapsed:.0f}}s)")
        success += 1
    else:
        tee_print(f"    ✗ 上传失败 (exit code: {{result_rc}}, 耗时 {{elapsed:.0f}}s)")
        failed += 1

tee_print()
tee_print("=" * 65)
tee_print(f"  完成！成功: {{success}}  跳过: {{skipped}}  失败: {{failed}}")
tee_print("=" * 65)
tee_print()
input("按 Enter 键退出...")
'''

    return runner_code


@app.route("/api/upload-config", methods=["GET"])
def get_upload_config():
    """Return current upload configuration"""
    return jsonify(UPLOAD_CONFIG)


@app.route("/api/translate", methods=["POST"])
def translate_text():
    """Translate Chinese text to English using MiniMax M2.7 (Token Plan, Anthropic-compatible API)"""
    data = request.get_json()
    text = (data.get("text", "") or "").strip()
    if not text:
        return jsonify({"error": "文本为空"}), 400

    config = load_config()
    translate_cfg = config.get("translate", {})
    api_key = translate_cfg.get("apiKey", "")
    model = translate_cfg.get("model", "MiniMax-M2.7")
    api_base = translate_cfg.get("apiBase", "https://api.minimaxi.com/anthropic/v1/messages")

    if not api_key:
        return jsonify({"error": "未配置 API Key"}), 500

    system_prompt = (
        "You are a professional translator. Translate the following Chinese text into English. "
        "Rules:\n"
        "- Output ONLY the English translation, nothing else.\n"
        "- Do NOT add explanations, notes, quotes, or any extra text.\n"
        "- Do NOT include the original Chinese text.\n"
        "- Do NOT include any markdown formatting, punctuation wrappers, or commentary.\n"
        "- Just output the pure English translation as-is."
    )

    try:
        resp = requests.post(
            api_base,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 1024,
                "system": system_prompt,
                "messages": [
                    {"role": "user", "content": text},
                ],
            },
            timeout=60,
        )
        resp.raise_for_status()
        result = resp.json()

        # Anthropic Messages API response: content is an array of blocks
        translated = ""
        if "content" in result and isinstance(result["content"], list):
            for block in result["content"]:
                if block.get("type") == "text":
                    translated += block.get("text", "")

        translated = translated.strip()

        if not translated:
            return jsonify({"error": "翻译返回为空", "raw": result}), 500

        return jsonify({"translated": translated})

    except requests.exceptions.Timeout:
        return jsonify({"error": "翻译请求超时"}), 504
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"翻译请求失败: {str(e)}"}), 500
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"error": f"解析翻译结果失败: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
