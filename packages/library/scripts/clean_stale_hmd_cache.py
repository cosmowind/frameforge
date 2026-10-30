"""清理 0701-0705 旧 h265 文件（之前 remux 失败留下的）
新 run 会重新 decode + remux + mp4

只删除 h265（没 mp4 配对的），不动其他文件
"""
import os
import sys
import glob

hmd_cache_root = 'D:/sp/dev/video-manager/runtime/hmd_cache'

deleted = []
for date in ['2026-07-01', '2026-07-02', '2026-07-04']:
    date_dir = os.path.join(hmd_cache_root, date)
    if not os.path.isdir(date_dir):
        continue
    for session_name in os.listdir(date_dir):
        session_dir = os.path.join(date_dir, session_name)
        if not os.path.isdir(session_dir):
            continue
        # 检查是否只有 h265 没有 mp4
        h265_files = glob.glob(os.path.join(session_dir, '*.h265'))
        mp4_files = glob.glob(os.path.join(session_dir, '*.mp4'))
        if h265_files and not mp4_files:
            for h in h265_files:
                if '--confirm' in sys.argv:
                    try:
                        os.remove(h)
                        deleted.append(h)
                    except Exception as e:
                        print(f'  ✗ 删除失败: {h}: {e}')
                else:
                    deleted.append(h)  # dry-run 记录

print(f'=== 找到 {len(deleted)} 个孤立 h265 文件 ===')
for f in deleted[:10]:
    print(f'  {f}')
if '--confirm' not in sys.argv:
    print('\n（DRY-RUN 模式，加 --confirm 才真正删除）')
else:
    print(f'\n✅ 已删除 {len(deleted)} 个 h265 文件')