"""Reset all to No, then mark only exact 7 confirmed matches."""
import csv

with open('runtime/data/video_manager.csv', 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
    fieldnames = list(rows[0].keys())

yes_before = sum(1 for r in rows if r.get('uploaded', '').strip() == 'Yes')
print(f'Before: {yes_before} Yes, {len(rows)-yes_before} No')

# Reset all to No
for row in rows:
    row['uploaded'] = 'No'

# Exact 7 confirmed matches from other computer uploads
confirmed = [
    '0625_4aa45c_session_00027',
    '0625_4aa45c_session_00028',
    '0625_4aa45c_session_00029',
    '0625_9df5dc_session_00012',
    '0629_4aa45c_session_00000',
    '0630_9df5dc_session_00008',
    '0630_9df5dc_session_00009',
]

count = 0
for row in rows:
    path = row.get('path', '')
    session = path.replace('\\', '/').rstrip('/').split('/')[-1]
    if session in confirmed:
        row['uploaded'] = 'Yes'
        count += 1
        print(f'  Marked: {session}')

with open('runtime/data/video_manager.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(rows)

yes_after = sum(1 for r in rows if r.get('uploaded', '').strip() == 'Yes')
print(f'After: {yes_after} Yes, {len(rows)-yes_after} No')
