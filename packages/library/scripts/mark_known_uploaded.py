"""Mark known uploaded sessions as Yes in CSV."""
import csv, os

with open('runtime/data/video_manager.csv', 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
    fieldnames = list(rows[0].keys())

# Sessions confirmed uploaded (from our tests + Recent uploads screenshot)
known_uploaded = [
    '0625_4aa45c_session_00027',
    '0625_4aa45c_session_00028',
    '0625_4aa45c_session_00029',
    '0625_9df5dc_session_00012',
    '0629_4aa45c_session_00000',
    '0630_9df5dc_session_00003_1',
    '0630_9df5dc_session_00002_1',
    '0630_9df5dc_session_00001_1',
    '0630_4aa45c_session_00009',
    '0630_4aa45c_session_00008',
    '0630_4aa45c_session_00007',
]

count = 0
for row in rows:
    path = row.get('path', '')
    session = path.replace('\\', '/').rstrip('/').split('/')[-1]
    if session in known_uploaded and row.get('uploaded', '').strip() != 'Yes':
        row['uploaded'] = 'Yes'
        count += 1
        print(f'MARKED: {session}')

with open('runtime/data/video_manager.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(rows)

yes_count = sum(1 for r in rows if r.get('uploaded', '').strip() == 'Yes')
print(f'\nTotal newly marked: {count}')
print(f'CSV: {yes_count} Yes, {len(rows)-yes_count} No')
