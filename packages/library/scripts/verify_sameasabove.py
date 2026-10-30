"""Verify sameAsAbove saves correctly to PG (and survives scan race)."""
import requests, time, sys

BASE = 'http://127.0.0.1:5000'
data = requests.get(f'{BASE}/api/data').json()
data_sorted = sorted(data, key=lambda r: r.get('path',''))

prev = cur = None
for i in range(1, len(data_sorted)):
    p, c = data_sorted[i-1], data_sorted[i]
    if p.get('recorder_id') and not c.get('recorder_id'):
        prev, cur = p, c
        break

if not prev:
    # fallback: any filled source, any empty target
    for r in data_sorted:
        if r.get('recorder_id'):
            src = r
            break
    for r in data_sorted:
        if not r.get('recorder_id'):
            tgt = r
            break
    prev, cur = src, tgt

print(f'PREV col/task/env = {prev["recorder_id"]} | {prev["task_id"]} | {prev["env_id"]}')
print(f'CUR  col/task/env = {cur["recorder_id"]} | {cur["task_id"]} | {cur["env_id"]}')

orig_cur = (cur['recorder_id'], cur['task_id'], cur['env_id'])
cur['recorder_id'] = prev['recorder_id']
cur['task_id'] = prev['task_id']
cur['env_id'] = prev['env_id']
r = requests.post(f'{BASE}/api/save-rows', json={'rows': [dict(cur)]})
print(f'POST save-rows -> {r.json()}')

time.sleep(0.3)
data2 = requests.get(f'{BASE}/api/data').json()
cur2 = next(r for r in data2 if r['path']==cur['path'])
print(f'AFTER col/task/env = {cur2["recorder_id"]} | {cur2["task_id"]} | {cur2["env_id"]}')
ok = (cur2['recorder_id']==prev['recorder_id'] and
      cur2['task_id']==prev['task_id'] and
      cur2['env_id']==prev['env_id'])
print(f'-> PG 持久化? {ok}')

r2 = requests.post(f'{BASE}/api/scan', json={'directory':'/media/videos','scope':'current'}, timeout=120)
print(f'POST /api/scan -> {r2.status_code}')
time.sleep(0.3)
data3 = requests.get(f'{BASE}/api/data').json()
cur3 = next(r for r in data3 if r['path']==cur['path'])
print(f'AFTER scan col/task/env = {cur3["recorder_id"]} | {cur3["task_id"]} | {cur3["env_id"]}')
ok3 = (cur3['recorder_id']==prev['recorder_id'] and
       cur3['task_id']==prev['task_id'] and
       cur3['env_id']==prev['env_id'])
print(f'-> 触发 scan 后仍持久化? {ok3}')

rollback = dict(cur)
rollback['recorder_id'] = orig_cur[0]
rollback['task_id'] = orig_cur[1]
rollback['env_id'] = orig_cur[2]
requests.post(f'{BASE}/api/save-rows', json={'rows': [rollback]})
print('(rolled back)')

sys.exit(0 if (ok and ok3) else 1)