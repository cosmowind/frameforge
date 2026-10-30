"""补做 0701-0705 的 dedup（之前 regex 没匹配到 07xx）"""
import csv
import os
import shutil
import re
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv('D:/sp/dev/video-manager/.env')
DSN = os.environ.get('VIDEO_MANAGER_DB_DSN', '')

CSV_PATH = 'D:/sp/dev/video-manager/runtime/data/video_manager.csv'
backup = CSV_PATH + '.before_0701_0705.csv'
shutil.copy(CSV_PATH, backup)
print(f'CSV 备份: {backup}')

with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
fieldnames = list(rows[0].keys())
print(f'CSV 加载 {len(rows)} 行')

by_path = defaultdict(list)
for i, r in enumerate(rows):
    p = r.get('path','').replace(chr(92), '/')
    by_path[p].append((i, r))

delete_indices = set()
merge_count = 0

for path, items in by_path.items():
    if len(items) == 1:
        continue
    # 修复: 匹配 0701-0705
    m = re.search(r'/(07[0-9][0-9])/', path)
    if not m:
        continue
    date = m.group(1)
    if date not in {'0701','0702','0703','0704','0705'}:
        continue

    # 保留 thisPC_local，删除 otherPC_local
    this_pc = [x for x in items if x[1].get('location_status','') == 'thisPC_local']
    other = [x for x in items if x[1].get('location_status','') == 'otherPC_local']
    if this_pc and other:
        keep_idx, keep_row = this_pc[0]
        for drop_idx, drop_row in other:
            for k in fieldnames:
                if k == 'path':
                    continue
                if drop_row.get(k,'').strip() and not keep_row.get(k,'').strip():
                    keep_row[k] = drop_row[k]
                    merge_count += 1
            delete_indices.add(drop_idx)

print(f'\n待删除: {len(delete_indices)}, 合并: {merge_count}')

new_rows = [r for i, r in enumerate(rows) if i not in delete_indices]
with open(CSV_PATH, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
    w.writeheader()
    w.writerows(new_rows)
print(f'CSV: {len(rows)} → {len(new_rows)}')

# PG 同步
if DSN:
    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import NullPool
    eng = create_engine(DSN, poolclass=NullPool, future=True)
    with eng.begin() as conn:
        rs = conn.execute(text("SELECT path, location_status, uploaded, recorder_id, task_id, env_id, duration_sec, source_device FROM videos"))
        pg_by_path = defaultdict(list)
        for row in rs:
            path = row[0].replace(chr(92), '/')
            pg_by_path[path].append(row)
        pg_deleted = 0
        for path, items in pg_by_path.items():
            if len(items) == 1:
                continue
            m = re.search(r'/(07[0-9][0-9])/', path)
            if not m:
                continue
            date = m.group(1)
            if date not in {'0701','0702','0703','0704','0705'}:
                continue
            this_pc_rows = [r for r in items if r[1] == 'thisPC_local']
            other_rows = [r for r in items if r[1] == 'otherPC_local']
            if this_pc_rows and other_rows:
                keep = this_pc_rows[0]
                for drop in other_rows:
                    for k_idx, k_name in [(2,'uploaded'),(3,'recorder_id'),(4,'task_id'),
                                            (5,'env_id'),(6,'duration_sec'),(7,'source_device')]:
                        if drop[k_idx] and not keep[k_idx]:
                            conn.execute(
                                text(f"UPDATE videos SET {k_name} = :v WHERE path = :p"),
                                {'v': drop[k_idx], 'p': keep[0]}
                            )
                    conn.execute(text("DELETE FROM videos WHERE path = :p"), {'p': drop[0]})
                    pg_deleted += 1
        print(f'PG 删除: {pg_deleted}')

print('\n✅ 完成！')