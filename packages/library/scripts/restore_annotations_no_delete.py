"""Restore previously-filled annotations to PG and CSV.

Root cause: 130 paths exist twice in PG — once with backslash-style path
('/media/videos\\0625\\...') and empty annotations, once with forward-slash
path and rich annotations.  They represent the SAME 130 videos; only the
path string encoding differs.  The CSV has both rows too (forward-slash
duplicates).  We do NOT delete any rows (per user requirement).

Recovery plan (in-place, no row count change):
  1. For the 130 'backslash + empty' PG rows: copy the rich annotation
     (task_id / recorder_id / env_id / uploaded / extra_description /
      duration_sec / file_type / device_id / original_history_date /
      score) from the matching forward-slash PG row.  Also normalize the
     backslash path to forward-slash.
  2. For the 64 paths with `uploaded=Yes` annotation that was lost during
     the c10182d dedup pass: restore from the union of 5 pre-snapshots.
  3. For the 1 path overwritten by the other device
     (/media/0621/data/sample_session_00000): restore file_type +
     extra_description from the pre snapshot.

Source of truth priority:
  - Forward-slash PG row > Forward-slash CSV row > Pre-snapshots (5)
    (most recent pre snapshot wins for non-stable fields)

Default mode: dry-run.  Pass --execute to apply to PG + CSV.
"""
from __future__ import annotations
import csv
import os
import sys
from collections import defaultdict
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

CSV_PATH = "runtime/data/video_manager.csv"
PG_TABLE = "videos"

# 5 pre-snapshots, ascending priority (most recent wins for non-stable fields)
PRE_SNAPSHOTS = [
    ("runtime/data/video_manager.csv.before_focused.csv", 0),
    ("runtime/data/video_manager.csv.before_0701_0705.csv", 1),
    ("runtime/data/video_manager.csv.before_durbackfill.csv", 2),
    ("runtime/data/video_manager.csv.before_dedup_v4.csv", 3),
    ("runtime/data/video_manager.csv.before_durbackfill_v2.csv", 4),
]

# Fields where richer = better.  When restoring, prefer non-empty values.
# `uploaded` is special: "Yes" beats "No" (definitive positive).
RESTORE_FIELDS = ["uploaded", "extra_description", "score", "duration_sec",
                  "recorder_id", "task_id", "env_id", "device_id",
                  "file_type", "original_history_date"]

BS = chr(92)
def norm(p): return p.replace(BS, "/").rstrip("/")

