"""从 .hmd_fast.json 状态文件回写 duration_sec 到 video_manager.csv + PG

严格条件（只处理符合所有条件的视频）：
1. location_status == 'thisPC_local'（本机本地）
2. uploaded == 'No' 或空（未上传的）
3. mp4 文件在 cache 中存在（确实预处理完成）
4. status.json status == 'done' 且 duration_sec > 0

不处理：
- 已上传的视频（duration 不会再被需要）
- 其他电脑的历史/本地视频（不在本机，不用动）
- 没有 mp4 的（预处理没完成）
- status=processing 或 error 的（还没好）
"""
import csv
import os
import json
import shutil
from dotenv import load_dotenv

load_dotenv('D:/sp/dev/video-manager/.env')
DSN = os.environ.get('VIDEO_MANAGER_DB_DSN', '')

CSV_PATH = 'D:/sp/dev/video-manager/runtime/data/video_manager.csv'
CACHE_ROOT = 'D:/sp/dev/video-manager/runtime/hmd_cache'

# 1) 加载 CSV
with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
fieldnames = list(rows[0].keys())

# 2) 扫描所有 status.json，建立 session_name -> duration_sec 映射
#    额外检查 mp4 是否真的存在
dur_map = {}  # session_name -> duration_sec
skipped = {'processing': 0, 'no_mp4': 0, 'no_dur': 0, 'not_done': 0}
for date_dir in os.listdir(CACHE_ROOT):
    full = os.path.join(CACHE_ROOT, date_dir)
    if not os.path.isdir(full):
        continue
    for session_name in os.listdir(full):
        session_dir = os.path.join(full, session_name)
        if not os.path.isdir(session_dir):
            continue
        status_file = os.path.join(session_dir, '.hmd_fast.json')
        if not os.path.isfile(status_file):
            continue
        # 检查 mp4 是否存在
        bn = session_name
        mp4_candidates = [os.path.join(session_dir, f"{bn}.mp4"),
                          os.path.join(session_dir, "left.mp4")]
        has_mp4 = any(os.path.isfile(m) and os.path.getsize(m) > 0
                      for m in mp4_candidates)
        if not has_mp4:
            skipped['no_mp4'] += 1
            continue
        try:
            with open(status_file, 'r', encoding='utf-8') as f:
                st = json.load(f)
            if st.get('status') != 'done':
                if st.get('status') == 'processing':
                    skipped['processing'] += 1
                else:
                    skipped['not_done'] += 1
                continue
            dur = st.get('duration_sec')
            if not dur or float(dur) <= 0:
                skipped['no_dur'] += 1
                continue
            dur_map[session_name] = int(round(float(dur)))
        except Exception as e:
            print(f'  WARN: {status_file}: {e}')

print(f'=== 找到 {len(dur_map)} 个可回填的 video（mp4+done+duration>0）===')
print(f'跳过统计: {skipped}')

# 3) 更新 CSV（严格过滤：仅本机本地 + 未上传）
updated_csv = 0
skipped_csv = 0
for r in rows:
    p = (r.get('path','') or '').replace(chr(92), '/')
    bn = os.path.basename(p)

    # 严格过滤
    loc = r.get('location_status','')
    up = r.get('uploaded','')
    # 只处理本机本地
    if loc != 'thisPC_local':
        skipped_csv += 1
        continue
    # 跳过已上传的（duration 不再被需要）
    if up == 'Yes':
        skipped_csv += 1
        continue
    # 必须有可回填的 duration
    if bn not in dur_map:
        continue
    # 已经有 duration 的不覆盖
    if (r.get('duration_sec','') or '').strip():
        continue
    r['duration_sec'] = str(dur_map[bn])
    updated_csv += 1

print(f'CSV 准备更新: {updated_csv} 行（跳过 {skipped_csv} 个非本地/已上传）')

# 4) 写回
backup = CSV_PATH + '.before_durbackfill_v2.csv'
shutil.copy(CSV_PATH, backup)
with open(CSV_PATH, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
    w.writeheader()
    w.writerows(rows)
print(f'✅ CSV 已写（备份: {backup}）')

# 5) 同步 PG（也用同样过滤）
if DSN:
    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import NullPool
    eng = create_engine(DSN, poolclass=NullPool, future=True)
    pg_updated = 0
    pg_skipped = 0
    with eng.begin() as conn:
        for r in rows:
            p = (r.get('path','') or '').replace(chr(92), '/')
            bn = os.path.basename(p)
            loc = r.get('location_status','')
            up = r.get('uploaded','')
            d = (r.get('duration_sec','') or '').strip()
            # 严格过滤
            if loc != 'thisPC_local':
                pg_skipped += 1
                continue
            if up == 'Yes':
                pg_skipped += 1
                continue
            if bn not in dur_map:
                continue
            if not d:
                continue
            result = conn.execute(
                text("UPDATE videos SET duration_sec = :d WHERE path = :p OR path LIKE :p2"),
                {'d': d, 'p': p, 'p2': f'%{bn}%'}
            )
            if result.rowcount:
                pg_updated += 1
    print(f'PG 更新: {pg_updated} 行（跳过 {pg_skipped} 个非本地/已上传）')

print('\n✅ 完成！')