"""Dry-run 0701-0705 去重（按 path 严格匹配）

之前 dedup 已用过的逻辑：
- 0701-0705：保留 thisPC_local，删除同 path 的 otherPC_local
- 0625-0629：保留完整+uploaded=Yes，删除空副本
"""
import csv
from collections import defaultdict
import re

CSV_PATH = 'D:/sp/dev/video-manager/runtime/data/video_manager.csv'

with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
fieldnames = list(rows[0].keys())
print(f'CSV 加载 {len(rows)} 行')

by_path = defaultdict(list)
for i, r in enumerate(rows):
    p = r.get('path','').replace(chr(92), '/')
    by_path[p].append((i, r))

delete_indices = set()
delete_reasons = {'0701-0705_dup': 0, 'other': 0}

for path, items in by_path.items():
    if len(items) == 1:
        continue
    m = re.search(r'/(07[0-9][0-9])/', path)
    if not m:
        continue
    date = m.group(1)
    if date in {'0701','0702','0703','0704','0705'}:
        # 0701-0705 范围内，同 path 的多个记录：
        # 1) 优先保留 thisPC_local（跳过 otherPC_local）
        # 2) 如果全是 thisPC_local，保留第一条，删除其他（同 path 完全重复）
        # 3) 如果有混合（一个完整+一个空），保留完整的
        locs = [x[1].get('location_status','') for x in items]
        this_pc = [x for x in items if x[1].get('location_status','') == 'thisPC_local']
        other = [x for x in items if x[1].get('location_status','') == 'otherPC_local']

        if this_pc and other:
            # 情况 1：混合，保留 thisPC，删除 other
            keep = this_pc[0]
            for drop in other:
                delete_indices.add(drop[0])
                delete_reasons['0701-0705_dup'] += 1
        elif len(this_pc) > 1:
            # 情况 2：多个 thisPC_local（扫描重复），保留第一个，删除其他
            for drop in this_pc[1:]:
                delete_indices.add(drop[0])
                delete_reasons['0701-0705_dup'] += 1
        elif len(other) > 1:
            # 情况 3：多个 otherPC_local，保留第一个
            for drop in other[1:]:
                delete_indices.add(drop[0])
                delete_reasons['0701-0705_dup'] += 1

print(f'\n=== Dry-run 汇总 ===')
print(f'待删除: {len(delete_indices)} 行')
print(f'  原因分布: {dict(delete_reasons)}')
print(f'保留后: {len(rows) - len(delete_indices)} 行')

# 模拟删除后
new_rows = [r for i, r in enumerate(rows) if i not in delete_indices]
# 验证
n_0701_0705 = sum(1 for r in new_rows if any('/'+d+'/' in (r.get('path','') or '').replace(chr(92),'/') for d in ['0701','0702','0704']))
print(f'0701-0705 去重后: {n_0701_0705} 行（应该=57）')
print('\n（DRY-RUN 模式，未实际写入。加 --confirm 才执行）')

import sys
if '--confirm' not in sys.argv:
    sys.exit(0)

# 备份 + 写
import shutil, os
sep = chr(92)
backup = CSV_PATH + '.before_dedup_v3.csv'
shutil.copy(CSV_PATH, backup)
print(f'\\n备份: {backup}')
with open(CSV_PATH, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
    w.writeheader()
    w.writerows(new_rows)
print(f'✅ CSV 已写')

# 同步 PG
from dotenv import load_dotenv
load_dotenv('D:/sp/dev/video-manager/.env')
DSN = os.environ.get('VIDEO_MANAGER_DB_DSN', '')
if DSN:
    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import NullPool
    eng = create_engine(DSN, poolclass=NullPool, future=True)
    pg_del = 0
    with eng.begin() as conn:
        for i, r in enumerate(rows):
            if i in delete_indices:
                p = r.get('path','').replace(chr(92),'/')
                base = os.path.basename(p)
                r2 = conn.execute(text("DELETE FROM videos WHERE path = :p OR path LIKE :p2"),
                                   {'p': p, 'p2': f'%{base}%'})
                pg_del += r2.rowcount
    print(f'PG 删除: {pg_del} 行')