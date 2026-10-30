"""Restore lost annotations on runtime/data/video_manager.csv + PG using
video_manager.csv.before_focused.csv (07-06 17:08, 606 rows, 271 unique paths,
pre-dedup, full source_device history) as the source of truth.

Strategy
--------
The dedup operation in commit c10182d collapsed multi-row (multi-device) entries
into a single row, but in many cases kept the wrong row.  Specifically:

  * 132 `otherPC_local` rows were absorbed into `thisPC_local` / `otherPC_history`
  * 64 paths lost their `uploaded=Yes` annotation
  * 61–64 paths lost their `task_id` / `env_id` / `recorder_id` annotation
  * 1 path was overwritten by the other device (PC-20250831ZJSG):
        /media/0621/data/sample_session_00000
    pre  : file_type=data  extra='Data session · 1 files · 104 MB'
    cur  : file_type=hmd   extra='HMD session · 1 parts · 104 MB · mcap' source=PC-20250831ZJSG

For every path that exists in BOTH pre and cur:
  - For each annotation field, if pre had a non-empty value and cur is empty,
    restore it from the highest-priority pre row.
  - For the 1 path overwritten by the other device, restore the pre file_type,
    extra_description, and clear source_device.

Default mode: dry-run.  Pass --execute to apply to CSV + PG.

Usage
-----
  cd src
  python -m scripts.restore_video_manager_from_pre             # dry-run
  python -m scripts.restore_video_manager_from_pre --execute   # apply
"""
from __future__ import annotations
import csv
import os
import sys
from collections import defaultdict
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

CSV_PATH = "runtime/data/video_manager.csv"
PRE_SNAPSHOT = "runtime/data/video_manager.csv.before_focused.csv"
PG_TABLE = "videos"

# Fields that we know were locally-annotated and are safe to restore from pre
# `duration_sec` is intentionally excluded: it was deliberately re-measured from
# status.json in commit 108dab3 (and refined in cb1646e).  Pre-snapshot values
# are 1–40% smaller because the original measurement came from a different
# file state.  We do NOT want to regress the more-accurate current values.
RESTORE_FIELDS = ["uploaded", "extra_description", "score",
                  "recorder_id", "task_id", "env_id", "device_id",
                  "file_type", "original_history_date"]
# We do NOT overwrite location_status automatically — status changes are
# already documented in pre and were the result of the dedup.  We only fix the
# 1 known regression (the sample_session path).

PRIORITY = ["thisPC_local", "thisPC_history", "otherPC_local", "otherPC_history"]
# When multiple pre rows for the same path have a non-empty value for the same
# field, prefer thisPC_local (most local knowledge), then thisPC_history, etc.

# The one path that was overwritten by the OTHER device (PC-20250831ZJSG).
# Restoring its pre values is unambiguous because the pre snapshot is the only
# place that has the correct file_type / extra_description for this path.
OTHER_DEVICE_OVERRIDE_PATHS = {
    "/media/0621/data/sample_session_00000": {
        # These three fields are what the pre snapshot has, and the cur snapshot
        # was clobbered by the other device's full sync.
        "file_type": "data",
        "extra_description": "Data session · 1 files · 104 MB",
        "source_device": "",  # blank out so we don't carry the other-device tag forward
    },
}

def load(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f)), f.read(3)  # rows + BOM flag

ANNOTATION_RICH_FIELDS = ["uploaded", "task_id", "env_id", "recorder_id",
                          "duration_sec", "extra_description", "file_type",
                          "device_id", "score", "original_history_date"]

def row_richness(r):
    """Count of non-empty annotation fields in a row."""
    return sum(1 for f in ANNOTATION_RICH_FIELDS if (r.get(f, "") or "").strip())

def pick_best_pre(pre_rows, field):
    """Return the best non-empty value of `field` from a list of pre rows.

    Sort key:
      1. status priority (thisPC_local > thisPC_history > otherPC_local > otherPC_history)
      2. row richness (more annotation fields filled = better)
      3. For uploaded specifically, "Yes" > "No" (definitive positive)
    """
    candidates = []
    for r in pre_rows:
        v = r.get(field, "") or ""
        if v:
            status = r.get("location_status", "")
            prio = PRIORITY.index(status) if status in PRIORITY else 99
            # Tie-breaker: prefer the row that has more annotations filled in
            richness = row_richness(r)
            # Special: for uploaded, "Yes" beats "No" if both candidates exist
            uploaded_pref = 0
            if field == "uploaded" and v == "Yes":
                uploaded_pref = -1
            candidates.append((prio, -richness, uploaded_pref, v))
    if not candidates:
        return ""
    candidates.sort()
    return candidates[0][3]

