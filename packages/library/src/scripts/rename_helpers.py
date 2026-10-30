#!/usr/bin/env python3
"""
Parsing and naming utilities for the rename pipeline.

Provides:
  - parse_args(): CLI argument parsing
  - extract_mmdd(): extract MMDD date from a path
  - parse_session_name(): parse folder name into (device_id, session_num, suffix)
  - is_downloading(): detect if a folder is still being downloaded
  - build_new_name(): construct the new mmdd_deviceId_session_NNNNN name
"""

import os
import re
import sys
from pathlib import Path

# ── Constants ──

# 默认跳过的路径（正在下载/需要本轮跳过的）
DEFAULT_SKIP = set()

# 视为"正在下载"的标记（文件夹不完整）
DOWNLOAD_INDICATORS = [".downloading", ".partial", ".in_progress"]


# ── Functions ──

def parse_args():
    execute = "--execute" in sys.argv
    fix_thumbs = "--fix-thumbnails" in sys.argv
    skip_paths = set(DEFAULT_SKIP)
    for a in sys.argv[1:]:
        if a.startswith("--skip="):
            skip_paths.add(a[len("--skip="):])
    return execute, fix_thumbs, skip_paths


def extract_mmdd(path):
    """从路径中提取 MMDD 日期"""
    parts = str(path).replace("\\", "/").split("/")
    for p in reversed(parts):
        if len(p) == 4 and p.isdigit():
            m, d = int(p[:2]), int(p[2:])
            if 1 <= m <= 12 and 1 <= d <= 31:
                return p
    return None


def parse_session_name(dirname):
    """解析文件夹名，返回 (device_id_short, session_num, suffix)
    例: '4aa45c_session_00005.uploaded' -> ('4aa45c', 'session_00005', '.uploaded')
         '0620_4aa45c_session_00005' -> ('4aa45c', 'session_00005', '')  ← 已重命名
         '9df5dc_session_00000' -> ('9df5dc', 'session_00000', '')
    """
    # 匹配: [可选mmdd_] deviceId_session_NNNNN [.可选后缀]
    m = re.match(r'^(?:\d{4}_)?([0-9a-f]{6})_(session_\d{5})(.*)$', dirname, re.IGNORECASE)
    if not m:
        return None
    return m.group(1), m.group(2), m.group(3)


def is_downloading(folder):
    """检测文件夹是否正在下载中"""
    path = Path(folder)
    if not path.is_dir():
        return True  # 不存在就当正在下载
    # 检查下载标记文件
    for ind in DOWNLOAD_INDICATORS:
        if (path / ind).exists():
            return True
    # 检查是否有 .hmd 文件（源文件夹有则不是纯缓存）
    # 如果没有 metadata.json 也没有 .hmd 文件，可能还没下载完
    has_media = any(path.glob("*.hmd")) or any(path.glob("*.mp4"))
    has_meta = (path / "metadata.json").exists()
    if not has_meta and not has_media:
        # 空文件夹或只有缓存文件的文件夹
        return True
    return False


def build_new_name(mmd, device_id_short, session_num, suffix=""):
    """构建新文件夹名：mmdd_deviceId_session_NNNNN[.suffix]"""
    return f"{mmd}_{device_id_short}_{session_num}{suffix}"
