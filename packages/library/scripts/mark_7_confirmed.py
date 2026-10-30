"""Mark only 7 confirmed uploads, reset rest to No in both CSV and PG."""
import csv
import psycopg2

confirmed = [
    '0625_4aa45c_session_00027',
    '0625_4aa45c_session_00028',
    '0625_4aa45c_session_00029',
    '0625_9df5dc_session_00012',
    '0629_4aa45c_session_00000',
    '0630_9df5dc_session_00008',
    '0630_9df5dc_session_00009',
]

# --- CSV ---
with open('runtime/data/video_manager.csv', 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
    fieldnames = list(rows[0].keys())

for row in rows:
    path = row.get('path', '')
    session = path.replace('\\', '/').rstrip('/').split('/')[-1]
    row['uploaded'] = 'Yes' if session in confirmed else 'No'

with open('runtime/data/video_manager.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(rows)

csv_yes = sum(1 for r in rows if r.get('uploaded', '').strip() == 'Yes')
print(f'CSV: {csv_yes} Yes, {len(rows)-csv_yes} No')

# --- PG ---
conn = psycopg2.connect('postgresql://ffuser:changeme@db.example.com:5432/video_manager')
cur = conn.cursor()

# First reset all to No
cur.execute("UPDATE videos SET uploaded = 'No'")

# Then set Yes for confirmed
for session in confirmed:
    cur.execute("UPDATE videos SET uploaded = 'Yes' WHERE path LIKE %s", (f'%{session}%',))
    if cur.rowcount > 0:
        print(f'  PG marked: {session} ({cur.rowcount} row)')

conn.commit()
cur.execute('SELECT COUNT(*) FROM videos WHERE uploaded = %s', ('Yes',))
pg_yes = cur.fetchone()[0]
print(f'PG: {pg_yes} Yes')

cur.close()
conn.close()
print('\nDone. Only 7 confirmed uploads marked as Yes.')
