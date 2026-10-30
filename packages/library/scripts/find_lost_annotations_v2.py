"""Find lost video annotations: compare latest backup vs current state."""
import csv
import os
from collections import defaultdict
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

def norm(p):
    return (p or '').replace('\\', '/').lower()

ANN = ['recorder_id', 'task_id', 'env_id']
LATEST_BACKUP = 'runtime/csv_backups/video_manager_20260706_215718.csv'

# Load backup
with open(LATEST_BACKUP, encoding='utf-8-sig') as f:
    bk_rows = list(csv.DictReader(f))
bk_by_n = {norm(r['path']): r for r in bk_rows}
print(f'Backup {LATEST_BACKUP}: {len(bk_rows)} rows, {len(bk_by_n)} unique paths')

# Load current CSV
with open('runtime/data/video_manager.csv', encoding='utf-8-sig') as f:
    csv_rows = list(csv.DictReader(f))
csv_by_n = {norm(r['path']): r for r in csv_rows}
print(f'Current CSV: {len(csv_rows)} rows, {len(csv_by_n)} unique paths')

# Load PG
dsn = os.environ.get('VIDEO_MANAGER_DB_DSN')
eng = create_engine(dsn, poolclass=NullPool, future=True)
with eng.connect() as conn:
    pg_rows = conn.execute(text(f"SELECT path, {', '.join(ANN)} FROM videos")).fetchall()
pg_by_n = {norm(r._mapping['path']): r._mapping for r in pg_rows}
print(f'PG: {len(pg_rows)} rows, {len(pg_by_n)} unique paths')
print()

# Annotated counts
def ann_count(d):
    return sum(1 for r in d.values() if any((r.get(f) or '').strip() for f in ANN))

print(f'Annotated counts:')
print(f'  backup 20260706_215718 : {ann_count(bk_by_n):3}')
print(f'  current CSV            : {ann_count(csv_by_n):3}')
print(f'  PG                     : {ann_count(pg_by_n):3}')
print()

# Find paths where backup has annotation but current doesn't
lost_paths = []
for path, bk in bk_by_n.items():
    bk_ann = {f: (bk.get(f) or '').strip() for f in ANN}
    if not any(bk_ann.values()):
        continue  # backup row wasn't annotated anyway
    cur = csv_by_n.get(path)
    pg = pg_by_n.get(path)
    cur_ann = {f: (cur.get(f) or '').strip() for f in ANN} if cur else {f: '' for f in ANN}
    pg_ann = {f: (pg.get(f) or '').strip() for f in ANN} if pg else {f: '' for f in ANN}
    # Compare to backup
    missing_in_csv = {f for f in ANN if bk_ann[f] and not cur_ann[f]}
    missing_in_pg = {f for f in ANN if bk_ann[f] and not pg_ann[f]}
    if missing_in_csv or missing_in_pg:
        lost_paths.append((path, bk_ann, cur_ann, pg_ann, missing_in_csv, missing_in_pg))

print(f'Paths where backup has annotation but current missing: {len(lost_paths)}')
print()

# Sample first 10
for path, bk_ann, cur_ann, pg_ann, m_csv, m_pg in lost_paths[:10]:
    print(f'  {path[-60:]}')
    print(f'    backup: {bk_ann}')
    print(f'    csv:    {cur_ann}   missing: {m_csv}')
    print(f'    pg:     {pg_ann}   missing: {m_pg}')

# Stats: how many lost in CSV only, PG only, both
lost_csv_only = sum(1 for p in lost_paths if p[4] and not p[5])
lost_pg_only = sum(1 for p in lost_paths if p[5] and not p[4])
lost_both = sum(1 for p in lost_paths if p[4] and p[5])
lost_csv_partial = sum(1 for p in lost_paths if p[4])  # some missing in csv
lost_pg_partial = sum(1 for p in lost_paths if p[5])
print()
print(f'  Lost in CSV only: {lost_csv_only}')
print(f'  Lost in PG only:  {lost_pg_only}')
print(f'  Lost in both:     {lost_both}')
print(f'  CSV total:        {lost_csv_partial}')
print(f'  PG total:         {lost_pg_partial}')