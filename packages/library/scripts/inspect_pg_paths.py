"""Inspect PG videos for path encoding inconsistencies."""
import sys
sys.path.insert(0, 'src')
from sqlalchemy import text
from models.pg_store import _get_engine
from collections import defaultdict
import os

engine = _get_engine()
with engine.connect() as conn:
    rows = conn.execute(text('SELECT path, recorder_id, task_id, env_id FROM videos')).fetchall()
print(f'Total PG rows: {len(rows)}')


def normalize(p: str) -> str:
    # Use os.path.normpath + lowercase for cross-platform comparison
    return os.path.normpath(p).replace('\\', '/').lower()


groups = defaultdict(list)
for (p, c, t, e) in rows:
    groups[normalize(p)].append((p, c, t, e))

multi = {k: v for k, v in groups.items() if len(v) > 1}
print(f'Distinct after normalize: {len(groups)}')
print(f'Multi-encoded groups: {len(multi)}')

# Show examples of mismatched values across encoding variants
mismatched_examples = 0
print('\nExamples of encoding dups with mismatched values:')
for k, vs in list(multi.items())[:5]:
    print(f'\n  Norm path: {k}')
    for p, c, t, e in vs:
        print(f'    {repr(p):60s} col={c!r} task={t!r} env={e!r}')
    # Check if values are actually different
    val_set = {(c, t, e) for _, c, t, e in vs}
    if len(val_set) > 1:
        mismatched_examples += 1

print(f'\nGroups with mismatched values: {mismatched_examples}/{len(multi)}')