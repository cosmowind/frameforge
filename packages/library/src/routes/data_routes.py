"""data_routes — core data CRUD: config, data, scan, save, delete, merge-history."""

import csv
import datetime
import glob
import json
import logging
import os
import re
import shutil
import subprocess
import sys

from flask import Blueprint, jsonify, request

from config import (
    ARCHIVE_DIR, BASE_DIR, DEFAULT_FIELDNAMES, THUMBNAILS_DIR,
    _DIM_REGISTRY, USE_PG, SOURCE_DEVICE,
)
from config import USE_PG
if USE_PG:
    from models.pg_store import get_fieldnames, load_config, read_csv, write_csv
else:
    from models.csv_store import get_fieldnames, load_config, read_csv, write_csv
from services.lazy_loader import (
    _get_hmd_fast_preprocess,
    _get_hmd_preprocess, _get_device_monitor,
)
from services.video import _thumb_cache_key
from routes.data_helpers import (
    _extract_date_from_path,
    parse_history_date_from_filename,
    _auto_upsert_hmd_devices_to_sd_cards,
    _auto_upsert_data_devices_to_sd_cards,
    _get_size_mb_per_min_from_service,
)
from utils.path_utils import canon_path as _canon_local

logger = logging.getLogger(__name__)
bp = Blueprint("data", __name__)


# ─────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────

@bp.route("/api/config", methods=["GET", "POST"])
def handle_config():
    if request.method == "GET":
        return jsonify(load_config())
    config = request.get_json()
    existing = load_config()
    for key in ["scanDirectory", "fieldnames", "columnLabels", "columnTypes",
                "columnVisibility", "columnWidths", "columnOrder",
                "sortColumn", "sortDirection", "sortStack", "estimate"]:
        if key in config:
            existing[key] = config[key]
    if "scanDirectory" in config:
        if "deviceMonitor" not in existing:
            existing["deviceMonitor"] = {}
        existing["deviceMonitor"]["destinationBase"] = config["scanDirectory"]
    from config import CONFIG_PATH
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    return jsonify({"ok": True})


# ─────────────────────────────────────────────────────────────────
# Data
# ─────────────────────────────────────────────────────────────────

@bp.route("/api/data")
def get_data():
    """Return CSV rows with HMD size estimates attached."""
    rows = read_csv()
    _preview_skip = {"left.mp4", "right.mp4"}
    rows = [r for r in rows if os.path.basename(r.get("path", "")).lower() not in _preview_skip]

    def _norm(p):
        return os.path.normpath(p).replace("\\", "/").lower()
    seen = {}
    for r in rows:
        n = _norm(r.get("path", ""))
        if n in seen:
            existing_iso = seen[n].get("scan_date", "") or ""
            this_iso = r.get("scan_date", "") or ""
            if this_iso >= existing_iso:
                seen[n] = r
        else:
            seen[n] = r
    rows = list(seen.values())

    ratio, _src = _get_size_mb_per_min_from_service()
    for r in rows:
        if (r.get("file_type") or "") != "hmd":
            continue
        try:
            m = re.search(r"(\d+(?:\.\d+)?)\s*MB", r.get("extra_description", "") or "")
            if m:
                size_mb = float(m.group(1))
                r["_size_mb"] = size_mb
                r["_estimate_sec"] = int(round((size_mb / ratio) * 60))
        except Exception:
            pass
    return jsonify(rows)


# ─────────────────────────────────────────────────────────────────
# Scan
# ─────────────────────────────────────────────────────────────────

