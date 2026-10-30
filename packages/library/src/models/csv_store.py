# ────────────────────────────────────────────────────────────────
# csv_store.py — CSV 主表读写、排序、配置字段管理
# 拆分自 app.py（S4）
# ────────────────────────────────────────────────────────────────

import csv
import json
import os
import shutil as _shutil
from datetime import datetime

from config import RUNTIME_DIR, CSV_PATH, CONFIG_PATH, DEFAULT_FIELDNAMES


def load_config():
    """读取 config.json，返回 dict。文件不存在时返回空 dict。"""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def get_fieldnames():
    """Return CSV column order. Always merge with DEFAULT_FIELDNAMES so
    any newly added columns (file_type, device_id, ...) are present
    even if config.json was last saved before they were added."""
    config = load_config()
    cfg_fields = config.get("fieldnames") or list(DEFAULT_FIELDNAMES)
    # Union: keep config.json order first, then append any defaults not in it
    seen = set(cfg_fields)
    merged = list(cfg_fields)
    for fn in DEFAULT_FIELDNAMES:
        if fn not in seen:
            merged.append(fn)
            seen.add(fn)
    return merged


def get_fieldnames_cached():
    """Get fieldnames, cached at request time so config changes take effect."""
    return get_fieldnames()


def read_csv():
    """读取 video_manager.csv，返回 list[dict]。文件不存在时返回空列表。"""
    if not os.path.exists(CSV_PATH):
        return []
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return [row for row in reader]


def write_csv(rows):
    """Write video_manager.csv atomically (10 份备份 + os.replace)."""
    fieldnames = get_fieldnames()
    _atomic_write_csv(CSV_PATH, rows, fieldnames, backup_prefix="video_manager")


def _atomic_write_csv(path, rows, fieldnames, backup_prefix="data"):
    """Generic atomic CSV write with per-path backup rotation.

    - Backs up the current file (if non-empty) to csv_backups/<prefix>_<ts>.csv
    - Keeps the latest 10 backups per prefix (other prefixes unaffected)
    - Writes to <path>.tmp then os.replace for atomic swap
    """
    try:
        backup_dir = os.path.join(RUNTIME_DIR, "csv_backups")
        os.makedirs(backup_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"{backup_prefix}_{ts}.csv")
        if os.path.exists(path) and os.path.getsize(path) > 0:
            _shutil.copy2(path, backup_path)
        # Trim backups matching this prefix to last 10
        prefix_prefix = f"{backup_prefix}_"
        backups = sorted(
            fn for fn in os.listdir(backup_dir)
            if fn.startswith(prefix_prefix) and fn.endswith(".csv")
        )
        while len(backups) > 10:
            os.remove(os.path.join(backup_dir, backups[0]))
            backups.pop(0)
    except Exception:
        pass  # 备份失败不阻塞写入
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(tmp_path, path)  # 原子替换
    except Exception:
        # 清理残留的临时文件
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        raise
