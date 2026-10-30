"""聚焦的保守数据修复（DRY-RUN）：
1. 0701-0705：保留 thisPC_local，删除相同 path 的 otherPC_local
2. 0625-0629：保留完整已上传，删除同 path 的空数据
3. 不会动其他日期的记录
"""
import csv
from collections import defaultdict, Counter

fp = 'D:/sp/dev/video-manager/runtime/data/video_manager.csv'
with open(fp, 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
fieldnames = list(rows[0].keys())
print(f'CSV 加载 {len(rows)} 行')

# 按 path 分组
by_path = defaultdict(list)
for i, r in enumerate(rows):
    p = r.get('path','').replace(chr(92), '/')
    by_path[p].append((i, r))

# 规则：
# - 0701-0705：保留 thisPC_local，删 otherPC_local
# - 0625-0629：保留 uploaded=Yes + 完整字段，删空的
# - 其他日期：完全不动

import re
to_delete = []
to_keep = []

for path, items in by_path.items():
    if len(items) == 1:
        to_keep.extend(items)
        continue
    m = re.search(r'/(\d{4})/', path)
    date = m.group(1) if m else ''

    if date in {'0701','0702','0703','0704','0705'}:
        # 保留 thisPC_local，删 otherPC_local
        this_pc = [x for x in items if x[1].get('location_status','') == 'thisPC_local']
        other = [x for x in items if x[1].get('location_status','') == 'otherPC_local']
        if this_pc and other:
            to_keep.extend(this_pc)
            to_delete.extend(other)
            print(f'  0701-0705 同 path 多条: keep thisPC_local, drop otherPC_local: {path[-50:]}')
        else:
            to_keep.extend(items)
    elif date in {'0625','0626','0627','0628','0629'}:
        # 保留 uploaded=Yes + 完整字段
        full = [x for x in items
                if x[1].get('uploaded','').strip() == 'Yes'
                and x[1].get('recorder_id','').strip()
                and x[1].get('task_id','').strip()
                and x[1].get('env_id','').strip()]
        empty = [x for x in items if x not in full]
        if full and empty:
            to_keep.extend(full)
            to_delete.extend(empty)
            print(f'  0625-0629 同 path 多条: keep full, drop empty: {path[-50:]}')
        else:
            to_keep.extend(items)
    else:
        # 其他日期不动
        to_keep.extend(items)

print(f'\n=== DRY-RUN 汇总 ===')
print(f'  当前行数: {len(rows)}')
print(f'  待删除: {len(to_delete)}')
print(f'  保留: {len(to_keep)}')

# 看删除的内容分类
delete_reasons = Counter()
for i, r in to_delete:
    p = r.get('path','')
    m = re.search(r'/(\d{4})/', p)
    date = m.group(1) if m else ''
    if date in {'0701','0702','0703','0704','0705'}:
        delete_reasons['0701-0705 otherPC_local duplicate'] += 1
    elif date in {'0625','0626','0627','0628','0629'}:
        delete_reasons['0625-0629 empty/partial duplicate'] += 1
    else:
        delete_reasons['other'] += 1
print(f'  删除原因分布: {dict(delete_reasons)}')

# 删完后预估状态
print(f'\n=== 删完后状态预估 ===')
uploaded_after = sum(1 for i, r in to_keep if r.get('uploaded','').strip() == 'Yes')
this_pc_after = sum(1 for i, r in to_keep if r.get('location_status','') == 'thisPC_local')
print(f'  uploaded=Yes: {uploaded_after}')
print(f'  thisPC_local: {this_pc_after}')
print(f'  0625-0629 完整: {sum(1 for i, r in to_keep if any(d in r.get("path","") for d in ["/0625/","/0626/","/0627/","/0628/","/0629/"]) and r.get("uploaded","")=="Yes" and r.get("recorder_id","") and r.get("task_id","") and r.get("env_id",""))}')
print(f'  0701-0705 thisPC: {sum(1 for i, r in to_keep if any(d in r.get("path","") for d in ["/0701/","/0702/","/0703/","/0704/","/0705/"]) and r.get("location_status","")=="thisPC_local")}')