@bp.route("/api/scan", methods=["POST"])
def scan_directory():
    """Scan a directory for mp4/HMD/Data sessions and update video_manager.csv."""
    data = request.get_json()
    directory = data.get("directory", "").strip()
    if not directory or not os.path.isdir(directory):
        return jsonify({"error": "目录不存在"}), 400
    scope = data.get("scope", "current")

    # Path 规范化辅助：os.walk 在 Windows 上会返回混合分隔符（root 用 /、子目录用 \），
    # 这会让「mp4 已被新值更新」和「新 walk 出来的同路径旧 row」以两个 key 同时存在，
    # 最终 write_csv UPSERT 时第二个 row 覆盖第一个 —— 「同上翻车」根因之一。
    # 在所有 dict 索引/UPSERT 前先把 path 转成统一形式（用 utils.path_utils.canon_path：
    # 反斜杠→正斜杠 + normpath 折叠 + lower 大小写不敏感）。

    mp4_files = []
    hmd_folders = []
    data_folders = []
    for root, _dirs, files in os.walk(directory):
        has_parts = any(f.startswith("part_") and f.endswith(".hmd") for f in files)
        has_meta = "metadata.json" in files
        has_mcap = any(f.endswith(".mcap") for f in files)
        has_session_json = "session.json" in files

        if has_parts and has_meta:
            parts = sorted(glob.glob(os.path.join(root, "part_*.hmd")))
            if parts:
                total = sum(os.path.getsize(p) for p in parts)
                meta = None
                try:
                    with open(os.path.join(root, "metadata.json"), "r", encoding="utf-8") as f:
                        meta = json.load(f)
                except Exception:
                    pass

                dev = (meta.get("devices") or [{}])[0] if meta else {}
                dev_id_short = (dev.get("identity", {}).get("device_id", "") or "")[-6:] if dev else ""
                folder_name = os.path.basename(root)
                new_folder_name = folder_name
                if dev_id_short and not folder_name.startswith(dev_id_short + "_"):
                    from utils.path_utils import extract_mmdd_from_path as _extract_mmdd_from_path
                    from utils.path_utils import should_add_date_prefix as _should_add_date_prefix
                    from utils.path_utils import get_location_status as _get_location_status
                    mmdd = _extract_mmdd_from_path(root)
                    if mmdd and _should_add_date_prefix(root):
                        target_prefix = f"{mmdd}_{dev_id_short}_"
                        if folder_name.startswith(target_prefix):
                            pass
                        elif not folder_name.startswith(mmdd + "_"):
                            new_folder_name = f"{mmdd}_{dev_id_short}_{folder_name}"
                        else:
                            rest = folder_name[len(mmdd) + 1:]
                            new_folder_name = f"{mmdd}_{dev_id_short}_{rest}"
                    else:
                        new_folder_name = f"{dev_id_short}_{folder_name}"
                    if new_folder_name != folder_name:
                        new_root = os.path.join(os.path.dirname(root), new_folder_name)
                        if not os.path.exists(new_root):
                            try:
                                os.rename(root, new_root)
                                root = new_root
                            except Exception as e:
                                print(f"[HMD rename failed] {folder_name} → {new_folder_name}: {e}", file=sys.stderr)

                hmd_folders.append({
                    "folder": root,
                    "parts": [os.path.basename(p) for p in parts],
                    "total_size": total,
                    "metadata": meta,
                })
                _dirs[:] = []
                continue

        elif has_mcap and has_session_json:
            mcap_files = [f for f in files if f.endswith(".mcap")]
            total = sum(os.path.getsize(os.path.join(root, f)) for f in mcap_files)
            meta = None
            try:
                with open(os.path.join(root, "session.json"), "r", encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception:
                pass
            device_id = meta.get("device_id", "") if meta else ""
            device_short = device_id[-6:] if device_id else ""
            hmd_folders.append({
                "folder": root,
                "parts": mcap_files,
                "total_size": total,
                "metadata": meta,
                "format": "mcap",
                "device_short": device_short,
            })
            _dirs[:] = []
            continue

        is_hmd_dir = has_parts and has_meta
        is_data_dir = False
        session_json_path = os.path.join(root, "session.json")
        metadata_path = os.path.join(root, "metadata.json")
        has_session_json = os.path.isfile(session_json_path)
        has_data_meta = os.path.isfile(metadata_path) and not has_parts
        if has_session_json or has_data_meta:
            is_data_dir = True
            config_path = session_json_path if has_session_json else metadata_path
            dev_short = ""
            hostname = ""
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                dev = None
                if "devices" in meta:
                    dev = (meta.get("devices") or [{}])[0]
                elif "device" in meta:
                    dev = meta.get("device") or {}
                elif "device_id" in meta:
                    dev_id = meta.get("device_id", "") or ""
                    dev_short = dev_id[-6:] if dev_id else ""
                if dev:
                    dev_id = dev.get("identity", {}).get("device_id", "") or ""
                    if not dev_id and "device_id" in dev:
                        dev_id = dev.get("device_id", "") or ""
                    dev_short = dev_id[-6:] if dev_id else ""
                    hostname = dev.get("identity", {}).get("hostname", "") or ""
                    if not hostname and "hostname" in dev:
                        hostname = dev.get("hostname", "") or ""
            except Exception:
                pass
            data_folders.append({
                "folder": root,
                "files": [f for f in files if f not in ("session.json", "metadata.json")],
                "file_count": len([f for f in files if f not in ("session.json", "metadata.json")]),
                "total_size": sum(os.path.getsize(os.path.join(root, f)) for f in files
                                  if os.path.isfile(os.path.join(root, f)) and f not in ("session.json", "metadata.json")),
                "device_short": dev_short,
                "hostname": hostname,
            })
            _dirs[:] = []
            continue

        for fname in files:
            if not fname.lower().endswith(".mp4"):
                continue
            lower = fname.lower()
            if lower in ("left.mp4", "right.mp4"):
                continue
            if is_hmd_dir:
                continue
            mp4_files.append(os.path.join(root, fname))

    def _norm(p):
        return os.path.normpath(p).replace("\\", "/").lower()
    seen_norm = set()
    mp4_files = [p for p in mp4_files if not (_norm(p) in seen_norm or seen_norm.add(_norm(p)))]
    hmd_folders = [u for u in hmd_folders if not (_norm(u["folder"]) in seen_norm or seen_norm.add(_norm(u["folder"])))]
    data_folders = [d for d in data_folders if not (_norm(d["folder"]) in seen_norm or seen_norm.add(_norm(d["folder"])))]

    mp4_set = {_canon_local(p) for p in mp4_files}
    hmd_set = {_canon_local(u["folder"]) for u in hmd_folders}
    data_set = {_canon_local(d["folder"]) for d in data_folders}
    existing = read_csv()
    # 规范化已有 row 的 path key（防止 read_csv 返回的旧数据 / local CSV 缓存带 backslash）
    existing_map = {_canon_local(row["path"]): row for row in existing}

    canonical = {}
    for p, row in existing_map.items():
        n = _norm(p)
        if n in canonical:
            existing_iso = canonical[n].get("scan_date", "") or ""
            this_iso = row.get("scan_date", "") or ""
            if this_iso >= existing_iso:
                canonical[n] = row
        else:
            canonical[n] = row
    existing_map = canonical

    for path, row in existing_map.items():
        is_hmd_row = (row.get("file_type") or "") == "hmd"
        if path in hmd_set:
            row["location_status"] = _get_location_status(path, True)
        elif is_hmd_row and os.path.isdir(path) and (
            os.path.isfile(os.path.join(path, "metadata.json")) or
            os.path.isfile(os.path.join(path, "session.json"))
        ):
            row["location_status"] = _get_location_status(path, True)
        elif os.path.isfile(path):
            row["location_status"] = _get_location_status(path, True)
            if not row.get("duration_sec", "").strip():
                try:
                    sec = subprocess.run(
                        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                         "-of", "default=noprint_wrappers=1:nokey=1", path],
                        capture_output=True, encoding="utf-8", errors="replace", timeout=15,
                    )
                    row["duration_sec"] = str(int(round(float(sec.stdout.strip()))))
                except Exception:
                    pass
        else:
            row["location_status"] = _get_location_status(path, False)

    from utils.format_utils import get_file_date as _get_file_date
    from utils.format_utils import get_hmd_date as _get_hmd_date
    from utils.format_utils import parse_duration_to_sec as _parse_duration_to_sec
    from services.data_service import read_hmd_duration_from_status as _read_hmd_duration_from_status

    for mp4_path in sorted(mp4_files):
        mp4_key = _canon_local(mp4_path)
        if mp4_key not in existing_map:
            row = {fn: "" for fn in DEFAULT_FIELDNAMES}
            row["path"] = mp4_key
            row["location_status"] = _get_location_status(mp4_path, True)
            row["scan_date"] = datetime.datetime.now().strftime("%Y-%m-%d")
            row["original_history_date"] = _get_file_date(mp4_path)
            row["uploaded"] = "No"
            row["source_device"] = SOURCE_DEVICE
            try:
                sec_proc = subprocess.run(
                    ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", mp4_path],
                    capture_output=True, encoding="utf-8", errors="replace", timeout=15,
                )
                row["duration_sec"] = str(int(round(float(sec_proc.stdout.strip()))))
            except Exception:
                pass
            existing_map[mp4_key] = row

    for u in hmd_folders:
        u_key = _canon_local(u["folder"])
        if u_key not in existing_map:
            row = {fn: "" for fn in DEFAULT_FIELDNAMES}
            row["path"] = u_key
            row["location_status"] = _get_location_status(u["folder"], True)
            row["scan_date"] = datetime.datetime.now().strftime("%Y-%m-%d")
            row["original_history_date"] = _get_hmd_date(u["folder"], u.get("metadata"), directory)
            row["uploaded"] = "No"
            row["source_device"] = SOURCE_DEVICE
            duration_str = _read_hmd_duration_from_status(u["folder"])
            row["duration_sec"] = (
                str(int(round(_parse_duration_to_sec(duration_str)))) if duration_str else ""
            )
            format_label = "mcap" if u.get("format") == "mcap" else "part_*.hmd"
            row["extra_description"] = f"HMD session · {len(u['parts'])} parts · {u['total_size']/1024/1024:.0f} MB · {format_label}"
            row["file_type"] = "hmd"
            meta = u.get("metadata") or {}
            if u.get("format") == "mcap":
                dev_id = meta.get("device_id", "") if meta else ""
            else:
                dev = (meta.get("devices") or [{}])[0]
                dev_id = dev.get("identity", {}).get("device_id", "") or ""
            row["device_id"] = dev_id[-6:] if dev_id else ""
            existing_map[u_key] = row

    for d in data_folders:
        d_key = _canon_local(d["folder"])
        if d_key not in existing_map:
            row = {fn: "" for fn in DEFAULT_FIELDNAMES}
            row["path"] = d_key
            row["location_status"] = "local"
            row["scan_date"] = datetime.datetime.now().strftime("%Y-%m-%d")
            dir_name = os.path.basename(os.path.normpath(directory))
            data_date = ""
            if len(dir_name) == 4 and dir_name.isdigit():
                month = dir_name[:2]
                day = dir_name[2:]
                year = datetime.datetime.now().year
                data_date = f"{year}-{month}-{day}"
            else:
                try:
                    mtime = os.path.getmtime(d["folder"])
                    data_date = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
                except Exception:
                    data_date = datetime.datetime.now().strftime("%Y-%m-%d")
            row["original_history_date"] = data_date
            row["uploaded"] = "No"
            row["source_device"] = SOURCE_DEVICE
            row["file_type"] = "data"
            row["device_id"] = d.get("device_short", "")
            row["extra_description"] = f"Data session · {d['file_count']} files · {d['total_size']/1024/1024:.0f} MB"
            try:
                for f in d.get("files", []):
                    fp = os.path.join(d["folder"], f)
                    if f.lower().endswith((".mp4", ".mov", ".m4v")):
                        try:
                            sec = subprocess.run(
                                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                                 "-of", "default=noprint_wrappers=1:nokey=1", fp],
                                capture_output=True, encoding="utf-8", errors="replace", timeout=15,
                            )
                            if sec.stdout.strip():
                                row["duration_sec"] = str(int(round(float(sec.stdout.strip()))))
                                break
                        except Exception:
                            pass
            except Exception:
                pass
            existing_map[d_key] = row

    _auto_upsert_data_devices_to_sd_cards(data_folders)
    _auto_upsert_hmd_devices_to_sd_cards(hmd_folders)

    hmd_fast_pre = _get_hmd_fast_preprocess()
    if hmd_fast_pre:
        from utils.format_utils import get_hmd_date
        existing_paths_canon = {_canon_local(row["path"]) for row in existing}
        for u in hmd_folders:
            if _canon_local(u["folder"]) not in existing_paths_canon:
                try:
                    hmd_fast_pre.start_async(u["folder"])
                except Exception as e:
                    print(f"[hmd fast preprocess kick-off] {u['folder']}: {e}", file=sys.stderr)

    write_csv(list(existing_map.values()))

    return jsonify({
        "ok": True,
        "scanned": directory,
        "mp4_count": len(mp4_files),
        "hmd_count": len(hmd_folders),
        "data_count": len(data_folders),
        "total_rows": len(existing_map),
    })


