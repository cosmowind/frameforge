"""data_helpers — private helper functions shared by data_routes and cleanup_routes."""

import datetime
import os
import re

from config import USE_PG, _DIM_REGISTRY

if USE_PG:
    from models.pg_dim import read_dim_rows as _read_dim_rows
else:
    from models.dim_registry import read_dim_rows as _read_dim_rows


def _extract_date_from_path(path):
    """Extract MMDD date key from path (for hmd_cache structure)."""
    parts = os.path.normpath(path).split(os.sep)
    for part in reversed(parts):
        if len(part) == 4 and part.isdigit():
            return part
    return ""


def parse_history_date_from_filename(filename):
    """Parse date from historical CSV filename like video_manager0517-1.csv."""
    match = re.search(r"(\d{2})(\d{2})", filename)
    if match:
        month, day = match.groups()
        year = datetime.datetime.now().year
        try:
            return datetime.datetime(year, int(month), int(day)).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return datetime.datetime.now().strftime("%Y-%m-%d")


def _auto_upsert_hmd_devices_to_sd_cards(hmd_folders):
    """Auto-create sd_cards dimension records for new HMD devices (upsert, 不丢已有记录)。"""
    if not hmd_folders:
        return
    if not USE_PG:
        _auto_upsert_hmd_devices_to_sd_cards_csv(hmd_folders)
        return
    # PG 路径：直接 upsert 单条，不依赖 atomic_write_dim 的全量 TRUNCATE
    # SD 卡表主键是 volume_serial，device_id 无唯一约束，所以先查后插
    try:
        from models.pg_dim import _get_engine
        from sqlalchemy import text
        engine = _get_engine()
        for u in hmd_folders:
            meta = u.get("metadata") or {}
            dev = (meta.get("devices") or [{}])[0]
            dev_id = (dev.get("identity", {}).get("device_id", "") or "").strip()
            if not dev_id:
                continue
            # 先查后插：device_id 已存在则跳过
            with engine.begin() as conn:
                exists = conn.execute(
                    text("SELECT 1 FROM sd_cards WHERE device_id = :dev_id LIMIT 1"),
                    {"dev_id": dev_id}
                ).fetchone()
                if not exists:
                    conn.execute(text("""
                        INSERT INTO sd_cards (device_id, capture_mode, notes)
                        VALUES (:dev_id, 'stereo', 'auto-registered from HMD scan')
                    """), {"dev_id": dev_id})
    except Exception as e:
        print(f"[_auto_upsert_hmd_devices] error: {e}")


def _auto_upsert_hmd_devices_to_sd_cards_csv(hmd_folders):
    """CSV 模式的 fallback（使用 atomic_write_dim 全量写入）。"""
    spec = _DIM_REGISTRY.get("sd_cards")
    if not spec:
        return
    abs_path = spec["path"]
    rows = _read_dim_rows(abs_path, spec["schema"], spec["key"], create_if_missing=True) or []
    existing_ids = {r.get("device_id", "").strip() for r in rows}
    for u in hmd_folders:
        meta = u.get("metadata") or {}
        dev = (meta.get("devices") or [{}])[0]
        dev_id = (dev.get("identity", {}).get("device_id", "") or "").strip()
        if not dev_id or dev_id in existing_ids:
            continue
        existing_ids.add(dev_id)
        rows.append({"device_id": dev_id, "capture_mode": "stereo",
                     "notes": "auto-registered from HMD scan"})
    if len(rows) > len(existing_ids):
        from models.dim_registry import atomic_write_dim as _atomic_write_dim
        _atomic_write_dim("sd_cards", abs_path, rows, spec["schema"])


def _auto_upsert_data_devices_to_sd_cards(data_folders):
    """Auto-create sd_cards dimension records for new Data devices (upsert, 不丢已有记录)。"""
    if not data_folders:
        return
    if not USE_PG:
        _auto_upsert_data_devices_to_sd_cards_csv(data_folders)
        return
    try:
        from models.pg_dim import _get_engine
        from sqlalchemy import text
        engine = _get_engine()
        for d in data_folders:
            dev_short = (d.get("device_short") or "").strip()
            if not dev_short:
                continue
            with engine.begin() as conn:
                exists = conn.execute(
                    text("SELECT 1 FROM sd_cards WHERE device_id = :dev_id LIMIT 1"),
                    {"dev_id": dev_short}
                ).fetchone()
                if not exists:
                    conn.execute(text("""
                        INSERT INTO sd_cards (device_id, capture_mode, notes)
                        VALUES (:dev_id, 'single', 'auto-registered from Data scan')
                    """), {"dev_id": dev_short})
    except Exception as e:
        print(f"[_auto_upsert_data_devices] error: {e}")


def _auto_upsert_data_devices_to_sd_cards_csv(data_folders):
    """CSV 模式的 fallback。"""
    spec = _DIM_REGISTRY.get("sd_cards")
    if not spec:
        return
    abs_path = spec["path"]
    rows = _read_dim_rows(abs_path, spec["schema"], spec["key"], create_if_missing=True) or []
    existing_ids = {r.get("device_id", "").strip() for r in rows}
    for d in data_folders:
        dev_short = (d.get("device_short") or "").strip()
        if not dev_short or dev_short in existing_ids:
            continue
        existing_ids.add(dev_short)
        rows.append({"device_id": dev_short, "capture_mode": "single",
                     "notes": "auto-registered from Data scan"})
    if len(rows) > len(existing_ids):
        from models.dim_registry import atomic_write_dim as _atomic_write_dim
        _atomic_write_dim("sd_cards", abs_path, rows, spec["schema"])


def _get_size_mb_per_min_from_service():
    """Proxy to data_service to avoid circular import."""
    from services.data_service import get_size_mb_per_min as _g
    return _g()
