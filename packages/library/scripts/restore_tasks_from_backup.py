"""Restore tasks from latest backup as source of truth.

Operations:
1. INSERT missing task rows (e.g. d55b_d6bd7e25_f97b_001) into PG + local CSV
2. UPDATE polluted fields (scene/location_address/environment/facility_venue)
   where backup has Chinese but current CSV/PG has English.

Source of truth: dim_tasks_<LATEST_BACKUP_WITH_CHINESE>.csv
Default mode: dry-run. Pass --execute to apply.
"""
from __future__ import annotations
import csv
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

BACKUP_GLOB = "dim_tasks_*.csv"
BACKUP_DIR = "runtime/csv_backups"
CSV_PATH = "runtime/data/tasks.csv"
PG_TABLE = "tasks"

# 4 fields that get polluted (English overwrite)
POLLUTABLE_FIELDS = ["scene", "location_address", "environment", "facility_venue"]
# Fields that we know are stable Chinese in current state — never overwrite these
STABLE_FIELDS = ["product", "task", "tool", "process", "process_en",
                 "difficulty", "business_type", "business_name",
                 "environment_description", "environment_description_en", "notes"]

def has_chinese(s: str) -> bool:
    return any('一' <= ch <= '鿿' for ch in s)

def is_ascii_only(s: str) -> bool:
    return all(ord(ch) < 128 for ch in s) if s else True

