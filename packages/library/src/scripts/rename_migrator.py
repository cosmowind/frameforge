#!/usr/bin/env python3
"""
Migration logic for the rename pipeline: status-file updates, CSV path
updates, thumbnail migration, and the main() entry-point.

Requires rename_all (source/cache scanning) and rename_helpers (utilities).
"""

import csv
import hashlib
import os
import sys
import json
import shutil
from pathlib import Path

# ── Config ──
VIDEO_ROOT = Path(r"/media")
RUNTIME_DIR = Path(r"./vendor")
HMD_CACHE_ROOT = RUNTIME_DIR / "hmd_cache"
CSV_PATH = RUNTIME_DIR / "data" / "video_manager.csv"
THUMB_DIR = RUNTIME_DIR / "thumbnails"

# ── Imports from siblings ──
try:
    from scripts.rename_helpers import parse_args
    from scripts.rename_all import (
        scan_source_folders,
        scan_renamed_source_folders,
        scan_renamed_cache_folders,
        scan_cache_folders,
        scan_cache_files,
    )
except ImportError:
    from rename_helpers import parse_args
    from rename_all import (
        scan_source_folders,
        scan_renamed_source_folders,
        scan_renamed_cache_folders,
        scan_cache_folders,
        scan_cache_files,
    )


# ── 步骤4：更新状态 JSON 中的 left_mp4 引用 ──

