"""show 0701-0705 paths"""
import csv
fp = 'D:/sp/dev/video-manager/runtime/data/video_manager.csv'
with open(fp, 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
for r in rows[:50]:
    p = (r.get('path','') or '').replace(chr(92), '/')
    if any('/'+d+'/' in p for d in ['0701','0702','0704']):
        print(f'  loc={r.get("location_status","")!r}  path={p}')
print('---')
# Sample 0701
for r in rows:
    p = (r.get('path','') or '').replace(chr(92), '/')
    if '/0701/' in p:
        print(f'  0701: {p}')
        break
print('Total 0701-0705:')
sep = chr(92)
n = 0
for r in rows:
    p = (r.get('path','') or '').replace(sep, '/')
    if any('/'+d+'/' in p for d in ['0701','0702','0704']):
        n += 1
print(f'  {n}')