def find_latest_backup() -> str:
    """Pick backup where d55b still existed — i.e. latest pre-140104 backup."""
    # We know the timeline from previous run; pick the latest with Chinese in scene col
    import glob
    candidates = sorted(glob.glob(os.path.join(BACKUP_DIR, BACKUP_GLOB)))
    # walk newest → oldest, pick first that has Chinese in scene col for at least one row
    for path in reversed(candidates):
        try:
            with open(path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if has_chinese(row.get("scene", "") or ""):
                        return path
        except Exception:
            continue
    return candidates[-1] if candidates else None

def load_csv(path: str) -> list[dict]:
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def escape_sql(v: str) -> str:
    return v.replace("'", "''")

def main():
    execute = "--execute" in sys.argv
    # Conservative: only restore the specific task the user explicitly asked about.
    # Pass --include-all-missing to restore every row in backup that current CSV/PG lacks.
    target_only = "--target-only" in sys.argv
    target_task_id = "d55b_d6bd7e25_f97b_001"
    backup = find_latest_backup()
    print(f"[INFO] Source of truth (backup): {backup}")
    print(f"[INFO] Mode: {'restore all missing' if not target_only else f'only restore {target_task_id}'}")
    if not backup:
        print("No backup found!", file=sys.stderr)
        sys.exit(2)

    backup_rows = {r["task_id"]: r for r in load_csv(backup)}
    current_csv = {r["task_id"]: r for r in load_csv(CSV_PATH)}

    dsn = os.environ.get("VIDEO_MANAGER_DB_DSN")
    if not dsn:
        print("VIDEO_MANAGER_DB_DSN not set", file=sys.stderr); sys.exit(2)
    eng = create_engine(dsn, poolclass=NullPool, future=True)

    inserts_csv = []    # rows to append to local CSV
    inserts_pg = []     # rows to INSERT into PG
    updates_csv = []    # (task_id, field, new_value)
    updates_pg = []     # (task_id, field, new_value)

    with eng.connect() as conn:
        pg_rows = {r._mapping["task_id"]: dict(r._mapping) for r in
                   conn.execute(text(f"SELECT * FROM {PG_TABLE}")).fetchall()}

        # 1) Find rows in backup but not in current CSV → need INSERT
        for tid, bk_row in backup_rows.items():
            if target_only and tid != target_task_id:
                continue
            if tid not in current_csv:
                inserts_csv.append(bk_row)
            if tid not in pg_rows:
                inserts_pg.append(bk_row)

        # 2) For shared task_ids, restore polluted fields
        for tid in sorted(set(backup_rows.keys()) & set(current_csv.keys())):
            bk = backup_rows[tid]
            cur = current_csv[tid]
            for field in POLLUTABLE_FIELDS:
                bk_v = bk.get(field, "") or ""
                cur_v = cur.get(field, "") or ""
                # Pollution: backup has Chinese, current is ASCII or empty
                if has_chinese(bk_v) and (not cur_v or is_ascii_only(cur_v)) and cur_v != bk_v:
                    updates_csv.append((tid, field, bk_v))
                # Same for PG
                pg_v = (pg_rows.get(tid, {}) or {}).get(field, "") or ""
                if has_chinese(bk_v) and (not pg_v or is_ascii_only(pg_v)) and pg_v != bk_v:
                    updates_pg.append((tid, field, bk_v))

    # ── Print summary ──
    print(f"\n{'='*70}")
    print(f"## 计划操作")
    print(f"{'='*70}")
    print(f"  备份含 {len(backup_rows)} 行；当前 CSV {len(current_csv)} 行；PG {len(pg_rows)} 行")
    print(f"  INSERT 缺失行 → CSV: {len(inserts_csv)}  PG: {len(inserts_pg)}")
    print(f"  UPDATE 受污染字段 → CSV: {len(updates_csv)}  PG: {len(updates_pg)}")
    print()

    # Show INSERT plan
    if inserts_pg:
        print(f"-- INSERT 缺失 task（PG + CSV 同步插入）--")
        for r in inserts_pg:
            print(f"   {r['task_id']}  scene='{r.get('scene','')}' product='{r.get('product','')}' ...")

    # Show UPDATE plan grouped by task
    if updates_pg:
        print(f"\n-- UPDATE 受污染字段（从备份恢复中文）--")
        by_tid = {}
        for tid, field, val in updates_pg:
            by_tid.setdefault(tid, []).append((field, val))
        for tid, changes in sorted(by_tid.items()):
            print(f"   [{tid}]")
            for field, val in changes:
                print(f"      {field} = '{val}'")

    if not execute:
        print(f"\n[DRY-RUN] Pass --execute to apply.")
        return

    # ── Apply to PG ──
    with eng.connect() as conn:
        for r in inserts_pg:
            cols = list(r.keys())
            vals = [r[c] for c in cols]
            col_str = ", ".join(f'"{c}"' for c in cols)
            ph = ", ".join(f":{i}" for i in range(len(cols)))
            params = {str(i): v for i, v in enumerate(vals)}
            try:
                conn.execute(text(f"INSERT INTO {PG_TABLE} ({col_str}) VALUES ({ph})"), params)
                print(f"  PG INSERT {r['task_id']}")
            except Exception as e:
                print(f"  PG INSERT {r['task_id']} FAILED: {e}", file=sys.stderr)
        # UPDATEs (grouped per task for fewer round trips)
        by_tid = {}
        for tid, field, val in updates_pg:
            by_tid.setdefault(tid, []).append((field, val))
        for tid, changes in by_tid.items():
            set_clause = ", ".join(f"{field} = :{i}" for i, (field, _) in enumerate(changes))
            params = {str(i): v for i, (_, v) in enumerate(changes)}
            params["tid"] = tid
            try:
                conn.execute(text(f"UPDATE {PG_TABLE} SET {set_clause} WHERE task_id = :tid"), params)
                print(f"  PG UPDATE {tid}: {len(changes)} fields")
            except Exception as e:
                print(f"  PG UPDATE {tid} FAILED: {e}", file=sys.stderr)
        conn.commit()

    # ── Apply to local CSV ──
    if inserts_csv or updates_csv:
        all_rows = list(load_csv(CSV_PATH))
        # INSERT
        for r in inserts_csv:
            all_rows.append(r)
        # UPDATE in-place
        idx = {r["task_id"]: i for i, r in enumerate(all_rows)}
        for tid, field, val in updates_csv:
            if tid in idx:
                all_rows[idx[tid]][field] = val
        # Write back with BOM preserved
        with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
            w.writeheader()
            w.writerows(all_rows)
        print(f"  CSV: +{len(inserts_csv)} inserts, ~{len(updates_csv)} field updates")

    print(f"\n[EXECUTED] inserts_csv={len(inserts_csv)} inserts_pg={len(inserts_pg)} "
          f"updates_csv={len(updates_csv)} updates_pg={len(updates_pg)}")

if __name__ == "__main__":
    main()