#!/usr/bin/env python
"""重新预处理所有"未提交 + 本地有源文件 + 缓存不完整"的 HMD session。

跳过条件：
  - uploaded = 'Yes'       → 已提交，不处理
  - 本地 part_*.hmd 不存在  → 无源文件，不处理
  - 缓存已有可用媒体源       → cover.jpg / mp4 / h265 任一存在即可出缩略图

只处理真正需要预处理（没有任何可用媒体源）的 session。
"""

import os
import sys
import csv
import json
import glob
import time
import threading

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE_DIR, "src"))

from tools import hmd_fast as hmd_fast_preprocess

CSV_PATH = os.path.join(BASE_DIR, "runtime", "data", "video_manager.csv")
CACHE_ROOT = hmd_fast_preprocess.get_cache_root()


def main():
    if not os.path.exists(CSV_PATH):
        print("CSV 文件不存在:", CSV_PATH)
        return

    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    # ---------- 筛选需要处理的 session ----------
    to_process = []

    for r in rows:
        path = r.get("path", "").strip()
        ftype = r.get("file_type", "").strip()
        uploaded = r.get("uploaded", "").strip()

        if ftype != "hmd" or not path:
            continue

        # 1) 已提交 → 跳过
        if uploaded.lower() == "yes":
            continue

        # 2) 本地无源文件 → 跳过
        if not os.path.isdir(path):
            continue
        parts = glob.glob(os.path.join(path, "part_*.hmd"))
        if not parts:
            continue

        # 3) 检查缓存是否已有可用媒体（新旧命名兼容）
        cache = hmd_fast_preprocess.get_output_dir(path)
        base = os.path.basename(os.path.normpath(path))
        cover_ok = os.path.isfile(os.path.join(cache, "cover.jpg")) and os.path.getsize(os.path.join(cache, "cover.jpg")) > 0
        mp4_ok = (
            (os.path.isfile(os.path.join(cache, f"{base}.mp4")) and os.path.getsize(os.path.join(cache, f"{base}.mp4")) > 0)
            or (os.path.isfile(os.path.join(cache, "left.mp4")) and os.path.getsize(os.path.join(cache, "left.mp4")) > 0)
        )
        h265_ok = (
            (os.path.isfile(os.path.join(cache, f"{base}.h265")) and os.path.getsize(os.path.join(cache, f"{base}.h265")) > 0)
            or (os.path.isfile(os.path.join(cache, "left.h265")) and os.path.getsize(os.path.join(cache, "left.h265")) > 0)
        )

        if cover_ok or mp4_ok or h265_ok:
            # 至少有一个可出缩略图的源 → 跳过
            continue

        # 还需要处理
        stat = _read_status(cache)
        to_process.append({
            "path": path,
            "base": os.path.basename(os.path.normpath(path)),
            "cache": cache,
            "status": stat,
        })

    if not to_process:
        print("[OK] 所有本地未提交的 HMD session 缓存都已就绪！")
        return

    print(f"[INFO] 共找到 {len(to_process)} 个需要预处理的 session：")
    for s in to_process:
        print(f"   [{s['status']}] {s['base']}  ({len(glob.glob(os.path.join(s['path'], 'part_*.hmd')))} parts)")
    print()

    # ---------- 顺序启动预处理 ----------
    print("[START] 开始预处理（单线程串行，避免 I/O 竞争）...")
    started = 0
    for s in to_process:
        # 清除可能残留的半成品
        _clear_cache_safely(s["cache"])

        hmd_fast_preprocess.start_async(s["path"])
        started += 1
        print(f"  [{started}/{len(to_process)}] STARTED {s['base']}")
        time.sleep(0.3)

    print(f"\n[DONE] 已启动 {started} 个预处理任务，后台运行中...")
    print("可在浏览器主界面 -> 预处理面板查看进度")


def _read_status(cache_dir):
    """读取预处理状态（若有），返回简短描述"""
    fast_status = os.path.join(cache_dir, ".hmd_fast.json")
    proc_status = os.path.join(cache_dir, ".hmd_process.json")
    statuses = []
    for sp in (fast_status, proc_status):
        if os.path.isfile(sp):
            try:
                with open(sp, "r", encoding="utf-8") as f:
                    d = json.load(f)
                statuses.append(f"{os.path.basename(sp)}={d.get('status','?')}")
            except Exception:
                pass
    return " | ".join(statuses) if statuses else "no status"


def _clear_cache_safely(cache_dir):
    """清除可能残留的半成品（不删 frames 目录）。"""
    base = os.path.basename(os.path.normpath(cache_dir))
    for fn in ("left.h265", "right.h265", "left.mp4", "right.mp4",
               f"{base}.h265", f"{base}_right.h265",
               f"{base}.mp4", f"{base}_right.mp4",
               ".hmd_fast.json", ".hmd_process.json"):
        fp = os.path.join(cache_dir, fn)
        if os.path.isfile(fp):
            try:
                os.remove(fp)
            except OSError:
                pass


if __name__ == "__main__":
    main()
