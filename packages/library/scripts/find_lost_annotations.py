"""Find the 130 'extra' video records (CSV duplicates / PG-only paths) and check their annotations.

Compare:
- For each duplicate path in CSV: which row has annotation, which is empty?
- For each PG-only path (slash mismatch): does it have annotations that CSV lost?
"""
import csv
import os
from collections import defaultdict
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

def norm(p):
    return (p or '').replace('\\', '/').lower()

ANNOT_FIELDS = ['recorder_id', 'task_id', 'env_id', 'device_id', 'score']

# ─── Load CSV ───
with open('runtime/data/video_manager.csv', encoding='utf-8-sig') as f:
    csv_rows = list(csv.DictReader(f))
print(f'CSV total rows: {len(csv_rows)}')

# Group by normalized path
by_path = defaultdict(list)
for i, r in enumerate(csv_rows):
    by_path[norm(r['path'])].append((i, r))

dup_paths = {p: rs for p, rs in by_path.items() if len(rs) > 1}
print(f'CSV duplicate path groups: {len(dup_paths)}  (rows beyond first copy: {sum(len(rs)-1 for rs in dup_paths.values())})')

# For each duplicate path: compare annotations
print()
print('=== Duplicate rows in CSV: do copies differ in annotations? ===')
dup_with_diff = 0
for path, rows in list(dup_paths.items())[:5]:
    print(f'\n[{path[-60:]}]  ({len(rows)} rows)')
    for i, r in rows:
        ann = '|'.join(f'{f}={r.get(f,"")!r}' for f in ANNOT_FIELDS if r.get(f))
        print(f'  row#{i:3}  {ann or "(all empty)"}')
        if len(rows) > 2:
            # show full first row to see if has values
            pass

# How many duplicate groups have at least one row with annotation while another is empty?
dup_with_annotation_loss = 0
for path, items in dup_paths.items():
    rows_only = [r for (i, r) in items]
    annotated = [r for r in rows_only if any((r.get(f) or '').strip() for f in ANNOT_FIELDS)]
    empty = [r for r in rows_only if not any((r.get(f) or '').strip() for f in ANNOT_FIELDS)]
    if annotated and empty:
        dup_with_annotation_loss += 1

print(f'\n>>> Duplicate paths where some rows have annotation and some are empty: {dup_with_annotation_loss}')
print(f'    (these are the candidates — annotations might be in the "extra" copy)')

# Now check PG
dsn = os.environ.get('VIDEO_MANAGER_DB_DSN')
eng = create_engine(dsn, poolclass=NullPool, future=True)
with eng.connect() as conn:
    pg_rows = conn.execute(text(f"SELECT path, {', '.join(ANNOT_FIELDS)} FROM videos")).fetchall()

pg_by_n = defaultdict(list)
for r in pg_rows:
    pg_by_n[norm(r._mapping['path'])].append(r._mapping)

# How many paths appear ONLY in PG (i.e. normalized path not in CSV)?
csv_norms = set(by_path.keys())
pg_only_norms = [p for p in pg_by_n if p not in csv_norms]
print(f'\nPaths in PG but NOT in CSV (after normalization): {len(pg_only_norms)}')
if pg_only_norms:
    print('Examples:')
    for p in pg_only_norms[:5]:
        pg_r = pg_by_n[p][0]
        ann = '|'.join(f'{f}={pg_r.get(f,"")!r}' for f in ANNOT_FIELDS if pg_r.get(f))
        # Find original CSV path that might match by basename
        basename = p.split('/')[-1]
        print(f'  {p}')
        print(f'    PG: {ann or "(empty)"}')

# Check: among duplicate paths, do PG and CSV agree on which row is "the" annotation?
print()
print('=== Sample duplicate path resolution ===')
sample = list(dup_paths.items())[:3]
for path, items in sample:
    print(f'\n[{path[-60:]}]')
    pg_r = pg_by_n.get(path, [None])[0]
    if pg_r:
        ann = '|'.join(f'{f}={pg_r.get(f,"")!r}' for f in ANNOT_FIELDS if pg_r.get(f))
        print(f'  PG : {ann or "(empty)"}')
    for i, r in items:
        ann = '|'.join(f'{f}={r.get(f,"")!r}' for f in ANNOT_FIELDS if r.get(f))
        print(f'  CSV row#{i}: {ann or "(empty)"}')