"""
历史合并与清理操作。
处理历史 CSV 合并、记录删除、孤立缓存清理等维护逻辑。
"""

import csv
import os
import re
import shutil
from datetime import datetime

from config import (
    BASE_DIR, CSV_PATH, DEFAULT_FIELDNAMES,
    ARCHIVE_DIR, RUNTIME_DIR,
)
if __import__('config').USE_PG:
    from models.pg_store import read_csv, write_csv
else:
    from models.csv_store import read_csv, write_csv

from .video import _thumb_cache_key
from utils.path_utils import get_location_status, is_local_status


# ----------------------------------------------------------------
# 历史合并
# ----------------------------------------------------------------

def parse_history_date_from_filename(filename):
    """从历史 CSV 文件名解析日期，如 video_manager0517-1.csv -> 2026-05-17。"""
    match = re.search(r'(\d{2})(\d{2})', filename)
    if match:
        month, day = match.groups()
        year = datetime.now().year
        try:
            return datetime(year, int(month), int(day)).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return datetime.now().strftime("%Y-%m-%d")


def merge_history():
    """合并所有历史 CSV 文件到 archive/video_manager_history.csv。"""
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    all_history_files = [
        "video_manager0517-1.csv", "video_manager0517-2.csv", "video_manager0517-3.csv",
        "video_manager0518-1.csv", "video_manager0519-1.csv", "video_manager0520.csv",
        "video_manager-bak.csv", "video_manager - 副本.csv"
    ]
    merged = {}
    for hist_file in all_history_files:
        hist_path = os.path.join(BASE_DIR, hist_file)
        if not os.path.exists(hist_path):
            continue
        hist_date = parse_history_date_from_filename(hist_file)
        try:
            with open(hist_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    path = row.get("path", "").strip()
                    if not path:
                        continue
                    full_row = {fn: "" for fn in DEFAULT_FIELDNAMES}
                    for key, val in row.items():
                        if key in DEFAULT_FIELDNAMES:
                            full_row[key] = val
                    full_row["location_status"] = get_location_status(path, os.path.isfile(path))
                    full_row["scan_date"] = hist_date
                    if not is_local_status(full_row["location_status"]):
                        full_row["original_history_date"] = hist_date
                    if path in merged:
                        existing_date = merged[path].get("scan_date", "")
                        if hist_date > existing_date:
                            merged[path] = full_row
                    else:
                        merged[path] = full_row
        except Exception as e:
            print(f"Error reading {hist_file}: {e}")
            continue

    history_path = os.path.join(ARCHIVE_DIR, "video_manager_history.csv")
    with open(history_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=DEFAULT_FIELDNAMES)
        writer.writeheader()
        for row in sorted(merged.values(), key=lambda r: (r.get("scan_date", ""), r.get("path", ""))):
            writer.writerow(row)

    for hist_file in all_history_files:
        src = os.path.join(BASE_DIR, hist_file)
        dst = os.path.join(ARCHIVE_DIR, hist_file)
        if os.path.exists(src) and not os.path.exists(dst):
            os.rename(src, dst)

    return len(merged), history_path


# ----------------------------------------------------------------
# 删除记录（含本地文件删除 + 缓存清理）
# ----------------------------------------------------------------

def delete_records_data(indices, delete_files=False):
    """删除 CSV 中指定索引的记录，仅允许删除已上传（uploaded=Yes）的记录。
    可选删除本地文件释放磁盘空间。
    Returns: (kept, removed_info, blocked_info, deleted_files_count, deleted_size_mb, monitor_resumed)
    """
    rows = read_csv()
    blocked = []
    removed = []
    kept = []

    for i, row in enumerate(rows):
        if i in indices:
            vpath = row.get("path", "").strip()
            uploaded = row.get("uploaded", "").strip()
            if uploaded != "Yes":
                fname = os.path.basename(vpath) if vpath else f"行 {i}"
                blocked.append({"index": i, "path": vpath, "name": fname, "uploaded": uploaded})
                kept.append(row)
                continue
            removed.append({
                "index": i, "path": vpath,
                "file_type": row.get("file_type", ""), "uploaded": uploaded,
            })
        else:
            kept.append(row)

    if not removed:
        return None, removed, blocked, 0, 0.0, False

    write_csv(kept)

    # 删除本地文件
    deleted_files = 0
    deleted_size_mb = 0.0
    if delete_files:
        for r in removed:
            vpath = r.get("path", "")
            ftype = r.get("file_type", "")
            if not vpath:
                continue
            try:
                if ftype in ("hmd", "data"):
                    if os.path.isdir(vpath):
                        dir_size = 0
                        for dirpath, dirnames, filenames in os.walk(vpath):
                            for fn in filenames:
                                fp = os.path.join(dirpath, fn)
                                try:
                                    dir_size += os.path.getsize(fp)
                                except OSError:
                                    pass
                        shutil.rmtree(vpath)
                        deleted_files += 1
                        deleted_size_mb += dir_size / (1024 * 1024)
                else:
                    if os.path.isfile(vpath):
                        fsize = os.path.getsize(vpath)
                        os.unlink(vpath)
                        deleted_files += 1
                        deleted_size_mb += fsize / (1024 * 1024)
            except Exception:
                pass

    # 清理关联缓存
    cleaned_caches = 0
    cleaned_thumbs = 0
    for r in removed:
        vpath = r.get("path", "")
        ftype = r.get("file_type", "")
        if not vpath:
            continue
        if ftype == "hmd":
            try:
                from .lazy_loader import _get_hmd_preprocess
                hmd_pre = _get_hmd_preprocess()
                if hmd_pre:
                    cache_dir = hmd_pre.get_output_dir(vpath)
                    if os.path.isdir(cache_dir):
                        shutil.rmtree(cache_dir)
                        cleaned_caches += 1
            except Exception:
                pass
        try:
            key = _thumb_cache_key(vpath)
            from config import THUMBNAILS_DIR
            thumb_path = os.path.join(THUMBNAILS_DIR, f"{key}.jpg")
            if os.path.isfile(thumb_path):
                os.unlink(thumb_path)
                cleaned_thumbs += 1
        except Exception:
            pass

    # 恢复设备监控
    monitor_resumed = False
    if delete_files and deleted_files > 0:
        from .lazy_loader import _get_device_monitor
        dm = _get_device_monitor()
        if dm:
            monitor_resumed = dm.resume_monitor()

    return kept, removed, blocked, deleted_files, round(deleted_size_mb, 2), monitor_resumed


# ----------------------------------------------------------------
# 孤立缓存清理
# ----------------------------------------------------------------

def clean_orphan_cache():
    """清理无对应 CSV 记录的 hmd_cache 目录和缩略图文件。"""
    from utils.path_utils import extract_date_from_path as _extract_date_from_path
    from config import THUMBNAILS_DIR

    rows = read_csv()
    registered_paths = set()
    registered_hmd_keys = set()
    registered_hmd_basenames = set()
    for r in rows:
        vp = os.path.normpath(r.get("path", "")).lower()
        if vp:
            registered_paths.add(vp)
        if r.get("file_type", "") == "hmd":
            rpath = r.get("path", "")
            base = os.path.basename(os.path.normpath(rpath)).lower()
            registered_hmd_basenames.add(base)
            date_key = _extract_date_from_path(rpath)
            registered_hmd_keys.add((date_key, base))

    # Clean hmd_cache
    hmd_cache_root = os.path.join(RUNTIME_DIR, "hmd_cache")
    cleaned_caches = 0
    if os.path.isdir(hmd_cache_root):
        for date_dir in os.listdir(hmd_cache_root):
            date_path = os.path.join(hmd_cache_root, date_dir)
            if not os.path.isdir(date_path):
                continue
            for session_dir in os.listdir(date_path):
                session_path = os.path.join(date_path, session_dir)
                if not os.path.isdir(session_path):
                    continue
                key = (date_dir, session_dir.lower())
                if key not in registered_hmd_keys and session_dir.lower() not in registered_hmd_basenames:
                    try:
                        shutil.rmtree(session_path)
                        cleaned_caches += 1
                    except Exception:
                        pass
            try:
                remaining = [d for d in os.listdir(date_path) if os.path.isdir(os.path.join(date_path, d))]
                if not remaining:
                    os.rmdir(date_path)
            except Exception:
                pass

    # Clean thumbnails
    kept_thumbs = 0
    cleaned_thumbs = 0
    if os.path.isdir(THUMBNAILS_DIR):
        for fname in os.listdir(THUMBNAILS_DIR):
            if not fname.lower().endswith(".jpg"):
                continue
            fpath = os.path.join(THUMBNAILS_DIR, fname)
            if not os.path.isfile(fpath):
                continue
            matched = False
            for vp in registered_paths:
                try:
                    if _thumb_cache_key(vp) == os.path.splitext(fname)[0]:
                        matched = True
                        break
                except Exception:
                    pass
            if matched:
                kept_thumbs += 1
            else:
                try:
                    os.unlink(fpath)
                    cleaned_thumbs += 1
                except Exception:
                    pass

    return cleaned_caches, cleaned_thumbs, kept_thumbs
