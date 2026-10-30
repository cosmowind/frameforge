"""Preview SQL UPDATE statements that restore Chinese fields polluted in PG.

For each polluted row, generate: UPDATE <table> SET <field>='<value>', ... WHERE <key>='<key>';

Default behavior: print SQL to stdout (dry-run). Pass --execute to apply.
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
                                       "recording_hours_today", "recording_experience_days",
                                       "hand_size_cm", "notes"],
     "id",            "recorders"),
    ("runtime/data/sd_cards.csv",     ["volume_serial", "volume_label", "device_id", "device_name",
                                       "capture_mode",
                                       "country_code", "region", "city",
                                       "stable_site_identifier",
                                       "notes"],
     "volume_serial", "sd_cards"),
    ("runtime/data/tasks.csv",        ["task_id", "scene", "product", "task", "tool", "process", "process_en",
                                       "difficulty", "quota_min",
                                       "location_address",
                                       "business_type", "business_name",
                                       "environment",
                                       "environment_description", "environment_description_en",
                                       "facility_venue",
                                       "notes"],
     "task_id",       "tasks"),
    ("runtime/data/environments.csv", ["env_id", "scene", "location_address",
                                       "environment", "environment_description", "environment_description_en",
                                       "facility_venue",
                                       "notes"],
     "env_id",        "environments"),
]

def has_chinese(s: str) -> bool:
    return any('一' <= ch <= '鿿' for ch in s)

def is_ascii_only(s: str) -> bool:
    return all(ord(ch) < 128 for ch in s) if s else True

def load_csv(path: str) -> dict[str, dict]:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        first_col = reader.fieldnames[0]
        return {row[first_col]: row for row in reader}

def escape_sql(v: str) -> str:
    """SQL string literal escape (single quote doubling)."""
    return v.replace("'", "''")

def main():
    execute = "--execute" in sys.argv
    dsn = os.environ.get("VIDEO_MANAGER_DB_DSN")
    if not dsn:
        print("VIDEO_MANAGER_DB_DSN not set", file=sys.stderr)
        sys.exit(2)
    eng = create_engine(dsn, poolclass=NullPool, future=True)
    total_updates = 0
    total_rows = 0
    with eng.connect() as conn:
        for csv_path, schema, key, pg_table in TARGETS:
            csv_rows = load_csv(csv_path)
            if not csv_rows:
                continue
            for k, csv_row in csv_rows.items():
                sets = []
                for field in schema:
                    if field == key:
                        continue
                    csv_v = csv_row.get(field, "") or ""
                    if not has_chinese(csv_v):
                        continue  # CSV 本身不是中文，跳过
                    # 读 PG 当前值
                    row = conn.execute(
                        text(f"SELECT {field} FROM {pg_table} WHERE {key}=:k"),
                        {"k": k}
                    ).fetchone()
                    if row is None:
                        continue  # PG 没有这行，跳过
                    pg_v = row[0] or ""
                    if csv_v == pg_v:
                        continue
                    if not is_ascii_only(pg_v):
                        continue  # PG 已经有中文（或别的非 ASCII），不是污染，不动
                    # 是污染：把 CSV 中文写回 PG
                    sets.append(f"  {field} = '{escape_sql(csv_v)}'")
                if sets:
                    total_rows += 1
                    total_updates += len(sets)
                    sql = f"UPDATE {pg_table} SET\n" + ",\n".join(sets) + f"\nWHERE {key} = '{escape_sql(k)}';"
                    print(f"-- {pg_table}.{key}={k}")
                    print(sql)
                    print()
                    if execute:
                        conn.execute(text(sql))
        if execute:
            conn.commit()
            print(f"\n[EXECUTED] {total_rows} rows, {total_updates} fields updated.")
        else:
            print(f"\n[DRY-RUN] Would update {total_rows} rows / {total_updates} fields. Pass --execute to apply.")

if __name__ == "__main__":
    main()