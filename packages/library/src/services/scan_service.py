"""
目录扫描服务。
处理递归目录扫描、HMD/Data session 检测、去重、设备自动注册等核心逻辑。
"""

import glob
import json
import os
import subprocess
import sys
from datetime import datetime

from config import (
    BASE_DIR, DEFAULT_FIELDNAMES, SESSION_MARKER,
    _DIM_REGISTRY, USE_PG, SOURCE_DEVICE,
)
if USE_PG:
    from models.pg_store import read_csv, write_csv
    from models.pg_dim import (
        read_dim_rows as _read_dim_rows,
        atomic_write_dim as _atomic_write_dim,
    )
else:
    from models.csv_store import read_csv, write_csv
    from models.dim_registry import (
        read_dim_rows as _read_dim_rows,
        atomic_write_dim as _atomic_write_dim,
    )
from utils.path_utils import (
    extract_mmdd_from_path, should_add_date_prefix, get_location_status,
)
from utils.format_utils import get_file_date as _get_file_date, get_hmd_date as _get_hmd_date
from utils.format_utils import parse_duration_to_sec as _parse_duration_to_sec

from .lazy_loader import (
    _get_hmd_preprocess, _get_hmd_fast_preprocess,
)
from .video import _thumb_cache_key
from .preprocess_service import init_preprocess_status_from_rows, auto_warm_all


# ────────────────────────────────────────────────────────────────
# 扫描核心算法
# ────────────────────────────────────────────────────────────────

