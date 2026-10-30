"""Distinguish video ownership by path."""
import csv, os

with open('runtime/data/video_manager.csv', 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

sp_count = 0
video_count = 0
for r in rows:
    path = r.get('path', '').replace('\\', '/')
    if os.path.isdir(path) or os.path.isfile(path):
        if '/media/videos' in path:
            sp_count += 1
        elif '/media' in path:
            video_count += 1

print(f'This computer (/media/videos): {sp_count} local files')
print(f'Other computer (/media): {video_count} local files')
