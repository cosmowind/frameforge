"""Audit local CSV vs remote PG for Chinese/English pollution.

For each dim table (recorders, sd_cards, tasks, environments):
- Load local CSV
- Load PG rows
- Find rows where PG value is ASCII-only but CSV value has non-ASCII (Chinese)
- Report field-by-field diff

Run: cd src && python -m scripts.audit_pg_csv_i18n
"""
from __future__ import annotations
import csv
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

# Tables we audit: (csv_path, schema, key, pg_table)
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
    """Return {key: row_dict} from local CSV."""
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {row.get(reader.fieldnames[0]) or row[next(iter(reader.fieldnames))]: row
                for row in reader}

def load_pg(table: str, schema: list[str], key: str) -> dict[str, dict]:
    dsn = os.environ.get("VIDEO_MANAGER_DB_DSN")
    if not dsn:
        raise RuntimeError("VIDEO_MANAGER_DB_DSN not set")
    eng = create_engine(dsn, poolclass=NullPool, future=True)
    cols = ", ".join(schema)
    out = {}
    with eng.connect() as conn:
        for r in conn.execute(text(f"SELECT {cols} FROM {table}")).fetchall():
            d = {fn: ("" if v is None else v) for fn, v in r._mapping.items()}
            out[d[key]] = d
    return out

def diff_field(csv_v: str, pg_v: str) -> str | None:
    """Return non-None diff label if PG is English but CSV is Chinese."""
    if csv_v == pg_v:
        return None
    if not csv_v or not pg_v:
        return None
    # Pollution criteria: CSV has Chinese, PG is ASCII-only (English pollution)
    if has_chinese(csv_v) and is_ascii_only(pg_v):
        return f"中文→英文"
    # Other diffs still interesting but not 'pollution' per se
    return None

def main():
    total_rows = 0
    polluted_rows = 0
    polluted_fields = 0
    for csv_path, schema, key, pg_table in TARGETS:
        print(f"\n{'='*72}\n## {pg_table}  (key={key}, csv={csv_path})\n{'='*72}")
        csv_rows = load_csv(csv_path)
        try:
            pg_rows = load_pg(pg_table, schema, key)
        except Exception as e:
            print(f"  [SKIP] PG load failed: {e}")
            continue
        print(f"  CSV rows: {len(csv_rows)}    PG rows: {len(pg_rows)}")
        # Check CSV-only, PG-only, and shared
        csv_keys = set(csv_rows.keys())
        pg_keys = set(pg_rows.keys())
        if missing_in_pg := csv_keys - pg_keys:
            print(f"  [INFO] {len(missing_in_pg)} keys in CSV missing from PG (sample: {list(missing_in_pg)[:3]})")
        if extra_in_pg := pg_keys - csv_keys:
            print(f"  [INFO] {len(extra_in_pg)} keys in PG missing from CSV (sample: {list(extra_in_pg)[:3]})")
        # Field-by-field diff on shared keys
        shared = csv_keys & pg_keys
        for k in sorted(shared):
            row_diffs = []
            for field in schema:
                if field == key:
                    continue
                csv_v = csv_rows[k].get(field, "") or ""
                pg_v = pg_rows[k].get(field, "") or ""
                label = diff_field(csv_v, pg_v)
                if label:
                    csv_preview = csv_v[:30] + ("…" if len(csv_v) > 30 else "")
                    pg_preview = pg_v[:30] + ("…" if len(pg_v) > 30 else "")
                    row_diffs.append((field, csv_preview, pg_preview, label))
            if row_diffs:
                polluted_rows += 1
                polluted_fields += len(row_diffs)
                print(f"  [{k}]")
                for field, csv_v, pg_v, label in row_diffs:
                    print(f"      {field}: CSV='{csv_v}' | PG='{pg_v}'  ({label})")
        total_rows += len(shared)
    print(f"\n{'='*72}\n## 总览\n{'='*72}")
    print(f"  比对行数: {total_rows}")
    print(f"  被污染行数（PG 含英文、CSV 含中文）: {polluted_rows}")
    print(f"  被污染字段数: {polluted_fields}")
    print(f"\n检查标准：CSV 含中文字符 + PG 全部 ASCII = 污染嫌疑")
    print(f"修复策略：稍后根据本表输出决定要覆盖哪些字段（不批量覆盖）")

if __name__ == "__main__":
    main()