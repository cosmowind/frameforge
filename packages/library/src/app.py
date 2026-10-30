import csv
import glob
import io
import json
import logging
import os
import queue
import re
import requests
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
from datetime import datetime
from typing import Optional

from flask import Flask, Response, jsonify, request, send_file, make_response, stream_with_context
from config import *       # 项目中所有常量、路径配置（拆分自 S1）
from config import USE_PG, DATABASE_DSN

if USE_PG:
    from models.pg_store import (
        get_fieldnames, load_config, read_csv, write_csv,
        _atomic_write_csv, mark_uploaded, check_file, marker_path,
    )
    from models.pg_dim import (
        resolve_dim as _resolve_dim,
        read_dim_rows as _read_dim_rows,
        validate_dim_row as _validate_dim_row,
        atomic_write_dim as _atomic_write_dim,
    )
else:
    from models.csv_store import (
        get_fieldnames, load_config, read_csv, write_csv,
        _atomic_write_csv,
    )
    from services.misc_service import (
        mark_uploaded, check_file, marker_path, has_marker, write_marker,
        cleanup_after_upload,
    )
    from models.dim_registry import (
        resolve_dim as _resolve_dim,
        read_dim_rows as _read_dim_rows,
        validate_dim_row as _validate_dim_row,
        atomic_write_dim as _atomic_write_dim,
    )

from utils.path_utils import extract_date_from_path as _extract_date_from_path
from utils.path_utils import get_hmd_cache_dir as _get_hmd_cache_dir
from utils.path_utils import extract_mmdd_from_path as _extract_mmdd_from_path
from utils.path_utils import should_add_date_prefix as _should_add_date_prefix
from utils.format_utils import fmt_duration as _fmt_duration
from utils.format_utils import parse_duration_to_sec as _parse_duration_to_sec

# ── 蓝图路由 ──
from routes.misc_routes import bp as misc_bp
from routes.data_routes import bp as data_bp
from routes.cleanup_routes import bp as cleanup_bp
from routes.dim_routes import bp as dim_bp
from routes.video_routes import bp as video_bp
from routes.hmd_routes import bp as hmd_bp
from routes.upload_routes import bp as upload_bp
from routes.upload_config_routes import bp as upload_config_bp
from routes.auto_upload_routes import bp as auto_upload_bp
from services import upload_service
from services.preprocess_service import init_preprocess_status_from_rows, get_preprocess_overview
from services.misc_service import _extract_date_from_path
from services.helper_service import tee_print

logger = logging.getLogger(__name__)

app = Flask(__name__)



# ── 注册蓝图 ──
app.register_blueprint(misc_bp)
app.register_blueprint(data_bp)
app.register_blueprint(cleanup_bp)
app.register_blueprint(dim_bp)
app.register_blueprint(video_bp)
app.register_blueprint(hmd_bp)
app.register_blueprint(upload_bp)
app.register_blueprint(upload_config_bp)
app.register_blueprint(auto_upload_bp)

@app.route("/api/dim-editable-options", methods=["GET", "POST"])
def dim_editable_options():
    """GET/POST editable dropdown options for dimension fields (scene, business_type, business_name).
    
    Stored in config.json under dimEditableOptions key.
    GET returns current options (with upload taxonomy defaults merged).
    POST body: { field: string, action: "add"|"remove"|"set", options?: [{value,label}], value?: string }
    """
    cfg = load_config()
    stored = cfg.get("dimEditableOptions", {})
    
    if request.method == "GET":
        # Return user-stored editable options for business_type and business_name only.
        # scene is a fixed taxonomy (from upload page) and no longer user-editable.
        defaults = {
            "business_type": stored.get("business_type", []),
            "business_name": stored.get("business_name", []),
        }
        return jsonify(defaults)
    
    # POST
    body = request.get_json(silent=True) or {}
    field = body.get("field", "")
    action = body.get("action", "")
    
    if field not in ("business_type", "business_name"):
        return jsonify({"error": "invalid field"}), 400
    
    if field not in stored:
        stored[field] = []
    
    if action == "add":
        new_opt = body.get("option")
        if new_opt and isinstance(new_opt, dict) and "value" in new_opt and "label" in new_opt:
            vals = [o["value"] for o in stored[field]]
            if new_opt["value"] not in vals:
                stored[field].append(new_opt)
    elif action == "remove":
        val = body.get("value", "")
        stored[field] = [o for o in stored[field] if o["value"] != val]
    elif action == "set":
        opts = body.get("options", [])
        if isinstance(opts, list):
            stored[field] = opts
    
    cfg["dimEditableOptions"] = stored
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    
    return jsonify({"ok": True, "field": field, "options": stored[field]})


