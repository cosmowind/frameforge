"""Restore user-added tasks to runtime/data/tasks.csv + PG.

Source of truth: the UNION of all 122 dim_tasks_*.csv snapshots in
runtime/csv_backups/. For each task_id, keeps the most recent version
(latest by snapshot timestamp).

Default mode: dry-run.  Pass --execute to apply.

Usage:
  cd src
  python -m scripts.restore_user_added_tasks             # dry-run
  python -m scripts.restore_user_added_tasks --execute   # apply
"""
from __future__ import annotations
import csv
import os
import sys
from collections import defaultdict
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

CSV_PATH = "runtime/data/tasks.csv"
PG_TABLE = "tasks"
BACKUP_DIR = "runtime/csv_backups"
BACKUP_GLOB = "dim_tasks_*.csv"

def load_csv(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def find_latest_version_per_task() -> dict[str, dict]:
    """Return {task_id: row} using the most recent snapshot that has each task."""
    candidates = []
    for f in sorted(os.listdir(BACKUP_DIR)):
        if f.startswith(BACKUP_GLOB.split("*")[0]) and f.endswith(".csv"):
            ts = f.replace(BACKUP_GLOB.split("*")[0], "").replace(".csv", "")
            candidates.append((ts, os.path.join(BACKUP_DIR, f)))
    # Sort ascending (oldest first) so the LAST occurrence wins (we overwrite)
    candidates.sort()
    best: dict[str, dict] = {}
    for _ts, path in candidates:
        for r in load_csv(path):
            best[r["task_id"]] = r
    return best

def main():
    execute = "--execute" in sys.argv
    backup = find_latest_version_per_task()
    print(f"[INFO] Source of truth: union of {len([f for f in os.listdir(BACKUP_DIR) if f.startswith('dim_tasks_')])} dim_tasks_*.csv snapshots")
    print(f"[INFO] Combined unique task_id: {len(backup)}")

    current_csv = {r["task_id"]: r for r in load_csv(CSV_PATH)}
    print(f"[INFO] Current tasks.csv: {len(current_csv)}")

    # Find missing task_ids
    missing = {tid: row for tid, row in backup.items() if tid not in current_csv}
    print(f"\n{'='*72}\n## 缺失 task 列表（pre 有，cur 缺）\n{'='*72}")
    print(f"  共 {len(missing)} 个\n")
    for tid in sorted(missing):
        r = missing[tid]
        print(f"  {tid}")
        for f in ("scene", "product", "task", "process", "location_address", "environment",
                  "business_name", "tool"):
            v = r.get(f, "") or ""
            if v:
                print(f"      {f} = {v!r}")
        print()

    if not missing:
        print("[OK] 没有缺失 task")
        return

    if not execute:
        print(f"[DRY-RUN] Pass --execute to apply.")
        return

    # ── Apply to PG ──
    dsn = os.environ.get("VIDEO_MANAGER_DB_DSN")
    if not dsn:
        print("VIDEO_MANAGER_DB_DSN not set; cannot apply to PG", file=sys.stderr)
        sys.exit(2)
    eng = create_engine(dsn, poolclass=NullPool, future=True)
    with eng.connect() as conn:
        # 拿 PG 中已有的 task_id，避免重复
        pg_existing = {r._mapping["task_id"] for r in
                       conn.execute(text(f"SELECT task_id FROM {PG_TABLE}")).fetchall()}
        print(f"\n[INFO] PG 中现有 task_id: {len(pg_existing)}")
        applied_pg = 0
        for tid, r in missing.items():
            if tid in pg_existing:
                print(f"  [SKIP-PG] {tid} (already in PG)")
                continue
            cols = list(r.keys())
            vals = [r[c] for c in cols]
            col_str = ", ".join(f'"{c}"' for c in cols)
            ph = ", ".join(f":{i}" for i in range(len(cols)))
            params = {str(i): v for i, v in enumerate(vals)}
            try:
                conn.execute(text(f"INSERT INTO {PG_TABLE} ({col_str}) VALUES ({ph})"), params)
                applied_pg += 1
            except Exception as e:
                print(f"  PG INSERT {tid} FAILED: {e}", file=sys.stderr)
        conn.commit()
        print(f"[EXECUTED] PG: {applied_pg} task rows inserted")

    # ── Apply to CSV ──
    rows = list(load_csv(CSV_PATH))
    fieldnames = list(rows[0].keys()) if rows else []
    existing_tids = {r["task_id"] for r in rows}
    applied_csv = 0
    for tid, r in missing.items():
        if tid in existing_tids:
            print(f"  [SKIP-CSV] {tid} (already in CSV)")
            continue
        rows.append(r)
        applied_csv += 1
    with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"[EXECUTED] CSV: {applied_csv} task rows appended to {CSV_PATH}")

if __name__ == "__main__":
    main()