def scan_directory(directory, scope="current"):
    """核心扫描算法：递归遍历目录，检测 MP4/HMD/Data session，构建 CSV 行。

    Returns: (result_rows, result_all, hmd_folders, data_folders)
    """
    mp4_files = []
    hmd_folders = []
    data_folders = []

    for root, _dirs, files in os.walk(directory):

        has_parts = any(f.startswith("part_") and f.endswith(".hmd") for f in files)
        has_meta = "metadata.json" in files
        has_mcap = any(f.endswith(".mcap") for f in files)
        has_session_json = "session.json" in files

        # HMD session: part_*.hmd + metadata.json
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
                # Auto-rename: add date prefix + device_id prefix
                dev = (meta.get("devices") or [{}])[0] if meta else {}
                dev_id_short = (dev.get("identity", {}).get("device_id", "") or "")[-6:] if dev else ""
                folder_name = os.path.basename(root)
                new_folder_name = ""
                if dev_id_short and not folder_name.startswith(dev_id_short + "_"):
                    mmdd = extract_mmdd_from_path(root)
                    if mmdd and should_add_date_prefix(root):
                        # 统一加时间前缀  →  mmdd_deviceIdShort_session_XXXXX
                        target_prefix = f"{mmdd}_{dev_id_short}_"
                        if folder_name.startswith(target_prefix):
                            # 已经是正确格式，跳过
                            pass
                        elif not folder_name.startswith(mmdd + "_"):
                            # 没有任何前缀 → 加 mmdd + deviceIdShort
                            new_folder_name = f"{mmdd}_{dev_id_short}_{folder_name}"
                        else:
                            # 有 mmdd 前缀但没有 deviceIdShort → 插入 deviceIdShort
                            rest = folder_name[len(mmdd) + 1:]
                            new_folder_name = f"{mmdd}_{dev_id_short}_{rest}"
                    else:
                        new_folder_name = f"{dev_id_short}_{folder_name}"
                if new_folder_name:
                    new_root = os.path.join(os.path.dirname(root), new_folder_name)
                    if not os.path.exists(new_root):
                        try:
                            os.rename(root, new_root)
                            root = new_root
                            print(f"[HMD rename] {folder_name} → {new_folder_name}", file=sys.stderr)
                        except Exception as e:
                            print(f"[HMD rename failed] {folder_name} → {new_folder_name}: {e}", file=sys.stderr)
                hmd_folders.append({
                    "folder": root, "parts": [os.path.basename(p) for p in parts],
                    "total_size": total, "metadata": meta,
                })
                _dirs[:] = []
                continue

        # .mcap format
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
                "folder": root, "parts": mcap_files, "total_size": total,
                "metadata": meta, "format": "mcap", "device_short": device_short,
            })
            _dirs[:] = []
            continue

        # Data session: session.json or metadata.json without HMD parts
        is_hmd_dir = has_parts and has_meta
        is_data_dir = False
        session_json_path = os.path.join(root, "session.json")
        metadata_path = os.path.join(root, "metadata.json")
        has_session_json_file = os.path.isfile(session_json_path)
        has_data_meta = os.path.isfile(metadata_path) and not has_parts
        if has_session_json_file or has_data_meta:
            is_data_dir = True
            config_path = session_json_path if has_session_json_file else metadata_path
            dev_short, hostname = _extract_data_device_info(config_path)
            data_folders.append({
                "folder": root,
                "files": [f for f in files if f not in ("session.json", "metadata.json")],
                "file_count": len([f for f in files if f not in ("session.json", "metadata.json")]),
                "total_size": sum(os.path.getsize(os.path.join(root, f)) for f in files
                                  if os.path.isfile(os.path.join(root, f))
                                  and f not in ("session.json", "metadata.json")),
                "device_short": dev_short, "hostname": hostname,
            })
            _dirs[:] = []
            continue

        # MP4 files — skip preview artifacts (left.mp4/right.mp4 etc.)
        # 旧命名：left.mp4, right.mp4; 新命名：{session_name}.mp4, {session_name}_right.mp4
        for fname in files:
            if not fname.lower().endswith(".mp4"):
                continue
            lower = fname.lower()
            if lower in ("left.mp4", "right.mp4"):
                continue
            # 跳过新命名的 session mp4 (位于 HMD 目录中)
            if is_hmd_dir:
                continue
            mp4_files.append(os.path.join(root, fname))

    # Deduplicate by normalized path
    def _norm(p):
        return os.path.normpath(p).replace("\\", "/").lower()

    seen_norm = set()
    mp4_files = [p for p in mp4_files if not (_norm(p) in seen_norm or seen_norm.add(_norm(p)))]
    hmd_folders = [u for u in hmd_folders
                   if not (_norm(u["folder"]) in seen_norm or seen_norm.add(_norm(u["folder"])))]
    data_folders = [d for d in data_folders
                    if not (_norm(d["folder"]) in seen_norm or seen_norm.add(_norm(d["folder"])))]

    mp4_set = set(mp4_files)
    hmd_set = {u["folder"] for u in hmd_folders}
    data_set = {d["folder"] for d in data_folders}
    existing = read_csv()
    existing_map = {row["path"]: row for row in existing}
    _existing_before_scan_set = set(existing_map.keys())

    # Canonical path dedup in existing rows
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
    _existing_before_scan_set = set(existing_map.keys())

    # Update existing rows: check location_status, fill duration
    for path, row in existing_map.items():
        is_hmd_row = (row.get("file_type") or "") == "hmd"
        if path in hmd_set:
            row["location_status"] = get_location_status(path, True)
        elif is_hmd_row and os.path.isdir(path) and (
            os.path.isfile(os.path.join(path, "metadata.json"))
            or os.path.isfile(os.path.join(path, "session.json"))
        ):
            row["location_status"] = get_location_status(path, True)
        elif os.path.isfile(path):
            row["location_status"] = get_location_status(path, True)
            if not row.get("duration_sec", "").strip():
                try:
                    sec = subprocess.run(
                        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                         "-of", "default=noprint_wrappers=1:nokey=1", path],
                        capture_output=True, text=True, timeout=15,
                    )
                    row["duration_sec"] = str(int(round(float(sec.stdout.strip()))))
                except Exception:
                    pass
        else:
            row["location_status"] = get_location_status(path, False)

    # Add new MP4s
    for mp4_path in sorted(mp4_files):
        if mp4_path not in existing_map:
            row = {fn: "" for fn in DEFAULT_FIELDNAMES}
            row["path"] = mp4_path
            row["location_status"] = get_location_status(mp4_path, True)
            row["scan_date"] = datetime.now().strftime("%Y-%m-%d")
            row["original_history_date"] = _get_file_date(mp4_path)
            row["uploaded"] = "No"
            row["source_device"] = SOURCE_DEVICE
            try:
                sec_proc = subprocess.run(
                    ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", mp4_path],
                    capture_output=True, text=True, timeout=15,
                )
                row["duration_sec"] = str(int(round(float(sec_proc.stdout.strip()))))
            except Exception:
                pass
            existing_map[mp4_path] = row

    # Add new HMD folders
    for u in hmd_folders:
        if u["folder"] not in existing_map:
            row = {fn: "" for fn in DEFAULT_FIELDNAMES}
            row["path"] = u["folder"]
            row["location_status"] = get_location_status(u["folder"], True)
            row["scan_date"] = datetime.now().strftime("%Y-%m-%d")
            row["original_history_date"] = _get_hmd_date(u["folder"], u.get("metadata"), directory)
            row["uploaded"] = "No"
            row["source_device"] = SOURCE_DEVICE
            from .data_service import read_hmd_duration_from_status
            duration_str = read_hmd_duration_from_status(u["folder"])
            row["duration_sec"] = (
                str(int(round(_parse_duration_to_sec(duration_str)))) if duration_str else ""
            )
            format_label = "mcap" if u.get("format") == "mcap" else "part_*.hmd"
            row["extra_description"] = (
                f"HMD session · {len(u['parts'])} parts · "
                f"{u['total_size']/1024/1024:.0f} MB · {format_label}"
            )
            row["file_type"] = "hmd"
            meta = u.get("metadata") or {}
            dev_id = ""
            if u.get("format") == "mcap":
                dev_id = meta.get("device_id", "") if meta else ""
            else:
                dev = (meta.get("devices") or [{}])[0]
                dev_id = dev.get("identity", {}).get("device_id", "") or ""
            row["device_id"] = dev_id[-6:] if dev_id else ""
            existing_map[u["folder"]] = row

    # Add new Data folders
    for d in data_folders:
        if d["folder"] not in existing_map:
            row = {fn: "" for fn in DEFAULT_FIELDNAMES}
            row["path"] = d["folder"]
            row["location_status"] = get_location_status(d["folder"], True)
            row["scan_date"] = datetime.now().strftime("%Y-%m-%d")
            dir_name = os.path.basename(os.path.normpath(directory))
            if len(dir_name) == 4 and dir_name.isdigit():
                month, day = dir_name[:2], dir_name[2:]
                data_date = f"{datetime.now().year}-{month}-{day}"
            else:
                try:
                    mtime = os.path.getmtime(d["folder"])
                    data_date = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
                except Exception:
                    data_date = datetime.now().strftime("%Y-%m-%d")
            row["original_history_date"] = data_date
            row["uploaded"] = "No"
            row["source_device"] = SOURCE_DEVICE
            row["file_type"] = "data"
            row["device_id"] = d.get("device_short", "")
            row["extra_description"] = (
                f"Data session · {d['file_count']} files · {d['total_size']/1024/1024:.0f} MB"
            )
            try:
                for f in d.get("files", []):
                    fp = os.path.join(d["folder"], f)
                    if f.lower().endswith((".mp4", ".mov", ".m4v")):
                        try:
                            sec = subprocess.run(
                                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                                 "-of", "default=noprint_wrappers=1:nokey=1", fp],
                                capture_output=True, text=True, timeout=15,
                            )
                            if sec.stdout.strip():
                                row["duration_sec"] = str(int(round(float(sec.stdout.strip()))))
                                break
                        except Exception:
                            pass
            except Exception:
                pass
            existing_map[d["folder"]] = row

    # Auto-create sd_cards dimension records
    auto_upsert_data_devices_to_sd_cards(data_folders)
    auto_upsert_hmd_devices_to_sd_cards(hmd_folders)

    # Kick off background preprocessing for new HMD folders
    # DISABLED: 磁盘满时禁止自动预处理
    # hmd_fast_pre = _get_hmd_fast_preprocess()
    # if hmd_fast_pre:
    #     for u in hmd_folders:
    #         if u["folder"] not in _existing_before_scan_set:
    #             try:
    #                 hmd_fast_pre.start_async(u["folder"])
    #             except Exception as e:
    #                 print(f"[hmd fast preprocess kick-off] {u['folder']}: {e}", file=sys.stderr)
    #         else:
    from .data_service import read_hmd_duration_from_status
    for u in hmd_folders:
        if u["folder"] in _existing_before_scan_set:
            status_dur = read_hmd_duration_from_status(u["folder"])
            if status_dur:
                existing_row = existing_map.get(u["folder"])
                cur_dur = (existing_row.get("duration_sec") or "").strip() if existing_row else ""
                if existing_row and not cur_dur:
                    existing_row["duration_sec"] = str(
                        int(round(_parse_duration_to_sec(status_dur)))
                    )

    # Dedup & sort
    _dedup_map = {}
    for row in existing_map.values():
        nk = os.path.normpath(row.get("path", "")).replace("\\", "/").lower()
        if nk not in _dedup_map:
            _dedup_map[nk] = row
        else:
            old = _dedup_map[nk]
            old_filled = sum(1 for v in old.values() if v and v.strip())
            new_filled = sum(1 for v in row.values() if v and v.strip())
            if new_filled > old_filled:
                _dedup_map[nk] = row
    result_all = sorted(_dedup_map.values(), key=lambda r: (r.get("scan_date", ""), r.get("path", "")))

    # Init preprocess status
    init_preprocess_status_from_rows(list(existing_map.values()))

    # Scope filter on response only
    if scope == "current":
        dir_norm = os.path.normpath(directory).lower()
        today = datetime.now().strftime("%Y-%m-%d")
        result = [r for r in result_all
                  if os.path.normpath(r.get("path", "")).lower().startswith(dir_norm)
                  or r.get("scan_date") == today]
    else:
        result = result_all

    # Persist
    write_csv(result_all)

    # Auto-warm
    # DISABLED: 磁盘满时禁止自动预处理
    # auto_warm_all(result_all)

    return result, result_all, hmd_folders, data_folders


