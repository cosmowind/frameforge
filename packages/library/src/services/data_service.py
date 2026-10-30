"""
数据操作服务。
提供 CSV 保存/导出、视频时长读取、HMD 时长估算等功能。
"""

import json
import os
import re
import subprocess
import sys

from config import DEFAULT_FIELDNAMES, DEFAULT_SIZE_MB_PER_MIN, CONFIG_PATH, USE_PG
if USE_PG:
    from models.pg_store import read_csv, write_csv, load_config, get_fieldnames
else:
    from models.csv_store import read_csv, write_csv, load_config, get_fieldnames
from utils.format_utils import fmt_duration as _fmt_duration
from services.lazy_loader import (
    _get_hmd_preprocess, _get_hmd_fast_preprocess,
)


# ────────────────────────────────────────────────────────────────
# 视频时长
# ────────────────────────────────────────────────────────────────

def get_video_duration(filepath):
    """使用 ffprobe 获取视频时长格式化字符串（H:MM:SS 或 M:SS）。"""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", filepath],
            capture_output=True, encoding="utf-8", errors="replace", timeout=15,
        )
        seconds = float(result.stdout.strip())
        if seconds <= 0:
            return ""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h}:{m:02d}:{s:02d}" if h > 0 else f"{m}:{s:02d}"
    except Exception:
        return ""


def read_hmd_duration_from_status(session_folder):
    """从 .hmd_fast.json 或 .hmd_process.json 读取 HMD session 时长。"""
    hmd_pre = _get_hmd_preprocess()
    hmd_fast = _get_hmd_fast_preprocess()
    if not hmd_pre and not hmd_fast:
        return None

    if hmd_fast:
        fast_status = hmd_fast.get_status_path(session_folder)
        if os.path.isfile(fast_status):
            try:
                with open(fast_status, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("status") == "done":
                    sec = data.get("duration_sec")
                    if isinstance(sec, (int, float)) and sec > 0:
                        return _fmt_duration(int(sec))
            except Exception:
                pass

    if hmd_pre:
        status_file = hmd_pre.get_status_path(session_folder)
        if os.path.isfile(status_file):
            try:
                with open(status_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("status") == "done":
                    sec = data.get("duration_sec")
                    if isinstance(sec, (int, float)) and sec > 0:
                        return _fmt_duration(int(sec))
            except Exception:
                pass

    return None


# ────────────────────────────────────────────────────────────────
# 保存 & 导出
# ────────────────────────────────────────────────────────────────

def save_data(rows):
    """保存 CSV 行数据，带 scan_date 回填保护。"""
    fieldnames = get_fieldnames()
    try:
        existing = read_csv()
        existing_by_path = {r.get("path", ""): r for r in existing}
    except Exception:
        existing_by_path = {}

    protected = 0
    cleaned = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        cleaned_row = {}
        for fn in fieldnames:
            val = row.get(fn, "") if isinstance(row, dict) else ""
            cleaned_row[fn] = str(val).strip()
        if not cleaned_row.get("scan_date"):
            old = existing_by_path.get(cleaned_row.get("path", ""))
            if old and old.get("scan_date"):
                cleaned_row["scan_date"] = old["scan_date"]
                protected += 1
        cleaned.append(cleaned_row)
    write_csv(cleaned)
    return len(cleaned), protected


def export_txt(selected_cols):
    """导出 CSV 数据为制表符分隔文本。"""
    rows = read_csv()
    lines = []
    # Headers
    header_parts = []
    for c in selected_cols:
        header_parts.append(c)
    lines.append("\t".join(header_parts))
    # Rows
    for r in rows:
        row_parts = []
        for c in selected_cols:
            val = r.get(c, "")
            val = str(val).replace("\t", " ").replace("\n", " ").replace("\r", " ")
            row_parts.append(val)
        lines.append("\t".join(row_parts))
    return "\n".join(lines)


# ────────────────────────────────────────────────────────────────
# HMD 时长估算
# ────────────────────────────────────────────────────────────────

def aggregate_hmd_size_ratio():
    """遍历 CSV 中已预处理的 HMD row，计算 MB/分钟 中位数（按设备分组）。"""
    samples = []
    hmd_pre = _get_hmd_preprocess()
    for r in read_csv():
        if (r.get("file_type") or "") != "hmd":
            continue
        path = (r.get("path") or "").strip()
        if not path or not os.path.isdir(path):
            continue
        if not hmd_pre:
            continue
        status_file = hmd_pre.get_status_path(path)
        if not os.path.isfile(status_file):
            continue
        try:
            with open(status_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("status") != "done":
                continue
            sec = data.get("duration_sec")
            if not isinstance(sec, (int, float)) or sec <= 0:
                continue
        except Exception:
            continue
        total = 0
        try:
            for fname in os.listdir(path):
                if fname.startswith("part_") and fname.endswith(".hmd"):
                    total += os.path.getsize(os.path.join(path, fname))
        except Exception:
            continue
        if total <= 0:
            continue
        size_mb = total / 1024 / 1024
        duration_min = sec / 60.0
        if duration_min <= 0:
            continue
        camera = (r.get("device_id") or "").strip() or "unknown"
        samples.append({
            "path": path, "size_mb": round(size_mb, 2),
            "duration_sec": int(sec),
            "size_mb_per_min": round(size_mb / duration_min, 3),
            "camera": camera,
        })
    if not samples:
        return None, 0, samples, {}, 0

    sorted_ratios = sorted(s["size_mb_per_min"] for s in samples)
    n = len(sorted_ratios)
    median = sorted_ratios[n // 2] if n % 2 else (sorted_ratios[n // 2 - 1] + sorted_ratios[n // 2]) / 2

    by_camera = {}
    for s in samples:
        by_camera.setdefault(s["camera"], []).append(s["size_mb_per_min"])
    medians_by_camera = {}
    for cam, ratios in by_camera.items():
        rs = sorted(ratios)
        cn = len(rs)
        medians_by_camera[cam] = round(
            rs[cn // 2] if cn % 2 else (rs[cn // 2 - 1] + rs[cn // 2]) / 2, 3
        )

    return round(median, 3), len(samples), samples, medians_by_camera, len(medians_by_camera)


def get_size_mb_per_min():
    """读取 config > 聚合中位数 > 默认值。"""
    cfg = load_config()
    saved = cfg.get("estimate", {}).get("size_mb_per_min")
    if isinstance(saved, (int, float)) and saved > 0:
        return float(saved), "user"
    median, n, _, _, _ = aggregate_hmd_size_ratio()
    if median:
        return median, f"auto (median of {n} sessions)"
    return DEFAULT_SIZE_MB_PER_MIN, "default"


def estimate_hmd_duration_sec(total_size_bytes, ratio_mb_per_min=None):
    """根据 HMD session 总大小（字节）估算时长（秒）。"""
    if total_size_bytes is None or total_size_bytes <= 0:
        return 0
    if ratio_mb_per_min is None:
        ratio_mb_per_min, _ = get_size_mb_per_min()
    size_mb = total_size_bytes / 1024 / 1024
    return int(round((size_mb / ratio_mb_per_min) * 60))