# ─────────────────────────────────────────────────────────────────
# Save
# ─────────────────────────────────────────────────────────────────

@bp.route("/api/save", methods=["POST"])
def save_data():
    rows = request.get_json()
    if not isinstance(rows, list):
        return jsonify({"error": "Invalid data format", "type": str(type(rows))}), 400
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
    return jsonify({"ok": True, "count": len(cleaned), "protected": protected})


@bp.route("/api/save-rows", methods=["POST"])
def save_rows():
    """逐行合并保存：以 path 为主键匹配已有行，匹配到则更新，否则追加。"""
    body = request.get_json(silent=True) or {}
    rows_to_save = body.get("rows", [])
    if not isinstance(rows_to_save, list):
        return jsonify({"error": "rows must be a list"}), 400
    fieldnames = get_fieldnames()
    existing = read_csv()
    # 规范化所有 row 的 path key —— 防止 read_csv 返回的旧数据 / local CSV 缓存
    # 含 backslash/大小写差异形式，导致与 POST 进来的 normalized path 不匹配而漏更新
    # （_canon_local 已从 utils.path_utils 导入，行为：backslashes → forward slashes + normpath + lower）
    # 用 list-of-indices 而不是 dict（防御：CSV 里若有重复 path，dict 只会保留最后一个 index，
    # 导致只更新一行，另一行保留旧值被重新 UPSERT 到 PG —— 上游「同上」翻车的根因之一）
    path_to_indices: dict[str, list[int]] = {}
    for i, r in enumerate(existing):
        path_to_indices.setdefault(_canon_local(r.get("path", "")), []).append(i)
    updated = 0
    added = 0
    for row in rows_to_save:
        if not isinstance(row, dict):
            continue
        path = _canon_local(row.get("path", "").strip())
        if not path:
            continue
        cleaned_row = {fn: str(row.get(fn, "")).strip() for fn in fieldnames}
        # 同时把 row 内的 path 也规范化为 key 形式（保证 UPSERT 用同一形式）
        cleaned_row["path"] = path
        if path in path_to_indices:
            # 更新所有同 path 的行（CSV 有重复时也保证全部一致）
            for idx in path_to_indices[path]:
                # Merge: keep scan_date from existing if new is empty
                if not cleaned_row.get("scan_date") and existing[idx].get("scan_date"):
                    cleaned_row["scan_date"] = existing[idx]["scan_date"]
                existing[idx] = cleaned_row
                updated += 1
        else:
            existing.append(cleaned_row)
            path_to_indices[path] = [len(existing) - 1]
            added += 1
    write_csv(existing)
    return jsonify({"ok": True, "updated": updated, "added": added, "total": len(existing)})


