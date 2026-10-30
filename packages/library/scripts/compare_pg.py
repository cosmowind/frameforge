"""对比 PG vs CSV 找出数据差异"""
import os
import csv
from dotenv import load_dotenv
load_dotenv('D:/sp/dev/video-manager/.env')
DSN = os.environ.get('VIDEO_MANAGER_DB_DSN', '')

current_path = 'D:/sp/dev/video-manager/runtime/data/video_manager.csv'
with open(current_path, 'r', encoding='utf-8-sig') as f:
    csv_rows = list(csv.DictReader(f))

# 取前 5 个 0625-0629 视频
sample_paths = []
for r in csv_rows:
    p = r.get('path','')
    if any(p.find(m) >= 0 for m in ['0625','0626','0627','0628','0629']):
        sample_paths.append(p)
    if len(sample_paths) >= 10:
        break

print(f'抽样 {len(sample_paths)} 个 0625-0629 路径:')
for p in sample_paths:
    print(f'  {p}')

if DSN:
    from sqlalchemy import create_engine, text
    eng = create_engine(DSN, future=True)
    with eng.begin() as conn:
        for p in sample_paths:
            # 用 path 匹配
            rs = conn.execute(text("SELECT path, uploaded, location_status, duration_sec, recorder_id, task_id, env_id FROM videos WHERE path = :p OR path LIKE :p2"),
                              {'p': p, 'p2': '%' + os.path.basename(p) + '%'})
            for row in rs:
                print(f'  PG: {row}')
            else:
                pass
        print('\n=== PG 0625-0629 总数 ===')
        rs = conn.execute(text("SELECT count(*) FROM videos WHERE path LIKE '%0625%' OR path LIKE '%0626%' OR path LIKE '%0627%' OR path LIKE '%0628%' OR path LIKE '%0629%'"))
        for row in rs:
            print(f'  PG 总数: {row[0]}')

        print('\n=== CSV 0625-0629 总数 ===')
        count = sum(1 for r in csv_rows if any(r.get('path','').find(m) >= 0 for m in ['0625','0626','0627','0628','0629']))
        print(f'  CSV 总数: {count}')