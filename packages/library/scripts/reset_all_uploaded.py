"""Reset ALL videos to uploaded=No in both local CSV and cloud PG."""
import csv
import psycopg2

# --- Reset local CSV ---
csv_path = 'runtime/data/video_manager.csv'
with open(csv_path, 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
    fieldnames = list(rows[0].keys())

yes_before = sum(1 for r in rows if r.get('uploaded', '').strip() == 'Yes')
for row in rows:
    row['uploaded'] = 'No'

with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(rows)

print(f'Local CSV: reset {yes_before} Yes -> all No')

# --- Reset cloud PG ---
conn = psycopg2.connect('postgresql://ffuser:changeme@db.example.com:5432/video_manager')
cur = conn.cursor()

cur.execute('SELECT COUNT(*) FROM videos WHERE uploaded = %s', ('Yes',))
cloud_yes = cur.fetchone()[0]
cur.execute("UPDATE videos SET uploaded = 'No'")
conn.commit()
print(f'Cloud PG: reset {cloud_yes} Yes -> all No')

cur.close()
conn.close()
print('\nAll reset to uploaded=No. Need to re-mark only confirmed uploads.')