# ─────────────────────────────────────────────────────────────────
# Merge history
# ─────────────────────────────────────────────────────────────────

@bp.route("/api/merge-history", methods=["POST"])
def merge_history():
    """Merge all historical CSV files into archive/video_manager_history.csv."""
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
                    full_row["location_status"] = "local" if os.path.isfile(path) else "history"
                    full_row["scan_date"] = hist_date
                    if full_row["location_status"] == "history":
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
    return jsonify({"ok": True, "merged_count": len(merged), "history_file": history_path})


# ─────────────────────────────────────────────────────────────────
# Delete
# ─────────────────────────────────────────────────────────────────

@bp.route("/api/delete", methods=["POST"])
def delete_records():
    """Delete uploaded records by indices. Optionally delete local files."""
    body = request.get_json()
    indices = body.get("indices", [])
    delete_files = body.get("deleteFiles", False)
    if not indices or not isinstance(indices, list):
        return jsonify({"error": "请提供要删除的行索引列表"}), 400
    rows = read_csv()
    blocked = []
    removed = []
    kept = []
    for i, row in enumerate(rows):
        if i in indices:
            vpath = row.get("path", "").strip()
            uploaded = row.get("uploaded", "").strip()
            ftype = row.get("file_type", "")
            if uploaded != "Yes":
                fname = os.path.basename(vpath) if vpath else f"行 {i}"
                blocked.append({"index": i, "path": vpath, "name": fname, "uploaded": uploaded})
                kept.append(row)
                continue
            removed.append({"index": i, "path": vpath, "file_type": ftype, "uploaded": uploaded})
        else:
            kept.append(row)
    if not removed:
        return jsonify({
            "error": "没有可删除的记录（所选视频均未上传，请先上传到 frameforge 后再删除）",
            "blocked": blocked, "blocked_count": len(blocked),
        }), 400
    write_csv(kept)
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
            except Exception as e:
                logger.error(f"[删除] 删除本地文件失败 {vpath}: {e}")
    cleaned_caches = 0
    cleaned_thumbs = 0
    for r in removed:
        vpath = r.get("path", "")
        ftype = r.get("file_type", "")
        if not vpath:
            continue
        if ftype == "hmd":
            try:
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
            thumb_path = os.path.join(THUMBNAILS_DIR, f"{key}.jpg")
            if os.path.isfile(thumb_path):
                os.unlink(thumb_path)
                cleaned_thumbs += 1
        except Exception:
            pass
    monitor_resumed = False
    if delete_files and deleted_files > 0:
        dm = _get_device_monitor()
        if dm:
            monitor_resumed = dm.resume_monitor()
    result = {
        "ok": True, "deleted": len(removed), "remaining": len(kept),
        "deleted_paths": [r["path"] for r in removed],
        "cleaned_caches": cleaned_caches, "cleaned_thumbs": cleaned_thumbs,
        "blocked": blocked, "blocked_count": len(blocked),
    }
    if delete_files:
        result["deleted_files"] = deleted_files
        result["deleted_size_mb"] = round(deleted_size_mb, 2)
        result["monitor_resumed"] = monitor_resumed
    return jsonify(result)