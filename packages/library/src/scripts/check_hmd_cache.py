#!/usr/bin/env python
"""检查 hmd_cache 预处理状态并输出待处理列表。

新结构: hmd_cache/<date>/<session>/

按优先级排序：
  1. 需要抽预览帧的（h265 已有但 frames 不全或 cover 缺失）
  2. 需要完整预处理的（h265 也不存在）
  3. 需要 mp4 编码的（h265 已有但 mp4 缺失）
"""
import os
import sys
import csv
import json
import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CSV_PATH = os.path.join(BASE_DIR, "runtime", "data", "video_manager.csv")
CACHE_ROOT = os.path.join(BASE_DIR, "runtime", "hmd_cache")


def _extract_date_from_path(path):
    parts = os.path.normpath(path).split(os.sep)
    for part in reversed(parts):
        if len(part) == 4 and part.isdigit():
            month = part[:2]
            day = part[2:]
            year = datetime.datetime.now().year
            return f"{year}-{month}-{day}"
    return "unknown"


def get_cache_dir(path):
    date_key = _extract_date_from_path(path)
    base = os.path.basename(os.path.normpath(path))
    return os.path.join(CACHE_ROOT, date_key, base)


def check_session(path, ftype):
    """检查一个 session 的预处理状态。
    Returns: dict with status info or None if everything is done.
    """
    if ftype != "hmd":
        return None
    
    cache = get_cache_dir(path)
    base = os.path.basename(os.path.normpath(path))
    
    # 检查各类文件的完整性（新旧命名兼容）
    # 优先新命名，回退旧命名
    _h265_new = os.path.join(cache, f"{base}.h265")
    _h265_old = os.path.join(cache, "left.h265")
    h265_path = _h265_new if os.path.isfile(_h265_new) else _h265_old
    _mp4_new = os.path.join(cache, f"{base}.mp4")
    _mp4_old = os.path.join(cache, "left.mp4")
    mp4_path = _mp4_new if os.path.isfile(_mp4_new) else _mp4_old
    cover_path = os.path.join(cache, "cover.jpg")
    frames_dir = os.path.join(cache, "frames")
    fast_status_path = os.path.join(cache, ".hmd_fast.json")
    proc_status_path = os.path.join(cache, ".hmd_process.json")
    
    has_h265 = os.path.isfile(h265_path) and os.path.getsize(h265_path) > 0
    has_mp4 = os.path.isfile(mp4_path) and os.path.getsize(mp4_path) > 0
    has_cover = os.path.isfile(cover_path) and os.path.getsize(cover_path) > 0
    
    # 检查 6 帧预览
    frames_count = 0
    if os.path.isdir(frames_dir):
        frames_count = len([f for f in os.listdir(frames_dir) if f.endswith('.jpg')])
    has_frames = frames_count >= 6
    
    # 读取状态文件
    fast_status = None
    proc_status = None
    if os.path.isfile(fast_status_path):
        try:
            with open(fast_status_path, "r", encoding="utf-8") as f:
                fast_status = json.load(f)
        except Exception:
            pass
    if os.path.isfile(proc_status_path):
        try:
            with open(proc_status_path, "r", encoding="utf-8") as f:
                proc_status = json.load(f)
        except Exception:
            pass
    
    fast_done = (fast_status and fast_status.get("status") == "done" and
                 has_h265 and has_cover and has_frames)
    proc_done = (proc_status and proc_status.get("status") == "done" and has_mp4)
    
    # 如果全部完成，返回 None
    if fast_done and proc_done:
        return None
    
    # 确定需要什么操作
    needs = []
    
    if not has_h265:
        needs.append("decode")  # 最基础：解码
    else:
        if not has_frames:
            needs.append("extract-frames")
        if not has_cover:
            needs.append("generate-cover")
        if not has_mp4:
            needs.append("encode-mp4")
    
    if not needs:
        # 文件都在但状态不对，标记为状态修复
        needs.append("fix-status")
    
    # 优先级：帧/封面优先（快速可见），再是 mp4 编码
    priority = 0
    if "extract-frames" in needs or "generate-cover" in needs:
        priority = 1  # 高优先级：快速出预览
    elif "decode" in needs:
        priority = 2  # 需要解码（耗时）
    elif "encode-mp4" in needs:
        priority = 3  # 需要编码 mp4（耗时但 h265 已有）
    else:
        priority = 9
    
    fast_stage = fast_status.get("stage", "none") if fast_status else "none"
    proc_stage = proc_status.get("stage", "none") if proc_status else "none"
    
    return {
        "path": path,
        "base": base,
        "cache": cache,
        "has_h265": has_h265,
        "has_frames": has_frames,
        "frames_count": frames_count,
        "has_cover": has_cover,
        "has_mp4": has_mp4,
        "needs": needs,
        "priority": priority,
        "fast_stage": fast_stage,
        "proc_stage": proc_stage,
        "fast_status": fast_status.get("status", "none") if fast_status else "none",
        "proc_status": proc_status.get("status", "none") if proc_status else "none",
    }


