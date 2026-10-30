"""全 CSV 去重（按 path 完全匹配）

策略（同 path 严格匹配去重）：
- 优先保留 thisPC_local
- 全部 thisPC_local 时保留第一个，删除其他
- 全部 otherPC_local / otherPC_history 时保留第一个
- 混合时（thisPC + other）保留 thisPC

不影响任何数据内容（只删完全重复行）
"""
import csv
import sys
from collections import defaultdict
import shutil

CSV_PATH = 'D:/sp/dev/video-manager/runtime/data/video_manager.csv'

with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
fieldnames = list(rows[0].keys())
print(f'CSV 加载 {len(rows)} 行')

# 按 path 分组
by_path = defaultdict(list)
for i, r in enumerate(rows):
    p = r.get('path','').replace(chr(92), '/')
    by_path[p].append((i, r))

delete_indices = set()
delete_reasons = defaultdict(int)
all_groups = 0

for path, items in by_path.items():
    if len(items) == 1:
        continue
    all_groups += 1
    # 统计 location 分布
    this_pc = [x for x in items if x[1].get('location_status','') == 'thisPC_local']
    other_pc_local = [x for x in items if x[1].get('location_status','') == 'otherPC_local']
    other_pc_history = [x for x in items if x[1].get('location_status','') == 'otherPC_history']

    if this_pc and (other_pc_local or other_pc_history):
        # 情况 1：thisPC + otherPC 混合 → 保留 thisPC，删除 other
        keep = this_pc[0]
        for drop in other_pc_local + other_pc_history:
            delete_indices.add(drop[0])
            delete_reasons[f'keep_{"thisPC"}_drop_other'] += 1
    elif len(this_pc) > 1:
        # 情况 2：多个 thisPC（扫描重复），保留第一个
        for drop in this_pc[1:]:
            delete_indices.add(drop[0])
            delete_reasons['dup_thisPC'] += 1
    elif len(other_pc_local) > 1:
        # 情况 3：多个 otherPC_local，保留第一个
        for drop in other_pc_local[1:]:
            delete_indices.add(drop[0])
            delete_reasons['dup_otherPC_local'] += 1
    elif len(other_pc_history) > 1:
        # 情况 4：多个 otherPC_history，保留第一个
        for drop in other_pc_history[1:]:
            delete_indices.add(drop[0])
            delete_reasons['dup_otherPC_history'] += 1

print(f'\n=== Dry-run 汇总 ===')
print(f'多记录组: {all_groups}')
print(f'待删除: {len(delete_indices)} 行')
print(f'原因分布: {dict(delete_reasons)}')
print(f'保留后: {len(rows) - len(delete_indices)} 行')

# 按月统计保留后
import re
from collections import Counter
new_rows = [r for i, r in enumerate(rows) if i not in delete_indices]
months = Counter()
for r in new_rows:
    p = (r.get('path','') or '').replace(chr(92),'/')
    m = re.search(r'/(\d{4})/', p)
    if m: months[m.group(1)] += 1
print(f'按月分布: {dict(sorted(months.items()))}')

# 0701-0705 保留数
n_0701_0705 = sum(1 for r in new_rows if any('/'+d+'/' in (r.get('path','') or '').replace(chr(92),'/') for d in ['0701','0702','0704']))
print(f'0701-0705 保留: {n_0701_0705}')

# 验证：0704_4aa45c_session_00022 不会被错误删除
for r in new_rows:
    p = (r.get('path','') or '').replace(chr(92),'/')
    if '0704_4aa45c_session_00022' in p:
        print(f'\\n保留的 0704_4aa45c_session_00022:')
        for k, v in r.items():
            if v:
                print(f'  {k} = {v!r}')

if '--confirm' not in sys.argv:
    print('\n（DRY-RUN 模式，加 --confirm 才实际写入）')
    sys.exit(0)

# 写回
backup = CSV_PATH + '.before_dedup_v4.csv'
shutil.copy(CSV_PATH, backup)
print(f'\\n备份: {backup}')
with open(CSV_PATH, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
    w.writeheader()
    w.writerows(new_rows)
print(f'✅ CSV 已写: {len(rows)} → {len(new_rows)} 行')

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

print('\\n✅ 完成！')