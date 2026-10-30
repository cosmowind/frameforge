"""Check which confirmed sessions are in CSV with /media/videos path."""
import csv

def get_session(path):
    if not path:
        return ''
    return path.replace('\\', '/').rstrip('/').split('/')[-1]

confirmed = [
    '0625_4aa45c_session_00027',
    '0625_4aa45c_session_00028',
    '0625_4aa45c_session_00029',
    '0625_9df5dc_session_00012',
    '0629_4aa45c_session_00000',
    '0630_9df5dc_session_00008',
    '0630_9df5dc_session_00009',
]

with open('runtime/data/video_manager.csv', 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

matched = []
for r in rows:
    session = get_session(r.get('path', ''))
    if session in confirmed:
        path = r.get('path', '')
        is_sp = '/media/videos' in path.replace('\\', '/')
        matched.append((session, path, is_sp))

print(f'Confirmed sessions in CSV: {len(matched)}')
for s, p, is_sp in matched:
    print(f'  {s}: /media/videos={is_sp}')
    print(f'    {p}')
