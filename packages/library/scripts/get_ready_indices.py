"""Get all ready video indices."""
import csv, os

with open('runtime/data/video_manager.csv', 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

ready = []
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
    ready.append((i, session))

print(f'Reay: {len(ready)} videos')
indices = ' '.join(str(idx) for idx, _ in ready)
print(f'--row-index {indices}')
