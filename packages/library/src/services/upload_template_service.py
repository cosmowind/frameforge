import os
import json
from config import *

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
        "sections": [{"id": s["id"], "title": s["title"]} for s in sections],
        "fields": fields_out,
    })



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



