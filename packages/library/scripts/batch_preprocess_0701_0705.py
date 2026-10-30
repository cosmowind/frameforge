"""后端直接批量预处理 0701-0705 的所有本地 HMD 视频

绕过前端不可靠的 click → fetch 链路，直接在 Python 里调用：
- hmd_pre.start_async(folder)  # 异步启动
- 等待状态变 done 或 error
- 失败时打印错误信息
- 完成后输出 MP4 路径

用法：python batch_preprocess_0701_0705.py [--dry-run]
"""
import csv
import os
import sys
import time
import glob
import json
import argparse
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

# 加载 Flask app 上下文（需要 DB / config / services）
sys.path.insert(0, 'D:/sp/dev/video-manager/src')
os.chdir('D:/sp/dev/video-manager/src')

CSV_PATH = 'D:/sp/dev/video-manager/runtime/data/video_manager.csv'
CACHE_ROOT = 'D:/sp/dev/video-manager/runtime/hmd_cache'


def _extract_date_from_path(path):
    """DEPRECATED: 用 hmd_fast 的版本（返回 YYYY-MM-DD）"""
    from tools.hmd_fast.path_utils import _extract_date_from_path as _hmd_extract
    return _hmd_extract(path)


def get_cache_dir(folder):
    """计算 hmd_cache 中的缓存目录（与 hmd_fast 内部一致）"""
    # 关键：必须用 hmd_fast 的 _extract_date_from_path（返回 YYYY-MM-DD）
    # 不要自己提取 MMDD，否则路径对不上
    from tools.hmd_fast.path_utils import _extract_date_from_path as _hmd_extract
    date_key = _hmd_extract(folder)
    bn = os.path.basename(os.path.normpath(folder))
    return os.path.join(CACHE_ROOT, date_key, bn)


def load_local_videos():
    """从 CSV 读 0701-0705 + thisPC_local + uploaded=No + HMD + 未预处理 的视频"""
    with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    candidates = []
    for r in rows:
        p = (r.get('path','') or '').replace(chr(92), '/')
        loc = r.get('location_status','')
        up = r.get('uploaded','')
        ftype = r.get('file_type','')
        # 过滤条件
        if not any('/'+d+'/' in p for d in ['0701','0702','0704']):
            continue
        if loc != 'thisPC_local':
            continue
        if up == 'Yes':
            continue
        if ftype != 'hmd':
            continue
        # 路径必须在 thisPC 挂载点下
        if not p.startswith('/media/videos/'):
            continue
        # 源文件存在
        if not os.path.isdir(p):
            continue
        # 有 part_*.hmd
        if not glob.glob(os.path.join(p, 'part_*.hmd')):
            continue
        # 已预处理成功（mp4 存在）→ 跳过
        cache_dir = get_cache_dir(p)
        bn = os.path.basename(p)
        mp4_paths = [os.path.join(cache_dir, f"{bn}.mp4"), os.path.join(cache_dir, "left.mp4")]
        if any(os.path.isfile(mp) for mp in mp4_paths):
            continue
        # 状态文件正在 processing → 跳过（避免重复入队）
        for sf in [os.path.join(cache_dir, ".hmd_process.json"),
                   os.path.join(cache_dir, ".hmd_fast.json")]:
            if os.path.isfile(sf):
                try:
                    with open(sf, 'r', encoding='utf-8') as f:
                        st = json.load(f)
                    if st.get('status') == 'processing':
                        print(f'  跳过 {bn} (正在 processing)')
                        # 视为需要等待而非跳过
                        candidates.append(('WAIT', p))
                        break
                except Exception:
                    pass
        else:
            # 没有 processing 状态文件 → 加入待处理
            candidates.append(('PROCESS', p))
    return candidates


