"""详细检查 0701-0705 路径匹配"""
import csv
import pathlib
from collections import Counter

fp = 'D:/sp/dev/video-manager/runtime/data/video_manager.csv'
with open(fp, 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

# 按日期 + 路径前缀 + location_status 统计
patterns = Counter()
for r in rows:
    p = (r.get('path','') or '').replace(chr(92), '/')  # 反斜杠转正斜杠
    for d in ['0619','0620','0621','0622','0625','0626','0627','0628','0629','0701','0702','0703','0704','0705']:
        marker = '/' + d + '/'
        if marker in p:
            prefix = p[:p.find(marker)]
            loc = r.get('location_status','')
            patterns[(d, prefix, loc)] += 1
            break

print('=== 0701-0705 在 CSV 中的 path 前缀 + location_status ===')
for (d, p, loc), c in sorted(patterns.items()):
    if d in {'0701','0702','0703','0704','0705'}:
        print(f'  {d}  前缀={p!r}  loc={loc!r}  数量={c}')

# 全部 location_status 分布
print('\n=== 0701-0705 全部 location_status ===')
loc_count = Counter()
for r in rows:
    p = (r.get('path','') or '').replace(chr(92), '/')
    for d in ['0701','0702','0703','0704','0705']:
        if '/' + d + '/' in p:
            loc_count[r.get('location_status','')] += 1
            break
for k, v in loc_count.most_common():
    print(f'  {k!r}: {v}')

# 本地 0701-0705 文件清单
print('\n=== 本地 0701-0705 文件 ===')
local_root = pathlib.Path('/media/videos')
for d in ['0701','0702','0703','0704','0705']:
    p = local_root / d / 'hmd'
    if p.exists():
        sessions = [e.name for e in p.iterdir() if e.is_dir() and (e/'metadata.json').exists()]
        print(f'  {d}: {len(sessions)} 个 session')
        for s in sessions[:3]:
            print(f'    - {s}')
    else:
        print(f'  {d}: 目录不存在')

# CSV 已有 (device, basename) 集合
existing = set()
for r in rows:
    p = (r.get('path','') or '').replace(chr(92), '/')
    base = p.rstrip('/').split('/')[-1] if p else ''
    dev = (r.get('device_id','') or '').strip()
    existing.add((dev, base))

# 哪些本地 session 没在 CSV
print('\n=== 本地有但 CSV 没有的 (按 (device, basename)) ===')
new_count = 0
for d in ['0701','0702','0703','0704','0705']:
    p = local_root / d / 'hmd'
    if not p.exists():
        continue
    for entry in p.iterdir():
        if entry.is_dir() and (entry/'metadata.json').exists():
            base = entry.name
            dev = base.split('_')[1] if '_' in base else ''
            if (dev, base) not in existing:
                new_count += 1
                if new_count <= 10:
                    print(f'  {d}  {dev}  {base}  ({entry})')
print(f'  共 {new_count} 个新 session')