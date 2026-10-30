#!/usr/bin/env python
"""批量预处理符合条件的 HMD Session。

筛选规则：
  - file_type == "hmd"
  - uploaded != "Yes"（未上传）
  - extra_description != "1"（未标记为待上传）

对每个符合条件的 session 执行快速预处理：
  HMD解码 → H265 → 快速MP4封装 → 6帧预览 → 封面 → 清理H265
"""

import os
import sys
import csv
import time

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CSV_PATH = os.path.join(ROOT_DIR, "runtime", "data", "video_manager.csv")

# 把 src 加入 sys.path（脚本位于 src/scripts/，往上 2 层到项目根）
sys.path.insert(0, os.path.join(ROOT_DIR, "src"))

from tools.hmd_fast import process_fast, check_fast_done


def find_qualifying():
    """返回符合条件的 (行号, folder路径, extra_description) 列表。"""
    if not os.path.isfile(CSV_PATH):
        print(f"[错误] CSV 不存在: {CSV_PATH}")
        return []

    rows = []
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            if row.get("file_type") != "hmd":
                continue
            if row.get("uploaded", "").strip().lower() == "yes":
                continue
            extra = row.get("extra_description", "").strip()
            if extra == "1":
                continue
            folder = row.get("path", "").strip()
            if not folder or not os.path.isdir(folder):
                continue
            rows.append((idx + 1, folder, extra, row.get("duration_sec", "")))
    return rows


def main():
    print("=" * 70)
    print("  批量预处理脚本 — HMD Session 快速预处理")
    print("  筛选: HMD + 未上传 + extra_description ≠ '1'")
    print("=" * 70)

    qualifying = find_qualifying()

    if not qualifying:
        print("\n[OK] 没有符合条件的新视频需要预处理。")
        return

    # ── 统计信息 ──
    total_duration = 0
    print(f"\n发现 {len(qualifying)} 个符合条件的 HMD session:\n")
    print(f"{'#':>3}  {'路径':<65} {'时长':>8}  {'备注'}")
    print("-" * 110)
    for row_num, folder, extra, dur in qualifying:
        basename = os.path.basename(folder)
        dur_str = dur if dur else "?"
        try:
            total_duration += int(float(dur))
        except (ValueError, TypeError):
            pass
        extra_short = extra[:40] if extra else ""
        print(f"{row_num:>3}  {basename:<65} {dur_str:>8}s  {extra_short}")

    total_h = total_duration / 3600
    print("-" * 110)
    print(f"合计: {len(qualifying)} 个, 总时长 ≈ {total_h:.1f} 小时")

    # ── 确认 ──
    auto_yes = "--yes" in sys.argv or "-y" in sys.argv
    print(f"\n[!] 预处理将消耗大量磁盘空间（峰值约 2x 源文件大小）。")
    if auto_yes:
        print("    (--yes 已指定，自动确认)")
    else:
        resp = input("输入 y 继续，其他键取消: ").strip().lower()
        if resp != "y":
            print("已取消。")
            return

    # ── 逐个处理 ──
    print("\n" + "=" * 70)
    print("开始批量预处理...\n")

    success = 0
    skip = 0
    fail = 0
    started = time.time()

    for i, (_, folder, _, _) in enumerate(qualifying):
        basename = os.path.basename(folder)
        idx = i + 1
        print(f"\n[{idx}/{len(qualifying)}] {basename}")

        if check_fast_done(folder):
            print(f"  [SKIP] already done")
            skip += 1
            continue

        try:
            t0 = time.time()
            process_fast(folder, extract_frames=True, extract_cover=True)
            elapsed = time.time() - t0
            print(f"  [OK] done ({elapsed:.1f}s)")
            success += 1
        except Exception as e:
            print(f"  [FAIL] {e}")
            fail += 1

    # ── 总结 ──
    total_elapsed = time.time() - started
    print("\n" + "=" * 70)
    print(f"batch preprocess done!")
    print(f"  success: {success}")
    print(f"  skip: {skip}")
    print(f"  fail: {fail}")
    print(f"  elapsed: {total_elapsed:.0f}s ({total_elapsed/60:.1f}min)")
    print("=" * 70)


if __name__ == "__main__":
    main()
