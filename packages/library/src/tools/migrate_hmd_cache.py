#!/usr/bin/env python
"""迁移 hmd_cache 到日期分级目录结构。

旧结构: hmd_cache/<session_basename>/
新结构: hmd_cache/<YYYY-MM-DD>/<session_basename>/

不同日期可能存在同名 session（如 0619/4aa45c_session_00000 与 0621/4aa45c_session_00000），
旧扁平结构会导致后处理的覆盖先处理的。新结构用日期目录隔开。
"""
import os
import sys
import csv
import json
import shutil
import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CSV_PATH = os.path.join(BASE_DIR, "runtime", "data", "video_manager.csv")
CACHE_ROOT = os.path.join(BASE_DIR, "runtime", "hmd_cache")


def _extract_date_from_path(path):
    """从源路径中提取日期目录名 (MMDD 格式)，返回 'YYYY-MM-DD' 或 None。"""
    parts = os.path.normpath(path).split(os.sep)
    for part in reversed(parts):
        if len(part) == 4 and part.isdigit():
            month = part[:2]
            day = part[2:]
            year = datetime.datetime.now().year
            return f"{year}-{month}-{day}"
    return None


def load_csv():
    if not os.path.exists(CSV_PATH):
        return []
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main():
    rows = load_csv()
    
    # 构建 basename → 所有日期 的映射
    # 因为一个 basename 可能对应多个日期，我们需要克隆目录
    basename_dates = {}  # basename → set of date_keys
    hmd_rows = []
    
    for r in rows:
        if r.get("file_type", "") != "hmd":
            continue
        path = r.get("path", "")
        if not path:
            continue
        base = os.path.basename(os.path.normpath(path))
        date_key = _extract_date_from_path(path)
        if not date_key:
            print(f"[skip] 无法提取日期: {path}")
            continue
        if base not in basename_dates:
            basename_dates[base] = set()
        basename_dates[base].add(date_key)
        hmd_rows.append((base, date_key, path))
    
    if not os.path.isdir(CACHE_ROOT):
        print(f"hmd_cache 目录不存在: {CACHE_ROOT}")
        return
    
    migrated = 0
    skipped = 0
    
    for entry in os.listdir(CACHE_ROOT):
        src_path = os.path.join(CACHE_ROOT, entry)
        if not os.path.isdir(src_path):
            continue
        
        # 跳过已经是日期格式的目录（如 "2026-06-19"）
        if len(entry) == 10 and entry[4] == '-' and entry[7] == '-':
            print(f"[skip] 已是日期目录: {entry}")
            skipped += 1
            continue
        
        # 查找这个 basename 在 CSV 中有哪些日期
        dates = basename_dates.get(entry, set())
        
        if not dates:
            print(f"[warn] 缓存目录无 CSV 记录: {entry} (将移动到 unknown/)")
            dates = {"unknown"}
        
        for date_key in dates:
            dst_dir = os.path.join(CACHE_ROOT, date_key, entry)
            if os.path.exists(dst_dir):
                print(f"[skip] 目标已存在: {date_key}/{entry}")
                continue
            
            os.makedirs(os.path.dirname(dst_dir), exist_ok=True)
            try:
                shutil.move(src_path, dst_dir)
                print(f"[moved] {entry} → {date_key}/{entry}")
                migrated += 1
                break  # 只移动一次（如果多个日期共享同一源目录）
            except Exception as e:
                print(f"[error] 移动失败 {entry} → {date_key}/{entry}: {e}")
    
    # 清理空的旧目录（可能在移动后变成空）
    for entry in os.listdir(CACHE_ROOT):
        src_path = os.path.join(CACHE_ROOT, entry)
        if os.path.isdir(src_path) and len(entry) != 10:  # 不是日期格式
            try:
                remaining = os.listdir(src_path)
                if not remaining:
                    os.rmdir(src_path)
                    print(f"[clean] 移除空目录: {entry}")
            except Exception:
                pass
    
    print(f"\n迁移完成: {migrated} 个目录已迁移, {skipped} 个已跳过")


if __name__ == "__main__":
    main()