def _extract_data_device_info(config_path):
    """从 Data session 配置文件中提取 device_short 和 hostname。"""
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
    return dev_short, hostname


# ────────────────────────────────────────────────────────────────
# HMD/Data session 扫描辅助函数
# ────────────────────────────────────────────────────────────────

def scan_hmd_sessions(directory):
    """列出目录下包含 metadata.json 的子目录（HMD session）。"""
    sessions = []
    try:
        entries = sorted(os.listdir(directory))
    except Exception as e:
        return sessions, str(e)

    for entry in entries:
        full = os.path.join(directory, entry)
        meta_path = os.path.join(full, SESSION_MARKER)
        if not (os.path.isdir(full) and os.path.isfile(meta_path)):
            continue
        record = {
            "path": full, "name": entry, "parts": [], "size_bytes": 0,
            "device_id": "", "device_short": "", "hostname": "", "cameras": [], "error": None,
        }
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            parts = sorted(glob.glob(os.path.join(full, "part_*.hmd")))
            record["parts"] = [os.path.basename(p) for p in parts]
            record["size_bytes"] = sum(os.path.getsize(p) for p in parts)
            dev = (meta.get("devices") or [{}])[0]
            dev_id = dev.get("identity", {}).get("device_id", "") or ""
            record["device_id"] = dev_id
            record["device_short"] = dev_id[-6:] if dev_id else ""
            record["hostname"] = dev.get("identity", {}).get("hostname", "") or ""
            record["cameras"] = dev.get("config", {}).get("cameras", []) or []
        except Exception as e:
            record["error"] = str(e)
        sessions.append(record)
    return sessions, None


