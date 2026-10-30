#!/usr/bin/env python3
"""
修复脚本：纠正被重复添加设备ID前缀的视频文件夹名，并清理 CSV 记录。

问题：某些文件夹被错误命名为 id_mmdd_id_session_000x 格式
      正确应为 mmdd_id_session_000x

步骤：
  1. 扫描 /media 下所有匹配错误模式的文件夹，重命名为正确格式
  2. 从 video_manager.csv 中删除指向错误路径的记录
  3. 输出报告，提示用户重新扫描
"""

import os
import re
import sys
import csv

# ── 配置 ──
SCAN_DIR = r"/media"
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CSV_PATH = os.path.join(ROOT_DIR, "runtime", "data", "video_manager.csv")
HMD_CACHE_DIR = os.path.join(ROOT_DIR, "runtime", "hmd_cache")

# 错误命名模式：devId_mmdd_devId_session_NNNNN
# 例如：9df5dc_0620_9df5dc_session_00000
WRONG_PATTERN = re.compile(
    r'^([a-fA-F0-9]{6})_'   # deviceId (6 hex chars)
    r'(\d{4})_'              # mmdd (4 digits)
    r'\1_'                   # same deviceId again (the duplicate!)
    r'(session_\d{5})$'      # session_NNNNN
)


def fix_folder_names(base_dir):
    """查找并重命名错误命名的文件夹。返回 (renamed_count, renamed_list)。"""
    renamed = []
    print(f"\n{'='*60}")
    print(f"步骤 1: 扫描并修复文件夹名")
    print(f"扫描目录: {base_dir}")
    print(f"{'='*60}")

    for root, dirs, _files in os.walk(base_dir):
        # 需要在遍历过程中修改 dirs，所以复制列表
        for dirname in list(dirs):
            m = WRONG_PATTERN.match(dirname)
            if not m:
                continue

            dev_id = m.group(1)
            mmdd = m.group(2)
            session = m.group(3)
            correct_name = f"{mmdd}_{dev_id}_{session}"

            old_path = os.path.join(root, dirname)
            new_path = os.path.join(root, correct_name)

            if os.path.exists(new_path):
                print(f"  [跳过] 目标已存在: {correct_name}")
                continue

            try:
                os.rename(old_path, new_path)
                dirs[dirs.index(dirname)] = correct_name  # 更新 dirs 以便继续遍历
                renamed.append((old_path, new_path))
                print(f"  [重命名] {dirname}")
                print(f"        →  {correct_name}")
            except Exception as e:
                print(f"  [失败] {dirname} → {correct_name}: {e}")

    print(f"\n共重命名 {len(renamed)} 个文件夹")
    return renamed


def fix_hmd_cache(renamed):
    """同步重命名 hmd_cache 中对应的缓存目录。
    renamed: list of (old_source_path, new_source_path)
    """
    print(f"\n{'='*60}")
    print(f"步骤 2: 修复 hmd_cache 缓存目录")
    print(f"{'='*60}")

    if not os.path.isdir(HMD_CACHE_DIR):
        print("  hmd_cache 目录不存在，跳过")
        return 0

    cache_renamed = 0
    for old_src, new_src in renamed:
        old_base = os.path.basename(os.path.normpath(old_src))
        new_base = os.path.basename(os.path.normpath(new_src))

        # cache 路径: hmd_cache/<date>/<session_basename>/
        for date_dir in os.listdir(HMD_CACHE_DIR):
            date_path = os.path.join(HMD_CACHE_DIR, date_dir)
            if not os.path.isdir(date_path):
                continue
            old_cache = os.path.join(date_path, old_base)
            new_cache = os.path.join(date_path, new_base)
            if os.path.isdir(old_cache) and not os.path.exists(new_cache):
                try:
                    os.rename(old_cache, new_cache)
                    cache_renamed += 1
                    print(f"  [缓存] {old_base} → {new_base}")
                except Exception as e:
                    print(f"  [缓存失败] {old_base}: {e}")

    print(f"\n共重命名 {cache_renamed} 个缓存目录")
    return cache_renamed


