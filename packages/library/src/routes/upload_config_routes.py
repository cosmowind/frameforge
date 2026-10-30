from flask import Blueprint, jsonify, request
from config import *
from config import USE_PG
import os
import json
from datetime import datetime
import logging

if USE_PG:
    from models.pg_store import read_csv
else:
    from models.csv_store import read_csv
from services.misc_service import _read_clipboard, _write_clipboard, _save_upload_template_config
from services.upload_config_service import _load_upload_template_config
from services.upload_service import (
    _translate_zh_to_en, _load_env_info, _load_recorder_info,
    _load_sd_card_info, _load_task_info,
)
logger = logging.getLogger(__name__)

bp = Blueprint('upload_config', __name__)


@bp.route("/api/upload-config", methods=["GET"])
def get_upload_config():
    """Return current upload configuration"""
    return jsonify(UPLOAD_CONFIG)




@bp.route("/api/upload-template/<int:row_index>", methods=["GET"])
def get_upload_template(row_index):
    """Return pre-filled upload template data for a specific video row.

    Merges:
    - uploadTemplate defaults from config.json
    - video_manager.csv row fields
    - task info from tasks.csv (via task_id)
    - env info from environments.csv (via env_id)
    - recorder info from recorders.csv (via recorder_id)
    """
    rows = read_csv()
    if row_index < 0 or row_index >= len(rows):
        return jsonify({"error": f"行索引 {row_index} 超出范围（共 {len(rows)} 行）"}), 400

    video_row = rows[row_index]
    template = _load_upload_template_config()

    # ── 从维表获取关联信息 ──
    recorder_id = (video_row.get("recorder_id") or "").strip()
    device_id = (video_row.get("device_id") or "").strip()
    task_id = (video_row.get("task_id") or "").strip()
    env_id = (video_row.get("env_id") or "").strip()
    source_device = (video_row.get("source_device") or "").strip()

    # 来源设备
    if source_device and not template.get("source_device"):
        template["source_device"] = source_device

    recorder_info = _load_recorder_info(recorder_id) if recorder_id else None
    sd_card_info = _load_sd_card_info(device_id) if device_id else None
    task_info = _load_task_info(task_id) if task_id else None
    env_info = _load_env_info(env_id) if env_id else None

    # ── 预填字段（优先级：维表 > 模板默认 > 内置默认） ──
    # 1) Recorder fields
    if recorder_info:
        if not template.get("operator_name"):
            template["operator_name"] = recorder_info.get("id", "")
        for f in ["operator_job", "operator_consent", "age_range", "gender",
                   "handedness", "gloves", "workforce_type", "role_experience",
                   "task_experience", "recording_hours_today",
                   "recording_experience_days", "hand_size_cm"]:
            val = recorder_info.get(f, "").strip()
            if val and not template.get(f):
                template[f] = val

    # 2) SD card / location fields
    if sd_card_info:
        _sd_to_tpl = {
            "capture_mode": "captureMode",
            "country_code": "country",
            "region": "state_province",
            "city": "city",
        }
        for csv_key, tpl_key in _sd_to_tpl.items():
            val = (sd_card_info.get(csv_key) or "").strip()
            if val and not template.get(tpl_key):
                template[tpl_key] = val

    # 3) Task fields (difficulty, process, business_type/name)
    if task_info:
        if task_info.get("difficulty") and not template.get("task_difficulty"):
            template["task_difficulty"] = task_info["difficulty"]
        # process_en（已翻译英文）优先于 process（中文原文）
        proc_val = (task_info.get("process_en") or "").strip()
        if not proc_val:
            proc_val = (task_info.get("process") or "").strip()
        if proc_val and not template.get("task_description"):
            template["task_description"] = proc_val
        # business_type, business_name from tasks
        for f in ["business_type", "business_name"]:
            val = (task_info.get(f) or "").strip()
            if val and not template.get(f):
                template[f] = val

    # 4) Environment fields (from environments.csv via env_id)
    if env_info:
        # environment_description_en（已翻译英文）优先于 environment_description（中文原文）
        env_desc_val = (env_info.get("environment_description_en") or "").strip()
        if not env_desc_val:
            env_desc_val = (env_info.get("environment_description") or "").strip()
        if env_desc_val and not template.get("environment_description"):
            template["environment_description"] = env_desc_val
        if env_info.get("scene") and not template.get("scene"):
            template["scene"] = env_info["scene"]
        if env_info.get("location_address") and not template.get("location_address"):
            template["location_address"] = env_info["location_address"]
        for f in ["environment", "facility_venue"]:
            val = (env_info.get(f) or "").strip()
            if val and not template.get(f):
                template[f] = val

    # ── 构建返回的字段列表（含 prefill value + label + section） ──
    sections = [
        {
            "id": "task",
            "title": "Task Attributes",
            "fields": [
                "operator_name", "operator_job", "operator_consent",
                "task_difficulty", "task_description", "environment_description",
                "business_type", "business_name",
                "environment", "facility_venue", "scene",
            ]
        },
        {
            "id": "location",
            "title": "Environment & Location",
            "fields": [
                "country", "state_province", "city",
                "location_address",
            ]
        },
        {
            "id": "operator",
            "title": "Operator",
            "fields": [
                "age_range", "gender", "handedness", "gloves", "workforce_type",
                "role_experience", "task_experience",
                "recording_hours_today", "recording_experience_days",
                "hand_size_cm",
                "source_device",
            ]
        },
    ]

    fields_out = []
    for sec in sections:
        for key in sec["fields"]:
            fld = {
                "key": key,
                "label": UPLOAD_TEMPLATE_LABELS.get(key, key),
                "value": template.get(key, ""),
                "section_id": sec["id"],
            }
            # task_description: 英文 + 中文双版本
            if key == "task_description" and fld["value"]:
                if task_info:
                    process_cn = (task_info.get("process") or "").strip()
                    process_en = (task_info.get("process_en") or "").strip()
                    if process_en:
                        fld["translated"] = process_en
                    else:
                        en = _translate_zh_to_en(fld["value"])
                        if en:
                            fld["translated"] = en
                    if process_cn:
                        fld["cn"] = process_cn
                else:
                    en = _translate_zh_to_en(fld["value"])
                    if en:
                        fld["translated"] = en
                        fld["cn"] = fld["value"]
            # environment_description: 英文 + 中文双版本
            if key == "environment_description" and fld["value"]:
                if env_info:
                    env_cn = (env_info.get("environment_description") or "").strip()
                    env_en = (env_info.get("environment_description_en") or "").strip()
                    if env_en:
                        fld["translated"] = env_en
                    elif env_cn:
                        en = _translate_zh_to_en(env_cn)
                        if en:
                            fld["translated"] = en
                    if env_cn:
                        fld["cn"] = env_cn
                else:
                    en = _translate_zh_to_en(fld["value"])
                    if en:
                        fld["translated"] = en
                        fld["cn"] = fld["value"]
            fields_out.append(fld)

    return jsonify({
        "row_index": row_index,
        "video_path": video_row.get("path", ""),
        "video_name": os.path.basename(video_row.get("path", "")),
        "recorder_id": recorder_id,
        "recorder_name": (recorder_info or {}).get("name", "") if recorder_info else "",
        "task_id": task_id,
        "env_id": env_id,
        "env_desc": (env_info or {}).get("environment_description", "") if env_info else "",
        "source_device": (video_row.get("source_device") or "").strip(),
        "sections": [{"id": s["id"], "title": s["title"]} for s in sections],
        "fields": fields_out,
    })



