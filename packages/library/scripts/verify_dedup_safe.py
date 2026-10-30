"""安全验证：每个待删除的 0625-0630 行，验证它是被保留行的空副本"""
import csv
import re
from collections import defaultdict

fp = 'D:/sp/dev/video-manager/runtime/data/video_manager.csv'
with open(fp, 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

# 按 path 分组
by_path = defaultdict(list)
for i, r in enumerate(rows):
    p = r.get('path','').replace(chr(92), '/')
    by_path[p].append((i, r))

# 找出 0625-0630 多条 path 的组
multi_path_groups = []
for path, items in by_path.items():
    if len(items) <= 1:
        continue
    m = re.search(r'/(06[2-3][0-9])/', path)
    if not m:
        continue
    date = m.group(1)
    multi_path_groups.append((date, path, items))

print(f'=== 0625-0630 同 path 多条的组: {len(multi_path_groups)} ===')

def score(r):
    s = 0
    for k in ['recorder_id','task_id','env_id','duration_sec','uploaded','source_device']:
        if r.get(k, '').strip():
            s += 1
    return s

# 对每组分析：是否有"完整数据"和"空数据"并存
full_count = 0
empty_count = 0
warning_count = 0
for date, path, items in multi_path_groups:
    scored = [(score(r), i, r) for i, r in items]
    scored.sort(key=lambda x: -x[0])
    best_score, best_i, best_r = scored[0]
    if best_score >= 3:
        full_count += 1
        for s, i, r in scored[1:]:
            if s == 0:
                empty_count += 1
            else:
                missing_in_best = []
                for k in ['recorder_id','task_id','env_id','duration_sec','uploaded','source_device']:
                    if r.get(k,'').strip() and not best_r.get(k,'').strip():
                        missing_in_best.append(f'{k}={r.get(k,"")!r}')
                if missing_in_best:
                    warning_count += 1
                    if warning_count <= 10:
                        print(f'  ⚠ [{date}] {path[-50:]}')
                        print(f'      KEEP [{best_i}]: score={best_score}')
                        print(f'      DROP [{i}]: score={s}, 有但 KEEP 缺的字段: {missing_in_best}')

print(f'\n=== 验证结果 ===')
print(f'  完整数据组: {full_count}')
print(f'  纯空副本 (score=0): {empty_count}')
print(f'  有数据但被覆盖: {warning_count}')

# uploaded=Yes 是否都被保留
print(f'\n=== uploaded=Yes 是否都被保留 ===')
uploaded_kept = 0
uploaded_dropped = 0
for date, path, items in multi_path_groups:
    def score_item(x):
        s = 0
        for k in ['recorder_id','task_id','env_id','duration_sec','uploaded','source_device']:
            if x[1].get(k,'').strip():
                s += 1
        return (x[1].get('uploaded','')=='Yes', s)
    best_i = max(items, key=score_item)[0]
    for i, r in items:
        if r.get('uploaded','').strip() == 'Yes':
            if best_i == i:
                uploaded_kept += 1
            else:
                uploaded_dropped += 1
                if uploaded_dropped <= 10:
                    print(f'  ⚠ uploaded=Yes 但不保留: [{i}] {path[-50:]}')
print(f'  uploaded=Yes 保留: {uploaded_kept}')
print(f'  uploaded=Yes 丢弃: {uploaded_dropped}')

# uploaded=Yes 但字段不完整
print(f'\n=== uploaded=Yes 但字段不全（不会被 dedup，但需修复） ===')
incomplete_uploaded = []
for i, r in enumerate(rows):
    if r.get('uploaded','').strip() != 'Yes':
        continue
    if r.get('recorder_id','').strip() and r.get('task_id','').strip() and r.get('env_id','').strip():
        continue
    incomplete_uploaded.append((i, r))
print(f'  共 {len(incomplete_uploaded)} 条')
for i, r in incomplete_uploaded[:5]:
    print(f'    [{i}] c={r.get("recorder_id","")!r} t={r.get("task_id","")!r} e={r.get("env_id","")!r}')

# 全局统计
print(f'\n=== 整合后总览 ===')
total = len(rows)
uploaded_yes_all = sum(1 for r in rows if r.get('uploaded','').strip() == 'Yes')
uploaded_complete = sum(1 for r in rows if r.get('uploaded','').strip() == 'Yes' and r.get('recorder_id','').strip() and r.get('task_id','').strip() and r.get('env_id','').strip())
this_pc = sum(1 for r in rows if r.get('location_status','').strip() == 'thisPC_local')
print(f'  CSV 总行数: {total}')
print(f'  uploaded=Yes (所有): {uploaded_yes_all}')
print(f'  uploaded=Yes + 完整字段: {uploaded_complete}')
print(f'  thisPC_local: {this_pc}')