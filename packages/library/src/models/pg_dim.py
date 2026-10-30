# ────────────────────────────────────────────────────────────────
# pg_dim.py — PostgreSQL 版维表操作，对齐 dim_registry 接口
# ────────────────────────────────────────────────────────────────

from __future__ import annotations

import logging
import os
import re

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from config import BASE_DIR, _CSV_INJECTION_LEAD, _DIM_REGISTRY
from models import cache

logger = logging.getLogger(__name__)


def _get_engine():
    dsn = os.environ.get("VIDEO_MANAGER_DB_DSN")
    if not dsn:
        raise RuntimeError("VIDEO_MANAGER_DB_DSN 未配置")
    if not hasattr(_get_engine, "_engine"):
        _get_engine._engine = create_engine(dsn, poolclass=NullPool, future=True)
    return _get_engine._engine


# 主键字段名 -> PostgreSQL 表名映射
_KEY_TO_TABLE = {
    "id": "recorders",
    "volume_serial": "sd_cards",
    "task_id": "tasks",
    "env_id": "environments",
}
# 主键字段名 -> 维表名（反向映射，用于缓存 key）
_KEY_TO_DIM_NAME = {v: k for k, v in _KEY_TO_TABLE.items()}
# 维度名 -> PostgreSQL 表名映射
_NAME_TO_TABLE = {
    "recorders": "recorders",
    "sd_cards": "sd_cards",
    "tasks": "tasks",
    "environments": "environments",
}


def resolve_dim(name: str):
    """返回 (abs_path, schema, key)，与 dim_registry 兼容；path 为模拟路径。"""
    spec = _DIM_REGISTRY.get(name)
    if not spec:
        return None, None, None
    abs_path = os.path.join(BASE_DIR, spec["path"])
    return abs_path, spec["schema"], spec["key"]


def _read_dim_from_pg(table: str, schema: list[str], key: str) -> list[dict]:
    """直接从 PostgreSQL 读取维表（内部用，不经缓存）。"""
    engine = _get_engine()
    try:
        with engine.connect() as conn:
            cols = ", ".join(schema)
            rows = conn.execute(text(f"SELECT {cols} FROM {table} ORDER BY {key}")).fetchall()
            result = []
            for r in rows:
                row = {fn: ("" if v is None else v) for fn, v in r._mapping.items()}
                result.append(row)
            return result
    except Exception as e:
        logger.warning(f"读取维表 {table} 失败: {e}")
        return []


def read_dim_rows(abs_path, schema, key, create_if_missing: bool = True):
    """从缓存读取维表，过期自动刷新。"""
    table = _KEY_TO_TABLE.get(key)
    if not table:
        return []
    return cache.get_dim(table, lambda: _read_dim_from_pg(table, schema, key))


def validate_dim_row(name: str, incoming: dict, schema: list[str], validators: dict | None = None):
    """校验并清洗一行维表数据，返回 (cleaned_dict, errors_list)。"""
    errors = []
    cleaned = {}
    for fn in schema:
        val = incoming.get(fn, "")
        if isinstance(val, str):
            val = val.strip()
        if isinstance(val, str) and val and val[0] in _CSV_INJECTION_LEAD:
            val = "'" + val
        cleaned[fn] = val if val is not None else ""
    if validators:
        for rule, spec in validators.items():
            if rule.endswith("_required"):
                field = rule[: -len("_required")]
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


def atomic_write_dim(name: str, abs_path: str, rows: list[dict], schema: list[str]) -> None:
    """原子写入维表：先写 PostgreSQL，再同步 CSV（避免 PG 和 CSV 不一致）。"""
    table = _NAME_TO_TABLE.get(name)
    if not table:
        raise ValueError(f"未知维表: {name}")
    cache.invalidate_dim(table)  # 写前先失效缓存
    engine = _get_engine()
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY"))
        if rows:
            cols = ", ".join(schema)
            placeholders = ", ".join([f":{fn}" for fn in schema])
            stmt = text(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})")
            payload = [{fn: r.get(fn, "") for fn in schema} for r in rows]
            conn.execute(stmt, payload)
    # 同步写 CSV（避免 PG 与 CSV 不一致）
    from models.pg_store import _atomic_write_csv
    _atomic_write_csv(abs_path, rows, schema, backup_prefix=f"dim_{name}")