@bp.route("/api/upload-template-by-path", methods=["GET"])
def get_upload_template_by_path():
    """通过 path 查找上传模板（解决 rowIndex 不一致问题）。"""
    video_path = request.args.get("path", "")
    if not video_path:
        return jsonify({"error": "缺少 path 参数"}), 400
    rows = read_csv()
    norm_target = os.path.normpath(video_path).replace("\\", "/")
    # 全匹配优先
    for i, row in enumerate(rows):
        row_path = os.path.normpath(row.get("path", "")).replace("\\", "/")
        if row_path == norm_target:
            return get_upload_template(i)
    # 忽略大小写匹配
    norm_target_lower = norm_target.lower()
    for i, row in enumerate(rows):
        row_path = os.path.normpath(row.get("path", "")).replace("\\", "/")
        if row_path.lower() == norm_target_lower:
            return get_upload_template(i)
    return jsonify({"error": f"未找到路径: {video_path}"}), 400



@bp.route("/api/upload-template-config", methods=["GET", "POST"])
def upload_template_config():
    """GET/POST upload template default values."""
    if request.method == "GET":
        return jsonify(_load_upload_template_config())
    body = request.get_json(silent=True) or {}
    allowed = set(UPLOAD_TEMPLATE_DEFAULTS.keys())
    updates = {k: v for k, v in body.items() if k in allowed}
    cfg = _load_upload_template_config()
    cfg.update(updates)
    _save_upload_template_config(cfg)
    return jsonify({"ok": True, "updated": list(updates.keys())})


