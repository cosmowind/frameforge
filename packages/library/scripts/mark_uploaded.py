"""Mark uploaded sessions in video_manager.csv based on upload_state.json."""
import csv, json, os

RUNTIME = os.path.join(os.path.dirname(__file__), '..', 'runtime', 'data')
csv_path = os.path.join(RUNTIME, 'video_manager.csv')
state_path = os.path.join(RUNTIME, 'upload_state.json')

# Load upload state
with open(state_path, 'r', encoding='utf-8') as f:
    state = json.load(f)

# Extract session names from uploaded paths (strip .mp4 suffix for matching)
uploaded_sessions = set()
for p in state.get('uploaded', []):
    session_name = p.replace('\\', '/').rstrip('/').split('/')[-1]
    # Strip .mp4 suffix since CSV paths are directory paths without extension
    if session_name.endswith('.mp4'):
        session_name = session_name[:-4]
    uploaded_sessions.add(session_name)

print(f"Sessions in upload_state.json: {len(uploaded_sessions)}")
for s in sorted(uploaded_sessions):
    print(f"  {s}")

# Load CSV
with open(csv_path, 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
    fieldnames = list(rows[0].keys())

# Mark matching rows
count = 0
for row in rows:
    path = row.get('path', '')
    session_name = path.replace('\\', '/').rstrip('/').split('/')[-1]
    if session_name in uploaded_sessions and row.get('uploaded', '').strip() != 'Yes':
        row['uploaded'] = 'Yes'
        count += 1
        print(f"  MARKED: {session_name}")

# Write back
with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(rows)

print(f"\nTotal marked: {count}")
yes_count = sum(1 for r in rows if r.get('uploaded', '').strip() == 'Yes')
no_count = len(rows) - yes_count
print(f"CSV status: {yes_count} Yes, {no_count} Not yet")
