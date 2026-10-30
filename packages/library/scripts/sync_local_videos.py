"""Sync only local CSV videos to PG. Only modify rows that exist in local CSV."""
import csv
import psycopg2

# Load local CSV
with open('runtime/data/video_manager.csv', 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
    fieldnames = list(rows[0].keys())

local_sessions = set()
for row in rows:
    path = row.get('path', '')
    session = path.replace('\\', '/').rstrip('/').split('/')[-1]
    local_sessions.add(session)

print(f'Local CSV: {len(rows)} videos, {len(local_sessions)} unique sessions')

# --- CSV: keep only local sessions ---
# (already correct in CSV)
csv_yes = sum(1 for r in rows if r.get('uploaded', '').strip() == 'Yes')
print(f'CSV: {csv_yes} Yes, {len(rows)-csv_yes} No')

# --- PG: only update rows where path matches local sessions ---
conn = psycopg2.connect('postgresql://ffuser:changeme@db.example.com:5432/video_manager')
cur = conn.cursor()

# Get PG rows that match local sessions
cur.execute("SELECT id, path, uploaded FROM videos")
pg_all = cur.fetchall()
print(f'PG: total {len(pg_all)} videos')

# Find PG rows that match local sessions
pg_match = []
for pg_id, pg_path, pg_uploaded in pg_all:
    if pg_path:
        session = pg_path.replace('\\', '/').rstrip('/').split('/')[-1]
        if session in local_sessions:
            pg_match.append((pg_id, session, pg_path))

print(f'PG rows matching local sessions: {len(pg_match)}')

# For matched PG rows: set uploaded=No (CSV already has correct Yes/No)
cur.execute("UPDATE videos SET uploaded = 'No' WHERE id IN %s",
            (tuple(r[0] for r in pg_match),))

# Then set Yes for confirmed uploads
confirmed = [
    '0625_4aa45c_session_00027',
    '0625_4aa45c_session_00028',
    '0625_4aa45c_session_00029',
    '0625_9df5dc_session_00012',
    '0629_4aa45c_session_00000',
    '0630_9df5dc_session_00008',
    '0630_9df5dc_session_00009',
]
for pg_id, session, pg_path in pg_match:
    if session in confirmed:
        cur.execute("UPDATE videos SET uploaded = 'Yes' WHERE id = %s", (pg_id,))
        print(f'  PG Yes: {session}')

conn.commit()

# Verify
cur.execute("SELECT COUNT(*) FROM videos WHERE uploaded = 'Yes'")
pg_yes = cur.fetchone()[0]
print(f'PG after sync: {pg_yes} Yes (unchanged for non-local videos)')

cur.close()
conn.close()
print('\nDone. Only local CSV video rows modified in PG.')