# ── 视频补录参数助手 (autofill) ──
# 业务：用户在 publish.example.com 上传页面手填 3 个 free-text 字段
#   (operator-name, task-description, environment-description) + 可选 device-id
# 调用本组 API 一次性匹配 4 个维表并返回完整表单字段。
# 端点：
#   POST /api/auto-fill          — 主入口，给定 3 字段返回 fields
#   POST /api/auto-fill/match    — 候选 typeahead（任一字段补全提示）
#   POST /api/auto-fill/apply    — 把 matched 写回 video_manager.csv 对应行
#   GET  /api/auto-fill/defaults — 返回当前 upload template 默认值，供前端预填


@bp.route("/api/auto-fill", methods=["POST"])
def auto_fill():
    """主入口：给定 3 个 free-text 输入，返回可填到 publish.example.com 表单的完整 fields。

    如果 3 个字段都为空，会从 server 端 clipboard（_autofill_clipboard.json）拉取，
    这样 Playwright 浮动按钮"🚀 一键补全"无需在 3 个输入框中输入任何值即可触发。
    """
    from services.autofill_service import autofill as _autofill
    body = request.get_json(silent=True) or {}
    operator_name = (body.get("operator_name") or body.get("operator-name") or "").strip()
    task_desc = (body.get("task_description") or body.get("task-description") or "").strip()
    env_desc = (body.get("environment_description") or body.get("environment-description") or "").strip()
    device_id = (body.get("device_id") or "").strip()
    video_path = (body.get("video_path") or body.get("videoPath") or "").strip()

    # 3 个字段都空时：从 server clipboard 拉取
    if not any([operator_name, task_desc, env_desc, device_id]):
        cb = _read_clipboard()
        operator_name = cb.get("operator_name", "")
        task_desc = cb.get("task_description", "")
        env_desc = cb.get("environment_description", "")
        device_id = cb.get("device_id", "")
    if not any([operator_name, task_desc, env_desc, device_id]):
        return jsonify({
            "ok": False,
            "error": "至少提供一个输入字段，或先在维表管理点 📋 复制三件套 (operator_name / task_description / environment_description / device_id)",
        }), 400
    result = _autofill(
        operator_name=operator_name,
        task_desc=task_desc,
        env_desc=env_desc,
        device_id=device_id,
        video_path=video_path,
        upload_template_defaults=_load_upload_template_config(),
    )
    return jsonify(result)



@bp.route("/api/auto-fill/match", methods=["POST"])
def auto_fill_match():
    """候选 typeahead：任意输入字段返回 top-N 候选，便于下拉提示。
    body: { field: "operator_name"|"task_description"|"environment_description", prefix: str, limit?: int }
    """
    from services.autofill_service import (
        suggest_recorders, suggest_tasks, suggest_environments,
    )
    body = request.get_json(silent=True) or {}
    field = (body.get("field") or "").strip()
    prefix = (body.get("prefix") or "").strip()
    limit = int(body.get("limit") or 8)
    if field not in ("operator_name", "task_description", "environment_description", "device_id"):
        return jsonify({"ok": False, "error": "field 必须是 operator_name / task_description / environment_description / device_id"}), 400
    if field == "operator_name":
        items = suggest_recorders(prefix, limit)
    elif field == "task_description":
        items = suggest_tasks(prefix, limit)
    elif field == "environment_description":
        items = suggest_environments(prefix, limit)
    else:  # device_id
        if USE_PG:
            from models.pg_dim import read_dim_rows as _rd
        else:
            from models.dim_registry import read_dim_rows as _rd
        from config import _DIM_REGISTRY as _reg
        spec = _reg["sd_cards"]
        all_rows = _rd(spec["path"], spec["schema"], spec["key"], create_if_missing=False) or []
        target = prefix.lower()
        items = [r for r in all_rows
                 if not target or target in (r.get("device_id", "") + r.get("device_name", "")).lower()][:limit]
    # 精简返回
    out = []
    for r in items:
        out.append({
            "id": r.get("id", ""),
            "name": r.get("name", ""),
            "task_id": r.get("task_id", ""),
            "env_id": r.get("env_id", ""),
            "device_id": r.get("device_id", ""),
            "process": r.get("process", ""),
            "process_en": r.get("process_en", ""),
            "environment_description": r.get("environment_description", ""),
            "environment_description_en": r.get("environment_description_en", ""),
        })
    return jsonify({"ok": True, "field": field, "items": out})



