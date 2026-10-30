"""Restore lost video annotations from backup.

For each path where backup has recorder_id/task_id/env_id but current is empty,
restore from backup to BOTH local CSV and PG.

Conservative: only restores empty fields, never overwrites non-empty values.
"""
from __future__ import annotations
import csv
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

ANN = ['recorder_id', 'task_id', 'env_id']
LATEST_BACKUP = 'runtime/csv_backups/video_manager_20260706_215718.csv'

def norm(p):
    return (p or '').replace('\\', '/').lower()

def main():
    execute = "--execute" in sys.argv
    print(f"[INFO] Source of truth: {LATEST_BACKUP}")

    # Load backup
    with open(LATEST_BACKUP, encoding='utf-8-sig') as f:
        bk_rows = list(csv.DictReader(f))
    bk_by_n = {norm(r['path']): r for r in bk_rows}

    # Load current CSV
    with open('runtime/data/video_manager.csv', encoding='utf-8-sig') as f:
        csv_rows = list(csv.DictReader(f))

    # Load PG
    dsn = os.environ.get('VIDEO_MANAGER_DB_DSN')
    eng = create_engine(dsn, poolclass=NullPool, future=True)
    with eng.connect() as conn:
        pg_rows = conn.execute(text(f"SELECT path, {', '.join(ANN)} FROM videos")).fetchall()
    pg_by_n = {norm(r._mapping['path']): r._mapping for r in pg_rows}

    # Find restore candidates
    csv_restores = []  # (row_idx, field, value)
    pg_restores = []   # (normalized_path, field, value)
    examples_shown = 0

    for path_norm, bk in bk_by_n.items():
        bk_vals = {f: (bk.get(f) or '').strip() for f in ANN}
        if not any(bk_vals.values()):
            continue  # backup itself has no annotation

        # CSV: find any row with matching normalized path; restore empty fields
        for i, r in enumerate(csv_rows):
            if norm(r['path']) != path_norm:
                continue
            for f in ANN:
                cur_v = (r.get(f) or '').strip()
                if bk_vals[f] and not cur_v:
                    csv_restores.append((i, f, bk_vals[f]))

        # PG: restore empty fields (PG paths may have backslash; use ILIKE matching)
        pg_r = pg_by_n.get(path_norm)
        if pg_r:
            for f in ANN:
                pg_v = (pg_r.get(f) or '').strip()
                if bk_vals[f] and not pg_v:
                    pg_restores.append((pg_r['path'], f, bk_vals[f]))

    print(f"\n## 计划操作")
    print(f"  CSV 恢复: {len(csv_restores)} 字段更新")
    print(f"  PG  恢复: {len(pg_restores)} 字段更新")

    # Group by path for display
    by_path_csv = {}
    for i, f, v in csv_restores:
        by_path_csv.setdefault(i, []).append((f, v))
    by_path_pg = {}
    for path, f, v in pg_restores:
        by_path_pg.setdefault(path, []).append((f, v))

    print(f"\n  PG 涉及 {len(by_path_pg)} 个视频路径")
    if by_path_pg:
        for p, fields in list(by_path_pg.items())[:5]:
            print(f"    [{p[-60:]}]")
            for f, v in fields:
                print(f"      {f} = '{v}'")
        if len(by_path_pg) > 5:
            print(f"    …还有 {len(by_path_pg) - 5} 个")

    if not execute:
        print(f"\n[DRY-RUN] Pass --execute to apply.")
        return

    # ── Apply to PG ──
    print(f"\n[EXECUTING] Apply to PG...")
    with eng.connect() as conn:
        for path, fields in by_path_pg.items():
            set_clause = ", ".join(f"{f} = :{i}" for i, (f, _) in enumerate(fields))
            params = {str(i): v for i, (_, v) in enumerate(fields)}
            params["p"] = path
            try:
                res = conn.execute(
                    text(f"UPDATE videos SET {set_clause} WHERE path = :p"),
                    params
                )
                if res.rowcount > 0:
                    print(f"  ✓ PG UPDATE {path[-50:]}: {len(fields)} fields")
            except Exception as e:
                print(f"  ✗ PG UPDATE {path[-50:]} FAILED: {e}", file=sys.stderr)
        conn.commit()

    # ── Apply to local CSV ──
    if csv_restores:
        for i, f, v in csv_restores:
            csv_rows[i][f] = v
        with open('runtime/data/video_manager.csv', 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
            w.writeheader()
            w.writerows(csv_rows)
        print(f"  ✓ CSV: {len(csv_restores)} field updates applied")

    print(f"\n[EXECUTED] csv={len(csv_restores)} pg={len(pg_restores)}")

if __name__ == "__main__":
    main()