def clean_csv(renamed_paths):
    """从 video_manager.csv 中删除指向错误路径的记录。
    renamed_paths: list of (old_path, new_path) tuples
    """
    print(f"\n{'='*60}")
    print(f"步骤 3: 清理 CSV 记录")
    print(f"CSV 路径: {CSV_PATH}")
    print(f"{'='*60}")

    if not os.path.exists(CSV_PATH):
        print("  CSV 文件不存在，跳过")
        return 0, 0

    # 读取所有行
    with open(CSV_PATH, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        all_rows = list(reader)

    wrong_path_set = set()
    # 收集所有已知的错误路径
    for old_path, _new_path in renamed_paths:
        wrong_path_set.add(os.path.normpath(old_path))

    # 也扫描 CSV 中匹配错误模式的行
    csv_deleted = 0
    kept_rows = []
    for row in all_rows:
        path = row.get("path", "")
        folder_name = os.path.basename(os.path.normpath(path))
        if WRONG_PATTERN.match(folder_name) or os.path.normpath(path) in wrong_path_set:
            print(f"  [删除] {path}")
            csv_deleted += 1
        else:
            kept_rows.append(row)

    if csv_deleted == 0:
        print("  没有需要删除的记录")
    else:
        # 备份原 CSV
        backup_path = CSV_PATH + ".bak"
        import shutil
        shutil.copy2(CSV_PATH, backup_path)
        print(f"  已备份原 CSV → {backup_path}")

        # 写回
        with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(kept_rows)

        print(f"\n  共删除 {csv_deleted} 条记录，保留 {len(kept_rows)} 条")

    return csv_deleted, len(kept_rows)


def verify_old_records():
    """检查修正后的文件夹是否能匹配到 CSV 中的 history 记录。"""
    print(f"\n{'='*60}")
    print(f"步骤 4: 验证 history 记录匹配")
    print(f"{'='*60}")

    if not os.path.exists(CSV_PATH):
        print("  CSV 文件不存在，跳过")
        return

    with open(CSV_PATH, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    history_rows = [r for r in rows if (r.get("location_status") or '').endswith('_history')]
    matched = 0
    unmatched = 0
    unmatched_list = []

    for row in history_rows:
        path = row.get("path", "")
        if os.path.isdir(path):
            matched += 1
        else:
            unmatched += 1
            unmatched_list.append(path)

    print(f"  History 记录总数: {len(history_rows)}")
    print(f"  路径存在（将被重新发现为 local）: {matched}")
    print(f"  路径不存在（仍保持 history）: {unmatched}")

    if unmatched_list and len(unmatched_list) <= 10:
        for p in unmatched_list:
            print(f"    - {p}")
    elif unmatched_list:
        print(f"  （前10条）:")
        for p in unmatched_list[:10]:
            print(f"    - {p}")
        print(f"  ... 还有 {len(unmatched_list) - 10} 条")

    return matched, unmatched


def main():
    print("=" * 60)
    print("视频文件夹名称修复工具")
    print("修复  id_mmdd_id_session_000x → mmdd_id_session_000x")
    print("=" * 60)

    if not os.path.isdir(SCAN_DIR):
        print(f"\n[错误] 视频目录不存在: {SCAN_DIR}")
        print("请修改脚本中的 SCAN_DIR 变量后重试")
        sys.exit(1)

    if not os.path.exists(CSV_PATH):
        print(f"\n[警告] CSV 文件不存在: {CSV_PATH}")
        response = input("是否继续（仅修复文件夹名）？(y/n): ")
        if response.lower() != 'y':
            sys.exit(0)

    # 步骤 1: 修复文件夹名
    renamed = fix_folder_names(SCAN_DIR)

    # 步骤 2: 同步修复 hmd_cache
    if renamed:
        fix_hmd_cache(renamed)

    # 步骤 3: 清理 CSV
    if renamed:
        clean_csv(renamed)
    else:
        # 即使没有重命名，也扫描 CSV 中是否有遗留的错误记录
        print(f"\n{'='*60}")
        print(f"步骤 3: 扫描 CSV 中的错误记录")
        print(f"{'='*60}")
        clean_csv([])

    # 步骤 4: 验证
    verify_old_records()

    print(f"\n{'='*60}")
    print("修复完成！")
    print(f"{'='*60}")
    print("\n下一步操作：")
    print("  1. 启动 Video Manager 应用")
    print("  2. 点击 [开始扫描] 按钮重新扫描 /media")
    print("  3. 之前标记为 history 的记录应该会被重新识别为 local")
    print("  4. 检查扫描结果确认一切正常")
    print()


if __name__ == "__main__":
    main()