@bp.route("/api/auto-fill/apply", methods=["POST"])
def auto_fill_apply():
    """把 matched {recorder_id, task_id, env_id, device_id} 写回 video_manager.csv 对应行。
    body: { video_path: str, matched: {recorder_id?, task_id?, env_id?, device_id?} }
    """
    from services.autofill_service import apply_to_video_row
    body = request.get_json(silent=True) or {}
    video_path = (body.get("video_path") or "").strip()
    matched = body.get("matched") or {}
    if not video_path:
        return jsonify({"ok": False, "error": "缺少 video_path"}), 400
    if not isinstance(matched, dict) or not matched:
        return jsonify({"ok": False, "error": "缺少 matched（dict，至少一项）"}), 400
    ok = apply_to_video_row(video_path, matched)
    if not ok:
        return jsonify({"ok": False, "error": f"video_path 不在 video_manager.csv 中: {video_path}"}), 404
    return jsonify({"ok": True, "video_path": video_path, "applied": matched})



@bp.route("/api/auto-fill/defaults", methods=["GET"])
def auto_fill_defaults():
    """返回 upload template 当前默认值 + 4 个 dim 的样本行（供 UI 预填）。"""
    cfg = _load_upload_template_config()
    from services.autofill_service import (
        _load_dim as _ld,
    )
    return jsonify({
        "ok": True,
        "template": cfg,
        "labels": UPLOAD_TEMPLATE_LABELS,
        "samples": {
            "recorders":   _ld("recorders")[:3],
            "sd_cards":     _ld("sd_cards")[:3],
            "tasks":        _ld("tasks")[:3],
            "environments": _ld("environments")[:3],
        },
    })


# ── 维表→上传页面 一键复制三件套 (clipboard) ──
# 工作流：用户在维表管理页选一行（opx / process / env_desc）→ 点"📋 复制三件套"
# → server 把三件套写到 runtime/data/_autofill_clipboard.json
# → 上传页面（publish.example.com）的浮动按钮"📋"读 clipboard 填到对应输入框
_AUTOFILL_CLIPBOARD_PATH = os.path.join(RUNTIME_DIR, "data", "_autofill_clipboard.json")



@bp.route("/api/auto-fill/clipboard", methods=["GET", "POST", "DELETE"])
def auto_fill_clipboard():
    """GET 读 / POST 写 / DELETE 清空。"""
    if request.method == "GET":
        return jsonify({"ok": True, "clipboard": _read_clipboard()})
    if request.method == "DELETE":
        try:
            if os.path.exists(_AUTOFILL_CLIPBOARD_PATH):
                os.remove(_AUTOFILL_CLIPBOARD_PATH)
        except Exception:
            pass
        return jsonify({"ok": True, "cleared": True})
    # POST
    body = request.get_json(silent=True) or {}
    saved = _write_clipboard(body)
    return jsonify({"ok": True, "clipboard": saved})


# ── 维表管理页"复制单字段到 clipboard"快捷端点 ──

@bp.route("/api/auto-fill/clipboard/set-field", methods=["POST"])
def auto_fill_clipboard_set_field():
    """单独设置一个字段（不影响其他字段）。
    body: { field: "operator_name"|"task_description"|"environment_description"|"device_id", value: str, source?: str }
    """
    body = request.get_json(silent=True) or {}
    field = (body.get("field") or "").strip()
    value = (body.get("value") or "").strip()
    if field not in ("operator_name", "task_description",
                     "environment_description", "device_id"):
        return jsonify({"ok": False, "error": "field 不合法"}), 400
    cur = _read_clipboard()
    cur[field] = value
    cur["source"] = (body.get("source") or cur.get("source") or "")
    cur["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    saved = _write_clipboard(cur)
    return jsonify({"ok": True, "clipboard": saved, "field": field, "value": value})
