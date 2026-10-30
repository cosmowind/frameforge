"""Final 4-table verification: recorders / sd_cards / tasks / environments in PG.

Checks per table:
1. PG row count vs local CSV row count (must match for shared key namespace)
2. Field-by-field comparison PG vs local CSV
3. Report: rows that differ, fields that differ, missing-in-Pg, missing-in-CSV
4. Per-row Chinese-character check on each text field
"""
from __future__ import annotations
import csv
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

TARGETS = [
    ("runtime/data/recorders.csv",   ["id", "name", "phone",
                                       "operator_job", "operator_consent",
                                       "age_range", "gender", "handedness", "gloves", "workforce_type",
                                       "role_experience", "task_experience",
                                       "collection_hours_today", "collection_experience_days",
                                       "hand_size_cm", "notes"],
     "id",            "recorders",   "录入员"),
    ("runtime/data/sd_cards.csv",     ["volume_serial", "volume_label", "device_id", "device_name",
                                       "capture_mode",
                                       "country_code", "region", "city",
                                       "stable_site_identifier",
                                       "notes"],
     "volume_serial", "sd_cards",     "SD卡"),
    ("runtime/data/tasks.csv",        ["task_id", "scene", "product", "task", "tool", "process", "process_en",
                                       "difficulty", "quota_min",
                                       "location_address",
                                       "business_type", "business_name",
                                       "environment",
                                       "environment_description", "environment_description_en",
                                       "facility_venue",
                                       "notes"],
     "task_id",       "tasks",        "任务"),
    ("runtime/data/environments.csv", ["env_id", "scene", "location_address",
                                       "environment", "environment_description", "environment_description_en",
                                       "facility_venue",
                                       "notes"],
     "env_id",        "environments", "环境"),
]

def has_chinese(s: str) -> bool:
    return any('一' <= ch <= '鿿' for ch in s)

def is_ascii_only(s: str) -> bool:
    return all(ord(ch) < 128 for ch in s) if s else True

def load_csv(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8-sig") as f:
        rdr = csv.DictReader(f)
        first = rdr.fieldnames[0]
        return {row[first]: row for row in rdr}

def load_pg(table: str, schema: list[str]) -> dict:
    dsn = os.environ.get("VIDEO_MANAGER_DB_DSN")
    eng = create_engine(dsn, poolclass=NullPool, future=True)
    cols = ", ".join(schema)
    out = {}
    with eng.connect() as conn:
        for r in conn.execute(text(f"SELECT {cols} FROM {table}")).fetchall():
            d = {fn: ("" if v is None else v) for fn, v in r._mapping.items()}
            out[d[schema[0]]] = d
    return out

def main():
    print("=" * 76)
    print(f"  PG 四大表单最终验证")
    print("=" * 76)
    grand_total = {"diff_rows": 0, "diff_fields": 0, "missing_pg": 0, "missing_csv": 0}

    for csv_path, schema, key, pg_table, label in TARGETS:
        print(f"\n## {label}（PG: {pg_table} | CSV: {csv_path}）")
        print("-" * 76)
        csv_rows = load_csv(csv_path)
        try:
            pg_rows = load_pg(pg_table, schema)
        except Exception as e:
            print(f"  [ERROR] PG 加载失败: {e}")
            continue
        csv_keys = set(csv_rows.keys())
        pg_keys = set(pg_rows.keys())

        # 1. 行数对比
        print(f"  行数:  CSV={len(csv_keys)}  PG={len(pg_keys)}")
        if csv_keys == pg_keys:
            print(f"  ✓ 主键集合完全一致")
        else:
            missing_in_pg = csv_keys - pg_keys
            extra_in_pg = pg_keys - csv_keys
            if missing_in_pg:
                grand_total["missing_pg"] += len(missing_in_pg)
                print(f"  ✗ PG 缺 {len(missing_in_pg)} 个主键 (示例: {list(missing_in_pg)[:3]})")
            if extra_in_pg:
                grand_total["missing_csv"] += len(extra_in_pg)
                print(f"  ✗ CSV 缺 {len(extra_in_pg)} 个主键 (示例: {list(extra_in_pg)[:3]})")

        # 2. 字段对比（仅对共有 key）
        shared = csv_keys & pg_keys
        diff_rows = []
        diff_field_count = 0
        for k in sorted(shared):
            row_diffs = []
            for field in schema:
                if field == key:
                    continue
                csv_v = csv_rows[k].get(field, "") or ""
                pg_v = pg_rows[k].get(field, "") or ""
                if csv_v != pg_v:
                    row_diffs.append((field, csv_v, pg_v))
                    diff_field_count += 1
            if row_diffs:
                diff_rows.append((k, row_diffs))
        grand_total["diff_rows"] += len(diff_rows)
        grand_total["diff_fields"] += diff_field_count
        if diff_rows:
            print(f"  ✗ {len(diff_rows)} 行有字段差异，共 {diff_field_count} 个字段:")
            for k, fields in diff_rows[:5]:
                print(f"    [{k}]")
                for field, csv_v, pg_v in fields[:4]:
                    cv = csv_v[:25] + ("…" if len(csv_v) > 25 else "")
                    pv = pg_v[:25] + ("…" if len(pg_v) > 25 else "")
                    print(f"        {field}: CSV='{cv}' PG='{pv}'")
            if len(diff_rows) > 5:
                print(f"    …还有 {len(diff_rows) - 5} 行差异")
        else:
            print(f"  ✓ {len(shared)} 个共有主键的字段全部一致")

        # 3. 中文覆盖度（仅看 4 个常被污染的中文字段）
        print(f"  中文覆盖度:")
        for field in (["name"] if pg_table == "recorders" else
                      ["capture_mode", "region", "city"] if pg_table == "sd_cards" else
                      ["scene", "location_address", "environment", "facility_venue", "environment_description"] if pg_table == "tasks" else
                      ["scene", "location_address", "environment", "facility_venue", "environment_description"]):
            zh = sum(1 for k in shared if has_chinese((pg_rows.get(k) or {}).get(field, "") or ""))
            en = sum(1 for k in shared if is_ascii_only((pg_rows.get(k) or {}).get(field, "") or "") and (pg_rows.get(k) or {}).get(field))
            empty = sum(1 for k in shared if not (pg_rows.get(k) or {}).get(field))
            mark = "✓" if en == 0 else "✗"
            print(f"      {mark} {field:25} 中文:{zh:3}  英文:{en:3}  空:{empty:3}")

    print("\n" + "=" * 76)
    print(f"  总览")
    print("=" * 76)
    print(f"  字段差异行: {grand_total['diff_rows']} 行 / {grand_total['diff_fields']} 字段")
    print(f"  PG 缺主键:  {grand_total['missing_pg']}    CSV 缺主键: {grand_total['missing_csv']}")
    if grand_total['diff_rows'] == 0 and grand_total['missing_pg'] == 0 and grand_total['missing_csv'] == 0:
        print(f"\n  ✅ 四大表单 CSV ↔ PG 完全一致")
    else:
        print(f"\n  ⚠️ 仍存在差异，请查看上面详情")

if __name__ == "__main__":
    main()