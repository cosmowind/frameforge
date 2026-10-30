"""Compare videos CSV vs PG with path normalization."""
import csv
import os
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

ANNOTATION_FIELDS = ['recorder_id', 'task_id', 'env_id', 'device_id', 'uploaded',
                     'extra_description', 'score', 'duration_sec', 'location_status']

def norm(p):
    return (p or '').replace('\\', '/').lower()

with open('runtime/data/video_manager.csv', encoding='utf-8-sig') as f:
    csv_rows = list(csv.DictReader(f))

dsn = os.environ.get('VIDEO_MANAGER_DB_DSN')
eng = create_engine(dsn, poolclass=NullPool, future=True)

with eng.connect() as conn:
    pg_rows = conn.execute(text('SELECT path, ' + ', '.join(ANNOTATION_FIELDS) + ' FROM videos')).fetchall()

csv_by_n = {norm(r['path']): r for r in csv_rows}
pg_by_n = {norm(r._mapping['path']): r._mapping for r in pg_rows}

shared_n = set(csv_by_n.keys()) & set(pg_by_n.keys())
print(f'归一化后共有路径: {len(shared_n)} (CSV {len(csv_rows)} + PG {len(pg_rows)})')
print(f'CSV 独有: {len(set(csv_by_n.keys()) - set(pg_by_n.keys()))}')
print(f'PG 独有:  {len(set(pg_by_n.keys()) - set(csv_by_n.keys()))}')

diff_count = {f: 0 for f in ANNOTATION_FIELDS}
diff_examples = {f: [] for f in ANNOTATION_FIELDS}
for path in shared_n:
    pg_r = pg_by_n[path]
    csv_r = csv_by_n[path]
    for f in ANNOTATION_FIELDS:
        pg_v = pg_r[f] or ''
        csv_v = csv_r.get(f, '') or ''
        if csv_v != pg_v:
            diff_count[f] += 1
            if len(diff_examples[f]) < 5:
                diff_examples[f].append((path[-50:], csv_v, pg_v))

print()
print('字段差异统计（归一化后）:')
for f in ANNOTATION_FIELDS:
    n = diff_count[f]
    if n > 0:
        print(f'  ✗ {f:20} 差异 {n:3} 行')
        for path, csv_v, pg_v in diff_examples[f]:
            print(f'        …{path}  CSV={csv_v!r}  PG={pg_v!r}')
    else:
        print(f'  ✓ {f:20} 全一致')

# Also check direction: which side is more populated?
print()
print('=== 单边有值的字段（CSV 有 / PG 空 vs PG 有 / CSV 空）===')
csv_only = {f: 0 for f in ANNOTATION_FIELDS}
pg_only = {f: 0 for f in ANNOTATION_FIELDS}
for path in shared_n:
    pg_r = pg_by_n[path]
    csv_r = csv_by_n[path]
    for f in ANNOTATION_FIELDS:
        pg_v = pg_r[f] or ''
        csv_v = csv_r.get(f, '') or ''
        if csv_v and not pg_v:
            csv_only[f] += 1
        elif pg_v and not csv_v:
            pg_only[f] += 1

for f in ANNOTATION_FIELDS:
    if csv_only[f] or pg_only[f]:
        print(f'  {f:20}  CSV-only 有值: {csv_only[f]:3}    PG-only 有值: {pg_only[f]:3}')

# Check which side has MORE recorder/task/env populated (sample)
print()
print('=== 关键字段填充数对比 ===')
for f in ['recorder_id', 'task_id', 'env_id', 'extra_description', 'uploaded']:
    csv_filled = sum(1 for r in csv_rows if (r.get(f) or '').strip())
    pg_filled = sum(1 for pg_r in pg_by_n.values() if (pg_r.get(f) or '').strip())
    print(f'  {f:20} CSV filled: {csv_filled}    PG filled: {pg_filled}    delta: {pg_filled - csv_filled:+d}')