"""Migrate PG location_status to per-computer format."""
import psycopg2

def get_location_status(path, old_status):
    normalized = (path or '').replace('\\', '/')
    if '/media/videos' in normalized:
        computer = 'thisPC'
    else:
        computer = 'otherPC'
    state = 'history' if old_status == 'history' else 'local'
    return f'{computer}_{state}'

conn = psycopg2.connect('postgresql://ffuser:changeme@db.example.com:5432/video_manager')
cur = conn.cursor()

cur.execute('SELECT path, location_status FROM videos')
rows = cur.fetchall()

updated = 0
for path, old_status in rows:
    new_status = get_location_status(path, old_status)
    if old_status != new_status:
        cur.execute('UPDATE videos SET location_status = %s WHERE path = %s', (new_status, path))
        updated += 1

conn.commit()
print(f'Updated {updated} rows in PG')

cur.execute('SELECT location_status, COUNT(*) FROM videos GROUP BY location_status ORDER BY location_status')
for status, count in cur.fetchall():
    print(f'  {status}: {count}')

cur.close()
conn.close()