def main():
    execute = "--execute" in sys.argv

    if not os.path.exists(PRE_SNAPSHOT):
        print(f"ERROR: pre snapshot not found: {PRE_SNAPSHOT}", file=sys.stderr)
        sys.exit(2)
    pre_rows, _ = load(PRE_SNAPSHOT)
    cur_rows, _ = load(CSV_PATH)

    pre_by_path = defaultdict(list)
    for r in pre_rows:
        pre_by_path[r["path"]].append(r)
    cur_by_path = defaultdict(list)
    for r in cur_rows:
        cur_by_path[r["path"]].append(r)

    csv_updates = []  # list of (path, field, new_value)
    pg_updates = []   # list of (path, field, new_value)
    other_overrides = []

    for p in sorted(set(pre_by_path.keys()) & set(cur_by_path.keys())):
        pre_list = pre_by_path[p]
        cur_list = cur_by_path[p]
        cur_values = {f: {r.get(f, "") or "" for r in cur_list} for f in RESTORE_FIELDS}

        for f in RESTORE_FIELDS:
            best = pick_best_pre(pre_list, f)
            if not best:
                continue
            # Special handling for the 1 path that was overwritten by the other device
            if p in OTHER_DEVICE_OVERRIDE_PATHS and f in OTHER_DEVICE_OVERRIDE_PATHS[p]:
                new_val = OTHER_DEVICE_OVERRIDE_PATHS[p][f]
                if cur_list[0].get(f, "") != new_val:
                    other_overrides.append((p, f, new_val))
                continue
            # If cur already has this value, skip
            if best in cur_values[f]:
                continue
            # Cur doesn't have this value → restore
            csv_updates.append((p, f, best))
            pg_updates.append((p, f, best))

    # ── Print plan ──
    print(f"\n{'='*72}\n## 恢复计划\n{'='*72}")
    print(f"  pre  snapshot : {PRE_SNAPSHOT}  ({len(pre_rows)} rows, {len(pre_by_path)} paths)")
    print(f"  cur  CSV      : {CSV_PATH}  ({len(cur_rows)} rows, {len(cur_by_path)} paths)")
    print(f"  字段恢复: {len(csv_updates)} 条 (CSV + PG 同步)")
    print(f"  另一台设备覆盖回退: {len(other_overrides)} 条 (CSV + PG 同步)")

    from collections import Counter
    by_field = Counter(f for _, f, _ in csv_updates)
    print(f"\n  按字段分:")
    for f, c in by_field.most_common():
        print(f"    {f}: {c}")

    print(f"\n  字段恢复样本 (前 8 条):")
    for p, f, v in csv_updates[:8]:
        print(f"    [{f}] {p}  →  {v!r}")

    print(f"\n  另一台设备覆盖回退样本:")
    for p, f, v in other_overrides:
        print(f"    [{f}] {p}  →  {v!r}")

    if not execute:
        print(f"\n[DRY-RUN] Pass --execute to apply.")
        return

    # ── Apply to local CSV (BOM preserved) ──
    rows = list(cur_rows)
    fieldnames = list(rows[0].keys()) if rows else []
    idx = {r["path"]: i for i, r in enumerate(rows)}
    applied_csv = 0
    for p, f, v in csv_updates:
        if p in idx:
            rows[idx[p]][f] = v
            applied_csv += 1
    for p, f, v in other_overrides:
        if p in idx:
            rows[idx[p]][f] = v
            applied_csv += 1
    with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"\n[EXECUTED] CSV 写入: {applied_csv} 个字段更新")

    # ── Apply to PG ──
    dsn = os.environ.get("VIDEO_MANAGER_DB_DSN")
    if not dsn:
        print("  (跳过 PG) VIDEO_MANAGER_DB_DSN 未设置")
        return
    eng = create_engine(dsn, poolclass=NullPool, future=True)
    applied_pg = 0
    with eng.connect() as conn:
        # Build a path → pg_id map
        pg_map = {}
        for row in conn.execute(text(f"SELECT id, path FROM {PG_TABLE}")).fetchall():
            pg_map[row._mapping["path"]] = row._mapping["id"]

        for p, f, v in csv_updates + other_overrides:
            pg_id = pg_map.get(p)
            if pg_id is None:
                continue
            conn.execute(text(f"UPDATE {PG_TABLE} SET {f} = :v WHERE id = :id"),
                         {"v": v, "id": pg_id})
            applied_pg += 1
        conn.commit()
    print(f"[EXECUTED] PG 写入: {applied_pg} 个字段更新")

if __name__ == "__main__":
    main()
