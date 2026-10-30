"""执行聚焦的保守数据修复（带字段合并）"""
import csv
import os
import shutil
import re
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv('D:/sp/dev/video-manager/.env')
DSN = os.environ.get('VIDEO_MANAGER_DB_DSN', '')

CSV_PATH = 'D:/sp/dev/video-manager/runtime/data/video_manager.csv'

# 备份
backup_path = CSV_PATH + '.before_focused.csv'
shutil.copy(CSV_PATH, backup_path)
print(f'CSV 备份: {backup_path}')

with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
fieldnames = list(rows[0].keys())
print(f'CSV 加载 {len(rows)} 行')

# 按 path 分组
by_path = defaultdict(list)
for i, r in enumerate(rows):
    p = r.get('path','').replace(chr(92), '/')
    by_path[p].append((i, r))

# 决定哪些保留、哪些删除，并在保留行上合并丢弃行的字段
def score(r):
    s = 0
    for k in ['recorder_id','task_id','env_id','duration_sec','uploaded','source_device']:
        if r.get(k, '').strip():
            s += 1
    return s

delete_indices = set()
merge_log = []  # 记录合并的字段，避免遗漏

for path, items in by_path.items():
    if len(items) == 1:
        continue
    m = re.search(r'/(06[2-3][0-9])/', path)
    date = m.group(1) if m else ''
    is_local_date = date in {'0701','0702','0703','0704','0705'}
    is_target_date = date in {'0625','0626','0627','0628','0629'}

    if is_local_date:
        # 0701-0705: 保留 thisPC_local，删 otherPC_local
        this_pc = [x for x in items if x[1].get('location_status','') == 'thisPC_local']
        other = [x for x in items if x[1].get('location_status','') == 'otherPC_local']
        if this_pc and other:
            keep_item = this_pc[0]
            keep_idx, keep_row = keep_item
            # 合并: 把 other 的非空字段补到 keep
            for drop_idx, drop_row in other:
                for k in fieldnames:
                    if k == 'path':
                        continue
                    if drop_row.get(k,'').strip() and not keep_row.get(k,'').strip():
                        keep_row[k] = drop_row[k]
                        merge_log.append(f'  {path[-50:]}: merge {k}={drop_row[k]!r} → keep[{keep_idx}]')
                delete_indices.add(drop_idx)
    elif is_target_date:
        # 0625-0629: 保留完整+uploaded=Yes，删除空/部分
        scored = [(score(r), i, r) for i, r in items]
        scored.sort(key=lambda x: -x[0])
        best_score, best_i, best_r = scored[0]
        if best_score >= 3:  # 至少 3 个字段非空才算"完整"
            # 合并其他行字段到 best_r
            for s, di, dr in scored[1:]:
                for k in fieldnames:
                    if k == 'path':
                        continue
                    if dr.get(k,'').strip() and not best_r.get(k,'').strip():
                        best_r[k] = dr[k]
                        merge_log.append(f'  {path[-50:]}: merge {k}={dr[k]!r} → keep[{best_i}]')
                delete_indices.add(di)
        # 否则不删（没有完整数据可保留）

print(f'\n=== 待删除 {len(delete_indices)} 行 ===')
print(f'=== 合并日志（前 10） ===')
for m in merge_log[:10]:
    print(m)
print(f'  ...共 {len(merge_log)} 次字段合并')

# 写回
new_rows = [r for i, r in enumerate(rows) if i not in delete_indices]
with open(CSV_PATH, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
    w.writeheader()
    w.writerows(new_rows)
print(f'\n✅ CSV 写回: {len(rows)} → {len(new_rows)}')

# 验证
with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
    verify_rows = list(csv.DictReader(f))
uploaded_yes = sum(1 for r in verify_rows if r.get('uploaded','').strip() == 'Yes')
this_pc = sum(1 for r in verify_rows if r.get('location_status','').strip() == 'thisPC_local')
print(f'  uploaded=Yes: {uploaded_yes}')
print(f'  thisPC_local: {this_pc}')

# PG 同步
if DSN:
    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import NullPool
    eng = create_engine(DSN, poolclass=NullPool, future=True)
    with eng.begin() as conn:
        # 备份 PG
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS videos_backup_focused AS SELECT * FROM videos
        """))
        conn.execute(text("DELETE FROM videos_backup_focused"))
        conn.execute(text("INSERT INTO videos_backup_focused SELECT * FROM videos"))
        print(f'\nPG 备份到 videos_backup_focused')

        # 找 PG 中同 path 的多条，按 CSV 同样规则处理
        # 先列出所有 path
        rs = conn.execute(text("SELECT path, location_status, uploaded, recorder_id, task_id, env_id, duration_sec, source_device FROM videos"))
        pg_by_path = defaultdict(list)
        for row in rs:
            path = row[0].replace(chr(92), '/')
            pg_by_path[path].append(row)

        pg_deleted = 0
        for path, items in pg_by_path.items():
            if len(items) == 1:
                continue
            m = re.search(r'/(06[2-3][0-9])/', path)
            date = m.group(1) if m else ''
            is_local_date = date in {'0701','0702','0703','0704','0705'}
            is_target_date = date in {'0625','0626','0627','0628','0629'}

            if is_local_date:
                this_pc_rows = [r for r in items if r[1] == 'thisPC_local']
                other_rows = [r for r in items if r[1] == 'otherPC_local']
                if this_pc_rows and other_rows:
                    keep = this_pc_rows[0]
                    for drop in other_rows:
                        # 合并字段
                        for k_idx, k_name in [(2,'uploaded'),(3,'recorder_id'),(4,'task_id'),
                                                (5,'env_id'),(6,'duration_sec'),(7,'source_device')]:
                            if drop[k_idx] and not keep[k_idx]:
                                conn.execute(
                                    text(f"UPDATE videos SET {k_name} = :v WHERE path = :p"),
                                    {'v': drop[k_idx], 'p': keep[0]}
                                )
                        # 删除
                        conn.execute(text("DELETE FROM videos WHERE path = :p"), {'p': drop[0]})
                        pg_deleted += 1
            elif is_target_date:
                # 完整度评分
                def pg_score(r):
                    s = 0
                    for idx in [2, 3, 4, 5, 6, 7]:
                        if r[idx] and str(r[idx]).strip():
                            s += 1
                    return s
                sorted_items = sorted(items, key=lambda r: -pg_score(r))
                best = sorted_items[0]
                if pg_score(best) >= 3:
                    for drop in sorted_items[1:]:
                        for k_idx, k_name in [(2,'uploaded'),(3,'recorder_id'),(4,'task_id'),
                                                (5,'env_id'),(6,'duration_sec'),(7,'source_device')]:
                            if drop[k_idx] and not best[k_idx]:
                                conn.execute(
                                    text(f"UPDATE videos SET {k_name} = :v WHERE path = :p"),
                                    {'v': drop[k_idx], 'p': best[0]}
                                )
                        conn.execute(text("DELETE FROM videos WHERE path = :p"), {'p': drop[0]})
                        pg_deleted += 1

        print(f'PG 删除: {pg_deleted} 条')

print('\n✅ 整合完成！')
print(f'  CSV: {len(rows)} → {len(new_rows)} 行')
print(f'  备份: {backup_path} + videos_backup_focused')