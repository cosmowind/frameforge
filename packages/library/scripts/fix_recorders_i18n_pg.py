"""将 PG recorders 表中 op1–op11 的英文字段批量改为中文，使其适配前端下拉选项。

字段映射基于 src/static/js/dim-table-crud.js 的 _DIM_FIELDS.recorders：
  - gender          : Male → 男, Female → 女
  - handedness      : Right-handed → 右手, Left-handed → 左手, Ambidextrous → 双手皆可
  - gloves          : No — bare hands → 否 —— 徒手, Yes — wearing gloves → 是 —— 戴手套
  - workforce_type  : Real worker (does this job) → 真实员工(本职工作)
                     Contractor (hired for recording) → 承包者(为接入雇佣)
  - operator_consent: Yes → 是, No → 否
  - operator_job    : 见 JOB_MAP（与上传页面 235 项选项对齐）

role_experience / task_experience 是自由文本，不强制改中文，跳过。

默认 dry-run：打印 SQL 预览。执行：python scripts/fix_recorders_i18n_pg.py --execute
"""
from __future__ import annotations

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

PG_TABLE = "recorders"
PG_KEY = "id"

# 英 → 中 映射（与 dim-table-crud.js _DIM_FIELDS.recorders 选项一致）
GENDER_MAP = {
    "Male": "男",
    "Female": "女",
    "Prefer not to say": "不愿透露",
}
HANDEDNESS_MAP = {
    "Right-handed": "右手",
    "Left-handed": "左手",
    "Ambidextrous": "双手皆可",
}
GLOVES_MAP = {
    "No — bare hands": "否 —— 徒手",
    "Yes — wearing gloves": "是 —— 戴手套",
}
WORKFORCE_MAP = {
    "Real worker (does this job)": "真实员工(本职工作)",
    "Contractor (hired for recording)": "承包者(为接入雇佣)",
}
CONSENT_MAP = {
    "Yes": "是",
    "No": "否",
}
# 已知操作员职业（与 dim-table-crud.js operator_job 选项对齐）。未匹配的留原值并报告。
JOB_MAP = {
    "Production worker": "生产工人",
    "Factory worker": "工厂工人",
    "Packaging operator": "包装操作员",
    "Package handler": "包装处理员",
    "Product manager": "产品经理",
}

# 字段 → 映射表
FIELD_MAP = {
    "gender": GENDER_MAP,
    "handedness": HANDEDNESS_MAP,
    "gloves": GLOVES_MAP,
    "workforce_type": WORKFORCE_MAP,
    "operator_consent": CONSENT_MAP,
    "operator_job": JOB_MAP,
}


def get_engine():
    dsn = os.environ.get("VIDEO_MANAGER_DB_DSN")
    if not dsn:
        raise SystemExit("VIDEO_MANAGER_DB_DSN 未设置（.env 或环境变量）")
    return create_engine(dsn, poolclass=NullPool, future=True)


def escape_sql(v: str) -> str:
    return v.replace("'", "''")


def collect_updates(conn):
    """返回 [(id, field, old, new), ...]"""
    rows = conn.execute(text(f"SELECT * FROM {PG_TABLE} ORDER BY {PG_KEY}")).fetchall()
    updates = []
    for r in rows:
        d = {k: ("" if v is None else v) for k, v in r._mapping.items()}
        key_val = d.get(PG_KEY, "")
        for field, mapping in FIELD_MAP.items():
            old = d.get(field, "") or ""
            if not old:
                continue
            new = mapping.get(old)
            if new is None:
                # 已经是中文或未知值：跳过（未知值也不报错，由调用方报告）
                continue
            if new != old:
                updates.append((key_val, field, old, new))
    return updates


def main():
    execute = "--execute" in sys.argv
    eng = get_engine()

    # 先打印映射表，便于人工核对
    print("## 字段映射（与 dim-table-crud.js _DIM_FIELDS.recorders 选项一致）")
    for field, mapping in FIELD_MAP.items():
        print(f"  {field}:")
        for en, zh in mapping.items():
            print(f"    {en!r:50} → {zh!r}")
    print()

    total_rows = 0
    total_fields = 0
    unknown_values = {}  # field → set(unknown)
    with eng.connect() as conn:
        updates = collect_updates(conn)
        # 聚合同一 id 的更新到一条 UPDATE
        by_key = {}
        for key_val, field, old, new in updates:
            by_key.setdefault(key_val, []).append((field, old, new))

        if not by_key:
            print("[NO-OP] PG 中无需修复的字段（可能已是中文）")
            return

        for key_val, items in by_key.items():
            total_rows += 1
            total_fields += len(items)
            sets = ",\n    ".join(
                f"{f} = '{escape_sql(n)}'  -- was: {escape_sql(o)!r}"
                for f, o, n in items
            )
            print(f"-- {PG_KEY}={key_val}")
            print(f"UPDATE {PG_TABLE} SET\n    {sets}\nWHERE {PG_KEY} = '{escape_sql(key_val)}';")
            print()

        # 报告未知值（CSV/PG 中有但不在映射里）
        all_rows = conn.execute(text(f"SELECT * FROM {PG_TABLE}")).fetchall()
        for r in all_rows:
            d = {k: ("" if v is None else v) for k, v in r._mapping.items()}
            for field, mapping in FIELD_MAP.items():
                v = d.get(field, "") or ""
                if v and v not in mapping and not any('一' <= ch <= '鿿' for ch in v):
                    unknown_values.setdefault(field, set()).add(v)

        if unknown_values:
            print("## 警告：以下英文值不在映射表中，未自动转换（请人工处理）")
            for field, vals in unknown_values.items():
                print(f"  {field}: {sorted(vals)}")
            print()

        if execute:
            with eng.begin() as conn2:
                for key_val, items in by_key.items():
                    sets = ", ".join(f"{f} = :{f}" for f, _, _ in items)
                    params = {f: n for f, _, n in items}
                    params[PG_KEY] = key_val
                    conn2.execute(text(f"UPDATE {PG_TABLE} SET {sets} WHERE {PG_KEY} = :{PG_KEY}"), params)
            print(f"[EXECUTED] {total_rows} rows, {total_fields} fields updated.")
        else:
            print(f"[DRY-RUN] Would update {total_rows} rows / {total_fields} fields. Pass --execute to apply.")


if __name__ == "__main__":
    main()