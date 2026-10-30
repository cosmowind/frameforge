"""Debug session matching between CSV and PG."""
import csv
import psycopg2

def get_session(path):
    if not path:
        return ''
    return path.replace('\\', '/').rstrip('/').split('/')[-1]

# Local CSV sessions
with open('runtime/data/video_manager.csv', 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
local_sessions = {get_session(r.get('path', '')) for r in rows}
print(f'Local CSV: {len(rows)} videos, {len(local_sessions)} unique sessions')

# PG sessions
conn = psycopg2.connect('postgresql://ffuser:changeme@db.example.com:5432/video_manager')
cur = conn.cursor()
cur.execute('SELECT path, file_type FROM videos')
pg_all = cur.fetchall()

pg_sessions = {}
for vpath, vtype in pg_all:
    s = get_session(vpath)
    pg_sessions[s] = (vpath, vtype)
print(f'PG: {len(pg_sessions)} sessions')

# Non-local HMD not in data
non_local = []
for s, (vpath, vtype) in pg_sessions.items():
    if s not in local_sessions:
        is_data = '/data/' in (vpath or '').replace('\\', '/')
        is_hmd = (vtype or '').strip() == 'hmd'
        if is_hmd and not is_data:
            non_local.append((s, vpath))

print(f'PG non-local HMD (not data): {len(non_local)}')
for s, vpath in non_local[:10]:
    print(f'  {s}')
    print(f'    {vpath}')

cur.close()
conn.close()
