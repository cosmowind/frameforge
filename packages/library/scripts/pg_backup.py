#!/usr/bin/env python3
"""pg_backup.py — 用 SQLAlchemy 导出 video_manager 为 SQL INSERT 文件（兼容版本差异）。"""
import gzip
import glob
import os
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

DB_DSN = os.environ.get("VIDEO_MANAGER_DB_DSN", "")
BACKUP_DIR = "/www/wwwroot/projects/video_manager/runtime/backups/pg"
RETENTION_DAYS = 7
TABLES = ["videos", "recorders", "sd_cards", "tasks", "environments", "app_config"]


def _now_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _dump_table(conn, table: str) -> str:
    rows = conn.execute(text(f"SELECT * FROM {table}")).fetchall()
    if not rows:
        return ""
    cols = list(rows[0]._mapping.keys())
    lines = [f"-- Table: {table}"]
    for r in rows:
        vals = []
        for c in cols:
            v = r[c]
            if v is None:
                vals.append("NULL")
            elif isinstance(v, str):
                escaped = v.replace("'", "''")
                vals.append(f"'{escaped}'")
            elif isinstance(v, (int, float)):
                vals.append(str(v))
            else:
                escaped = str(v).replace("'", "''")
                vals.append(f"'{escaped}'")
        col_list = ", ".join(cols)
        val_list = ", ".join(vals)
        lines.append(f"INSERT INTO {table} ({col_list}) VALUES ({val_list});")
    return "\n".join(lines)


def main():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    engine = create_engine(DB_DSN, poolclass=NullPool, future=True)
    parts = [f"-- Backup: {_now_tag()}", "BEGIN;"]
    with engine.connect() as conn:
        for t in TABLES:
            try:
                sql = _dump_table(conn, t)
                if sql:
                    parts.append(sql)
            except Exception as e:
                print(f"[warn] skip {t}: {e}")
    parts.append("COMMIT;")
    dump = "\n\n".join(parts)
    out_path = os.path.join(BACKUP_DIR, f"video_manager_{_now_tag()}.sql.gz")
    with gzip.open(out_path, "wt", encoding="utf-8") as f:
        f.write(dump)
    print(f"[OK] backup -> {out_path} ({len(dump)} bytes)")
    # cleanup old backups
    files = glob.glob(os.path.join(BACKUP_DIR, "video_manager_*.sql.gz"))
    files.sort()
    for f in files[:-7]:
        os.remove(f)
    print(f"[OK] retained {len(files[-7:])} backups")


if __name__ == "__main__":
    main()
