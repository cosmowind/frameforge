import csv
import os
fp = 'D:/sp/dev/video-manager/runtime/data/video_manager.csv'
with open(fp, 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
n_dur = 0; n_no = 0
for r in rows:
    if (r.get('duration_sec','') or '').strip():
        n_dur += 1
    else:
        n_no += 1
print(f'全局: {n_dur}/{len(rows)} 有 duration ({n_no} 没)')
print('---')
n_dur = 0; n_no = 0
missing = []
for r in rows:
    p = (r.get('path','') or '').replace(chr(92), '/')
    if any('/'+d+'/' in p for d in ['0701','0702','0704']):
        if (r.get('duration_sec','') or '').strip():
            n_dur += 1
        else:
            n_no += 1
            missing.append(os.path.basename(p))
print(f'0701-0705: {n_dur} 有 / {n_no} 没')
for m in missing:
    print(f'  缺: {m}')