def scan_data_sessions(directory):
    """列出目录下包含 session.json 或 metadata.json 的 Data session 子目录。"""
    sessions = []
    try:
        entries = sorted(os.listdir(directory))
    except Exception as e:
        return sessions, str(e)

    for entry in entries:
        full = os.path.join(directory, entry)
        if not os.path.isdir(full):
            continue
        has_session_json = os.path.isfile(os.path.join(full, "session.json"))
        has_meta = os.path.isfile(os.path.join(full, "metadata.json"))
        if not (has_session_json or has_meta):
            continue
        config_path = os.path.join(full, "session.json" if has_session_json else "metadata.json")
        dev_short, hostname = _extract_data_device_info(config_path)
        files = [f for f in os.listdir(full)
                 if os.path.isfile(os.path.join(full, f))
                 and f not in ("session.json", "metadata.json")]
        total_size = sum(os.path.getsize(os.path.join(full, f)) for f in files)
        sessions.append({
            "path": full, "name": entry,
            "file_count": len(files), "size_bytes": total_size,
            "device_id": "", "device_short": dev_short, "hostname": hostname,
            "error": None,
        })
    return sessions, None


# ────────────────────────────────────────────────────────────────
# 设备自动注册到 sd_cards 维表
# ────────────────────────────────────────────────────────────────

