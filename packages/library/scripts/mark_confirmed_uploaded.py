"""Mark confirmed uploaded videos from Recent uploads list."""
import csv

confirmed = [
    '0625_9df5dc_session_00012',
    '0625_4aa45c_session_00029',
    '0625_4aa45c_session_00028',
    '0625_4aa45c_session_00027',
    '0629_4aa45c_session_00000',
    '0630_9df5dc_session_00003_1',
    '0630_9df5dc_session_00002_1',
    '0630_9df5dc_session_00001_1',
    '0630_4aa45c_session_00009',
    '0630_4aa45c_session_00008',
    '0630_4aa45c_session_00007',
    '0630_4aa45c_session_00006',
    '0630_4aa45c_session_00005',
    '0630_4aa45c_session_00004',
    '0630_4aa45c_session_00003',
    '0630_4aa45c_session_00002',
    '0630_4aa45c_session_00000',
    '0630_4aa45c_session_00001',
    '0630_9df5dc_session_00009',
    '0630_9df5dc_session_00008',
]

with open('runtime/data/video_manager.csv', 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
    fieldnames = list(rows[0].keys())

matched = []
for i, r in enumerate(rows):
    path = r.get('path', '')
    session = path.replace('\\', '/').rstrip('/').split('/')[-1]
    if session in confirmed:
        matched.append((i, session))

print(f'Found {len(matched)} matches in local CSV:')
for idx, session in matched:
    print(f'  [{idx}] {session}')

# Mark them
count = 0
for i, session in matched:
    if rows[i].get('uploaded', '').strip() != 'Yes':
        rows[i]['uploaded'] = 'Yes'
        count += 1

with open('runtime/data/video_manager.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(rows)

print(f'\nMarked {count} videos as uploaded=Yes')
yes_count = sum(1 for r in rows if r.get('uploaded', '').strip() == 'Yes')
no_count = len(rows) - yes_count
print(f'CSV status: {yes_count} Yes, {no_count} No')