def update_status_files(cache_root):
    """更新 .hmd_process.json 和 .hmd_fast.json 中 left_mp4/right_mp4 字段。"""
    updated = 0
    if not cache_root.is_dir():
        return updated

    for date_dir in cache_root.iterdir():
        if not date_dir.is_dir():
            continue
        for session_dir in date_dir.iterdir():
            if not session_dir.is_dir():
                continue

            base = session_dir.name

            for status_fn in (".hmd_process.json", ".hmd_fast.json"):
                status_path = session_dir / status_fn
                if not status_path.is_file():
                    continue

                try:
                    with open(status_path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    changed = False
                    if data.get("left_mp4") == "left.mp4":
                        data["left_mp4"] = f"{base}.mp4"
                        changed = True
                    if data.get("right_mp4") == "right.mp4":
                        data["right_mp4"] = f"{base}_right.mp4"
                        changed = True

                    if changed:
                        with open(status_path, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=2, ensure_ascii=False)
                        updated += 1
                        print(f"  [STATUS] {status_path} 已更新")
                except (json.JSONDecodeError, OSError) as e:
                    print(f"  [WARN] 无法更新 {status_path}: {e}")

    return updated


# ── 步骤5：更新 video_manager.csv 中的路径 ──

def _compute_thumb_fingerprint(path):
    """Compute the fingerprint used for thumbnail cache key (mirrors video.py:_thumb_cache_key)."""
    try:
        mtime = int(os.path.getmtime(path))
    except OSError:
        mtime = 0
    try:
        if os.path.isfile(path):
            size = os.path.getsize(path)
        elif os.path.isdir(path):
            total_size = 0
            file_count = 0
            for _dirpath, _dirnames, filenames in os.walk(path):
                file_count += len(filenames)
                for fn in filenames:
                    try:
                        total_size += os.path.getsize(os.path.join(_dirpath, fn))
                    except OSError:
                        pass
            size = (file_count << 40) | (total_size & ((1 << 40) - 1))
        else:
            size = 0
    except OSError:
        size = 0

    fingerprint = f"{path}|{mtime}|{size}"
    key = hashlib.sha1(fingerprint.encode("utf-8", errors="replace")).hexdigest()[:24]
    return key, fingerprint


def update_video_manager_csv(old_to_new_map):
    """Update video_manager.csv: replace old paths with new paths.

    old_to_new_map: dict {norm_old_path -> new_path_str}

    Returns: number of rows updated.
    """
    if not CSV_PATH.is_file():
        print("  [WARN] video_manager.csv not found, skip CSV update")
        return 0

    rows = []
    fieldnames = None
    try:
        with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            rows = [row for row in reader]
    except Exception as e:
        print(f"  [ERR] Cannot read CSV: {e}")
        return 0

    if not fieldnames:
        return 0

    updated = 0
    for row in rows:
        old_path = row.get("path", "").strip()
        if not old_path:
            continue
        norm_old = os.path.normpath(old_path)
        if norm_old in old_to_new_map:
            row["path"] = old_to_new_map[norm_old]
            updated += 1
            print(f"  [CSV] {old_path} -> {old_to_new_map[norm_old]}")
        else:
            # Try case-insensitive
            norm_lower = norm_old.lower()
            for k, v in old_to_new_map.items():
                if k.lower() == norm_lower:
                    row["path"] = v
                    updated += 1
                    print(f"  [CSV] {old_path} -> {v}")
                    break

    if updated:
        tmp_path = str(CSV_PATH) + ".tmp"
        try:
            with open(tmp_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            os.replace(tmp_path, str(CSV_PATH))
            print(f"  [CSV] Done: {updated} rows updated, saved to {CSV_PATH}")
        except Exception as e:
            print(f"  [ERR] CSV write failed: {e}")
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass
    else:
        print("  [CSV] No paths needed updating")

    return updated


# ── 步骤6：迁移缩略图 ──

def plan_thumb_migration(old_to_new_map):
    """Pre-compute thumbnail migration plan BEFORE source folders are renamed.

    Must be called while old paths still exist, so old thumbnail keys
    can be computed correctly.

    Returns: dict {new_normpath: (old_key, new_key)}
    """
    plan = {}
    if not THUMB_DIR.is_dir():
        return plan

    for old_path, new_path in old_to_new_map.items():
        old_key, _ = _compute_thumb_fingerprint(old_path)
        new_key, _ = _compute_thumb_fingerprint(new_path)

        if old_key == new_key:
            continue

        old_thumb = THUMB_DIR / f"{old_key}.jpg"
        new_thumb = THUMB_DIR / f"{new_key}.jpg"

        if old_thumb.is_file() and not new_thumb.exists():
            plan[new_path] = (old_key, new_key)

    return plan


def rebuild_thumb_plan_after_rename(old_to_new_map):
    """Post-hoc: reconstruct thumbnail migration plan AFTER source folders
    have been renamed (old paths no longer exist).

    Since only the folder name changed (not content), the mtime and size from
    the new path are identical to what they were before renaming. We can
    reconstruct the old thumbnail key by using new_path's mtime/size with
    old_path's string.

    Returns: dict {new_normpath: (old_key, new_key)}
    """
    plan = {}
    if not THUMB_DIR.is_dir():
        return plan

    def _fingerprint_from_meta(path_str, mtime, size):
        fp = f"{path_str}|{mtime}|{size}"
        key = hashlib.sha1(fp.encode("utf-8", errors="replace")).hexdigest()[:24]
        return key

    for old_path, new_path in old_to_new_map.items():
        # Compute new key from existing new path
        new_key, _ = _compute_thumb_fingerprint(new_path)

        # Get mtime/size from new path (should be identical to old path's)
        try:
            mtime = int(os.path.getmtime(new_path))
        except OSError:
            continue
        try:
            if os.path.isfile(new_path):
                size = os.path.getsize(new_path)
            elif os.path.isdir(new_path):
                total_size = 0
                file_count = 0
                for _dp, _dn, fns in os.walk(new_path):
                    file_count += len(fns)
                    for fn in fns:
                        try:
                            total_size += os.path.getsize(os.path.join(_dp, fn))
                        except OSError:
                            pass
                size = (file_count << 40) | (total_size & ((1 << 40) - 1))
            else:
                continue
        except OSError:
            continue

        # Reconstruct old key using old_path string + new_path's mtime/size
        old_key = _fingerprint_from_meta(old_path, mtime, size)

        if old_key == new_key:
            continue

        old_thumb = THUMB_DIR / f"{old_key}.jpg"
        new_thumb = THUMB_DIR / f"{new_key}.jpg"

        if old_thumb.is_file() and not new_thumb.exists():
            plan[new_path] = (old_key, new_key)

    return plan


def migrate_thumbnails(thumb_plan):
    """Rename thumbnails using a pre-computed plan from plan_thumb_migration().

    thumb_plan: dict {new_normpath: (old_key, new_key)}
    Must be computed BEFORE source folders are renamed.

    Returns: number of thumbnails migrated.
    """
    migrated = 0
    if not thumb_plan:
        return 0

    for new_path, (old_key, new_key) in thumb_plan.items():
        old_thumb = THUMB_DIR / f"{old_key}.jpg"
        new_thumb = THUMB_DIR / f"{new_key}.jpg"
        old_fp = THUMB_DIR / f"{old_key}.jpg.fp"
        new_fp = THUMB_DIR / f"{new_key}.jpg.fp"

        if not old_thumb.is_file():
            continue
        if new_thumb.exists():
            continue

        try:
            os.rename(str(old_thumb), str(new_thumb))
            migrated += 1
            print(f"  [THUMB] {old_key}.jpg -> {new_key}.jpg")
            if old_fp.is_file():
                try:
                    os.rename(str(old_fp), str(new_fp))
                except OSError:
                    pass
        except OSError as e:
            print(f"  [WARN] Thumb migration failed: {new_path}: {e}")

    if migrated:
        print(f"  [THUMB] Done: {migrated} thumbnails migrated")
    else:
        print("  [THUMB] No thumbnails needed migrating")

    return migrated


# ── 执行 ──

def main():
    execute, fix_thumbs, skip_set = parse_args()

    # ── Post-hoc thumbnail fix mode ──
    if fix_thumbs:
        print("=" * 70)
        print("  事后修复缩略图 — 从已重命名文件夹反推旧 key 并迁移")
        print("=" * 70)
        print(f"  视频根目录: {VIDEO_ROOT}")
        print(f"  缩略图目录: {THUMB_DIR}")
        print()

        # Scan already-renamed folders and reverse-engineer old→new mapping
        source_map = scan_renamed_source_folders(VIDEO_ROOT)
        cache_map = scan_renamed_cache_folders(HMD_CACHE_ROOT)
        old_to_new_map = {}
        old_to_new_map.update(source_map)
        old_to_new_map.update(cache_map)

        print(f"扫描到 {len(source_map)} 个已重命名的源文件夹 + {len(cache_map)} 个缓存文件夹")
        if not old_to_new_map:
            print("没有已重命名的文件夹，无需修复。")
            return

        print("重建缩略图迁移计划（使用新路径的 mtime/size 反推旧 key）...\n")

        thumb_plan = rebuild_thumb_plan_after_rename(old_to_new_map)
        print(f"  -> {len(thumb_plan)} 个缩略图待迁移\n")

        if not thumb_plan:
            print("没有可迁移的缩略图（可能已经是最新状态，或缩略图尚不存在）。")
            return

        print("--- 迁移缩略图 ---")
        migrate_thumbnails(thumb_plan)
        print("\n[DONE] 缩略图修复完成。")
        return

    print("=" * 70)
    if execute:
        print("  全量文件名迁移 — 执行模式")
    else:
        print("  全量文件名迁移 — 预览模式 (加 --execute 执行)")
    print("=" * 70)
    print(f"  视频根目录: {VIDEO_ROOT}")
    print(f"  缓存目录:   {HMD_CACHE_ROOT}")
    print(f"  跳过列表:")
    for s in sorted(skip_set):
        print(f"    - {s}")
    print()

    # ── 扫描 ──
    print("[1/6] 扫描源文件夹...")
    source_ops = scan_source_folders(VIDEO_ROOT, skip_set)
    print(f"  -> 发现 {len(source_ops)} 个源文件夹待重命名\n")

    print("[2/6] 扫描 hmd_cache 文件夹...")
    cache_folder_ops = scan_cache_folders(HMD_CACHE_ROOT, skip_set)
    print(f"  -> 发现 {len(cache_folder_ops)} 个缓存文件夹待重命名\n")

    print("[3/6] 扫描 hmd_cache 内部文件...")
    cache_file_ops = scan_cache_files(HMD_CACHE_ROOT, skip_set)
    print(f"  -> 发现 {len(cache_file_ops)} 个缓存文件待重命名\n")

    # Build old->new source path mapping (for CSV & thumbnail updates)
    old_to_new_map = {}
    for old, new_name, mmdd in source_ops:
        parent = os.path.dirname(old)
        new_path = os.path.join(parent, new_name)
        old_to_new_map[os.path.normpath(old)] = os.path.normpath(new_path)

    # Pre-compute thumbnail migration plan NOW while old paths still exist!
    # If we wait until after renaming, old paths are gone and keys can't be computed.
    if execute and old_to_new_map:
        thumb_plan = plan_thumb_migration(old_to_new_map)
    else:
        # Preview mode: also compute plan so counts are accurate
        thumb_plan = plan_thumb_migration(old_to_new_map)
    thumb_migrate_count = len(thumb_plan)

    print("[4/6] 检查 video_manager.csv 路径更新...")
    csv_rows_to_update = 0
    if old_to_new_map and CSV_PATH.is_file():
        try:
            with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    p = os.path.normpath(row.get("path", "").strip())
                    if p in old_to_new_map:
                        csv_rows_to_update += 1
                    else:
                        for k in old_to_new_map:
                            if p.lower() == k.lower():
                                csv_rows_to_update += 1
                                break
        except Exception:
            pass
    print(f"  -> {csv_rows_to_update} 行 CSV 路径待更新\n")

    print("[5/6] 检查缩略图迁移...")
    print(f"  -> {thumb_migrate_count} 个缩略图待迁移\n")

    print("[6/6] 检查状态文件...")
    status_count = 0
    # Quick count
    if HMD_CACHE_ROOT.is_dir():
        for date_dir in HMD_CACHE_ROOT.iterdir():
            if not date_dir.is_dir():
                continue
            for session_dir in date_dir.iterdir():
                if not session_dir.is_dir():
                    continue
                for fn in (".hmd_process.json", ".hmd_fast.json"):
                    if (session_dir / fn).is_file():
                        status_count += 1
    print(f"  -> 最多 {status_count} 个状态文件待检查\n")

    total = len(source_ops) + len(cache_folder_ops) + len(cache_file_ops)
    if total == 0 and csv_rows_to_update == 0 and thumb_migrate_count == 0:
        print("没有需要处理的项目，所有文件已是最新命名。")
        return

    # ── 显示预览 ──
    print("-" * 70)
    print(f"总计: {len(source_ops)} 源文件夹 + {len(cache_folder_ops)} 缓存文件夹 + {len(cache_file_ops)} 文件")
    print(f"       + {csv_rows_to_update} CSV行更新 + {thumb_migrate_count} 缩略图迁移")
    print("-" * 70)

    if source_ops:
        print("\n[DIR] 源文件夹重命名:")
        for old, new_name, mmdd in source_ops:
            parent = os.path.dirname(old)
            print(f"  {old}")
            print(f"  -> {os.path.join(parent, new_name)}")

    if cache_folder_ops:
        print("\n[DIR] hmd_cache 文件夹重命名:")
        for old, new_name, date_dir, mmdd, did, sn, suf in cache_folder_ops:
            new_path = date_dir / new_name
            print(f"  {old}")
            print(f"  -> {new_path}")

    if cache_file_ops:
        print("\n[VIDEO] hmd_cache 视频文件重命名:")
        rename_count = 0
        delete_count = 0
        for op, old, new in cache_file_ops:
            if op == "RENAME":
                rename_count += 1
                print(f"  {old}")
                print(f"  -> {new}")
            else:
                delete_count += 1
        if rename_count:
            print(f"  共 {rename_count} 个文件重命名")
        if delete_count:
            print(f"  (另 {delete_count} 个旧文件因新文件已存在，执行时将删除)")

    if csv_rows_to_update:
        print(f"\n[CSV] video_manager.csv 将有 {csv_rows_to_update} 行路径被更新")

    if thumb_migrate_count:
        print(f"\n[THUMB] 将有 {thumb_migrate_count} 个缩略图被迁移到新路径")

    if not execute:
        print("\n" + "=" * 70)
        print("  以上为预览。确认无误后执行: python rename_all.py --execute")
        print("=" * 70)
        return

    # ── 执行 ──
    print("\n" + "=" * 70)
    print("  开始执行重命名...")
    print("=" * 70)

    errors = []

    # 1) 源文件夹重命名
    if source_ops:
        print("\n--- 重命名源文件夹 ---")
        for old, new_name, mmdd in source_ops:
            parent = os.path.dirname(old)
            new_path = os.path.join(parent, new_name)
            try:
                os.rename(old, new_path)
                print(f"  [OK] {os.path.basename(old)} -> {new_name}")
            except OSError as e:
                errors.append(f"源文件夹: {old} -> {new_path}: {e}")
                print(f"  [ERR] {old}: {e}")

    # 2) hmd_cache 文件重命名（必须在文件夹重命名之前！）
    if cache_file_ops:
        print("\n--- 重命名 hmd_cache 视频文件 ---")
        for op, old, new in cache_file_ops:
            try:
                if op == "RENAME":
                    os.rename(old, new)
                    print(f"  [OK] {os.path.basename(old)} -> {os.path.basename(new)}")
                elif op == "DELETE_OLD":
                    os.remove(old)
                    print(f"  [OK] 删除旧文件: {os.path.basename(old)} (新文件已存在)")
            except OSError as e:
                errors.append(f"缓存文件: {old} -> {new}: {e}")
                print(f"  [ERR] {old}: {e}")

    # 3) hmd_cache 文件夹重命名（文件已改名后，再改文件夹名）
    if cache_folder_ops:
        print("\n--- 重命名 hmd_cache 文件夹 ---")
        for old, new_name, date_dir, mmdd, did, sn, suf in cache_folder_ops:
            new_path = date_dir / new_name
            try:
                os.rename(old, str(new_path))
                print(f"  [OK] {os.path.basename(old)} -> {new_name}")
            except OSError as e:
                errors.append(f"缓存文件夹: {old} -> {new_path}: {e}")
                print(f"  [ERR] {old}: {e}")

    # 4) 更新 video_manager.csv 路径
    if old_to_new_map:
        print("\n--- 更新 video_manager.csv ---")
        try:
            update_video_manager_csv(old_to_new_map)
        except Exception as e:
            errors.append(f"CSV更新: {e}")
            print(f"  [ERR] CSV更新失败: {e}")

    # 5) 迁移缩略图（使用重命名前预计算的 thumb_plan）
    if thumb_plan:
        print("\n--- 迁移缩略图 ---")
        try:
            migrate_thumbnails(thumb_plan)
        except Exception as e:
            errors.append(f"缩略图迁移: {e}")
            print(f"  [ERR] 缩略图迁移失败: {e}")

    # 6) 更新状态JSON
    print("\n--- 更新状态文件 (.hmd_process.json / .hmd_fast.json) ---")
    updated_count = update_status_files(HMD_CACHE_ROOT)
    if updated_count == 0:
        print("  (无需更新)")

    # ── 结果 ──
    print("\n" + "=" * 70)
    if errors:
        print(f"  完成（{len(errors)} 个错误）:")
        for e in errors:
            print(f"    - {e}")
    else:
        print("  [DONE] 全部完成，无错误。")
    print("=" * 70)


if __name__ == "__main__":
    main()
