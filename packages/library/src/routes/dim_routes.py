"""dim_routes — dimension table CRUD: recorders, tasks, environments, sd_cards."""

import re

from flask import Blueprint, jsonify, request

from config import _DIM_REGISTRY, USE_PG, CONFIG_PATH
if USE_PG:
    from models.pg_dim import (
        atomic_write_dim as _atomic_write_dim,
        read_dim_rows as _read_dim_rows,
        validate_dim_row as _validate_dim_row,
    )
    from models.pg_store import load_config
else:
    from models.csv_store import read_csv, load_config
    from models.dim_registry import (
        atomic_write_dim as _atomic_write_dim,
        read_dim_rows as _read_dim_rows,
        validate_dim_row as _validate_dim_row,
    )
from services.dim_service import (
    generate_next_task_id, resolve_row_range, slugify_segment,
)

bp = Blueprint("dim", __name__)


# ─────────────────────────────────────────────────────────────────
# Helpers (private to this module)
# ─────────────────────────────────────────────────────────────────

def _translate_process_to_en(chinese_text):
    """Translate Chinese process text to English. Delegates to dim_service."""
    from services.dim_service import translate_process_to_en as _t
    return _t(chinese_text)


# ─────────────────────────────────────────────────────────────────
# Dimension CRUD
# ─────────────────────────────────────────────────────────────────

@bp.route("/api/dim/<name>", methods=["GET", "POST"])
def handle_dim(name):
    """GET: 返回维表 rows + schema. POST: upsert by key."""
    spec = _DIM_REGISTRY.get(name)
    if not spec:
        return jsonify({"error": f"维度 '{name}' 未注册"}), 404
    abs_path = spec["path"]
    schema = spec["schema"]
    key = spec["key"]

    if request.method == "GET":
        rows = _read_dim_rows(abs_path, schema, key, create_if_missing=False)
        if rows is None:
            return jsonify({"error": f"维表文件不存在: {spec['path']}"}), 404
        return jsonify({
            "name": name,
            "schema": schema,
            "key": key,
            "rows": rows,
            "count": len(rows),
            "migrated": [],
        })

    # POST: upsert
    body = request.get_json(silent=True) or {}
    incoming = body.get("row") or {}
    mode = (body.get("mode") or "upsert").lower()
    if mode not in ("upsert", "insert", "update"):
        return jsonify({"error": "mode 必须是 upsert/insert/update"}), 400

    cleaned, errors = _validate_dim_row(name, incoming, schema, spec.get("validators") or {})
    if errors:
        return jsonify({"error": "校验失败", "errors": errors, "row": cleaned}), 400

    # 对 tasks 维表：若工序含中文且未提供英文译文，则自动翻译并保存到 process_en
    if name == "tasks":
        proc = (cleaned.get("process") or "").strip()
        if proc and not (cleaned.get("process_en") or "").strip():
            translated = _translate_process_to_en(proc)
            if translated:
                cleaned["process_en"] = translated

    # 对 environments 维表：若环境描述含中文且未提供英文译文，则自动翻译
    if name == "environments":
        env_desc = (cleaned.get("environment_description") or "").strip()
        if env_desc and not (cleaned.get("environment_description_en") or "").strip():
            translated = _translate_process_to_en(env_desc)
            if translated:
                cleaned["environment_description_en"] = translated

    rows = _read_dim_rows(abs_path, schema, key, create_if_missing=False)
    if rows is None:
        if spec.get("create_if_missing"):
            rows = []
        else:
            return jsonify({"error": f"维表文件不存在: {spec['path']}"}), 404

    key_val = cleaned.get(key, "")
    if not key_val:
        return jsonify({"error": f"主键 {key} 不能为空"}), 400

    # Find existing by key
    existing_idx = next((i for i, r in enumerate(rows) if r.get(key) == key_val), None)

    # 处理主键改名（前端用 ?original_key=xxx 传旧 key）
    original_key = (request.args.get("original_key") or "").strip() or key_val
    rename_from_idx = None
    if original_key != key_val:
        rename_from_idx = next((i for i, r in enumerate(rows) if r.get(key) == original_key), None)

    action = None
    if existing_idx is not None:
        if mode == "insert":
            return jsonify({"error": f"主键 '{key_val}' 已存在", "code": "duplicate"}), 409
        for fn in schema:
            rows[existing_idx][fn] = cleaned.get(fn, rows[existing_idx].get(fn, ""))
        action = "updated"
    elif rename_from_idx is not None:
        for fn in schema:
            rows[rename_from_idx][fn] = cleaned.get(fn, rows[rename_from_idx].get(fn, ""))
        action = "renamed"
    else:
        if mode == "update":
            return jsonify({"error": f"主键 '{key_val}' 不存在", "code": "not_found"}), 404
        rows.append({fn: cleaned.get(fn, "") for fn in schema})
        action = "inserted"

    _atomic_write_dim(name, abs_path, rows, schema)
    try:
        from services.autofill_service import invalidate_cache
        invalidate_cache(name)
    except Exception:
        pass
    return jsonify({"ok": True, "action": action, "row": cleaned, "count": len(rows)})


