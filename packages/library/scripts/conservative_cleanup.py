"""保守数据清理（按用户要求）：
1. KEEP: 0625-0629 录制日期 + uploaded=Yes + recorder/task/env 都填好
2. DELETE: 与 KEEP 记录 path 完全相同的（真正的重复行）
3. KEEP: 0701-0705 视频（已经标 thisPC_local）
4. SCAN: 0701-0705 本地目录中还没有的 → 标记添加

只输出 dry-run 结果，不修改任何数据
"""
import csv
import os
import re
import pathlib
from collections import defaultdict

CSV_PATH = 'D:/sp/dev/video-manager/runtime/data/video_manager.csv'

with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
fieldnames = list(rows[0].keys())
print(f'CSV 加载 {len(rows)} 行')

# 1) KEEP: 完整 + uploaded=Yes + 0625-0629
keep_indices = set()
keep_paths = set()  # 用于检测 path 完全重复
for i, r in enumerate(rows):
    p = r.get('path', '').replace('\\', '/')
    m = re.search(r'/(\d{4})/', p)
    date = m.group(1) if m else ''
    has_full = (r.get('recorder_id','').strip() and
                r.get('task_id','').strip() and
                r.get('env_id','').strip() and
                r.get('uploaded','').strip() == 'Yes')
    if date in {'0625','0626','0627','0628','0629'} and has_full:
        keep_indices.add(i)
        keep_paths.add(p)

print(f'KEEP (0625-0629 + uploaded=Yes + 完整): {len(keep_indices)}')

# 2) DELETE: 与 KEEP 同 path（真正的重复行）
#    注意：path 完全相同 → 真正的重复
to_delete = set()
for i, r in enumerate(rows):
    if i in keep_indices:
        continue
    p = r.get('path', '').replace('\\', '/')
    if p in keep_paths:
        to_delete.add(i)

print(f'待删除 (与 KEEP 同 path): {len(to_delete)}')
print('  样本:')
for i in list(to_delete)[:5]:
    r = rows[i]
    print(f'    [{i}] {r.get("path","")}  uploaded={r.get("uploaded","")!r}  c={r.get("recorder_id","")!r}')

# 3) KEEP all 0701-0705
to_keep_0701_0705 = []
for i, r in enumerate(rows):
    p = r.get('path', '').replace('\\', '/')
    m = re.search(r'/(\d{4})/', p)
    date = m.group(1) if m else ''
    if date in {'0701','0702','0703','0704','0705'}:
        to_keep_0701_0705.append((i, r))
print(f'\nKEEP (0701-0705 已有): {len(to_keep_0701_0705)}')

# 4) 扫描本地 0701-0705
print(f'\n=== 扫描本地 0701-0705 ===')
local_sessions = {}  # path -> (device, basename)
local_root = pathlib.Path('/media/videos')
for date in ['0701','0702','0703','0704','0705']:
    date_dir = local_root / date / 'hmd'
    if not date_dir.exists():
        continue
    for entry in date_dir.iterdir():
        if entry.is_dir() and (entry / 'metadata.json').exists():
            base = entry.name
            dev = base.split('_')[1] if '_' in base else ''
            local_sessions[str(entry).replace('\\','/')] = (dev, base)
print(f'  本地共 {len(local_sessions)} 个 HMD session')

# 5) 找新视频 (本地有但 CSV 没有)
existing_paths = {r.get('path','').replace('\\','/') for r in rows}
existing_devs = {(r.get('device_id','').strip(), os.path.basename(r.get('path','').replace('\\','/')))
                 for r in rows}

new_sessions = []
for path, (dev, base) in local_sessions.items():
    if path in existing_paths:
        continue
    if (dev, base) in existing_devs:
        # 已经有同 (device, basename) 的记录，但 path 不一样 → 重复
        print(f'  ⚠ 跳过（已存在同 device+basename）: {base}  本地={path}')
        continue
    new_sessions.append((dev, base, path))

print(f'\n=== 真正新增 (本地有 + CSV 没有) ===')
print(f'  数量: {len(new_sessions)}')
for dev, base, path in new_sessions[:15]:
    print(f'  + {dev:10s} {base}  → {path[-50:]}')

# 6) 总结
print(f'\n=== DRY-RUN 汇总 ===')
print(f'  当前行数: {len(rows)}')
print(f'  - 删除重复: {len(to_delete)}')
print(f'  + 扫描新增: {len(new_sessions)}')
print(f'  → 操作后: {len(rows) - len(to_delete) + len(new_sessions)}')