@app.route("/api/dim/environments/next-id", methods=["POST"])
def environments_next_id():
    """根据 environment_description 生成 env_id（md5 哈希）。"""
    import hashlib
    body = request.get_json(silent=True) or {}
    desc = (body.get("environment_description") or "").strip()
    if not desc:
        return jsonify({"ok": False, "reason": "environment_description 不能为空"}), 400
    h = hashlib.md5(desc.encode("utf-8")).hexdigest()[:10]
    env_id = "env_" + h
    # 检查冲突
    spec = _DIM_REGISTRY["environments"]
    abs_path = spec["path"]
    existing_rows = _read_dim_rows(abs_path, spec["schema"], spec["key"], create_if_missing=False) or []
    existing_ids = {r.get("env_id", "") for r in existing_rows}
    if env_id in existing_ids:
        return jsonify({"ok": True, "suggested": env_id, "exists": True})
    return jsonify({"ok": True, "suggested": env_id, "exists": False})


@app.route("/api/dim/tasks/reorder", methods=["POST"])
def tasks_reorder():
    """按前端传来的 task_id 列表重写 CSV 行序。"""
    data = request.get_json(force=True)
    ordered_ids = data.get("order", [])
    if not ordered_ids:
        return jsonify({"ok": False, "error": "order 为空"}), 400
    spec = _DIM_REGISTRY["tasks"]
    abs_path = spec["path"]
    schema = spec["schema"]
    key = spec["key"]
    rows = _read_dim_rows(abs_path, schema, key, create_if_missing=True)
    row_map = {r[key]: r for r in rows}
    new_rows = []
    for tid in ordered_ids:
        if tid in row_map:
            new_rows.append(row_map.pop(tid))
    # 追加剩余未在 order 中的行（兜底）
    new_rows.extend(row_map.values())
    _atomic_write_dim("tasks", abs_path, new_rows, schema)
    return jsonify({"ok": True, "count": len(new_rows)})


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

    # 配额默认值（分钟）：easy=60, medium=120, hard=600
    QUOTA_DEFAULTS = {"easy": 60, "medium": 120, "hard": 600}

    task_stats = []
    for tid, used_sec in task_agg.items():
        tinfo = task_map.get(tid, {})
        difficulty = tinfo.get("difficulty", "").strip()
        raw_quota = (tinfo.get("quota_min") or "").strip()
        quota_min = int(raw_quota) if raw_quota.isdigit() else QUOTA_DEFAULTS.get(difficulty)
        task_stats.append({
            "task_id": tid,
            "difficulty": difficulty,
            "product": tinfo.get("product", ""),
            "process": tinfo.get("process", ""),
            "used_sec": used_sec,
            "used_min": round(used_sec / 60, 1),
            "used_hours": round(used_sec / 3600, 1),
            "percent": round(used_sec / total_sec * 100, 1) if total_sec > 0 else 0.0,
            "quota_min": quota_min,
        })
    task_stats.sort(key=lambda x: x["used_sec"], reverse=True)

    # 任务限制检查
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


@app.route("/api/translate-process", methods=["POST"])
def translate_single_process():
    """单条工序翻译：接收中文工序文本，返回英文翻译结果。
    
    POST body: { text: str }
    返回: { ok: true, result: str }
    """
    body = request.get_json(silent=True) or {}
    text = (body.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text 为空"}), 400
    result = translate_process_to_en(text)
    return jsonify({"ok": True, "result": result or ""})






