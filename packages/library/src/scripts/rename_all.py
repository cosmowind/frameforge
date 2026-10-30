#!/usr/bin/env python3
"""
全量文件名迁移脚本：将现有本地视频统一更新为新命名规则。

功能：
  1. 源文件夹重命名：deviceId_session_XXXXX -> mmdd_deviceId_session_XXXXX
  2. hmd_cache 文件夹同步重命名
  3. hmd_cache 内视频文件重命名：left.mp4 -> {session_name}.mp4 等

用法：
  python rename_all.py              # 预览模式（仅显示将要执行的操作）
  python rename_all.py --execute    # 执行模式（实际重命名）
  python rename_all.py --skip /media/0620/hmd/9df5dc_session_00005  # 额外跳过

模块结构：
  rename_helpers.py   — 解析/命名工具函数
  rename_migrator.py  — 状态更新、CSV 更新、缩略图迁移、main()
  rename_all.py       — 源文件夹扫描、缓存文件夹/文件扫描（本文件）
"""

import os
from pathlib import Path

# ── Imports from sibling modules ──
try:
    from scripts.rename_helpers import (
        parse_session_name,
        is_downloading,
        build_new_name,
    )
except ImportError:
    from rename_helpers import (
        parse_session_name,
        is_downloading,
        build_new_name,
    )


# ── 步骤1：源文件夹重命名 ──

def scan_source_folders(video_root, skip_set):
    """扫描所有需要重命名的源文件夹。
    Returns: [(old_path, new_name, mmdd), ...]
    """
    ops = []
    if not video_root.is_dir():
        print(f"[WARN] 视频根目录不存在: {video_root}")
        return ops

    for mmdd_dir in sorted(video_root.iterdir()):
        if not mmdd_dir.is_dir():
            continue
        if not mmdd_dir.name.isdigit() or len(mmdd_dir.name) != 4:
            continue

        hmd_dir = mmdd_dir / "hmd"
        if not hmd_dir.is_dir():
            continue

        mmdd = mmdd_dir.name

        for item in sorted(hmd_dir.iterdir()):
            old_path = str(item)

            # 检查跳过
            if old_path in skip_set:
                print(f"  [SKIP] {old_path}")
                continue

            # 只处理目录
            if not item.is_dir():
                continue

            parsed = parse_session_name(item.name)
            if parsed is None:
                continue

            device_id_short, session_num, suffix = parsed

            # 如果已经包含 mmdd 前缀，跳过
            if item.name.startswith(mmdd + "_"):
                continue

            new_name = build_new_name(mmdd, device_id_short, session_num, suffix)
            new_path = hmd_dir / new_name

            if new_path.exists():
                print(f"  [CONFLICT] {old_path} -> {new_path} (目标已存在，跳过)")
                continue

            if is_downloading(item):
                print(f"  [DOWNLOADING] {old_path} (正在下载/不完整，跳过)")
                continue

            ops.append((str(old_path), new_name, mmdd))

    return ops


def scan_renamed_source_folders(video_root):
    """Scan source folders that already have mmdd_ prefix (already renamed).
    Reverse-engineers old name to build old→new path mapping.
    Returns: dict {norm_old_path: norm_new_path}
    """
    mapping = {}
    if not video_root.is_dir():
        return mapping

    for mmdd_dir in sorted(video_root.iterdir()):
        if not mmdd_dir.is_dir():
            continue
        if not mmdd_dir.name.isdigit() or len(mmdd_dir.name) != 4:
            continue

        hmd_dir = mmdd_dir / "hmd"
        if not hmd_dir.is_dir():
            continue

        mmdd = mmdd_dir.name
        prefix = mmdd + "_"

        for item in sorted(hmd_dir.iterdir()):
            if not item.is_dir():
                continue

            # Only process items that already have mmdd_ prefix
            if not item.name.startswith(prefix):
                continue

            # Derive old name by stripping prefix
            old_name = item.name[len(prefix):]
            old_path = str(hmd_dir / old_name)
            new_path = str(item)

            mapping[os.path.normpath(old_path)] = os.path.normpath(new_path)

    return mapping


def scan_renamed_cache_folders(cache_root):
    """Scan hmd_cache folders that already have mmdd_ prefix.
    Returns: dict {norm_old_path: norm_new_path}
    """
    mapping = {}
    if not cache_root.is_dir():
        return mapping

    for date_dir in sorted(cache_root.iterdir()):
        if not date_dir.is_dir():
            continue

        try:
            parts = date_dir.name.split("-")
            if len(parts) == 3:
                mmdd = f"{parts[1]}{parts[2]}"
            else:
                continue
        except (ValueError, IndexError):
            continue

        prefix = mmdd + "_"

        for item in sorted(date_dir.iterdir()):
            if not item.is_dir():
                continue

            if not item.name.startswith(prefix):
                continue

            old_name = item.name[len(prefix):]
            old_path = str(date_dir / old_name)
            new_path = str(item)

            mapping[os.path.normpath(old_path)] = os.path.normpath(new_path)

    return mapping


