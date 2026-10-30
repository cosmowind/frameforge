# ────────────────────────────────────────────────────────────────
# pg_store.py — PostgreSQL 版主表读写，对齐 csv_store 接口
# ────────────────────────────────────────────────────────────────

from __future__ import annotations

import csv
import io
import json
import logging
import os
from datetime import datetime
from typing import List

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from config import BASE_DIR, RUNTIME_DIR, CSV_PATH, DEFAULT_FIELDNAMES
from models import cache
from utils.path_utils import canon_path

logger = logging.getLogger(__name__)


def _get_dsn() -> str | None:
    """从环境变量或配置文件读取数据库连接串。"""
    dsn = os.environ.get("VIDEO_MANAGER_DB_DSN")
    if dsn:
        return dsn
    cfg_path = os.path.join(RUNTIME_DIR, "data", "config.json")
    if os.path.isfile(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            dsn = cfg.get("database", {}).get("dsn")
            if dsn:
                return dsn
        except Exception:
            pass
    return None


def _get_engine():
    """惰性创建 engine（单例）。"""
    dsn = _get_dsn()
    if not dsn:
        raise RuntimeError("VIDEO_MANAGER_DB_DSN 未配置，无法使用 PostgreSQL 模式")
    if not hasattr(_get_engine, "_engine"):
        _get_engine._engine = create_engine(dsn, poolclass=NullPool, future=True)
    return _get_engine._engine


def _row_to_dict(row) -> dict:
    """SQLAlchemy Row -> dict，兼容缺失字段为 ""。"""
    if row is None:
        return {}
    if isinstance(row, dict):
        return dict(row)
    return {k: ("" if v is None else v) for k, v in row._mapping.items()}


def _normalize_row(row: dict) -> dict:
    """按 DEFAULT_FIELDNAMES 对齐字段，缺失补 ""，多余丢弃。path 走 canon_path 规范化。"""
    result = {}
    for fn in DEFAULT_FIELDNAMES:
        val = row.get(fn, "")
        if fn == "path" and isinstance(val, str):
            val = canon_path(val)
        result[fn] = val
    return result


# ── 公共 API（与 csv_store 对齐） ────────────────────────────────

def get_fieldnames() -> list[str]:
    return list(DEFAULT_FIELDNAMES)


def load_config() -> dict:
    """读取 runtime/data/config.json，失败返回空 dict。"""
    cfg_path = os.path.join(RUNTIME_DIR, "data", "config.json")
    if os.path.isfile(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                return json.load(f) or {}
        except Exception as e:
            # 静默失败会让前端表格空白（colConfig=[]），记一条 warning 让 ops 看见
            logger.warning("load_config failed (%s): %s — 前端将退回默认列", type(e).__name__, e)
    return {}


def _read_csv_from_pg() -> List[dict]:
    """直接从 PostgreSQL 读取 videos 表（内部用，不经缓存）。"""
    engine = _get_engine()
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT * FROM videos ORDER BY created_at")).fetchall()
    result = [_normalize_row(_row_to_dict(r)) for r in rows]
    # 读取后同步写入本地 CSV（持久化缓存）
    _sync_local_csv(result)
    return result


def _sync_local_csv(rows: List[dict]) -> None:
    """将数据同步写入本地 CSV 文件（作为持久化缓存）。"""
    try:
        os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
        fieldnames = get_fieldnames()
        with open(CSV_PATH, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        logger.debug("本地 CSV 已同步: %d 条", len(rows))
    except Exception as e:
        logger.warning("同步本地 CSV 失败: %s", e)


def _read_csv_from_local() -> List[dict] | None:
    """从本地 CSV 读取，文件不存在或为空返回 None。"""
    try:
        if not os.path.isfile(CSV_PATH) or os.path.getsize(CSV_PATH) == 0:
            return None
        with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = [_normalize_row(dict(r)) for r in reader]
        return rows if rows else None
    except Exception:
        return None


def _local_csv_age() -> float:
    """返回本地 CSV 文件的年龄（秒），不存在返回 inf。"""
    try:
        return __import__("time").time() - os.path.getmtime(CSV_PATH)
    except Exception:
        return float("inf")


def read_csv() -> List[dict]:
    """优先从本地 CSV 读取（快速），过期则查 PG 并同步本地。"""
    # 本地 CSV 在 TTL 内 → 直接读本地（毫秒级）
    age = _local_csv_age()
    if age < cache.CACHE_TTL:
        local = _read_csv_from_local()
        if local is not None:
            logger.debug("从本地 CSV 加载 (%.0fs < %ds)，%d 条", age, cache.CACHE_TTL, len(local))
            # 同时填充内存缓存（供路径索引等使用）
            cache.fill_videos(local)
            return local
    # 超时或本地不存在 → 查 PG（自动同步本地 CSV）
    logger.debug("本地 CSV 过期 (%.0fs)，查询 PG", age)
    return cache.get_videos(_read_csv_from_pg)


def _canonical_path(p: str) -> str:
    """Path 规范化：所有分隔符转 /、normpath 折叠、lower 大小写不敏感。

    PG 的 unique(path) 约束是字面值匹配；调用方若传入 '/media/videos\\\\x'，
    与已有 '/media/videos/x' 行会变成两条记录（同上操作只更新其中一条，
    scan 又把另一条覆盖回去 —— 「同上翻车」根因）。
    """
    if not isinstance(p, str):
        return p
    return canon_path(p)


def write_csv(rows: List[dict]) -> None:
    """UPSERT 写入 videos 表（存在则更新，不存在则插入），同时同步本地 CSV。

    以 path 为唯一键，支持本地和 PG 共存互不覆盖。
    """
    cache.invalidate_videos()  # 写前先失效缓存
    engine = _get_engine()
    fieldnames = get_fieldnames()

    # 规范化所有 row 的 path —— 避免 D:\\x 与 D:/x 在 PG 中并存造成 UPSERT 漏命中
    norm_rows = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        nr = dict(r)
        if "path" in nr:
            nr["path"] = _canonical_path(nr["path"])
        norm_rows.append(nr)

    # 确保 path 上有 unique 约束（幂等操作）
    # 注意：ON CONFLICT DO UPDATE 不支持 DEFERRABLE 约束作为仲裁者，必须用 NOT DEFERRABLE
    try:
        with engine.begin() as conn:
            # 先尝试删除旧约束（可能带 DEFERRABLE）
            conn.execute(text("ALTER TABLE videos DROP CONSTRAINT IF EXISTS videos_path_key"))
            # 重建为 NOT DEFERRABLE
            conn.execute(text("ALTER TABLE videos ADD CONSTRAINT videos_path_key UNIQUE (path) NOT DEFERRABLE"))
    except Exception:
        pass  # 表不存在等错误，忽略

    if not norm_rows:
        _sync_local_csv([])
        return

    with engine.begin() as conn:
        cols = ", ".join(fieldnames)
        placeholders = ", ".join([f":{fn}" for fn in fieldnames])
        # INSERT ... ON CONFLICT DO UPDATE：增量写入，不丢 PG 中本地没有的行
        stmt = text(f"""
            INSERT INTO videos ({cols}) VALUES ({placeholders})
            ON CONFLICT (path) DO UPDATE SET
            {", ".join([f"{fn} = EXCLUDED.{fn}" for fn in fieldnames])}
        """)
        payload = [{fn: r.get(fn, "") for fn in fieldnames} for r in norm_rows]
        conn.execute(stmt, payload)

    # 写入 PG 成功后同步本地 CSV（也用规范化后的 rows）
    _sync_local_csv(norm_rows)


def _atomic_write_csv(
    path: str,
    rows: List[dict],
    fieldnames: list[str],
    backup_prefix: str = "",
    encoding: str = "utf-8-sig",
) -> None:
    """原子写 CSV 文件（供维表回退/导出用，不改动主表）。"""
    try:
        backup_dir = os.path.join(RUNTIME_DIR, "csv_backups")
        os.makedirs(backup_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"{backup_prefix}_{ts}.csv")
        if os.path.isfile(path) and os.path.getsize(path) > 0:
            import shutil
            shutil.copy2(path, backup_path)
    except Exception:
        pass
    with open(path, "w", newline="", encoding=encoding) as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ── 兼容旧接口（部分路由仍引用这些） ─────────────────────────────

def mark_uploaded(csv_index: int) -> bool:
    """将指定行 uploaded=Yes。"""
    rows = read_csv()
    if 0 <= csv_index < len(rows):
        rows[csv_index]["uploaded"] = "Yes"
        # location_status 由 scan_service 设置，不在上载时修改
        write_csv(rows)
        return True
    return False


def check_file(video_path: str) -> bool:
    return os.path.isfile(video_path)


def marker_path(video_path: str) -> str:
    return video_path + ".uploaded"
