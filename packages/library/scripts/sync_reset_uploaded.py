"""Reset uploaded=No in BOTH local CSV and cloud PG."""
import csv
import psycopg2

# --- Reset local CSV ---
with open('runtime/data/video_manager.csv', 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
    fieldnames = list(rows[0].keys())

csv_yes = sum(1 for r in rows if r.get('uploaded', '').strip() == 'Yes')
for row in rows:
    row['uploaded'] = 'No'

with open('runtime/data/video_manager.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(rows)

print(f'Local CSV: {csv_yes} Yes -> all No')

# --- Reset cloud PG ---
conn = psycopg2.connect('postgresql://ffuser:changeme@db.example.com:5432/video_manager')
cur = conn.cursor()

cur.execute('SELECT COUNT(*) FROM videos WHERE uploaded = %s', ('Yes',))
pg_yes = cur.fetchone()[0]
cur.execute("UPDATE videos SET uploaded = 'No'")
conn.commit()
print(f'Cloud PG: {pg_yes} Yes -> all No')

cur.close()
conn.close()
print('\nBoth CSV and PG reset to all No. Ready to re-mark confirmed uploads.')
