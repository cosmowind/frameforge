"""保守数据清理（dry-run）：
- 保留：0625-0629 录制日期 + uploaded=Yes + recorder/task/env 都填好
- 删除：与保留记录 path 相同 / (device_id, basename) 相同的记录
- 保留：0701-0705 视频（已经标 thisPC_local）
- 输出：每个动作的明细 + 整合后预估行数
"""
import csv
import os
import sys
from collections import defaultdict, OrderedDict

CSV_PATH = 'D:/sp/dev/video-manager/runtime/data/video_manager.csv'

with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
fieldnames = list(rows[0].keys())
print(f'CSV 加载 {len(rows)} 行')

# ── 1) 找出 KEEP 集合（0625-0629 + uploaded=Yes + 完整字段）──
keep_indices = set()
keep_keys = set()  # 防止删除 KEEP 自身
for i, r in enumerate(rows):
    p = r.get('path', '')
    norm = p.replace('\\', '/')
    base = os.path.basename(norm)
    dev = (r.get('device_id') or '').strip()
    # 提取日期：路径里 4 位数字
    import re
    m = re.search(r'[/\\](\d{4})[/\\]', norm)
    date = m.group(1) if m else ''
    # 完整字段检查
    has_full = (r.get('recorder_id','').strip() and
                r.get('task_id','').strip() and
                r.get('env_id','').strip() and
                r.get('uploaded','').strip() == 'Yes')
    if date in {'0625','0626','0627','0628','0629'} and has_full:
        keep_indices.add(i)
        keep_keys.add((dev, base))

print(f'KEEP (0625-0629 + uploaded=Yes + 完整字段): {len(keep_indices)} 行')

# ── 2) 找出 KEEP 之外、与 KEEP 重复的 → 候选删除 ──
to_delete = set()
to_keep_no_upload = []  # 0625-0629 完整但未上传的（应该保留为 pending）
to_keep_no_data = []     # 字段不完整的（保留待修复）
to_keep_0701_0705 = []   # 0701-0705 的视频
no_date_match = []       # 无法解析日期的

for i, r in enumerate(rows):
    if i in keep_indices:
        continue
    p = r.get('path', '')
    norm = p.replace('\\', '/')
    base = os.path.basename(norm)
    dev = (r.get('device_id') or '').strip()
    import re
    m = re.search(r'[/\\](\d{4})[/\\]', norm)
    date = m.group(1) if m else ''

    # 检查是否与 KEEP 重复 (device_id, basename)
    if (dev, base) in keep_keys:
        to_delete.add(i)
        continue

    # 0701-0705
    if date in {'0701','0702','0703','0704','0705'}:
        to_keep_0701_0705.append((i, r))
        continue

    # 0625-0629 完整但未上传
    has_full_data = (r.get('recorder_id','').strip() and
                     r.get('task_id','').strip() and
                     r.get('env_id','').strip())
    if date in {'0625','0626','0627','0628','0629'} and has_full_data:
        to_keep_no_upload.append((i, r))
        continue

    # 0625-0629 数据不完整
    if date in {'0625','0626','0627','0628','0629'}:
        to_keep_no_data.append((i, r))
        continue

    # 其他
    no_date_match.append((i, r))

print(f'\n=== 分类汇总 ===')
print(f'  KEEP (已上传完整): {len(keep_indices)}')
print(f'  待删除 (与 KEEP 重复): {len(to_delete)}')
print(f'  KEEP (0625-0629 完整未上传): {len(to_keep_no_upload)}')
print(f'  KEEP (0625-0629 不完整): {len(to_keep_no_data)}')
print(f'  KEEP (0701-0705): {len(to_keep_0701_0705)}')
print(f'  其他 (无日期/其他日期): {len(no_date_match)}')

# ── 3) 验证：to_delete 是否真的重复 ──
print(f'\n=== 待删除样本 (前 5) ===')
for i in list(to_delete)[:5]:
    r = rows[i]
    p = r.get('path', '')
    norm = p.replace('\\', '/')
    base = os.path.basename(norm)
    dev = (r.get('device_id') or '').strip()
    has_data = '✓' if r.get('recorder_id') and r.get('task_id') else '✗'
    print(f'  [{i}] {has_data} uploaded={r.get("uploaded","")!r:6s} dev={dev!r:10s} base={base!r} path={p!r}')

# ── 4) 验证：0701-0705 是否与已有重复 ──
print(f'\n=== 0701-0705 (本机) 详情 ===')
for i, r in to_keep_0701_0705[:8]:
    p = r.get('path', '')
    norm = p.replace('\\', '/')
    base = os.path.basename(norm)
    dev = (r.get('device_id') or '').strip()
    print(f'  [{i}] dev={dev!r} base={base!r} loc={r.get("location_status","")!r} uploaded={r.get("uploaded","")!r}')

# ── 5) 验证：0701-0705 文件是否真的在本地存在 ──
print(f'\n=== 0701-0705 文件存在性 ===')
exists_count = 0
missing_count = 0
for i, r in to_keep_0701_0705:
    p = r.get('path', '')
    if p and os.path.exists(p):
        exists_count += 1
    else:
        missing_count += 1
print(f'  存在: {exists_count} / {len(to_keep_0701_0705)}')
print(f'  缺失: {missing_count}')

# ── 6) 扫描本地 0701-0705 看有没有 CSV 还没记录的视频 ──
print(f'\n=== 扫描本地 0701-0705 新增 ===')
import pathlib
candidates = set()  # (device_id, basename) of local files
local_root = pathlib.Path('/media/videos')
for date in ['0701', '0702', '0703', '0704', '0705']:
    date_dir = local_root / date / 'hmd'
    if not date_dir.exists():
        print(f'  {date} 不存在: {date_dir}')
        continue
    for entry in date_dir.iterdir():
        if entry.is_dir() and (entry / 'metadata.json').exists():
            # HMD session
            base = entry.name
            dev = base.split('_')[1] if '_' in base else ''
            candidates.add((dev, base, str(entry).replace('\\','/')))

print(f'  本地共 {len(candidates)} 个 HMD session')

# 检查哪些已在 CSV 中
existing = set()
for i, r in enumerate(rows):
    p = r.get('path', '')
    norm = p.replace('\\', '/')
    base = os.path.basename(norm)
    dev = (r.get('device_id') or '').strip()
    existing.add((dev, base))

new_candidates = [c for c in candidates if (c[0], c[1]) not in existing]
print(f'  CSV 中没有的新增: {len(new_candidates)}')
if new_candidates:
    print('  样本 (前 10):')
    for dev, base, path in new_candidates[:10]:
        print(f'    {dev:10s} {base}  ({path[-50:]})')

print(f'\n=== DRY-RUN 完成 ===')
print(f'  删除后预估行数: {len(rows) - len(to_delete)} 行 (CSV)')
print(f'  + 新增本地: {len(new_candidates)} 行 → 最终 {len(rows) - len(to_delete) + len(new_candidates)} 行')