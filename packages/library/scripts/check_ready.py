"""Check how many unuploaded videos have complete dimension data."""
import csv, os

def load_dim(path):
    with open(f'runtime/data/{path}', 'r', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

with open('runtime/data/video_manager.csv', 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

recorders = {r['id'].strip() for r in load_dim('recorders.csv')}
tasks = {r['task_id'].strip() for r in load_dim('tasks.csv')}
envs = {r['env_id'].strip() for r in load_dim('environments.csv')}

ready = []
for i, r in enumerate(rows):
    if r.get('uploaded','').strip() == 'Yes':
        continue
    cid = r.get('recorder_id','').strip()
    tid = r.get('task_id','').strip()
    eid = r.get('env_id','').strip()
    if not (cid and tid and eid):
        continue
    if cid not in recorders or tid not in tasks or eid not in envs:
        continue
    path = r['path']
    if not os.path.isdir(path):
        continue
    hmd_count = len([f for f in os.listdir(path) if f.endswith('.hmd')])
    size_mb = sum(os.path.getsize(os.path.join(path, f)) for f in os.listdir(path)) / 1024 / 1024
    session = path.replace('\\', '/').rstrip('/').split('/')[-1]
    ready.append((i, r, session, hmd_count, size_mb))

print(f'本地已填好三维表且文件存在的未上传视频: {len(ready)} 个\n')
for idx, r, session, parts, size_mb in ready:
    print(f'  [{idx}] {session}  {parts} parts, {size_mb:.0f} MB  op={r["recorder_id"]}')
