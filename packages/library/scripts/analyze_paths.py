"""分析 CSV path 格式分布 + 找重复"""
import csv
import os
from collections import Counter, defaultdict

current_path = 'D:/sp/dev/video-manager/runtime/data/video_manager.csv'
with open(current_path, 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

# 统计 path 格式
formats = Counter()
for r in rows:
    p = r.get('path','')
    if not p:
        formats['empty'] += 1
    elif '/' in p and '\\' in p:
        formats['mixed'] += 1
    elif '/' in p:
        formats['forward'] += 1
    elif '\\' in p:
        formats['backslash'] += 1

print(f'=== CSV path 格式分布 ({len(rows)} 行) ===')
for fmt, c in formats.most_common():
    print(f'  {fmt}: {c}')

# 用 basename + device_id 找重复
groups = defaultdict(list)
for i, r in enumerate(rows):
    p = r.get('path','')
    base = os.path.basename(p.replace('\\','/'))
    dev = r.get('device_id','')
    key = f'{dev}/{base}'
    groups[key].append((i, r))

print(f'\n=== 同一 device+basename 的重复 (前 10 组) ===')
shown = 0
for key, items in sorted(groups.items()):
    if len(items) > 1:
        if shown >= 10:
            break
        print(f'\n[{key}] 共 {len(items)} 条:')
        for i, r in items:
            has_data = '✓' if r.get('recorder_id') and r.get('task_id') else '✗'
            print(f'  {has_data} [{i}] uploaded={r.get("uploaded","")!r}  loc={r.get("location_status","")!r}  path={r.get("path","")!r}')
        shown += 1
print(f'\n总共有重复的组数: {sum(1 for items in groups.values() if len(items) > 1)}')