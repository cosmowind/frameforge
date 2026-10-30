"""Verify CSV status breakdown."""
import csv, os

def get_session(path):
    if not path:
        return ''
    return path.replace('\\', '/').rstrip('/').split('/')[-1]

with open('runtime/data/video_manager.csv', 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

confirmed = [
    '0625_4aa45c_session_00027',
    '0625_4aa45c_session_00028',
    '0625_4aa45c_session_00029',
    '0625_9df5dc_session_00012',
    '0629_4aa45c_session_00000',
    '0630_9df5dc_session_00008',
    '0630_9df5dc_session_00009',
]

this_yes = 0
this_no = 0
other_yes = 0

for r in rows:
    path = r.get('path', '')
    session = get_session(path)
    is_sp = '/media/videos' in path.replace('\\', '/')

    if is_sp:
        if session in confirmed:
            this_yes += 1
        else:
            this_no += 1
    else:
        other_yes += 1

print(f'This computer confirmed Yes: {this_yes}')
print(f'This computer not confirmed No: {this_no}')
print(f'Other (uploaded on other PC): {other_yes}')
print(f'Total Yes: {this_yes + other_yes}')
