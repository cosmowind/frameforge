"""Check unuploaded videos - what's missing."""
import csv, os

def load_dim(path):
    with open(f'runtime/data/{path}', 'r', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

recorders = {r['id'].strip() for r in load_dim('recorders.csv')}
tasks = {r['task_id'].strip() for r in load_dim('tasks.csv')}
envs = {r['env_id'].strip() for r in load_dim('environments.csv')}

with open('runtime/data/video_manager.csv', 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

has_data = []
missing_recorder = []
missing_task = []
missing_env = []
missing_all = []
not_exist = []

for i, r in enumerate(rows):
    if r.get('uploaded', '').strip() == 'Yes':
        continue
    path = r['path']
    session = path.replace('\\', '/').rstrip('/').split('/')[-1]
    cid = r.get('recorder_id', '').strip()
    tid = r.get('task_id', '').strip()
    eid = r.get('env_id', '').strip()

    if not os.path.isdir(path):
        not_exist.append((i, session))
        continue
    if not cid:
        missing_recorder.append((i, session))
    elif cid not in recorders:
        missing_recorder.append((i, session, cid))
    elif not tid:
        missing_task.append((i, session))
    elif tid not in tasks:
        missing_task.append((i, session, tid))
    elif not eid:
        missing_env.append((i, session))
    elif eid not in envs:
        missing_env.append((i, session, eid))
    else:
        has_data.append((i, session, r['recorder_id']))

print(f'Total unuploaded: {len(rows) - sum(1 for r in rows if r.get("uploaded","").strip()=="Yes")}')
print(f'  - file not exist: {len(not_exist)}')
print(f'  - missing recorder: {len(missing_recorder)}')
print(f'  - missing task: {len(missing_task)}')
print(f'  - missing env: {len(missing_env)}')
print(f'  - READY to upload: {len(has_data)}')
print()
print('=== READY to upload ===')
for i, s, op in has_data:
    print(f'  [{i}] {s}  op={op}')
print()
print('=== Missing recorder (first 5) ===')
for item in missing_recorder[:5]:
    print(f'  {item}')
print()
print('=== Missing task (first 5) ===')
for item in missing_task[:5]:
    print(f'  {item}')
print()
print('=== Missing env (first 5) ===')
for item in missing_env[:5]:
    print(f'  {item}')
