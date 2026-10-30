# -*- coding: utf-8 -*-
"""强制将 /media/videos 下所有 session 目录注册到 video_manager.csv（CSV+PG）。"""
import sys, os, csv
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.stdout.reconfigure(encoding='utf-8')

from models.pg_store import read_csv, write_csv
from config import DEFAULT_FIELDNAMES

# Read existing - normalize all paths to forward slashes for comparison
existing = read_csv()
existing_paths = set()
for r in existing:
    p = (r.get('path') or '').replace('\\', '/').replace('\\\\', '/')
    existing_paths.add(p)
print(f'Existing rows: {len(existing)}, unique normalized paths: {len(existing_paths)}')

# Scan directory
base = r'/media/videos'
new_rows = []
for root, dirs, files in os.walk(base):
    for d in dirs:
        if 'session' not in d:
            continue
        p = os.path.join(root, d)
        norm_p = p.replace('\\', '/')
        if norm_p in existing_paths:
            continue
        new_rows.append({
            'path': p,
            'location_status': 'local',
            'scan_date': '',
            'original_history_date': '',
            'uploaded': 'No',
            'file_type': 'hmd',
        })

print(f'New rows found: {len(new_rows)}')
for r in new_rows[:5]:
    print(' ', r['path'])

if not new_rows:
    print('Nothing to register.')
else:
    all_rows = existing + new_rows
    write_csv(all_rows)
    print(f'Written {len(all_rows)} total rows to CSV+PG')
