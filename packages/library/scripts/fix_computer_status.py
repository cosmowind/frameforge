"""Fix uploaded status by computer ownership:
- This computer (/media/videos/): 7 Yes (confirmed), rest No
- Other computer: all Yes (uploaded on other machine)
"""
import csv
import psycopg2

def get_session(path):
    if not path:
        return ''
    return path.replace('\\', '/').rstrip('/').split('/')[-1]

# Load CSV
with open('runtime/data/video_manager.csv', 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
    fieldnames = list(rows[0].keys())

confirmed = [
    '0625_4aa45c_session_00027',
    '0625_4aa45c_session_00028',
    '0625_4aa45c_session_00029',
    '0625_9df5dc_session_00012',
    '0629_4aa45c_session_00000',
    '0630_9df5dc_session_00008',
    '0630_9df5dc_session_00009',
]

for row in rows:
    path = row.get('path', '')
    session = get_session(path)
    is_this_computer = '/media/videos' in path.replace('\\', '/')

    if is_this_computer:
        row['uploaded'] = 'Yes' if session in confirmed else 'No'
    else:
        # Other computer or not exists - mark as uploaded
        row['uploaded'] = 'Yes'

with open('runtime/data/video_manager.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(rows)

yes_count = sum(1 for r in rows if r.get('uploaded', '').strip() == 'Yes')
print(f'CSV: {yes_count} Yes, {len(rows)-yes_count} No')

# Fix PG
conn = psycopg2.connect('postgresql://ffuser:changeme@db.example.com:5432/video_manager')
cur = conn.cursor()

cur.execute("SELECT path FROM videos")
all_paths = [(r[0],) for r in cur.fetchall()]

for (vpath,) in all_paths:
    session = get_session(vpath)
    is_this_computer = '/media/videos' in (vpath or '').replace('\\', '/')

    if is_this_computer:
        if session in confirmed:
            cur.execute("UPDATE videos SET uploaded = 'Yes' WHERE path = %s", (vpath,))
        else:
            cur.execute("UPDATE videos SET uploaded = 'No' WHERE path = %s", (vpath,))
    else:
        cur.execute("UPDATE videos SET uploaded = 'Yes' WHERE path = %s", (vpath,))

conn.commit()
cur.execute("SELECT COUNT(*) FROM videos WHERE uploaded = 'Yes'")
yes_pg = cur.fetchone()[0]
print(f'PG: {yes_pg} Yes')

cur.close()
conn.close()
print('Done.')
