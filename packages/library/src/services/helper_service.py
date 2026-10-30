import logging
import sys
import os
import json
import glob
import shutil
import re
import threading
import time
from datetime import datetime
from typing import Optional, Dict, List, Any
from config import *
from config import USE_PG, DATABASE_DSN

logger = logging.getLogger(__name__)

def _load_upload_options() -> dict:
    """加载上传表单的枚举选项（国家、场景分类等）。
    数据来源: vendor-upload-pkg/stereo-upload-params/*.zh-CN.json
    """
    global _UPLOAD_OPTIONS_CACHE
    if _UPLOAD_OPTIONS_CACHE is not None:
        return _UPLOAD_OPTIONS_CACHE

    # 优先查找当前项目下的 vendor-upload-pkg，其次查找邻接目录
    params_dir = os.path.join(SRC_DIR, "vendor-upload-pkg", "stereo-upload-params")
    if not os.path.isdir(params_dir):
        # 邻接项目路径: ./vendor
        alt_dir = os.path.join(ROOT_DIR, "vendor-upload-pkg", "stereo-upload-params")
        if os.path.isdir(alt_dir):
            params_dir = alt_dir
    options = {
        "captureModes": [
            {"value": "single", "label": "单目"},
            {"value": "stereo", "label": "双目立体"},
            {"value": "three_views", "label": "三目"},
        ],
        "countries": [],
        "regions": {},
        "sceneCategories": [],
        "scenes": [],
        "gloves": [
            {"value": "No — bare hands", "label": "否 — 裸手"},
            {"value": "Yes — wearing gloves", "label": "是 — 佩戴手套"},
        ],
        "environments": [
            {"value": "Agriculture / Farming", "label": "农林"},
            {"value": "Construction / Trades", "label": "建筑/施工"},
            {"value": "Food Service / Dining", "label": "餐饮服务"},
            {"value": "Healthcare / Medical", "label": "医疗/健康"},
            {"value": "Home / Residential", "label": "住宅"},
            {"value": "Industrial Manufacturing", "label": "工业制造"},
            {"value": "Office / Knowledge Work", "label": "办公/知识工作"},
            {"value": "Other", "label": "其他"},
            {"value": "Outdoor / Nature", "label": "户外-自然"},
            {"value": "Outdoor / Urban", "label": "户外-城市"},
            {"value": "Retail / Commercial", "label": "零售/商业"},
            {"value": "Transportation", "label": "交通"},
            {"value": "Warehouse / Logistics", "label": "仓储物流"},
        ],
        "facilityVenues": [
            {"value": "Construction Site", "label": "施工现场"},
            {"value": "Hospital / Clinic", "label": "医院/诊所"},
            {"value": "Manufacturing Factory", "label": "制造工厂"},
            {"value": "Office Building", "label": "办公楼"},
            {"value": "Other", "label": "其他"},
            {"value": "Outdoor Site", "label": "户外场地"},
            {"value": "Residential Home", "label": "住宅"},
            {"value": "Restaurant / Kitchen", "label": "餐厅/厨房"},
            {"value": "Retail Store", "label": "零售商店"},
            {"value": "Warehouse", "label": "仓库"},
        ],
    }

    # 加载国家列表
    countries_path = os.path.join(params_dir, "countries.zh-CN.json")
    if os.path.isfile(countries_path):
        try:
            with open(countries_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data.get("values", []):
                options["countries"].append({
                    "value": item["code"],
                    "label": item["label"].get("zh-CN", item["code"]),
                })
        except Exception as e:
            print(f"[warn] 加载国家列表失败: {e}", file=sys.stderr)

    # 加载地区列表（US/CN/JP/GB 结构化数据）
    regions_path = os.path.join(params_dir, "regions.zh-CN.json")
    if os.path.isfile(regions_path):
        try:
            with open(regions_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for country_code, region_list in data.get("values", {}).items():
                options["regions"][country_code] = [
                    {"value": r["value"], "label": r.get("label", {}).get("zh-CN", r.get("value", ""))}
                    for r in region_list
                ]
        except Exception as e:
            print(f"[warn] 加载地区列表失败: {e}", file=sys.stderr)

    # 加载场景分类（21 大类 + 子类）
    scene_path = os.path.join(params_dir, "scene-categories.zh-CN.json")
    if os.path.isfile(scene_path):
        try:
            with open(scene_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            scene_flat = []
            for cat in data.get("values", []):
                cat_zh = cat["label"].get("zh-CN", cat["id"])
                cat_en = cat["label"].get("en", cat["id"])
                entry = {
                    "value": cat["id"],
                    "label": cat_zh,
                    "subcategories": [],
                }
                for sub in cat.get("subcategories", []):
                    sub_id = sub["id"]
                    sub_zh = sub["label"].get("zh-CN", sub_id)
                    sub_en = sub["label"].get("en", sub_id)
                    entry["subcategories"].append({
                        "value": sub_id,
                        "label": sub_zh,
                    })
                    # flat scenes list: only subcategories (not top-level categories)
                    # display as "大类 · 子类中文-English" so users know the taxonomy
                    scene_flat.append({
                        "value": sub_id,
                        "label": f"{cat_zh} · {sub_zh}",
                        "labelEn": sub_en,
                        "categoryZh": cat_zh,
                        "categoryEn": cat_en,
                    })
                options["sceneCategories"].append(entry)
            # sort flat list by Chinese label alphabetically
            scene_flat.sort(key=lambda x: x["label"])
            options["scenes"] = scene_flat
        except Exception as e:
            print(f"[warn] 加载场景分类失败: {e}", file=sys.stderr)

    # 加载实时抓取的 Scene 名称列表（从上传页面下拉框提取的 809 个选项）
    scene_names_path = os.path.join(SRC_DIR, "tools", "scene_options_live.json")
    if os.path.isfile(scene_names_path):
        try:
            with open(scene_names_path, "r", encoding="utf-8") as f:
                live_scenes = json.load(f)
            options["sceneNames"] = [
                {"value": s["value"], "label": s["value"], "labelZh": s.get("labelZh", s["value"])}
                for s in live_scenes.get("scenes", [])
            ]
        except Exception as e:
            print(f"[warn] 加载实时场景名称失败: {e}", file=sys.stderr)
    else:
        options["sceneNames"] = []

    _UPLOAD_OPTIONS_CACHE = options
    return options



def parse_history_date_from_filename(filename):
    """Parse date from historical CSV filename like video_manager0517-1.csv -> 2026-05-17"""
    match = re.search(r'(\d{2})(\d{2})', filename)
    if match:
        month, day = match.groups()
        year = datetime.now().year
        try:
            return datetime(year, int(month), int(day)).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return datetime.now().strftime("%Y-%m-%d")



def _aggregate_hmd_size_ratio():
    """Walk video_manager.csv, for each hmd row with .hmd_process.json done,
    return (median_size_mb_per_min, count, samples[], medians_by_camera, camera_count).

    samples: [{path, size_mb, duration_sec, size_mb_per_min, camera}, ...]
    medians_by_camera: { "<camera_id>": median_size_mb_per_min, ... }
    camera_count: number of distinct cameras in samples

    Groups by camera (CSV `device_id` field, last 6 chars of
    metadata.devices[0].identity.device_id) so a high-bitrate Insta360 and
    a low-bitrate phone don't collapse to a useless overall median.
    """
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
        # Compute total size of all part_*.hmd
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
        # Camera id from CSV (already last 6 chars of metadata device_id)
        camera = (r.get("device_id") or "").strip() or "unknown"
        samples.append({
            "path": path,
            "size_mb": round(size_mb, 2),
            "duration_sec": int(sec),
            "size_mb_per_min": round(size_mb / duration_min, 3),
            "camera": camera,
        })
    if not samples:
        return None, 0, samples, {}, 0
    # Overall median (more robust than mean against outliers)
    sorted_ratios = sorted(s["size_mb_per_min"] for s in samples)
    n = len(sorted_ratios)
    median = sorted_ratios[n // 2] if n % 2 else (sorted_ratios[n // 2 - 1] + sorted_ratios[n // 2]) / 2

    # Per-camera median grouping
    by_camera = {}
    for s in samples:
        by_camera.setdefault(s["camera"], []).append(s["size_mb_per_min"])
    medians_by_camera = {}
    for cam, ratios in by_camera.items():
        rs = sorted(ratios)
        cn = len(rs)
        medians_by_camera[cam] = round(
            rs[cn // 2] if cn % 2 else (rs[cn // 2 - 1] + rs[cn // 2]) / 2,
            3,
        )

    return round(median, 3), len(samples), samples, medians_by_camera, len(medians_by_camera)



def _get_size_mb_per_min():
    """Read from config; fallback to aggregated median; fallback to default."""
    cfg = load_config()
    saved = cfg.get("estimate", {}).get("size_mb_per_min")
    if isinstance(saved, (int, float)) and saved > 0:
        return float(saved), "user"
    median, n, _, _, _ = _aggregate_hmd_size_ratio()
    if median:
        return median, f"auto (median of {n} sessions)"
    return DEFAULT_SIZE_MB_PER_MIN, "default"



def estimate_hmd_duration_sec(total_size_bytes, ratio_mb_per_min=None):
    """Estimate duration in seconds from total HMD session size (bytes)."""
    if total_size_bytes is None or total_size_bytes <= 0:
        return 0
    if ratio_mb_per_min is None:
        ratio_mb_per_min, _ = _get_size_mb_per_min()
    size_mb = total_size_bytes / 1024 / 1024
    return int(round((size_mb / ratio_mb_per_min) * 60))





def tee_print(*args, **kwargs):
    """Print to both stdout and log file (if set)."""
    msg = " ".join(str(a) for a in args)
    # flush stdout first so real-time output works
    print(msg, **kwargs, flush=True)
    if LOG_FILE:
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as lf:
                lf.write(msg + "\\n")
        except Exception:
            pass

# Parse optional --log-file argument
_args = sys.argv[1:]
if len(_args) >= 2 and _args[0] == "--log-file":
    LOG_FILE = _args[1]
    tee_print = tee_print  # already defined


