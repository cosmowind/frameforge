"""misc_routes — index, favicon, statistics, estimate, disk-space, system utilities."""

import datetime
import json
import os
import shutil
import subprocess
import sys
import threading

from flask import Blueprint, Response, jsonify, request, send_file

from config import (
    CONFIG_PATH, DEFAULT_SIZE_MB_PER_MIN, RUNTIME_DIR, THUMBNAILS_DIR,
    _DIM_REGISTRY, USE_PG,
)
from config import USE_PG
from utils.path_utils import is_local_status
if USE_PG:
    from models.pg_store import load_config, read_csv, write_csv
    from models.pg_dim import read_dim_rows as _read_dim_rows
else:
    from models.csv_store import load_config, read_csv, write_csv
    from models.dim_registry import read_dim_rows as _read_dim_rows
from services.lazy_loader import (
    _get_device_monitor, _get_hmd_preprocess,
)

bp = Blueprint("misc", __name__)


# ─────────────────────────────────────────────────────────────────
# Helpers (private to this module)
# ─────────────────────────────────────────────────────────────────

def _aggregate_hmd_size_ratio():
    """Walk video_manager.csv, for each hmd row with .hmd_process.json done,
    return (median_size_mb_per_min, count, samples[], medians_by_camera, camera_count)."""
    samples = []
    hmd_pre = _get_hmd_preprocess()
    for r in read_csv():
        if (r.get("file_type") or "") != "hmd":
            continue
        path = (r.get("path") or "").strip()
        if not path or not os.path.isdir(path):
            continue
        if not hmd_pre:
            continue
        status_file = hmd_pre.get_status_path(path)
        if not os.path.isfile(status_file):
            continue
        try:
            with open(status_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("status") != "done":
                continue
            sec = data.get("duration_sec")
            if not isinstance(sec, (int, float)) or sec <= 0:
                continue
        except Exception:
            continue
        total = 0
        try:
            for fname in os.listdir(path):
                if fname.startswith("part_") and fname.endswith(".hmd"):
                    total += os.path.getsize(os.path.join(path, fname))
        except Exception:
            continue
        if total <= 0:
            continue
        size_mb = total / 1024 / 1024
        duration_min = sec / 60.0
        if duration_min <= 0:
            continue
        camera = (r.get("device_id") or "").strip() or "unknown"
        samples.append({
            "path": path,
            "size_mb": round(size_mb, 2),
            "duration_sec": int(sec),
            "size_mb_per_min": round(size_mb / duration_min, 3),
            "camera": camera,
        })
    if not samples:
        return None, 0, samples, {}, 0
    sorted_ratios = sorted(s["size_mb_per_min"] for s in samples)
    n = len(sorted_ratios)
    median = sorted_ratios[n // 2] if n % 2 else (sorted_ratios[n // 2 - 1] + sorted_ratios[n // 2]) / 2
    by_camera = {}
    for s in samples:
        by_camera.setdefault(s["camera"], []).append(s["size_mb_per_min"])
    medians_by_camera = {}
    for cam, ratios in by_camera.items():
        rs = sorted(ratios)
        cn = len(rs)
        medians_by_camera[cam] = round(
            rs[cn // 2] if cn % 2 else (rs[cn // 2 - 1] + rs[cn // 2]) / 2, 3,
        )
    return round(median, 3), len(samples), samples, medians_by_camera, len(medians_by_camera)


def _get_size_mb_per_min():
    """Read from config; fallback to aggregated median; fallback to default."""
    cfg = load_config()
    saved = cfg.get("estimate", {}).get("size_mb_per_min")
    if isinstance(saved, (int, float)) and saved > 0:
        return float(saved), "user"
    median, n, _, _, _ = _aggregate_hmd_size_ratio()
    if median:
        return median, f"auto (median of {n} sessions)"
    return DEFAULT_SIZE_MB_PER_MIN, "default"


def estimate_hmd_duration_sec(total_size_bytes, ratio_mb_per_min=None):
    """Estimate duration in seconds from total HMD session size (bytes)."""
    if total_size_bytes is None or total_size_bytes <= 0:
        return 0
    if ratio_mb_per_min is None:
        ratio_mb_per_min, _ = _get_size_mb_per_min()
    size_mb = total_size_bytes / 1024 / 1024
    return int(round((size_mb / ratio_mb_per_min) * 60))


# ─────────────────────────────────────────────────────────────────
# Index & static
# ─────────────────────────────────────────────────────────────────

@bp.route("/")
def index():
    resp = send_file("templates/index.html")
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@bp.route("/favicon.ico")
def favicon():
    import base64
    transparent_png = base64.b64decode(
        b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    )
    return Response(transparent_png, mimetype="image/png")


# ─────────────────────────────────────────────────────────────────
# Statistics
# ─────────────────────────────────────────────────────────────────

@bp.route("/api/statistics", methods=["GET"])
def get_statistics():
    """返回统计页面所需的多维聚合数据。"""
    all_videos = read_csv()

    tasks_spec = _DIM_REGISTRY.get("tasks", {})
    env_spec = _DIM_REGISTRY.get("environments", {})
    recorders_spec = _DIM_REGISTRY.get("recorders", {})

    tasks_rows = _read_dim_rows(tasks_spec.get("path"), tasks_spec.get("schema"),
                                tasks_spec.get("key"), create_if_missing=False) or []
    env_rows = _read_dim_rows(env_spec.get("path"), env_spec.get("schema"),
                              env_spec.get("key"), create_if_missing=False) or []
    recorder_rows = _read_dim_rows(recorders_spec.get("path"), recorders_spec.get("schema"),
                                    recorders_spec.get("key"), create_if_missing=False) or []

    task_map = {r.get("task_id", ""): r for r in tasks_rows}
    env_map = {r.get("env_id", ""): r for r in env_rows}
    recorder_map = {r.get("id", ""): r for r in recorder_rows}

    def _get_sec(row):
        try:
            return int(row.get("duration_sec") or 0)
        except (TypeError, ValueError):
            return 0

    # 1. 环境总时长
    env_agg = {}
    for v in all_videos:
        eid = (v.get("env_id") or "").strip()
        if not eid:
            continue
        env_agg[eid] = env_agg.get(eid, 0) + _get_sec(v)

    total_sec = sum(env_agg.values()) if env_agg else 0
    env_stats = []
    for eid, used_sec in env_agg.items():
        env_info = env_map.get(eid, {})
        env_stats.append({
            "env_id": eid,
            "env_desc": env_info.get("environment_description", "") or eid,
            "used_sec": used_sec,
            "used_min": round(used_sec / 60, 1),
            "percent": round(used_sec / total_sec * 100, 1) if total_sec > 0 else 0.0,
        })
    env_stats.sort(key=lambda x: x["used_sec"], reverse=True)
    env_max_pct = max((e["percent"] for e in env_stats), default=0.0)
    env_top5_pct = sum(e["percent"] for e in env_stats[:5])

    # 2. 任务总时长
    task_agg = {}
    for v in all_videos:
        tid = (v.get("task_id") or "").strip()
        if not tid:
            continue
        task_agg[tid] = task_agg.get(tid, 0) + _get_sec(v)

    task_stats = []
    for tid, used_sec in task_agg.items():
        tinfo = task_map.get(tid, {})
        difficulty = tinfo.get("difficulty", "").strip()
        task_stats.append({
            "task_id": tid,
            "difficulty": difficulty,
            "product": tinfo.get("product", ""),
            "process": tinfo.get("process", ""),
            "used_sec": used_sec,
            "used_min": round(used_sec / 60, 1),
            "used_hours": round(used_sec / 3600, 1),
            "percent": round(used_sec / total_sec * 100, 1) if total_sec > 0 else 0.0,
        })
    task_stats.sort(key=lambda x: x["used_sec"], reverse=True)

    task_limits = {}
    for ts in task_stats:
        diff = ts["difficulty"]
        pct = ts["percent"]
        if diff == "hard" and pct > 6.0:
            task_limits[ts["task_id"]] = {"type": "hard_exceeded", "detail": f"{pct}% > 6%"}
        elif diff == "medium" and pct > 4.0:
            task_limits[ts["task_id"]] = {"type": "medium_exceeded", "detail": f"{pct}% > 4%"}
        elif diff == "easy" and pct > 1.5:
            task_limits[ts["task_id"]] = {"type": "easy_exceeded", "detail": f"{pct}% > 1.5%"}

    # 3. 任务 × 环境总时长
    te_agg = {}
    for v in all_videos:
        tid = (v.get("task_id") or "").strip()
        eid = (v.get("env_id") or "").strip()
        if not tid or not eid:
            continue
        key = f"{tid}|{eid}"
        te_agg[key] = te_agg.get(key, 0) + _get_sec(v)

    te_stats = []
    te_limits = {}
    DIFFICULTY_LIMITS_HOURS = {"easy": 10, "medium": 20, "hard": 40}
    for key, used_sec in te_agg.items():
        tid, eid = key.split("|", 1)
        tinfo = task_map.get(tid, {})
        difficulty = tinfo.get("difficulty", "").strip()
        einfo = env_map.get(eid, {})
        used_hours = used_sec / 3600
        limit_hours = DIFFICULTY_LIMITS_HOURS.get(difficulty, None)
        exceeded = limit_hours is not None and used_hours > limit_hours
        te_stats.append({
            "task_id": tid,
            "process": tinfo.get("process", ""),
            "env_id": eid,
            "difficulty": difficulty,
            "env_desc": einfo.get("environment_description", "") or eid,
            "used_sec": used_sec,
            "used_min": round(used_sec / 60, 1),
            "used_hours": round(used_hours, 1),
            "limit_hours": limit_hours,
            "exceeded": exceeded,
            "percent": round(used_sec / total_sec * 100, 1) if total_sec > 0 else 0.0,
        })
        if exceeded:
            te_limits[key] = {"type": "te_exceeded", "detail": f"{round(used_hours,1)}h > {limit_hours}h"}
    te_stats.sort(key=lambda x: x["used_sec"], reverse=True)

    # 4. 操作员 × 任务 × 环境总时长
    ote_agg = {}
    for v in all_videos:
        cid = (v.get("recorder_id") or "").strip()
        tid = (v.get("task_id") or "").strip()
        eid = (v.get("env_id") or "").strip()
        if not cid or not tid or not eid:
            continue
        key = f"{cid}|{tid}|{eid}"
        ote_agg[key] = ote_agg.get(key, 0) + _get_sec(v)

    ote_stats = []
    ote_limits = {}
    OTE_LIMITS_HOURS = {"easy": 1, "medium": 2, "hard": 10}
    for key, used_sec in ote_agg.items():
        parts = key.split("|", 2)
        if len(parts) != 3:
            continue
        cid, tid, eid = parts
        tinfo = task_map.get(tid, {})
        difficulty = tinfo.get("difficulty", "").strip()
        cinfo = recorder_map.get(cid, {})
        einfo = env_map.get(eid, {})
        used_hours = used_sec / 3600
        limit_hours = OTE_LIMITS_HOURS.get(difficulty, None)
        exceeded = limit_hours is not None and used_hours > limit_hours
        ote_stats.append({
            "recorder_id": cid,
            "recorder_name": cinfo.get("name", "") or cid,
            "task_id": tid,
            "process": tinfo.get("process", ""),
            "env_id": eid,
            "difficulty": difficulty,
            "env_desc": einfo.get("environment_description", "") or eid,
            "used_min": round(used_sec / 60, 1),
            "used_hours": round(used_hours, 1),
            "limit_hours": limit_hours,
            "exceeded": exceeded,
        })
        if exceeded:
            ote_limits[key] = {"type": "ote_exceeded", "detail": f"{round(used_hours,1)}h > {limit_hours}h"}
    ote_stats.sort(key=lambda x: x["used_hours"], reverse=True)

    return jsonify({
        "total_sec": total_sec,
        "total_hours": round(total_sec / 3600, 1),
        "total_min": round(total_sec / 60, 1),
        "env_stats": {
            "data": env_stats,
            "max_pct": env_max_pct,
            "top5_pct": env_top5_pct,
            "max_limit": 20.0,
            "top5_limit": 60.0,
            "max_exceeded": env_max_pct > 20.0,
            "top5_exceeded": env_top5_pct > 60.0,
        },
        "task_stats": {
            "data": task_stats,
            "limits": task_limits,
        },
        "task_env_stats": {
            "data": te_stats,
            "limits": te_limits,
        },
        "operator_task_env_stats": {
            "data": ote_stats,
            "limits": ote_limits,
        },
    })


# ─────────────────────────────────────────────────────────────────
# Estimate (HMD size → duration ratio)
# ─────────────────────────────────────────────────────────────────

@bp.route("/api/estimate", methods=["GET"])
def get_estimate():
    """Return current size→duration ratio + how it was derived + samples."""
    cfg = load_config()
    saved = cfg.get("estimate", {})
    median, n, samples, medians_by_camera, camera_count = _aggregate_hmd_size_ratio()
    current, source = _get_size_mb_per_min()
    return jsonify({
        "size_mb_per_min": current,
        "source": source,
        "saved_value": saved.get("size_mb_per_min"),
        "auto_median": median,
        "sample_count": n,
        "samples": samples,
        "medians_by_camera": medians_by_camera,
        "camera_count": camera_count,
        "default": DEFAULT_SIZE_MB_PER_MIN,
    })


@bp.route("/api/estimate", methods=["POST"])
def set_estimate():
    """Update size_mb_per_min (or reset to auto)."""
    body = request.get_json(silent=True) or {}
    cfg = load_config()
    if "estimate" not in cfg:
        cfg["estimate"] = {}
    if body.get("reset"):
        cfg["estimate"].pop("size_mb_per_min", None)
    else:
        v = body.get("size_mb_per_min")
        if isinstance(v, (int, float)) and v > 0:
            cfg["estimate"]["size_mb_per_min"] = float(v)
        else:
            return jsonify({"error": "size_mb_per_min must be a positive number (or pass {reset:true})"}), 400
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return jsonify({"ok": True})


# ─────────────────────────────────────────────────────────────────
# Disk space / device monitor
# ─────────────────────────────────────────────────────────────────

@bp.route("/api/disk-space-status", methods=["GET"])
def disk_space_status():
    """获取设备监控的磁盘空间状态和暂停信息。"""
    dm = _get_device_monitor()
    if dm:
        return jsonify(dm.get_monitor_disk_space_status())
    else:
        cfg = load_config()
        dest = cfg.get("scanDirectory", r"/media")
        try:
            usage = shutil.disk_usage(dest)
            return jsonify({
                "paused_for_space": False,
                "free_gb": round(usage.free / (1024**3), 2),
                "total_gb": round(usage.total / (1024**3), 2),
                "used_gb": round(usage.used / (1024**3), 2),
                "disk_space_ratio": 2.0,
                "last_warning": None,
                "paused_at": None,
                "monitor_running": False,
                "monitor_scanning": False,
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500


@bp.route("/api/resume-monitor", methods=["POST"])
def resume_monitor_api():
    """手动尝试恢复设备监控（从磁盘空间不足暂停状态）。"""
    dm = _get_device_monitor()
    if not dm:
        return jsonify({"error": "设备监控模块未加载"}), 500
    resumed = dm.resume_monitor()
    status = dm.get_monitor_disk_space_status()
    return jsonify({
        "ok": True,
        "resumed": resumed,
        "disk_space": status,
        "message": "磁盘空间已恢复，监控已恢复扫描" if resumed
                   else "磁盘空间仍然不足，请继续清理已上传的视频文件",
    })


# ─────────────────────────────────────────────────────────────────
# One-off data fixes
# ─────────────────────────────────────────────────────────────────

@bp.route("/api/fix-dates", methods=["POST"], endpoint="fix_dates_oneoff")
def fix_dates_oneoff():
    """一次性迁移：把历史 local 行里错填到 scan_date 的"原始日期"挪回 original_history_date。"""
    rows = read_csv()
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    moved = 0
    for r in rows:
        if (is_local_status(r.get("location_status"))
                and r.get("scan_date")
                and not r.get("original_history_date")):
            r["original_history_date"] = r["scan_date"]
            r["scan_date"] = today
            moved += 1
    if moved > 0:
        write_csv(rows)
    return jsonify({"moved": moved, "today": today, "total": len(rows)})


@bp.route("/api/fix-empty-scan-dates", methods=["POST"], endpoint="fix_empty_scan_dates_oneoff")
def fix_empty_scan_dates_oneoff():
    """一次性迁移：把 location=local 且 scan_date=空 的行回填为今天。"""
    rows = read_csv()
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    filled = 0
    for r in rows:
        if is_local_status(r.get("location_status")) and not r.get("scan_date"):
            r["scan_date"] = today
            filled += 1
    if filled > 0:
        write_csv(rows)
    return jsonify({"filled": filled, "today": today, "total": len(rows)})


@bp.route("/api/pick-directory", methods=["POST"])
def pick_directory():
    """Open a native directory picker dialog and return the selected path."""
    initial = ""
    try:
        body = request.get_json(silent=True) or {}
        initial = (body.get("initial") or "").strip()
    except Exception:
        initial = ""

    picker_script = (
        "import sys, os\n"
        "import tkinter as tk\n"
        "from tkinter import filedialog\n"
        "initial = " + repr(initial) + "\n"
        "try:\n"
        "    root = tk.Tk()\n"
        "    root.withdraw()\n"
        "    root.attributes('-topmost', True)\n"
        "    if initial and os.path.isdir(initial):\n"
        "        path = filedialog.askdirectory(initialdir=initial, mustexist=True, title='选择视频目录')\n"
        "    else:\n"
        "        path = filedialog.askdirectory(mustexist=True, title='选择视频目录')\n"
        "    root.destroy()\n"
        "    print(path or '')\n"
        "except Exception as e:\n"
        "    print('ERROR:' + str(e), file=sys.stderr)\n"
        "    sys.exit(2)\n"
    )

    try:
        result = subprocess.run(
            [sys.executable, "-c", picker_script],
            capture_output=True, encoding="utf-8", errors="replace", timeout=300,
        )
        if result.returncode != 0:
            err = (result.stderr or "").strip()
            return jsonify({"error": f"选择对话框失败: {err}"}), 500
        path = (result.stdout or "").strip()
        if not path:
            return jsonify({"path": None})
        path = os.path.normpath(path)
        return jsonify({"path": path})
    except subprocess.TimeoutExpired:
        return jsonify({"error": "选择超时（>5 分钟）"}), 504
    except Exception as e:
        return jsonify({"error": f"打开选择对话框出错: {e}"}), 500