@bp.route("/api/dim/<name>/<key_val>", methods=["DELETE"])
def delete_dim_row(name, key_val):
    """Delete a row from a dimension table."""
    spec = _DIM_REGISTRY.get(name)
    if not spec:
        return jsonify({"error": f"维度 '{name}' 未注册"}), 404
    # Path traversal guard
    if not key_val or any(c in key_val for c in ("/", "\\", "..", "\x00")):
        return jsonify({"error": "非法主键"}), 400
    abs_path = spec["path"]
    schema = spec["schema"]
    key = spec["key"]

    rows = _read_dim_rows(abs_path, schema, key, create_if_missing=False)
    if rows is None:
        return jsonify({"error": f"{name}.csv 不存在"}), 404

    original_len = len(rows)
    rows = [r for r in rows if r.get(key, "").strip() != key_val]
    if len(rows) == original_len:
        return jsonify({"error": f"找不到 '{key_val}'"}), 404

    ok, err = _atomic_write_dim(name, abs_path, rows, schema)
    if not ok:
        return jsonify({"error": f"删除失败: {err}"}), 500
    return jsonify({"ok": True})


@bp.route("/api/dim/tasks/next-id", methods=["POST"])
def tasks_next_id():
    """Generate next available task_id for a (product, task, tool, process) tuple."""
    body = request.get_json(silent=True) or {}
    product = (body.get("product") or "").strip()
    task = (body.get("task") or "").strip()
    tool = (body.get("tool") or "").strip()
    process = (body.get("process") or "").strip()
    tid, err = generate_next_task_id(product, task, tool, process)
    if err:
        return jsonify({"ok": False, "suggested": None, "reason": err}), 400
    return jsonify({"ok": True, "suggested": tid})


@bp.route("/api/dim/tasks/translate-empty-process", methods=["POST"])
def tasks_translate_empty_process():
    """批量翻译工序：遍历 tasks.csv，对 process 含中文但 process_en 为空的记录自动翻译。"""
    body = request.get_json(silent=True) or {}
    exclude = set(body.get("exclude_task_ids") or [])
    exclude.discard("")

    spec = _DIM_REGISTRY.get("tasks")
    if not spec:
        return jsonify({"error": "tasks 维表未注册"}), 500

    abs_path = spec["path"]
    schema = spec["schema"]
    key = spec["key"]
    rows = _read_dim_rows(abs_path, schema, key, create_if_missing=False)
    if rows is None:
        return jsonify({"error": "tasks.csv 不存在"}), 404

    _CH_RE = re.compile(r'[一-鿿　-〿＀-￯]')
    translated = 0
    skipped = 0

    for r in rows:
        task_id = (r.get("task_id") or "").strip()
        process = (r.get("process") or "").strip()
        process_en = (r.get("process_en") or "").strip()
        if process_en:
            skipped += 1
            continue
        if not process or not _CH_RE.search(process):
            skipped += 1
            continue
        if task_id and task_id in exclude:
            skipped += 1
            continue
        result = _translate_process_to_en(process)
        if result:
            r["process_en"] = result
            translated += 1
        else:
            skipped += 1

    if translated > 0:
        _atomic_write_dim("tasks", abs_path, rows, schema)

    return jsonify({"ok": True, "translated": translated, "skipped": skipped})

# ── 扩展路由 ──

@bp.route("/api/dim-editable-options", methods=["GET", "POST"])
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



@bp.route("/api/dim/environments/next-id", methods=["POST"])
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



@bp.route("/api/dim/tasks/reorder", methods=["POST"])
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



@bp.route("/api/translate-process", methods=["POST"])
def translate_single_process():
    """单条工序翻译：接收中文工序文本，返回英文翻译结果。
    
    POST body: { text: str }
    返回: { ok: true, result: str }
    """
    body = request.get_json(silent=True) or {}
    text = (body.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text 为空"}), 400
    result = _translate_process_to_en(text)
    return jsonify({"ok": True, "result": result or ""})




