"""数据整合：消除 CSV+PG 中同一 (device_id, basename) 的重复记录

策略：
1. 按 (device_id, basename) 分组
2. 每组：合并数据（empty 字段从其他 record 取）+ 选最新/最完整版本作为 canonical
3. 规范化 path 为正斜杠
4. 重写 CSV (deduped)
5. 同步 PG（用规范化 path 作为主键）
"""
import csv
import os
import sys
from collections import defaultdict, OrderedDict
from dotenv import load_dotenv

load_dotenv('D:/sp/dev/video-manager/.env')
DSN = os.environ.get('VIDEO_MANAGER_DB_DSN', '')

CSV_PATH = 'D:/sp/dev/video-manager/runtime/data/video_manager.csv'

# ── 1) 加载 CSV ──
with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
fieldnames = list(rows[0].keys())
print(f'CSV 加载 {len(rows)} 行')

# ── 2) 按 (device_id, basename) 分组 ──
groups = OrderedDict()  # key -> list of (idx, row)
no_dev = []  # 没有 device_id 的行
for i, r in enumerate(rows):
    p = r.get('path', '')
    # 规范化 path 为正斜杠
    norm_path = p.replace('\\', '/')
    base = os.path.basename(norm_path)
    dev = (r.get('device_id') or '').strip()
    if not dev:
        no_dev.append((i, r, norm_path))
        continue
    key = f'{dev}|{base}'
    groups.setdefault(key, []).append((i, r, norm_path))

print(f'按 (device_id, basename) 分组: {len(groups)} 组, {sum(len(v) for v in groups.values())} 行')
print(f'无 device_id 的行: {len(no_dev)}')

# ── 3) 合并每组：保留一份 canonical，其他丢弃 ──
def merge_group(items):
    """合并一组重复行，返回单一 canonical 行 + 弃用行索引列表"""
    # 优先级：先看完整性（有 recorder/task/env），再看 uploaded
    def completeness(r):
        score = 0
        for f in ['recorder_id', 'task_id', 'env_id', 'duration_sec', 'uploaded', 'source_device']:
            if r.get(f, '').strip():
                score += 1
        return score
    # 排序：完整度高的优先，uploaded=Yes 优先
    items.sort(key=lambda x: (x[1].get('uploaded','') == 'Yes', completeness(x[1])), reverse=True)
    canonical = dict(items[0][1])
    # 合并：把后面 row 的非空字段填到 canonical
    for _, r, np in items[1:]:
        for k, v in r.items():
            if v and not canonical.get(k):
                canonical[k] = v
    # 规范化 path
    canonical['path'] = canonical.get('path', '').replace('\\', '/')
    return canonical, [idx for idx, _, _ in items[1:]]

deduped_rows = []
dropped_indices = []
for key, items in groups.items():
    if len(items) == 1:
        canonical, _ = merge_group(items)
    else:
        canonical, drop = merge_group(items)
        dropped_indices.extend(drop)
    deduped_rows.append(canonical)

# 处理无 device_id 的行（按 basename 分组）
no_dev_groups = defaultdict(list)
for i, r, np in no_dev:
    base = os.path.basename(np)
    no_dev_groups[base].append((i, r, np))
for base, items in no_dev_groups.items():
    canonical, _ = merge_group(items)
    deduped_rows.append(canonical)

print(f'\n合并后: {len(deduped_rows)} 行 (从 {len(rows)} 去重)')
print(f'删除: {len(dropped_indices)} 个重复索引')

# ── 4) 写回 CSV ──
# 先备份
import shutil
backup_path = CSV_PATH + '.dedup_backup'
shutil.copy(CSV_PATH, backup_path)
print(f'已备份到: {backup_path}')

