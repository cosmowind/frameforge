"""Find videos with task_id not in tasks.csv."""
import csv, os

def load_dim(path):
    with open(f'runtime/data/{path}', 'r', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

tasks = {r['task_id'].strip() for r in load_dim('tasks.csv')}
recorders = {r['id'].strip() for r in load_dim('recorders.csv')}
envs = {r['env_id'].strip() for r in load_dim('environments.csv')}

with open('runtime/data/video_manager.csv', 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

ready_valid = []
ready_bad_task = []
for i, r in enumerate(rows):
    if r.get('uploaded', '').strip() == 'Yes':
        continue
    cid = r.get('recorder_id', '').strip()
    tid = r.get('task_id', '').strip()
    eid = r.get('env_id', '').strip()
    if not (cid and tid and eid):
        continue
    if not os.path.isdir(r['path']):
        continue
    session = r['path'].replace('\\', '/').rstrip('/').split('/')[-1]
    if tid in tasks:
        ready_valid.append((i, session))
    else:
        ready_bad_task.append((i, session, tid))

print(f'Ready + VALID task_id: {len(ready_valid)}')
print(f'Ready + BAD task_id: {len(ready_bad_task)}')
print()
print('=== Bad task_id rows ===')
for i, s, t in ready_bad_task:
    print(f'  [{i}] {s}  task={t}')