def load_csv(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def load_pg(eng):
    with eng.connect() as conn:
        return [dict(r._mapping) for r in
                conn.execute(text(f"SELECT * FROM {PG_TABLE}")).fetchall()]

# ── Step 1: build the "best annotation per normalized path" from the live data
# (forward-slash PG rows are the primary source of truth for current annotations)

def aggregate_live(pg_rows, csv_rows):
    """Return: {norm_path: {field: best_value}} from forward-slash records."""
    best = defaultdict(dict)
    # PG first (authoritative for what's "current")
    for r in pg_rows:
        if BS in r["path"]:
            continue  # skip the empty backslash rows; we'll fill them later
        n = norm(r["path"])
        for f in RESTORE_FIELDS:
            v = (r.get(f, "") or "").strip()
            if not v:
                continue
            existing = best[n].get(f)
            if existing is None:
                best[n][f] = v
            elif f == "uploaded" and v == "Yes" and existing != "Yes":
                best[n][f] = v  # Yes overrides
    # CSV can fill any gap (e.g., fields PG missed)
    for r in csv_rows:
        if BS in r["path"]:
            continue
        n = norm(r["path"])
        for f in RESTORE_FIELDS:
            v = (r.get(f, "") or "").strip()
            if not v:
                continue
            if f not in best[n]:
                best[n][f] = v
            elif f == "uploaded" and v == "Yes" and best[n][f] != "Yes":
                best[n][f] = v
    return best

# ── Step 2: also harvest pre-snapshots (for the 64 uploaded=Yes + 1 path override)

def aggregate_pre():
    """Return: {norm_path: {field: (priority, value, source_file)}}
    where priority is the snapshot index (higher = more recent)."""
    out = defaultdict(dict)
    for path, prio in PRE_SNAPSHOTS:
        if not os.path.exists(path):
            continue
        for r in load_csv(path):
            if BS in r["path"]:
                continue
            n = norm(r["path"])
            for f in RESTORE_FIELDS:
                v = (r.get(f, "") or "").strip()
                if not v:
                    continue
                existing = out[n].get(f)
                if f == "uploaded":
                    if existing is None or (existing[1] != "Yes" and v == "Yes"):
                        out[n][f] = (prio, v, path)
                else:
                    if existing is None or prio > existing[0]:
                        out[n][f] = (prio, v, path)
    return out

# ── Step 3: special-case path that was clobbered by the other device
OTHER_DEVICE_OVERRIDE_PATHS = {
    norm("/media/0621/data/sample_session_00000"): {
        "file_type": "data",
        "extra_description": "Data session · 1 files · 104 MB",
        "source_device": "",  # blank out other-device tag
    },
}

def main():
    execute = "--execute" in sys.argv
    pg_rows = []
    eng = None
    if os.environ.get("VIDEO_MANAGER_DB_DSN"):
        eng = create_engine(os.environ["VIDEO_MANAGER_DB_DSN"],
                            poolclass=NullPool, future=True)
        pg_rows = load_pg(eng)
    csv_rows = load_csv(CSV_PATH)
    live = aggregate_live(pg_rows, csv_rows)
    pre = aggregate_pre()

    # ── Plan: (action, target, field, value) ──
    plan = []  # list of dicts: {action, target, field, value, reason}

    # A) Backslash PG rows: copy rich annotation from matching forward-slash row
    for r in pg_rows:
        if BS not in r["path"]:
            continue
        n = norm(r["path"])
        rich = live.get(n, {})
        if not rich:
            continue
        for f, v in rich.items():
            cur = (r.get(f, "") or "").strip()
            if cur != v:
                plan.append({
                    "action": "PG_UPDATE",
                    "target": r["path"],
                    "row_id": r.get("id"),
                    "field": f,
                    "value": v,
                    "reason": f"backslash row + 130 配对中的 forward-slash 行有 {f}={v!r}，原值空",
                })
        # Also normalize the path itself
        if r["path"] != n:
            plan.append({
                "action": "PG_UPDATE",
                "target": r["path"],
                "row_id": r.get("id"),
                "field": "path",
                "value": n,
                "reason": "path 归一化（backslash → forward-slash）",
            })

    # B) Pre-snapshot recoveries (the 64 uploaded=Yes, 5 duration_sec, 1+1 task/recorder/env)
    for p, fields in pre.items():
        live_rich = live.get(p, {})
        for f, (prio, v, src) in fields.items():
            # Skip if live already has this value
            if f in live_rich and (live_rich[f] == v or
                                   (f == "uploaded" and live_rich[f] == "Yes")):
                continue
            if f == "uploaded" and v != "Yes":
                continue  # only restore Yes
            # For non-uploaded, only restore if live doesn't have a different value
            if f != "uploaded" and f in live_rich and live_rich[f]:
                continue
            # Apply to BOTH PG (any path variant) and CSV
            # Find the PG row(s) for this path (any variant)
            for r in pg_rows:
                if norm(r["path"]) == p:
                    cur = (r.get(f, "") or "").strip()
                    if cur != v:
                        plan.append({
                            "action": "PG_UPDATE",
                            "target": r["path"],
                            "row_id": r.get("id"),
                            "field": f,
                            "value": v,
                            "reason": f"pre 快照有 {f}={v!r} (来自 {os.path.basename(src)})，cur 缺",
                        })
            # Apply to CSV
            for r in csv_rows:
                if norm(r["path"]) == p:
                    cur = (r.get(f, "") or "").strip()
                    if cur != v:
                        plan.append({
                            "action": "CSV_UPDATE",
                            "target": r["path"],
                            "field": f,
                            "value": v,
                            "reason": f"pre 快照有 {f}={v!r} (来自 {os.path.basename(src)})，cur 缺",
                        })

    # C) Other-device override
    for p, overrides in OTHER_DEVICE_OVERRIDE_PATHS.items():
        for r in pg_rows:
            if norm(r["path"]) == p:
                for f, v in overrides.items():
                    cur = (r.get(f, "") or "").strip()
                    if cur != v:
                        plan.append({
                            "action": "PG_UPDATE",
                            "target": r["path"],
                            "row_id": r.get("id"),
                            "field": f,
                            "value": v,
                            "reason": f"另一台设备覆盖回退 (PC-20250831ZJSG)：{f}={v!r}",
                        })
        for r in csv_rows:
            if norm(r["path"]) == p:
                for f, v in overrides.items():
                    cur = (r.get(f, "") or "").strip()
                    if cur != v:
                        plan.append({
                            "action": "CSV_UPDATE",
                            "target": r["path"],
                            "field": f,
                            "value": v,
                            "reason": f"另一台设备覆盖回退 (PC-20250831ZJSG)：{f}={v!r}",
                        })

    # ── Deduplicate plan (same target+field+value only once) ──
    seen = set()
    plan_dedup = []
    for p in plan:
        k = (p["action"], p["target"], p["field"], p["value"])
        if k in seen:
            continue
        seen.add(k)
        plan_dedup.append(p)
    plan = plan_dedup

    # ── Print plan ──
    pg_updates = [p for p in plan if p["action"] == "PG_UPDATE"]
    csv_updates = [p for p in plan if p["action"] == "CSV_UPDATE"]
    print(f"\n{'='*72}\n## 恢复计划（不删行）\n{'='*72}")
    print(f"  PG  updates: {len(pg_updates)}")
    print(f"  CSV updates: {len(csv_updates)}")
    print()
    from collections import Counter
    pg_field_counts = Counter(p["field"] for p in pg_updates)
    print("  PG 字段分布:")
    for f, c in pg_field_counts.most_common():
        print(f"    {f}: {c}")
    if csv_updates:
        csv_field_counts = Counter(p["field"] for p in csv_updates)
        print("  CSV 字段分布:")
        for f, c in csv_field_counts.most_common():
            print(f"    {f}: {c}")

    print()
    print("=== 130 backslash 行字段填充样本（前 5）===")
    bs_samples = [p for p in pg_updates
                  if "backslash" in p["reason"] and p["field"] != "path"][:5]
    for p in bs_samples:
        print(f"  {p['target']!r}  [{p['field']}]  =  {p['value']!r}")

    print()
    print("=== uploaded=Yes 恢复样本（前 5）===")
    yes_samples = [p for p in pg_updates if p["field"] == "uploaded"][:5]
    for p in yes_samples:
        print(f"  {p['target']!r}  uploaded  ←  'Yes'  ({p['reason'][:60]})")

    print()
    print("=== 另一台设备覆盖回退 ===")
    for p in [x for x in plan if "另一台设备" in x["reason"]]:
        print(f"  {p['target']!r}  [{p['field']}]  =  {p['value']!r}")

    if not execute:
        print(f"\n[DRY-RUN] Pass --execute to apply.")
        return

    # ── Apply to PG ──
    if eng is None:
        print("\nERROR: VIDEO_MANAGER_DB_DSN not set; cannot apply to PG", file=sys.stderr)
        sys.exit(2)
    applied_pg = 0
    with eng.connect() as conn:
        # Group updates by id
        by_id = defaultdict(list)
        for p in pg_updates:
            by_id[p["row_id"]].append((p["field"], p["value"]))
        for rid, changes in by_id.items():
            set_clause = ", ".join(f"{f} = :{i}" for i, (f, _) in enumerate(changes))
            params = {str(i): v for i, (_, v) in enumerate(changes)}
            params["rid"] = rid
            try:
                conn.execute(text(f"UPDATE {PG_TABLE} SET {set_clause} WHERE id = :rid"),
                             params)
                applied_pg += len(changes)
            except Exception as e:
                print(f"  PG UPDATE id={rid} FAILED: {e}", file=sys.stderr)
        conn.commit()
    print(f"\n[EXECUTED] PG: {applied_pg} field updates across {len(by_id)} rows")

    # ── Apply to CSV ──
    applied_csv = 0
    rows = list(csv_rows)
    fieldnames = list(rows[0].keys()) if rows else []
    for p in csv_updates:
        for r in rows:
            if r["path"] == p["target"]:
                if r.get(p["field"], "") != p["value"]:
                    r[p["field"]] = p["value"]
                    applied_csv += 1
                break
    with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"[EXECUTED] CSV: {applied_csv} field updates")

if __name__ == "__main__":
    main()