# 写
with open(CSV_PATH, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
    w.writeheader()
    w.writerows(deduped_rows)
print(f'CSV 已重写: {len(deduped_rows)} 行')

# ── 5) 同步 PG ──
if DSN:
    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import NullPool
    eng = create_engine(DSN, poolclass=NullPool, future=True)
    with eng.begin() as conn:
        # 5a) 备份 PG 数据到临时表
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS videos_backup_before_cleanup AS
            SELECT * FROM videos
        """))
        conn.execute(text("DELETE FROM videos_backup_before_cleanup"))
        conn.execute(text("""
            INSERT INTO videos_backup_before_cleanup
            SELECT * FROM videos
        """))
        print(f'\nPG 已备份到 videos_backup_before_cleanup')

        # 5b) 统计 PG 现有重复
        rs = conn.execute(text("""
            SELECT device_id, path, count(*) as cnt
            FROM videos
            WHERE device_id != '' AND device_id IS NOT NULL
            GROUP BY device_id, path
            HAVING count(*) > 1
        """))
        dup_count = 0
        for row in rs:
            dup_count += 1
        print(f'PG 中 (device_id, path) 重复: {dup_count} 组')

        # 5c) 按 (device_id, basename) 找到重复组
        # PG path 格式多样：统一 replace('\\','/') 后取 basename
        rs = conn.execute(text("""
            SELECT path, uploaded, location_status, duration_sec, recorder_id, task_id, env_id,
                   device_id, scan_date, original_history_date, extra_description, score,
                   file_type, source_device
            FROM videos
            WHERE device_id != '' AND device_id IS NOT NULL
        """))
        pg_rows = []
        for row in rs:
            pg_rows.append(row)

        # 按 (device_id, basename) 分组
        pg_groups = OrderedDict()
        for r in pg_rows:
            norm_path = r[0].replace('\\', '/')
            base = os.path.basename(norm_path)
            dev = (r[7] or '').strip()
            key = f'{dev}|{base}'
            pg_groups.setdefault(key, []).append(r)

        # 合并每组
        deleted_paths = []
        kept_count = 0
        for key, items in pg_groups.items():
            if len(items) == 1:
                kept_count += 1
                continue
            # 完整度排序
            def pg_completeness(r):
                score = 0
                for idx in [1, 3, 4, 5, 6]:  # uploaded, dur, recorder, task, env
                    if r[idx] and str(r[idx]).strip():
                        score += 1
                return score
            items.sort(key=lambda x: (x[1] == 'Yes', pg_completeness(x)), reverse=True)
            canonical = items[0]
            kept_count += 1
            # 把后面 record 的非空字段合并到 canonical
            for r in items[1:]:
                for idx, fname in [(1,'uploaded'),(2,'location_status'),(3,'duration_sec'),
                                    (4,'recorder_id'),(5,'task_id'),(6,'env_id'),
                                    (8,'scan_date'),(9,'original_history_date'),
                                    (10,'extra_description'),(11,'score'),
                                    (12,'file_type'),(13,'source_device')]:
                    if r[idx] and not canonical[idx]:
                        conn.execute(
                            text(f"UPDATE videos SET {fname} = :v WHERE path = :p"),
                            {'v': r[idx], 'p': canonical[0]}
                        )
            # 删除其他
            for r in items[1:]:
                conn.execute(text("DELETE FROM videos WHERE path = :p"), {'p': r[0]})
                deleted_paths.append(r[0])

        print(f'PG 处理: 保留 {kept_count} 条 (从 {len(pg_rows)} 去重), 删除 {len(deleted_paths)} 条')

        # 5d) 把 CSV 的 deduped_rows upsert 到 PG
        # 先按 (device_id, basename) 找 PG 中已存在的，然后决定 update vs insert
        rs = conn.execute(text("SELECT path, device_id FROM videos"))
        pg_existing = {}
        for row in rs:
            base = os.path.basename(row[0].replace('\\','/'))
            key = f'{(row[1] or "").strip()}|{base}'
            pg_existing[key] = row[0]  # path

        upserted = 0
        for r in deduped_rows:
            p = r.get('path','')
            base = os.path.basename(p)
            dev = (r.get('device_id') or '').strip()
            key = f'{dev}|{base}'
            if key in pg_existing:
                # update by current path
                conn.execute(text("""
                    UPDATE videos SET
                        path = :path, location_status = :loc, scan_date = :scan,
                        original_history_date = :orig, uploaded = :uploaded,
                        extra_description = :extra, score = :score, duration_sec = :dur,
                        file_type = :ft, recorder_id = :cid, task_id = :tid,
                        env_id = :eid, source_device = :sd, updated_at = NOW()
                    WHERE path = :cur
                """), {
                    'path': p, 'loc': r.get('location_status',''),
                    'scan': r.get('scan_date',''), 'orig': r.get('original_history_date',''),
                    'uploaded': r.get('uploaded',''), 'extra': r.get('extra_description',''),
                    'score': r.get('score',''), 'dur': r.get('duration_sec',''),
                    'ft': r.get('file_type',''), 'cid': r.get('recorder_id',''),
                    'tid': r.get('task_id',''), 'eid': r.get('env_id',''),
                    'sd': r.get('source_device',''), 'cur': pg_existing[key],
                })
                upserted += 1
            else:
                # insert
                conn.execute(text("""
                    INSERT INTO videos
                    (path, location_status, scan_date, original_history_date, uploaded,
                     extra_description, score, duration_sec, file_type, recorder_id,
                     task_id, env_id, source_device, created_at, updated_at)
                    VALUES (:path, :loc, :scan, :orig, :uploaded, :extra, :score, :dur,
                            :ft, :cid, :tid, :eid, :sd, NOW(), NOW())
                """), {
                    'path': p, 'loc': r.get('location_status',''),
                    'scan': r.get('scan_date',''), 'orig': r.get('original_history_date',''),
                    'uploaded': r.get('uploaded',''), 'extra': r.get('extra_description',''),
                    'score': r.get('score',''), 'dur': r.get('duration_sec',''),
                    'ft': r.get('file_type',''), 'cid': r.get('recorder_id',''),
                    'tid': r.get('task_id',''), 'eid': r.get('env_id',''),
                    'sd': r.get('source_device',''),
                })
                upserted += 1
        print(f'PG upsert: {upserted} 条')

print('\n✅ 整合完成！')
print(f'  CSV: {len(rows)} → {len(deduped_rows)} 行')
print(f'  PG: 同步到 {len(deduped_rows)} 条')
print(f'  备份: {backup_path} + videos_backup_before_cleanup')