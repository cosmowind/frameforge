"""Fix uploaded status CORRECTLY:
- For LOCAL videos (in CSV): only the 7 confirmed = Yes, rest = No
- For NON-LOCAL videos (not in CSV): HMD not in /data/ = Yes
"""
import csv
import psycopg2

def get_session(path):
    if not path:
        return ''
    return path.replace('\\', '/').rstrip('/').split('/')[-1]

# Load local CSV
with open('runtime/data/video_manager.csv', 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
    fieldnames = list(rows[0].keys())

local_sessions = set()
local_paths = {}
for row in rows:
    session = get_session(row.get('path', ''))
    local_sessions.add(session)
    local_paths[session] = row.get('path', '')

# Confirmed 7 uploads
confirmed = [
    '0625_4aa45c_session_00027',
    '0625_4aa45c_session_00028',
    '0625_4aa45c_session_00029',
    '0625_9df5dc_session_00012',
    '0629_4aa45c_session_00000',
    '0630_9df5dc_session_00008',
    '0630_9df5dc_session_00009',
]

# Fix CSV: local videos
for row in rows:
    session = get_session(row.get('path', ''))
    if session in confirmed:
        row['uploaded'] = 'Yes'
    else:
        row['uploaded'] = 'No'

with open('runtime/data/video_manager.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(rows)

csv_yes = sum(1 for r in rows if r.get('uploaded', '').strip() == 'Yes')
print(f'CSV fixed: {csv_yes} Yes (only 7 confirmed), rest No')

# Fix PG
conn = psycopg2.connect('postgresql://ffuser:changeme@db.example.com:5432/video_manager')
cur = conn.cursor()

cur.execute("SELECT path, file_type FROM videos")
all_videos = cur.fetchall()
print(f'PG: {len(all_videos)} videos')

local_yes = 0
nonlocal_yes = 0
for vpath, vtype in all_videos:
    session = get_session(vpath)
    is_data = '/data/' in (vpath or '').replace('\\', '/')
    is_hmd = (vtype or '').strip() == 'hmd'

    if session in local_sessions:
        # LOCAL video: only confirmed 7 = Yes
        if session in confirmed:
            cur.execute("UPDATE videos SET uploaded = 'Yes' WHERE path = %s", (vpath,))
            local_yes += 1
        else:
            cur.execute("UPDATE videos SET uploaded = 'No' WHERE path = %s", (vpath,))
    else:
        # NON-LOCAL video: HMD not in /data/ = Yes
        if is_hmd and not is_data:
            cur.execute("UPDATE videos SET uploaded = 'Yes' WHERE path = %s", (vpath,))
            nonlocal_yes += 1
        else:
            cur.execute("UPDATE videos SET uploaded = 'No' WHERE path = %s", (vpath,))

conn.commit()
cur.execute("SELECT COUNT(*) FROM videos WHERE uploaded = 'Yes'")
pg_yes = cur.fetchone()[0]
print(f'PG fixed: {pg_yes} Yes (local={local_yes}, nonlocal={nonlocal_yes})')

cur.close()
conn.close()
print('\nDone. Correct logic applied.')
