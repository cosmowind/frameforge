"""Check session matching between CSV and PG."""
import csv
import psycopg2

def get_session(path):
    if not path:
        return ''
    return path.replace('\\', '/').rstrip('/').split('/')[-1]

# Load CSV sessions
with open('runtime/data/video_manager.csv', 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
csv_sessions = {get_session(r.get('path', '')) for r in rows}
print(f'CSV sessions: {len(csv_sessions)}')

# PG sessions
conn = psycopg2.connect('postgresql://ffuser:changeme@db.example.com:5432/video_manager')
cur = conn.cursor()
cur.execute('SELECT path, uploaded, file_type FROM videos')
pg_videos = [(get_session(r[0]), r[1], r[2]) for r in cur.fetchall()]
pg_sessions = {s for s, _, _ in pg_videos}
print(f'PG sessions: {len(pg_sessions)}')

# Overlap
overlap = csv_sessions & pg_sessions
print(f'Overlap (in both): {len(overlap)}')

# PG only (non-local)
pg_only = pg_sessions - csv_sessions
print(f'PG only (non-local): {len(pg_only)}')

# CSV only (not in PG)
csv_only = csv_sessions - pg_sessions
print(f'CSV only (not in PG): {len(csv_only)}')

# Check PG uploaded status for overlap sessions
yes_in_overlap = sum(1 for s, u, _ in pg_videos if s in overlap and u == 'Yes')
print(f'\nPG overlap uploaded=Yes: {yes_in_overlap}')
print(f'PG overlap uploaded=No: {len(overlap) - yes_in_overlap}')

# PG only HMD status
pg_only_hmd = [(s, u) for s, u, t in pg_videos if s in pg_only and t == 'hmd']
yes_pg_only_hmd = sum(1 for s, u in pg_only_hmd if u == 'Yes')
print(f'\nPG only HMD: {len(pg_only_hmd)}, uploaded=Yes: {yes_pg_only_hmd}')

cur.close()
conn.close()
