"""Check unuploaded videos from CSV - what they have and what's missing."""
import csv, os

def load_dim(path):
    with open(f'runtime/data/{path}', 'r', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

with open('runtime/data/video_manager.csv', 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

# Show ALL unuploaded videos with data status
ready = []  # has recorder + task + env filled
partial = []  # missing at least one
for i, r in enumerate(rows):
    if r.get('uploaded', '').strip() == 'Yes':
        continue
    path = r['path']
    session = path.replace('\\', '/').rstrip('/').split('/')[-1]
    cid = r.get('recorder_id', '').strip()
    tid = r.get('task_id', '').strip()
    eid = r.get('env_id', '').strip()
    exists = os.path.isdir(path)

    issues = []
    if not cid: issues.append('no recorder')
    if not tid: issues.append('no task')
    if not eid: issues.append('no env')
    if not exists: issues.append('file not exist')

    row_info = {
        'idx': i,
        'session': session,
        'recorder_id': cid,
        'task_id': tid,
        'env_id': eid,
        'issues': issues,
        'exists': exists,
    }

    if not issues:
        ready.append(row_info)
    else:
        partial.append(row_info)

print(f'Unuploaded videos in CSV: {len(rows) - sum(1 for r in rows if r.get("uploaded","").strip()=="Yes")}')
print(f'  - READY (recorder+task+env all filled, file exists): {len(ready)}')
print(f'  - PARTIAL (some field missing): {len(partial)}')
print()
print('=== READY to upload ===')
for r in ready:
    print(f'  [{r["idx"]}] {r["session"]}  {r["recorder_id"]} / {str(r["task_id"])[:20]}... / {r["env_id"]}')
print()
print('=== PARTIAL (first 20) ===')
for r in partial[:20]:
    print(f'  [{r["idx"]}] {r["session"]}  issues: {r["issues"]}')
    print(f'         recorder={r["recorder_id"]}  task={str(r["task_id"])[:30]}...  env={r["env_id"]}')
