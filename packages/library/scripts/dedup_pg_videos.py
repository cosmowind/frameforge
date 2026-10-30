"""一次性脚本：合并 PG videos 表中同 normalized path 的所有行（含 forward/backward slash 两种 encoding）。

策略：
1. SELECT 所有行，按 canon_path 分组（同 D:/x 和 D:\\x 视为同一组）。
2. 每组保留 ctid 最小的（最先插入），其余 DELETE。
3. 同时把保留行的 path 字段 normalize 成 canon_path 形式（lower + forward slash），
   这样未来 UPSERT 能匹配得上。
"""
import sys
sys.path.insert(0, 'src')
from collections import defaultdict
from sqlalchemy import text
from models.pg_store import _get_engine
from utils.path_utils import canon_path

engine = _get_engine()
with engine.begin() as conn:
    rows = conn.execute(text("SELECT ctid, path FROM videos")).fetchall()
    print(f"PG videos 总行数: {len(rows)}")

    # 按 canon_path 分组（路径等价类）
    by_norm = defaultdict(list)
    for ctid, path in rows:
        norm = canon_path(path) if path else ""
        by_norm[norm].append((ctid, path))

    # 找出需要合并的组（>= 2 行）以及空 path 的行
    merged_groups = {n: items for n, items in by_norm.items() if len(items) > 1}
    print(f"含 dup 的 normalized path: {len(merged_groups)}")
    print(f"待删行数: {sum(len(v) - 1 for v in merged_groups.values())}")

    deleted = 0
    updated_path = 0
    for norm_path, items in merged_groups.items():
        # 按 ctid 升序：先插入的留，后插入的删
        items.sort(key=lambda x: (x[0][0], x[0][1]))  # ctid tuple ordering
        keep_ctid, keep_path = items[0]
        drop = items[1:]
        # 把保留行的 path 字段更新成 norm 形式（如果不同）
        if keep_path != norm_path and norm_path:
            conn.execute(text("UPDATE videos SET path = :n WHERE ctid = :c"),
                         {"n": norm_path, "c": str(keep_ctid)})
            updated_path += 1
        for drop_ctid, _ in drop:
            conn.execute(text("DELETE FROM videos WHERE ctid = :c"), {"c": str(drop_ctid)})
            deleted += 1

    # 单行但 path 未规范化的（保留行里有混合大小写或 backslash）
    for norm_path, items in by_norm.items():
        if len(items) == 1:
            ctid, path = items[0]
            if path != norm_path and norm_path:
                conn.execute(text("UPDATE videos SET path = :n WHERE ctid = :c"),
                             {"n": norm_path, "c": str(ctid)})
                updated_path += 1

    print(f"已删 {deleted} 行，更新 {updated_path} 行 path 字段为 canon 形式")

    after = conn.execute(text("SELECT COUNT(*) FROM videos")).scalar()
    unique_paths = conn.execute(text("SELECT COUNT(DISTINCT path) FROM videos")).scalar()
    print(f"PG videos 现在: {after} 行, {unique_paths} unique path")
    assert after == unique_paths, "STILL HAS DUPS"
    print("OK: PG 去重 + 规范化完成")