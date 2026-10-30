"""Mark all sessions visible in Recent uploads as uploaded in CSV."""
import csv, os

with open('runtime/data/video_manager.csv', 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
    fieldnames = list(rows[0].keys())

# Sessions visible in Recent uploads that are confirmed uploaded on frameforge
# (including "Already uploaded — skipped" and previously uploaded sessions)
already_on_server = [
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
    '0630_4aa45c_session_00010',
    '0630_9df5dc_session_00004',
    '0630_9df5dc_session_00005',
    '0630_9df5dc_session_00006',
    '0630_4aa45c_session_00006',
    '0630_4aa45c_session_00005',
    '0630_4aa45c_session_00004',
    '0630_4aa45c_session_00003',
    '0630_4aa45c_session_00002',
    '0630_4aa45c_session_00001',
    '0630_4aa45c_session_00000',
    '0630_9df5dc_session_00000',
    '0629_9df5dc_session_00000',
    '0629_9df5dc_session_00001',
    '0629_9df5dc_session_00002',
    '0629_9df5dc_session_00003',
    '0629_9df5dc_session_00004',
    '0629_9df5dc_session_00005',
    '0629_9df5dc_session_00006',
    '0629_9df5dc_session_00007',
    '0629_9df5dc_session_00008',
    '0629_9df5dc_session_00009',
    '0629_9df5dc_session_00010',
    '0629_9df5dc_session_00011',
    '0629_9df5dc_session_00012',
    '0629_9df5dc_session_00013',
    '0629_9df5dc_session_00014',
    '0629_9df5dc_session_00015',
    '0629_9df5dc_session_00016',
    '0629_9df5dc_session_00017',
    '0629_9df5dc_session_00018',
    '0629_9df5dc_session_00019',
    '0629_9df5dc_session_00020',
    '0629_4aa45c_session_00001',
    '0629_4aa45c_session_00002',
    '0629_4aa45c_session_00003',
    '0629_4aa45c_session_00004',
    '0629_4aa45c_session_00005',
    '0629_4aa45c_session_00006',
    '0629_4aa45c_session_00007',
    '0629_4aa45c_session_00008',
    '0629_4aa45c_session_00009',
    '0629_4aa45c_session_00010',
    '0629_4aa45c_session_00011',
    '0629_4aa45c_session_00012',
    '0629_4aa45c_session_00013',
    '0629_4aa45c_session_00014',
    '0629_4aa45c_session_00015',
    '0629_4aa45c_session_00016',
    '0629_4aa45c_session_00017',
    '0629_4aa45c_session_00018',
    '0629_4aa45c_session_00019',
    '0629_4aa45c_session_00020',
]

count = 0
for row in rows:
    path = row.get('path', '')
    session = path.replace('\\', '/').rstrip('/').split('/')[-1]
    if session in already_on_server and row.get('uploaded', '').strip() != 'Yes':
        row['uploaded'] = 'Yes'
        count += 1
        print(f'MARKED: {session}')

with open('runtime/data/video_manager.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(rows)

print(f'\nTotal newly marked: {count}')
yes_count = sum(1 for r in rows if r.get('uploaded', '').strip() == 'Yes')
print(f'CSV status: {yes_count} Yes, {len(rows)-yes_count} Not yet')
