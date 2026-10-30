# ────────────────────────────────────────────────────────────────
# dim_registry.py — 维表注册表 CRUD 辅助函数
# 拆分自 app.py（S3）
# ────────────────────────────────────────────────────────────────

import csv
import os
import re

from config import BASE_DIR, _CSV_INJECTION_LEAD, _DIM_REGISTRY
from models.csv_store import _atomic_write_csv


def resolve_dim(name):
    """Resolve a dim name from registry. Returns (abs_path, schema, key) or raises NotFound."""
    spec = _DIM_REGISTRY.get(name)
    if not spec:
        return None, None, None
    abs_path = os.path.join(BASE_DIR, spec["path"])
    return abs_path, spec["schema"], spec["key"]


def read_dim_rows(abs_path, schema, key, create_if_missing):
    """Read dim CSV; if missing and create_if_missing=True, create empty file with header."""
    if not os.path.exists(abs_path):
        if not create_if_missing:
            return None  # signal "not found"
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", newline="", encoding="utf-8-sig") as f:
            csv.DictWriter(f, fieldnames=schema).writeheader()
        return []
    with open(abs_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            # Coerce: any missing columns get ""; any extra columns get dropped
            cleaned = {fn: row.get(fn, "") for fn in schema}
            rows.append(cleaned)
    return rows


def validate_dim_row(name, incoming, schema, validators):
    """Return (cleaned_dict, errors_list). CSV-injection guard on free text."""
    errors = []
    cleaned = {}
    for fn in schema:
        val = incoming.get(fn, "")
        if isinstance(val, str):
            val = val.strip()
        # CSV-injection guard: reject formula-like leading chars in string fields
        if isinstance(val, str) and val and val[0] in _CSV_INJECTION_LEAD:
            val = "'" + val  # prepend single-quote (Excel 显示为字面量)
        cleaned[fn] = val if val is not None else ""
    # Field-level validators
    if validators:
        for rule, spec in validators.items():
            if rule.endswith("_required"):
                field = rule[:-len("_required")]
                if field in schema and not cleaned.get(field, ""):
                    errors.append(f"{field} 不能为空")
            elif rule in schema:
                val = cleaned.get(rule, "")
                if isinstance(spec, str) and spec.startswith("^"):
                    if val and not re.match(spec, val):
                        errors.append(f"{rule} 格式错误（应匹配 {spec}）")
                elif isinstance(spec, set):
                    if val and val not in spec:
                        errors.append(f"{rule} 必须是 {sorted(spec)} 之一")
    return cleaned, errors


def atomic_write_dim(name, abs_path, rows, schema):
    """原子写入维表 CSV（备份 + 替换）。"""
    _atomic_write_csv(abs_path, rows, schema, backup_prefix=f"dim_{name}")
