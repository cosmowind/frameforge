"""Check cloud DB uploaded status."""
import psycopg2

conn = psycopg2.connect('postgresql://ffuser:changeme@db.example.com:5432/video_manager')
cur = conn.cursor()

cur.execute("SELECT path, uploaded FROM video_manager WHERE uploaded = 'Yes' LIMIT 10")
rows = cur.fetchall()
print(f'Cloud DB uploaded=Yes: {len(rows)} rows (showing up to 10)')
for r in rows:
    path = r[0] if r[0] else ''
    session = path.replace('\\', '/').split('/')[-1] if path else ''
    print(f'  {session}: uploaded={r[1]}')

cur.execute('SELECT COUNT(*) FROM video_manager')
total = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM video_manager WHERE uploaded = 'Yes'")
uploaded = cur.fetchone()[0]
print(f'\nCloud DB total: {total}, uploaded=Yes: {uploaded}')

cur.close()
conn.close()
