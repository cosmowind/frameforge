"""Check path patterns in CSV and PG to distinguish computers."""
import csv
import psycopg2

def get_session(path):
    if not path:
        return ''
    return path.replace('\\', '/').rstrip('/').split('/')[-1]

# Load CSV sessions
with open('runtime/data/video_manager.csv', 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

csv_sessions = {}
for row in rows:
    session = get_session(row.get('path', ''))
    csv_sessions[session] = row.get('path', '')

# Check PG paths
conn = psycopg2.connect('postgresql://ffuser:changeme@db.example.com:5432/video_manager')
cur = conn.cursor()
cur.execute('SELECT path, uploaded, file_type FROM videos')
pg_videos = cur.fetchall()

this_computer_sessions = set()
other_computer_sessions = set()

for vpath, vuploaded, vtype in pg_videos:
    session = get_session(vpath)
    if session not in csv_sessions:
        # Not in CSV = other computer
        other_computer_sessions.add(session)
    else:
        # In CSV = this computer
        this_computer_sessions.add(session)

print(f'This computer (in CSV): {len(this_computer_sessions)} sessions')
print(f'Other computer (not in CSV): {len(other_computer_sessions)} sessions')
print(f'PG total: {len(pg_videos)}')

# Check path patterns
print('\nPG path patterns for other computer sessions:')
for vpath, vuploaded, vtype in pg_videos[:5]:
    session = get_session(vpath)
    if session in other_computer_sessions:
        print(f'  {vpath}')

print('\nPG path patterns for this computer sessions:')
for vpath, vuploaded, vtype in pg_videos[:5]:
    session = get_session(vpath)
    if session in this_computer_sessions:
        print(f'  {vpath}')

cur.close()
conn.close()
