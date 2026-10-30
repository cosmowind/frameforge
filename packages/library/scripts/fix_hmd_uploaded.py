"""Fix uploaded status: HMD outside /data/ = uploaded, /data/ or non-hmd = not uploaded."""
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

# Fix CSV
for row in rows:
    path = row.get('path', '')
    ftype = row.get('file_type', '').strip()
    is_data = '/data/' in path.replace('\\', '/')
    is_hmd = (ftype == 'hmd')
    if is_hmd and not is_data:
        row['uploaded'] = 'Yes'
    else:
        row['uploaded'] = 'No'

with open('runtime/data/video_manager.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(rows)

csv_yes = sum(1 for r in rows if r.get('uploaded', '').strip() == 'Yes')
print(f'CSV fixed: {csv_yes} Yes, {len(rows)-csv_yes} No')

# Fix PG: same rule for ALL videos
conn = psycopg2.connect('postgresql://ffuser:changeme@db.example.com:5432/video_manager')
cur = conn.cursor()

cur.execute("SELECT path, file_type FROM videos")
all_videos = cur.fetchall()
print(f'PG: checking {len(all_videos)} videos...')

yes_count = 0
for vpath, vtype in all_videos:
    is_data = '/data/' in (vpath or '').replace('\\', '/')
    is_hmd = (vtype or '').strip() == 'hmd'
    if is_hmd and not is_data:
        cur.execute("UPDATE videos SET uploaded = 'Yes' WHERE path = %s", (vpath,))
        yes_count += 1
    else:
        cur.execute("UPDATE videos SET uploaded = 'No' WHERE path = %s", (vpath,))

conn.commit()
print(f'PG fixed: {yes_count} HMD (not data) = Yes, rest = No')

cur.close()
conn.close()
print('\nDone. Both CSV and PG fixed.')