def wait_for_done(folder, timeout=600, poll=3):
    """等待 folder 预处理完成（done/error/timeout）"""
    cache_dir = get_cache_dir(folder)
    deadline = time.time() + timeout
    last_pct = -1
    while time.time() < deadline:
        # 优先检查 mp4 存在（最强的 done 信号）
        bn = os.path.basename(folder)
        if os.path.isfile(os.path.join(cache_dir, f"{bn}.mp4")) or \
           os.path.isfile(os.path.join(cache_dir, "left.mp4")):
            return 'done', {'mp4_found': True}
        # 检查状态文件
        for sf in [os.path.join(cache_dir, ".hmd_process.json"),
                   os.path.join(cache_dir, ".hmd_fast.json")]:
            if os.path.isfile(sf):
                try:
                    with open(sf, 'r', encoding='utf-8') as f:
                        st = json.load(f)
                    s = st.get('status','')
                    if s == 'error':
                        return 'error', st
                    if s == 'processing':
                        pct = st.get('progress', 0)
                        if pct != last_pct:
                            stage = st.get('stage','')
                            print(f'  [{bn}] processing {pct}% stage={stage}', flush=True)
                            last_pct = pct
                except Exception:
                    pass
        time.sleep(poll)
    return 'timeout', {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--confirm', action='store_true', help='真正启动（否则 dry-run）')
    parser.add_argument('--max-workers', type=int, default=1,
                        help='并发数（HMD 处理是 CPU+IO 密集，建议 1）')
    parser.add_argument('--limit', type=int, default=0, help='最多处理几个（测试用）')
    parser.add_argument('--timeout', type=int, default=600, help='单个超时（秒）')
    args = parser.parse_args()
    args.dry_run = args.dry_run and not args.confirm  # --confirm 隐含执行

    # 加载 Flask app context（让 lazy_loader 拿到模块）
    print('=== 加载预处理模块 ===')
    from services.lazy_loader import _get_hmd_preprocess, _get_hmd_fast_preprocess
    hmd_pre = _get_hmd_preprocess()
    hmd_fast = _get_hmd_fast_preprocess()
    if not hmd_pre and not hmd_fast:
        print('ERROR: 没有任何预处理模块加载')
        sys.exit(1)
    print(f'  hmd_pre (full MP4): {"✓" if hmd_pre else "✗"}')
    print(f'  hmd_fast (fast): {"✓" if hmd_fast else "✗"}')

    candidates = load_local_videos()
    if args.limit:
        candidates = candidates[:args.limit]
    print(f'\n=== 找到 {len(candidates)} 个待预处理视频 ===')
    for action, c in candidates:
        print(f'  [{action}] {c}')

    if args.dry_run:
        print('\n（DRY-RUN 模式，加 --confirm 才真正启动）')
        return

    # 启动
    success = 0
    failed = []
    for i, (action, folder) in enumerate(candidates, 1):
        bn = os.path.basename(folder)
        print(f'\n[{i}/{len(candidates)}] {bn} ({action})')
        if action == 'WAIT':
            # 已经有 processing 在跑，直接等待
            pass
        else:
            try:
                if hmd_fast:
                    hmd_fast.start_async(folder)
                elif hmd_pre:
                    hmd_pre.start_async(folder)
                print(f'  ✓ 已启动预处理')
            except Exception as e:
                print(f'  ✗ 启动失败: {e}')
                failed.append((bn, str(e)))
                continue

        # 等待完成
        status, st = wait_for_done(folder, timeout=args.timeout)
        if status == 'done':
            success += 1
            mp4 = st.get('mp4_path', '') or st.get('path', '') or 'mp4 found'
            print(f'  ✓ done')
        elif status == 'error':
            err = st.get('error', '未知错误')
            print(f'  ✗ error: {err[:120]}')
            failed.append((bn, err))
        else:
            print(f'  ⏱ timeout ({args.timeout}s)')
            failed.append((bn, 'timeout'))

    print(f'\n=== 汇总 ===')
    print(f'  成功: {success}/{len(candidates)}')
    if failed:
        print(f'  失败: {len(failed)}')
        for bn, err in failed:
            print(f'    {bn}: {err[:80]}')


if __name__ == '__main__':
    main()