# ── 步骤2：hmd_cache 文件夹重命名 ──

def scan_cache_folders(cache_root, skip_set):
    """扫描 hmd_cache 中需要重命名的文件夹。
    注意：cache 文件夹当前没有 mmdd 前缀，但有 date_key 父目录。
    Returns: [(old_path, new_name, date_key, device_id_short, session_num), ...]
    """
    ops = []
    if not cache_root.is_dir():
        print(f"[WARN] hmd_cache 根目录不存在: {cache_root}")
        return ops

    for date_dir in sorted(cache_root.iterdir()):
        if not date_dir.is_dir():
            continue

        # 从 date_key 提取 mmdd
        # date_key 格式: '2026-06-20'
        try:
            parts = date_dir.name.split("-")
            if len(parts) == 3:
                mmdd = f"{parts[1]}{parts[2]}"
            else:
                continue
        except (ValueError, IndexError):
            continue

        for item in sorted(date_dir.iterdir()):
            if not item.is_dir():
                continue

            parsed = parse_session_name(item.name)
            if parsed is None:
                continue

            device_id_short, session_num, suffix = parsed

            # 已经含 mmdd 前缀则跳过
            if item.name.startswith(mmdd + "_"):
                continue

            # 检查是否在跳过列表中
            # 构建可能的源路径来匹配 skip_set
            cand_source = f"/media\\{mmdd}\\hmd\\{device_id_short}_{session_num}"
            if cand_source in skip_set:
                print(f"  [SKIP cache] {item} (对应源文件夹被跳过)")
                continue

            # 也检查带 suffix 的
            if suffix:
                cand_source2 = f"/media\\{mmdd}\\hmd\\{device_id_short}_{session_num}{suffix}"
                if cand_source2 in skip_set:
                    print(f"  [SKIP cache] {item} (对应源文件夹被跳过)")
                    continue

            new_name = build_new_name(mmdd, device_id_short, session_num, suffix)
            new_path = date_dir / new_name

            if new_path.exists():
                print(f"  [CONFLICT cache] {item} -> {new_path} (目标已存在，跳过)")
                continue

            ops.append((str(item), new_name, date_dir, mmdd, device_id_short, session_num, suffix))

    return ops


# ── 步骤3：hmd_cache 内部文件重命名 ──

def scan_cache_files(cache_root, skip_set):
    """扫描 hmd_cache 中每个 session 文件夹内的视频文件，需重命名为新规则。
    left.mp4 -> {basename}.mp4
    right.mp4 -> {basename}_right.mp4
    left.h265 -> {basename}.h265
    right.h265 -> {basename}_right.h265
    left.hevc.mp4 -> {basename}.hevc.mp4

    注意：仅对已经带有 mmdd 前缀的新命名文件夹执行，或同时对旧文件夹的新命名目标执行。
    """
    ops = []
    if not cache_root.is_dir():
        return ops

    RENAME_MAP = {
        "left.mp4":       "{base}.mp4",
        "right.mp4":      "{base}_right.mp4",
        "left.h265":      "{base}.h265",
        "right.h265":     "{base}_right.h265",
        "left.hevc.mp4":  "{base}.hevc.mp4",
    }

    for date_dir in sorted(cache_root.iterdir()):
        if not date_dir.is_dir():
            continue

        # 从 date_key 提取 mmdd
        try:
            parts = date_dir.name.split("-")
            if len(parts) == 3:
                mmdd = f"{parts[1]}{parts[2]}"
            else:
                continue
        except (ValueError, IndexError):
            continue

        for session_dir in sorted(date_dir.iterdir()):
            if not session_dir.is_dir():
                continue

            old_base = session_dir.name

            # 确定新的 base 名（含 mmdd 前缀）
            parsed = parse_session_name(old_base)
            if parsed is None:
                continue

            device_id_short, session_num, suffix = parsed

            if old_base.startswith(mmdd + "_"):
                # 已有 mmdd 前缀，直接使用
                new_base = old_base
            else:
                # 旧命名：计算新名
                new_base = build_new_name(mmdd, device_id_short, session_num, suffix)

            for old_fname, new_fname_tpl in RENAME_MAP.items():
                old_path = session_dir / old_fname
                if not old_path.is_file():
                    continue

                new_fname = new_fname_tpl.format(base=new_base)
                new_path = session_dir / new_fname

                # 如果新文件名已存在且大小相同，跳过
                if new_path.exists():
                    if new_path.stat().st_size == old_path.stat().st_size:
                        # 同名文件已存在，可以删除旧的
                        ops.append(("DELETE_OLD", str(old_path), str(new_path)))
                        continue
                    else:
                        print(f"  [CONFLICT file] {old_path} -> {new_path} (目标已存在但大小不同)")
                        continue

                ops.append(("RENAME", str(old_path), str(new_path)))

    return ops


# ── Thin wrapper: delegate main() to rename_migrator ──

def main():
    try:
        from scripts.rename_migrator import main as _main
    except ImportError:
        from rename_migrator import main as _main
    _main()


if __name__ == "__main__":
    main()
