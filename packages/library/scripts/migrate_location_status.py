"""Migrate location_status from binary local/history to per-computer format."""
import csv

def get_location_status(path, old_status):
    normalized = path.replace('\\', '/')
    if '/media/videos' in normalized:
        computer = 'thisPC'
    else:
        computer = 'otherPC'
    state = 'history' if old_status == 'history' else 'local'
    return f'{computer}_{state}'

with open('runtime/data/video_manager.csv', 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
    fieldnames = list(rows[0].keys())

migrated = 0
for row in rows:
    old = row.get('location_status', '')
    new = get_location_status(row.get('path', ''), old)
    if old != new:
        row['location_status'] = new
        migrated += 1

with open('runtime/data/video_manager.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(rows)

print(f'Migrated {migrated} rows')
from collections import Counter
counts = Counter(r['location_status'] for r in rows)
for k, v in sorted(counts.items()):
    print(f'  {k}: {v}')