def auto_upsert_hmd_devices_to_sd_cards(hmd_folders):
    """为未注册 HMD 设备自动创建 sd_cards 维表记录。"""
    if not hmd_folders:
        return
    spec = _DIM_REGISTRY["sd_cards"]
    abs_path = os.path.join(BASE_DIR, spec["path"])
    schema = spec["schema"]
    key_col = spec["key"]
    rows = _read_dim_rows(abs_path, schema, key_col, spec.get("create_if_missing", False))
    existing_keys = {r[key_col] for r in rows}

    added = False
    for u in hmd_folders:
        meta = u.get("metadata") or {}
        dev = (meta.get("devices") or [{}])[0]
        identity = dev.get("identity", {}) or {}
        full_dev_id = identity.get("device_id", "") or ""
        hostname = identity.get("hostname", "") or ""
        dev_short = full_dev_id[-6:] if full_dev_id else ""
        if not dev_short:
            continue
        vol_serial = dev_short
        if vol_serial in existing_keys:
            continue
        new_row = {
            "volume_serial": vol_serial, "volume_label": "",
            "device_id": dev_short, "device_name": hostname or f"HMD-{dev_short}",
            "notes": f"auto-created from scan ({u['folder']})",
        }
        rows.append(new_row)
        existing_keys.add(vol_serial)
        added = True

    if added:
        _atomic_write_dim("sd_cards", abs_path, rows, schema)


def auto_upsert_data_devices_to_sd_cards(data_folders):
    """为未注册 Data 设备自动创建 sd_cards 维表记录。"""
    if not data_folders:
        return
    spec = _DIM_REGISTRY["sd_cards"]
    abs_path = os.path.join(BASE_DIR, spec["path"])
    schema = spec["schema"]
    key_col = spec["key"]
    rows = _read_dim_rows(abs_path, schema, key_col, spec.get("create_if_missing", False))
    existing_keys = {r[key_col] for r in rows}

    added = False
    for d in data_folders:
        dev_short = d.get("device_short", "")
        hostname = d.get("hostname", "")
        if not dev_short:
            continue
        candidate_id = dev_short
        if candidate_id in existing_keys:
            continue
        suffix = 1
        while candidate_id in existing_keys:
            suffix += 1
            candidate_id = f"{dev_short}_{suffix}"
        new_row = {
            "volume_serial": candidate_id, "volume_label": "",
            "device_id": candidate_id, "device_name": hostname or f"Data-{dev_short}",
            "notes": f"auto-created from data scan ({d['folder']})",
        }
        rows.append(new_row)
        existing_keys.add(candidate_id)
        added = True

    if added:
        _atomic_write_dim("sd_cards", abs_path, rows, schema)
