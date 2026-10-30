"""清理 0701-0705 的陈旧 preprocess 错误状态文件

根因：
- 早期 scan 时 source path 是 /media/videos/0701/0701_4aa45c_session_00000/
- 现在 CSV 已修正为 /media/videos/0701/hmd/0701_4aa45c_session_00000/
- 但旧的 .hmd_process.json "error" 状态文件残留在 cache 目录
- 导致前端显示"失败"

操作：
- 列出所有 status="error" 的 .hmd_process.json（0701-0705）
- 删除这些 stale 状态文件
- 重新触发 preprocessing 时会自动重建状态
"""
import os
import json

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
        # 检查两种 status 文件
        for status_file in ['.hmd_process.json', '.hmd_fast.json']:
            fp = os.path.join(session_dir, status_file)
            if not os.path.isfile(fp):
                continue
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if data.get('status') == 'error':
                    deleted.append({
                        'date': date,
                        'session': session_name,
                        'file': status_file,
                        'error': data.get('error', '')[:60],
                    })
            except Exception:
                pass

print(f'=== 找到 {len(deleted)} 个陈旧 error 状态文件 ===')
for d in deleted[:10]:
    print(f'  {d["date"]}/{d["session"]}/{d["file"]}  error: {d["error"]!r}')

# 执行删除
import sys
if '--confirm' not in sys.argv:
    print('\n（DRY-RUN 模式，加 --confirm 才真正删除）')
    sys.exit(0)

print('\n删除中...')
for d in deleted:
    fp = os.path.join(hmd_cache_root, d['date'], d['session'], d['file'])
    try:
        os.remove(fp)
    except Exception as e:
        print(f'  ✗ 删除失败: {fp}: {e}')
print(f'✅ 已删除 {len(deleted)} 个 stale error 状态文件')
print('\n下一步：')
print('  1. 硬刷新浏览器（Ctrl+Shift+R）')
print('  2. 视频管理页 → 点 ⏳ 预处理 → 全部预热')
print('  3. 重新跑预处理会用正确路径生成 status')