def main():
    rows = []
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
    
    # 收集所有 HMD sessions
    results = []
    for r in rows:
        path = r.get("path", "")
        ftype = r.get("file_type", "")
        if not path:
            continue
        status = check_session(path, ftype)
        if status:
            results.append(status)
    
    # 按优先级排序
    results.sort(key=lambda x: (x["priority"], x["base"]))
    
    # 统计
    total = len(results)
    completed = sum(1 for r in rows if r.get("file_type") == "hmd") - total
    need_frames = sum(1 for r in results if not r["has_frames"])
    need_cover = sum(1 for r in results if not r["has_cover"])
    need_decode = sum(1 for r in results if not r["has_h265"])
    need_mp4 = sum(1 for r in results if r["has_h265"] and not r["has_mp4"])
    
    print(f"{'='*60}")
    print(f"HMD 缓存预处理状态检查")
    print(f"{'='*60}")
    print(f"总计 HMD sessions: {completed + total}")
    print(f"  [OK] 已完成:      {completed}")
    print(f"  [!!] 待处理:      {total}")
    print(f"     - 需要解码:    {need_decode}")
    print(f"     - 需要抽帧:    {need_frames}")
    print(f"     - 需要封面:    {need_cover}")
    print(f"     - 需要 MP4:    {need_mp4}")
    print()
    
    if not results:
        print("所有 HMD sessions 已完成预处理。")
        return
    
    # 输出待处理列表
    print(f"{'─'*60}")
    print(f"待处理列表（按优先级排序）：")
    print(f"{'─'*60}")
    
    for r in results:
        prio_label = {1: "[FRAMES]", 2: "[DECODE]", 3: "[MP4]", 9: "[FIX]"}.get(r["priority"], "?")
        needs_str = "+".join(r["needs"])
        status_line = f"h265={'Y' if r['has_h265'] else 'N'} frames={r['frames_count']}/6 cover={'Y' if r['has_cover'] else 'N'} mp4={'Y' if r['has_mp4'] else 'N'}"
        print(f"  {prio_label} [{needs_str}] {r['base']}")
        print(f"        {status_line}  fast={r['fast_status']} proc={r['proc_status']}")
        print(f"        cache: {r['cache']}")
    
    # 输出可执行的命令建议
    print()
    print(f"{'─'*60}")
    print("建议操作：")
    print(f"{'─'*60}")
    print()
    
    # 第一步：优先处理需要抽帧/封面的（h265 已存在）
    frame_first = [r for r in results if r["priority"] == 1]
    if frame_first:
        print(f"# 第一步：抽取预览帧 + 生成封面（{len(frame_first)} 个，h265 已有）")
        for r in frame_first:
            if not r["has_frames"] and not r["has_cover"]:
                print(f'python -m tools.hmd_fast "{r["path"]}"')
            elif not r["has_frames"]:
                print(f'python -m tools.hmd_fast "{r["path"]}" --extract-frames')
            elif not r["has_cover"]:
                print(f'python -m tools.hmd_fast "{r["path"]}" --cover-only')
        print()
    
    # 第二步：需要解码的
    need_decode_list = [r for r in results if r["priority"] == 2]
    if need_decode_list:
        print(f"# 第二步：完整解码（{len(need_decode_list)} 个）")
        for r in need_decode_list:
            print(f'python -m tools.hmd_fast "{r["path"]}"')
        print()
    
    # 第三步：需要 MP4 编码的
    need_mp4_list = [r for r in results if r["priority"] == 3]
    if need_mp4_list:
        print(f"# 第三步：MP4 编码（{len(need_mp4_list)} 个，h265 已有）")
        for r in need_mp4_list:
            print(f'python tools/hmd_preprocess.py "{r["path"]}"')


if __name__ == "__main__":
    main()
