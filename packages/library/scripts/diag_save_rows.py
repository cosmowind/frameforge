import sys, os
sys.path.insert(0, 'src')
os.chdir('src')
from models.pg_store import read_csv, get_fieldnames
import json

existing = read_csv()
print('read_csv returned', len(existing), 'rows')
target = '/media/videos/0625/hmd/0625_4aa45c_session_00000'
def _canon(p): return p.replace("\\", "/") if isinstance(p, str) else p
canon = _canon(target)
print('canon:', repr(canon))
hits = [i for i,r in enumerate(existing) if _canon(r.get('path','')) == canon]
print('hits:', hits)
for i in hits:
    r = existing[i]
    print(' ', i, repr(r.get('path')), '| task_id=', repr(r.get('task_id')))
print('\n--- Now also check: after write, what would happen ---')
# Simulate the save_rows function
def save_rows_simulate(rows_to_save):
    fieldnames = get_fieldnames()
    existing2 = read_csv()
    path_to_indices = {}
    for i, r in enumerate(existing2):
        path_to_indices.setdefault(_canon(r.get('path','')), []).append(i)
    updated = 0; added = 0
    for row in rows_to_save:
        path = _canon(row.get('path','').strip())
        cleaned_row = {fn: str(row.get(fn,'')).strip() for fn in fieldnames}
        if path in path_to_indices:
            for idx in path_to_indices[path]:
                existing2[idx] = cleaned_row
                updated += 1
        else:
            existing2.append(cleaned_row)
            path_to_indices[path] = [len(existing2)-1]
            added += 1
    return updated, added, path_to_indices

# Use exactly the body the frontend sent
rows = [{
    "_estimate_sec": 1028, "_size_mb": 784, "recorder_id": "",
    "device_id": "4aa45c", "duration_sec": "945", "env_id": "",
    "extra_description": "x", "file_type": "hmd",
    "location_status": "thisPC_local", "original_history_date": "2026-06-25",
    "path": "/media/videos/0625/hmd/0625_4aa45c_session_00000",
    "scan_date": "2026-07-07", "score": "", "source_device": "qd",
    "task_id": "CURL_TEST_DIAG", "uploaded": "No"
}]
u, a, _ = save_rows_simulate(rows)
print(f"simulated updated={u}, added={a}")
