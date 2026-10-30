"""Sync uploaded=Yes from local CSV to cloud PG."""
import csv
import psycopg2

# Get sessions that are uploaded=Yes in local CSV
with open('runtime/data/video_manager.csv', 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

uploaded_sessions = []
for r in rows:
    if r.get('uploaded', '').strip() == 'Yes':
        path = r.get('path', '')
        session = path.replace('\\', '/').rstrip('/').split('/')[-1]
        uploaded_sessions.append(session)

print(f'Local CSV uploaded=Yes: {len(uploaded_sessions)} sessions')

# Connect to cloud PG
conn = psycopg2.connect('postgresql://ffuser:changeme@db.example.com:5432/video_manager')
cur = conn.cursor()

# Check cloud DB
cur.execute('SELECT COUNT(*) FROM videos WHERE uploaded = %s', ('Yes',))
cloud_uploaded = cur.fetchone()[0]
print(f'Cloud PG uploaded=Yes: {cloud_uploaded}')

# Update cloud PG for each session
updated = 0
for session in uploaded_sessions:
    cur.execute(
        'UPDATE videos SET uploaded = %s WHERE path LIKE %s AND (uploaded != %s OR uploaded IS NULL)',
        ('Yes', f'%{session}%', 'Yes')
    )
    if cur.rowcount > 0:
        updated += cur.rowcount
        print(f'  UPDATED: {session}')

conn.commit()
print(f'\nTotal rows updated in cloud PG: {updated}')

# Verify
cur.execute('SELECT COUNT(*) FROM videos WHERE uploaded = %s', ('Yes',))
cloud_uploaded_after = cur.fetchone()[0]
print(f'Cloud PG uploaded=Yes after sync: {cloud_uploaded_after}')

cur.close()
conn.close()
