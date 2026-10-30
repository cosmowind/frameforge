"""检查 0625-0629 和 0701-0705 的数据状态"""
import csv
import os
current_path = 'D:/sp/dev/video-manager/runtime/data/video_manager.csv'
with open(current_path, 'r', encoding='utf-8-sig') as f:
    current_rows = list(csv.DictReader(f))

# 详细看 0625-0629 视频的每列
print('=== 0625-0629 in CURRENT (前 3) 详细 ===')
count = 0
for i, r in enumerate(current_rows):
    p = r.get('path','')
    if any(p.find(m) >= 0 for m in ['0625','0626','0627','0628','0629']):
        if count < 3:
            print(f'[{i}] {p[-50:]}')
            for k, v in r.items():
                if v:
                    print(f'  {k}={v!r}')
            print('---')
        count += 1
print(f'共 {count} 个 0625-0629 视频')

# Check 0701-0705
print('\n=== 0701-0705 (本机 vs 其他) ===')
sep = '\\'
for i, r in enumerate(current_rows):
    p = (r.get('path','') or '').replace(sep, '/')
    for m in ['0701','0702','0703','0704','0705']:
        if '/' + m + '/' in p:
            exists = 'YES' if (p and os.path.exists(r.get('path',''))) else 'NO'
            print(f'  [{i}] loc={r.get("location_status","")!r}  exists={exists}  path={p[-40:]}')
            break