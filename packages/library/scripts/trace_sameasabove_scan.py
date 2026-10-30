"""Trace scan's effect on local CSV."""
import requests, csv, time

BASE = 'http://127.0.0.1:5000'
TEST_PATH = None

# 用一个能确定 prev 有 cur 没有 的 pair
data = requests.get(f'{BASE}/api/data').json()
data_sorted = sorted(data, key=lambda r: r.get('path',''))
prev = cur = None
for i in range(1, len(data_sorted)):
    p, c = data_sorted[i-1], data_sorted[i]
    if p.get('recorder_id') and not c.get('recorder_id'):
        prev, cur = p, c
        TEST_PATH = cur['path']
        break
if not prev:
    # fallback: 任意 filled 作为 source，任意 empty 作为 target
    for r in data_sorted:
        if r.get('recorder_id'):
            src = r
            break
    for r in data_sorted:
        if not r.get('recorder_id'):
            tgt = r
            break
    prev, cur = src, tgt
    TEST_PATH = cur['path']

print(f'TEST_PATH: ...{TEST_PATH[-30:]}')
print(f'PREV col/task/env = {prev["recorder_id"]} | {prev["task_id"]} | {prev["env_id"]}')
print(f'CUR  col/task/env = {cur["recorder_id"]} | {cur["task_id"]} | {cur["env_id"]}')

# mutate + save
cur['recorder_id'] = prev['recorder_id']
cur['task_id'] = prev['task_id']
cur['env_id'] = prev['env_id']
r = requests.post(f'{BASE}/api/save-rows', json={'rows': [dict(cur)]})
print(f'\n1) POST save-rows -> {r.json()}')

# 检查 local CSV
time.sleep(0.3)
with open('runtime/data/video_manager.csv','r',encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
matches = [r for r in rows if r['path']==TEST_PATH]
print(f'2) LOCAL CSV after save: {len(matches)} dup row(s)')
for i, r in enumerate(matches):
    print(f'   [{i}] col/task/env = {r["recorder_id"]} | {r["task_id"]} | {r["env_id"]}')

# 触发 scan
r2 = requests.post(f'{BASE}/api/scan', json={'directory':'/media/videos','scope':'current'}, timeout=120)
print(f'\n3) POST /api/scan -> {r2.status_code}')

# 再次检查 local CSV
time.sleep(0.3)
with open('runtime/data/video_manager.csv','r',encoding='utf-8-sig') as f:
    rows2 = list(csv.DictReader(f))
matches2 = [r for r in rows2 if r['path']==TEST_PATH]
print(f'4) LOCAL CSV after scan: {len(matches2)} dup row(s)')
for i, r in enumerate(matches2):
    print(f'   [{i}] col/task/env = {r["recorder_id"]} | {r["task_id"]} | {r["env_id"]}')

# /api/data
data2 = requests.get(f'{BASE}/api/data').json()
cur2 = next(r for r in data2 if r['path']==TEST_PATH)
print(f'\n5) /api/data after scan: col/task/env = {cur2["recorder_id"]} | {cur2["task_id"]} | {cur2["env_id"]}')

# 回滚
rollback = dict(cur)
rollback['recorder_id'] = ''
rollback['task_id'] = ''
rollback['env_id'] = ''
requests.post(f'{BASE}/api/save-rows', json={'rows': [rollback]})
print('(rolled back)')