"""Main DeviceMonitor class and module-level singletons."""

import json
import logging
import logging.handlers
import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from config import RUNTIME_DIR, SRC_DIR
from utils.path_utils import get_location_status
from .scanner import DriveScannerMixin, _get_progress_window
from .copier import FileCopierMixin

# ── 日志配置：RotatingFileHandler + StreamHandler ──
_root = logging.getLogger()
if not _root.handlers:
    _fh = logging.handlers.RotatingFileHandler(
        os.path.join(RUNTIME_DIR, 'logs', 'device_monitor.log'),
        maxBytes=5 * 1024 * 1024,  # 5MB 滚动
        backupCount=3,
        encoding='utf-8',
    )
    _fh.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    ))
    _sh = logging.StreamHandler(sys.stderr)
    _sh.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S',
    ))
    _root.setLevel(logging.INFO)
    _root.addHandler(_fh)
    _root.addHandler(_sh)
logger = logging.getLogger(__name__)

if getattr(sys, 'frozen', False):
    _TOOLS_DIR = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "tools")
else:
    _TOOLS_DIR = os.path.join(SRC_DIR, "tools")

# 默认配置
DEFAULT_CONFIG = {
    # 设备监控总开关；config.json 的 deviceMonitor.enabled 优先于这里的默认值
    "enabled": True,
    "destination_base": r"/media",
    "exclude_drives": ["C", "D", "c", "d"],
    "video_patterns": ["DCIM", "MP_ROOT", "PRIVATE"],
    "subdir_patterns": ["DJI001", "DJI002", "DJI003", "100GOPRO", "GOPRO", ""],
    "scan_interval": 60,  # 扫描间隔（秒）
    "delete_after_copy": True,  # 复制后删除源文件
    "file_extensions": [".mp4", ".MP4", ".mov", ".MOV", ".m4v", ".M4V"],
    # HMD 设备搜索路径（SD卡上的 hmd 数据目录）
    "hmd_patterns": ["hmd"],
    # Data 设备搜索路径（SD卡上的 data 数据目录）
    "data_patterns": ["data"],
}



class DeviceMonitor(DriveScannerMixin, FileCopierMixin):
    """存储卡监控器"""

    def __init__(self, config=None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.running = False
        self.scanning = False
        self.thread = None
        self.lock = threading.Lock()
        # ── 磁盘空间保护 ──
        self._paused_for_space = False      # 因磁盘空间不足而暂停扫描/复制
        self._disk_space_ratio = 2.0        # 空间倍数阈值：可用空间需 ≥ SD卡内容 × N（预处理需要额外空间）
        self._last_required_bytes = 0       # 上次导致暂停的所需字节数，用于恢复判断
        self._paused_at = None              # 暂停时间戳
        self._last_space_warning = None     # 上次空间警告信息
        # 从 config.json 读取全局 scanDirectory 作为目标目录
        self._load_scan_directory()
        
    def _load_scan_directory(self):
        """从 config.json 读取全局 scanDirectory，更新 destination_base 以及 HMD 配置"""
        import json
        if getattr(sys, 'frozen', False):
            _base = os.path.dirname(os.path.abspath(sys.argv[0]))
            config_path = os.path.join(_base, "config.json")
        else:
            config_path = os.path.join(RUNTIME_DIR, "data", "config.json")
        try:
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                scan_dir = cfg.get("scanDirectory", "").strip()
                if scan_dir and os.path.isdir(scan_dir):
                    self.config["destination_base"] = scan_dir
                    logger.info(f"已加载扫描目录: {scan_dir}")
                # deviceMonitor sub-config.  The README documents more keys
                # here than the monitor used to read: only hmdPatterns and
                # dataPatterns were wired up, so everything else a user set
                # was silently ignored.  Map the documented camelCase keys
                # onto the internal snake_case config; absent keys keep the
                # built-in defaults.
                dm = cfg.get("deviceMonitor", {}) or {}
                for _cfg_key, _internal_key in (
                    ("excludeDrives", "exclude_drives"),
                    ("scanInterval", "scan_interval"),
                    ("videoPatterns", "video_patterns"),
                    ("subdirPatterns", "subdir_patterns"),
                ):
                    if _cfg_key in dm:
                        self.config[_internal_key] = dm[_cfg_key]
                if "deleteAfterCopy" in dm:
                    self.config["delete_after_copy"] = bool(dm["deleteAfterCopy"])
                if "destinationBase" in dm:
                    self.config["destination_base"] = dm["destinationBase"]
                if "enabled" in dm:
                    self.config["enabled"] = bool(dm["enabled"])

                # Load HMD patterns from deviceMonitor config
                hmd_patterns = dm.get("hmdPatterns", ["hmd"])
                if hmd_patterns:
                    self.config["hmd_patterns"] = hmd_patterns
                    logger.info(f"已加载 HMD 搜索模式: {hmd_patterns}")
                
                # Load data patterns from deviceMonitor config
                data_patterns = dm.get("dataPatterns", ["data"])
                if data_patterns:
                    self.config["data_patterns"] = data_patterns
                    logger.info(f"已加载 data 搜索模式: {data_patterns}")
        except Exception as e:
            logger.debug(f"加载扫描目录失败: {e}")

    def _find_mp4_files(self, directory):
        """递归查找目录中的视频文件"""
        mp4_files = []
        extensions = self.config.get("file_extensions", [".mp4", ".MP4"])
        
        try:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if any(file.lower().endswith(ext.lower()) for ext in extensions):
                        mp4_files.append(os.path.join(root, file))
        except PermissionError:
            # 设备不稳定或已断开
            logger.warning(f"无法访问目录（设备可能已断开）: {directory}")
        except Exception as e:
            logger.error(f"扫描目录 {directory} 失败: {e}")
        
        return mp4_files
    
    # ────────────────────────────────────────────────────────────────
    # 原始日期获取（修复：不再用 Windows ctime，它只是复制时间）
    # ────────────────────────────────────────────────────────────────
    
    def _get_mp4_original_date(self, filepath):
        """获取 MP4 文件的真实录制日期。
        
        优先级：
        1) ffprobe -show_entries format_tags=creation_time → 精确录制时间
        2) os.path.getmtime → 文件最后修改时间（shutil.copy2 保留了源文件的 mtime）
        3) os.path.getctime → 文件创建时间（Windows 上对复制的文件是复制时间，不准确）
        4) fallback → 今天
        """
        # 1) ffprobe creation_time tag
        try:
            proc = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries",
                 "format_tags=creation_time",
                 "-of", "default=noprint_wrappers=1:nokey=1", filepath],
                capture_output=True, text=True, timeout=10,
            )
            tag = proc.stdout.strip()
            if tag:
                # Format: "2026-06-15T18:04:22.000000Z" or "2026-06-15 18:04:22"
                from datetime import datetime as _dt
                for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
                    try:
                        # Strip trailing Z and fractional seconds
                        clean = tag.rstrip("Z").split(".")[0] if "T" in tag else tag
                        return _dt.strptime(clean, fmt).strftime("%Y-%m-%d")
                    except ValueError:
                        continue
                # ISO format parsing failed, try direct split
                date_part = tag.split("T")[0].split(" ")[0]
                if len(date_part) == 10 and date_part[4] == '-' and date_part[7] == '-':
                    return date_part
        except Exception as e:
            logger.debug(f"ffprobe creation_time 获取失败 {filepath}: {e}")
        
        # 2) mtime (preserved by copy2 from source SD card)
        try:
            mtime = os.path.getmtime(filepath)
            date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
            # Sanity: if mtime is before 2000, it's likely wrong (embedded device default)
            if datetime.fromtimestamp(mtime).year >= 2000:
                return date_str
        except Exception:
            pass
        
        # 3) ctime (fallback, may be copy-time on Windows)
        try:
            return datetime.fromtimestamp(os.path.getctime(filepath)).strftime("%Y-%m-%d")
        except Exception:
            return datetime.now().strftime("%Y-%m-%d")
    
    def _get_hmd_original_date(self, session_path, metadata=None, dest_dir=None):
        """获取 HMD session 的原始录制日期。
        
        HMD 嵌入式设备没有 RTC，文件时间戳全是 2021-01-01（Linux 默认 epoch），
        metadata.json 的 start_time 为空、start_time_unix 是单调时钟。
        因此优先级为：
        1) metadata.json start_time 字段（如果非空，ISO 格式）
        2) 目标目录名中隐含的日期（如 /media\\0615 → 2025-06-15）
        3) 目录 mtime（如果 >= 2000 年，可能是有意义的时间）
        4) fallback → 今天
        """
        # 1) metadata start_time (ISO datetime string)
        if metadata:
            start_time = metadata.get("start_time", "")
            if start_time and isinstance(start_time, str) and len(start_time) >= 10:
                date_part = start_time.split("T")[0].split(" ")[0]
                if len(date_part) == 10 and date_part[4] == '-' and date_part[7] == '-':
                    return date_part
        
        # 2) Directory name date (dest_dir like /media\0615 → MMDD format)
        if dest_dir:
            dir_name = os.path.basename(os.path.normpath(dest_dir))
            if len(dir_name) == 4 and dir_name.isdigit():
                month = dir_name[:2]
                day = dir_name[2:]
                year = datetime.now().year
                return f"{year}-{month}-{day}"
        
        # 3) Directory mtime (if meaningful)
        try:
            mtime = os.path.getmtime(session_path)
            dt = datetime.fromtimestamp(mtime)
            if dt.year >= 2020:  # Embedded device defaults to 2021-01-01, skip those
                return dt.strftime("%Y-%m-%d")
        except Exception:
            pass
        
        # 4) fallback
        return datetime.now().strftime("%Y-%m-%d")

    def _check_mp4_already_exists(self, src_path, dest_dir):
        """检查 MP4 文件是否已在目标目录下存在（同名同大小）。
        
        Returns: 已存在文件的完整路径，或 None
        """
        src_name = os.path.basename(src_path)
        src_size = 0
        try:
            src_size = os.path.getsize(src_path)
        except Exception:
            return None
        
        # 先检查目标目录中的同名文件
        dest_path = os.path.join(dest_dir, src_name)
        if os.path.isfile(dest_path):
            try:
                if os.path.getsize(dest_path) == src_size:
                    return dest_path
            except Exception:
                pass
        
        # 再搜索整个 destination_base 下的同名同大小文件
        dest_base = self.config.get("destination_base", "")
        if dest_base and os.path.isdir(dest_base):
            try:
                for entry in os.listdir(dest_base):
                    sub_dir = os.path.join(dest_base, entry)
                    if not os.path.isdir(sub_dir):
                        continue
                    candidate = os.path.join(sub_dir, src_name)
                    if os.path.isfile(candidate):
                        try:
                            if os.path.getsize(candidate) == src_size:
                                return candidate
                        except Exception:
                            continue
            except Exception:
                pass
        
        return None
    
    def _check_hmd_already_exists(self, session, dest_dir):
        """检查 HMD session 是否已在目标目录下存在（同设备ID同session名同part数）。
        
        Returns: 已存在 session 目录的完整路径，或 None
        """
        new_name = self._rename_session_with_device_prefix(
            session["session_name"], session["device_id_short"],
            dest_path=dest_dir,
        )
        hmd_dest = os.path.join(dest_dir, "hmd")
        
        # 先检查目标目录
        candidate = os.path.join(hmd_dest, new_name)
        if os.path.isdir(candidate):
            try:
                files_in = os.listdir(candidate)
                parts_in = sum(1 for f in files_in if f.startswith("part_") and f.endswith(".hmd"))
                if parts_in == session["parts_count"] and "metadata.json" in files_in:
                    return candidate
            except Exception:
                pass
        
        # 再搜索整个 destination_base 下的 hmd 目录
        dest_base = self.config.get("destination_base", "")
        if dest_base and os.path.isdir(dest_base):
            try:
                for entry in os.listdir(dest_base):
                    sub_hmd = os.path.join(dest_base, entry, "hmd")
                    if not os.path.isdir(sub_hmd):
                        continue
                    candidate = os.path.join(sub_hmd, new_name)
                    if os.path.isdir(candidate):
                        try:
                            files_in = os.listdir(candidate)
                            parts_in = sum(1 for f in files_in if f.startswith("part_") and f.endswith(".hmd"))
                            if parts_in == session["parts_count"] and "metadata.json" in files_in:
                                return candidate
                        except Exception:
                            continue
            except Exception:
                pass
        
        return None

    def _get_drive_volume_info(self, drive):
        """获取 Windows 驱动器的卷序列号和卷标。
        
        Returns: (volume_serial, volume_label) 如 ("1A2B-3C4D", "DJI_SD")
        """
        try:
            import ctypes
            # Get volume information
            volume_name_buf = ctypes.create_unicode_buffer(256)
            serial_buf = ctypes.c_ulong()
            max_component_len = ctypes.c_ulong()
            fs_flags = ctypes.c_ulong()
            fs_name_buf = ctypes.create_unicode_buffer(256)
            
            ctypes.windll.kernel32.GetVolumeInformationW(
                ctypes.c_wchar_p(drive),
                volume_name_buf,
                ctypes.sizeof(volume_name_buf) // 2,
                serial_buf,
                max_component_len,
                fs_flags,
                fs_name_buf,
                ctypes.sizeof(fs_name_buf) // 2,
            )
            
            serial = serial_buf.value
            # Format as XXXX-XXXX (Windows standard)
            serial_str = f"{(serial >> 16) & 0xFFFF:04X}-{serial & 0xFFFF:04X}"
            label = volume_name_buf.value or ""
            return serial_str, label
        except Exception as e:
            logger.debug(f"获取驱动器卷信息失败 {drive}: {e}")
            return "", ""
    
    def _auto_register_mp4_device(self, drive, source_path):
        """自动将单目设备的 SD 卡信息注册到 sd_cards.csv 维表。
        
        使用 Windows 卷序列号和卷标识别设备。
        """
        if getattr(sys, 'frozen', False):
            sd_cards_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "sd_cards.csv")
        else:
            sd_cards_path = os.path.join(RUNTIME_DIR, "data", "sd_cards.csv")
        
        volume_serial, volume_label = self._get_drive_volume_info(drive)
        if not volume_serial:
            logger.warning(f"无法获取 SD 卡卷序列号: {drive}")
            return
        
        # Infer device_name from source path pattern (DJI001 → DJI, 100GOPRO → GoPro)
        device_name = volume_label or ""
        src_dir = source_path.lower()
        if "dji" in src_dir:
            if not device_name:
                device_name = "DJI"
        elif "gopro" in src_dir or "100gopro" in src_dir:
            if not device_name:
                device_name = "GoPro"
        
        # Read existing sd_cards
        import csv
        existing_rows = []
        existing_keys = set()
        schema = ["volume_serial", "volume_label", "device_id", "device_name", "notes"]
        
        if os.path.exists(sd_cards_path):
            try:
                with open(sd_cards_path, "r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        existing_rows.append(row)
                        existing_keys.add(row.get("volume_serial", ""))
            except Exception:
                pass
        
        if volume_serial in existing_keys:
            return  # already registered
        
        new_row = {
            "volume_serial": volume_serial,
            "volume_label": volume_label,
            "device_id": volume_serial,
            "device_name": device_name or f"SD-{volume_serial}",
            "notes": f"auto-created from device monitor (monocular)",
        }
        existing_rows.append(new_row)
        
        # Atomic write
        tmp_path = sd_cards_path + ".tmp"
        try:
            with open(tmp_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=schema)
                writer.writeheader()
                writer.writerows(existing_rows)
            os.replace(tmp_path, sd_cards_path)
            logger.info(f"已注册单目设备到 sd_cards.csv: {volume_serial} ({device_name})")
        except Exception as e:
            logger.error(f"写入 sd_cards.csv 失败: {e}")
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
    
    def _start_hmd_preprocess(self, copied_sessions):
        """触发已复制 HMD session 的预处理（splitStereo + ffmpeg → left.mp4）。
        
        预处理完成后，下次扫描时 app.py 会自动更新 CSV 中的 duration_sec。
        """
        try:
            if _TOOLS_DIR not in sys.path:
                sys.path.insert(0, _TOOLS_DIR)
            import hmd_preprocess
            for session in copied_sessions:
                dest_path = session["dest_path"]
                try:
                    hmd_preprocess.start_async(dest_path)
                    logger.info(f"[双目] 已触发预处理: {dest_path}")
                except Exception as e:
                    logger.warning(f"[双目] 预处理启动失败 {dest_path}: {e}")
        except ImportError as e:
            logger.warning(f"[双目] hmd_preprocess 模块不可用: {e}")
    
    def get_destination_dir(self):
        """获取目标目录 /media\\mmdd"""
        today = datetime.now()
        mmdd = today.strftime("%m%d")  # 月日格式，如 0521
        dest_dir = os.path.join(self.config["destination_base"], mmdd)
        os.makedirs(dest_dir, exist_ok=True)
        return dest_dir
    
    def register_to_csv(self, dest_dir, copied_files):
        """
        将复制完成的视频注册到 video_manager.csv
        复用 app.py 的 CSV 格式
        **安全机制**：写入前自动备份，防止意外数据丢失
        """
        import csv
        import shutil
        
        if getattr(sys, 'frozen', False):
            csv_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "video_manager.csv")
        else:
            csv_path = os.path.join(RUNTIME_DIR, "data", "video_manager.csv")
        
        # 读取现有数据并保留原始字段名（不再硬编码，避免丢失新增字段如 duration）
        existing_map = {}
        fieldnames = []
        existing_count = 0
        read_ok = False
        if os.path.exists(csv_path):
            try:
                with open(csv_path, "r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    fieldnames = reader.fieldnames or []
                    for row in reader:
                        path = row.get("path", "").strip()
                        if path:
                            existing_map[path] = row
                    existing_count = len(existing_map)
                    read_ok = True
            except Exception as e:
                logger.error(f"读取 CSV 失败: {e}")
        
        # CRITICAL SAFEGUARD: if CSV existed but couldn't be read, DON'T overwrite it
        if os.path.exists(csv_path) and not read_ok:
            logger.error(f"CSV 读取失败，拒绝写入以防数据丢失！")
            return
        
        # Fallback: if CSV doesn't exist or has no headers, use DEFAULT_FIELDNAMES from app
        if not fieldnames:
            try:
                from app import DEFAULT_FIELDNAMES
                fieldnames = list(DEFAULT_FIELDNAMES)
            except Exception:
                fieldnames = [
                    "path", "location_status", "scan_date", "original_history_date",
                    "work_content_cn", "work_content_en", "category", "recorder",
                    "upload_feasibility", "uploaded", "extra_description", "score", "duration"
                ]
        
        # 更新已有文件状态
        new_count = 0
        for src_path in copied_files:
            # 计算目标路径
            src_name = os.path.basename(src_path)
            dest_path = os.path.join(dest_dir, src_name)
            
            # 处理可能的重命名
            counter = 1
            name, ext = os.path.splitext(src_name)
            while dest_path in existing_map:
                dest_path = os.path.join(dest_dir, f"{name}_{counter}{ext}")
                counter += 1
            
            dest_path = os.path.normpath(dest_path)
            
            if dest_path not in existing_map:
                # 获取真实录制日期（ffprobe creation_time > mtime > ctime）
                file_date = self._get_mp4_original_date(src_path)
                new_row = {fn: "" for fn in fieldnames}
                new_row["path"] = dest_path
                new_row["location_status"] = get_location_status(dest_path, True)
                new_row["scan_date"] = datetime.now().strftime("%Y-%m-%d")  # 录入日期 = 今天
                new_row["original_history_date"] = file_date                # 原始日期 = 真实录制时间
                new_row["uploaded"] = "No"
                existing_map[dest_path] = new_row
                new_count += 1
                logger.info(f"已注册到 CSV: {dest_path}")
        
        # 更新所有文件的状态（根据实际路径判断所属电脑）
        for path, row in existing_map.items():
            row["location_status"] = get_location_status(path, os.path.isfile(path))
        
        # 排序
        result = sorted(
            existing_map.values(),
            key=lambda r: (r.get("scan_date", ""), r.get("path", ""))
        )
        
        # SAFEGUARD: refuse to write if we'd lose more than 10% of records
        if existing_count > 0 and len(result) < existing_count * 0.9:
            logger.error(
                f"数据丢失检测：原 {existing_count} 条 → 新 {len(result)} 条，"
                f"超过 10% 阈值，拒绝写入！"
            )
            return
        
        # 写入前自动备份（仅保留最近 10 个备份）
        try:
            backup_dir = os.path.join(RUNTIME_DIR, "csv_backups")
            os.makedirs(backup_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backup_dir, f"video_manager_{ts}.csv")
            if os.path.exists(csv_path):
                shutil.copy2(csv_path, backup_path)
                # 清理旧备份，保留最近 10 个
                backups = sorted(os.listdir(backup_dir))
                while len(backups) > 10:
                    os.remove(os.path.join(backup_dir, backups[0]))
                    backups.pop(0)
        except Exception as e:
            logger.warning(f"备份 CSV 失败（将继续写入）: {e}")
        
        # 原子写入：先写临时文件，再 rename，防止崩溃/并发损坏
        tmp_path = csv_path + ".tmp"
        try:
            with open(tmp_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(result)
            os.replace(tmp_path, csv_path)  # 原子替换
            logger.info(f"CSV 已更新，新增 {new_count} 条记录，总计 {len(result)} 条")
        except Exception as e:
            logger.error(f"写入 CSV 失败: {e}")
            # 清理临时文件
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
    
    def register_hmd_to_csv(self, dest_dir, copied_sessions):
        """将复制的 HMD session 注册到 video_manager.csv。
        
        copied_sessions: list of dicts with keys:
            - dest_path: 目标 session 目录路径
            - device_id_short: 设备ID末6位
            - hostname: 设备主机名
            - metadata: metadata.json 内容
            - parts_count: .hmd 分片文件数
            - total_size: 总大小（bytes）
        """
        import csv
        
        if getattr(sys, 'frozen', False):
            csv_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "video_manager.csv")
        else:
            csv_path = os.path.join(RUNTIME_DIR, "data", "video_manager.csv")
        
        existing_map = {}
        fieldnames = []
        existing_count = 0
        read_ok = False
        if os.path.exists(csv_path):
            try:
                with open(csv_path, "r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    fieldnames = reader.fieldnames or []
                    for row in reader:
                        path = row.get("path", "").strip()
                        if path:
                            # Dedup: same path → keep latest row
                            if path not in existing_map:
                                existing_map[path] = row
                            else:
                                # Keep the one with more info
                                if len(str(row.get("device_id", ""))) > len(str(existing_map[path].get("device_id", ""))):
                                    existing_map[path] = row
                    existing_count = len(existing_map)
                    read_ok = True
            except Exception as e:
                logger.error(f"读取 CSV 失败: {e}")
        
        if os.path.exists(csv_path) and not read_ok:
            logger.error(f"CSV 读取失败，拒绝写入以防数据丢失！")
            return
        
        if not fieldnames:
            try:
                from app import DEFAULT_FIELDNAMES
                fieldnames = list(DEFAULT_FIELDNAMES)
            except Exception:
                fieldnames = [
                    "path", "location_status", "scan_date", "original_history_date",
                    "work_content_cn", "work_content_en", "category",
                    "upload_feasibility", "uploaded", "extra_description", "score",
                    "duration_sec", "file_type", "device_id", "recorder_id",
                    "task_id", "task_name",
                ]
        
        # Ensure HMD fields exist in fieldnames
        for fn in ["file_type", "device_id", "duration_sec", "recorder_id", "task_id", "task_name"]:
            if fn not in fieldnames:
                fieldnames.append(fn)
        
        new_count = 0
        for session in copied_sessions:
            dest_path = os.path.normpath(session["dest_path"])
            
            if dest_path not in existing_map:
                dev_short = session["device_id_short"]
                size_mb = session["total_size"] / (1024 * 1024)
                # 获取真实录制日期（metadata start_time > 目录名日期 > mtime > fallback）
                hmd_date = self._get_hmd_original_date(
                    session["source_path"], session.get("metadata"), dest_dir
                )
                new_row = {fn: "" for fn in fieldnames}
                new_row["path"] = dest_path
                new_row["location_status"] = get_location_status(dest_path, True)
                new_row["scan_date"] = datetime.now().strftime("%Y-%m-%d")
                new_row["original_history_date"] = hmd_date
                new_row["uploaded"] = "No"
                new_row["file_type"] = "hmd"
                new_row["device_id"] = dev_short
                new_row["extra_description"] = f"HMD session · {session['parts_count']} parts · {size_mb:.0f} MB · part_*.hmd"
                existing_map[dest_path] = new_row
                new_count += 1
                logger.info(f"已注册 HMD session 到 CSV: {dest_path}")
        
        # Update location status for all rows
        for path, row in existing_map.items():
            is_hmd = (row.get("file_type") or "") == "hmd"
            if is_hmd:
                if os.path.isdir(path) and os.path.isfile(os.path.join(path, "metadata.json")):
                    row["location_status"] = "local"
                else:
                    row["location_status"] = "history"
            else:
                if os.path.isfile(path):
                    row["location_status"] = "local"
                else:
                    row["location_status"] = "history"
        
        # Sort
        result = sorted(existing_map.values(),
                        key=lambda r: (r.get("scan_date", ""), r.get("path", "")))
        
        # Safeguard
        if existing_count > 0 and len(result) < existing_count * 0.9:
            logger.error(f"数据丢失检测：原 {existing_count} 条 → 新 {len(result)} 条，超过 10% 阈值，拒绝写入！")
            return
        
        # Backup before write
        try:
            backup_dir = os.path.join(RUNTIME_DIR, "csv_backups")
            os.makedirs(backup_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backup_dir, f"video_manager_{ts}.csv")
            if os.path.exists(csv_path):
                shutil.copy2(csv_path, backup_path)
                backups = sorted(os.listdir(backup_dir))
                while len(backups) > 10:
                    os.remove(os.path.join(backup_dir, backups[0]))
                    backups.pop(0)
        except Exception as e:
            logger.warning(f"备份 CSV 失败（将继续写入）: {e}")
        
        # Atomic write
        tmp_path = csv_path + ".tmp"
        try:
            with open(tmp_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(result)
            os.replace(tmp_path, csv_path)
            logger.info(f"CSV 已更新，新增 {new_count} 条 HMD 记录，总计 {len(result)} 条")
        except Exception as e:
            logger.error(f"写入 CSV 失败: {e}")
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
        
        # Auto-register HMD devices to sd_cards.csv
        self._auto_register_hmd_devices(copied_sessions)
    
    def _auto_register_hmd_devices(self, copied_sessions):
        """自动将新发现的 HMD 设备注册到 sd_cards.csv 维表。"""
        if getattr(sys, 'frozen', False):
            sd_cards_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "sd_cards.csv")
        else:
            sd_cards_path = os.path.join(RUNTIME_DIR, "data", "sd_cards.csv")
        
        # Read existing sd_cards
        existing_rows = []
        existing_keys = set()
        schema = ["volume_serial", "volume_label", "device_id", "device_name", "notes"]
        
        import csv
        if os.path.exists(sd_cards_path):
            try:
                with open(sd_cards_path, "r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        existing_rows.append(row)
                        existing_keys.add(row.get("volume_serial", ""))
            except Exception:
                pass
        
        # Add new devices
        added = False
        for session in copied_sessions:
            dev_short = session["device_id_short"]
            hostname = session["hostname"]
            if not dev_short or dev_short in existing_keys:
                continue
            new_row = {
                "volume_serial": dev_short,
                "volume_label": "",
                "device_id": dev_short,
                "device_name": hostname or f"HMD-{dev_short}",
                "notes": f"auto-created from device monitor",
            }
            existing_rows.append(new_row)
            existing_keys.add(dev_short)
            added = True
            logger.info(f"已注册 HMD 设备到 sd_cards.csv: {dev_short} ({hostname})")
        
        if added:
            # Atomic write
            tmp_path = sd_cards_path + ".tmp"
            try:
                with open(tmp_path, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.DictWriter(f, fieldnames=schema)
                    writer.writeheader()
                    writer.writerows(existing_rows)
                os.replace(tmp_path, sd_cards_path)
                logger.info(f"sd_cards.csv 已更新，新增 HMD 设备记录")
            except Exception as e:
                logger.error(f"写入 sd_cards.csv 失败: {e}")
                try:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                except Exception:
                    pass
    
    def _auto_register_data_devices(self, data_sources):
        """自动将新发现的 Data 设备注册到 sd_cards.csv 维表。
        
        Data 设备的信息来自 session.json 或 metadata.json 中的设备信息。
        如果设备ID不存在于 sd_cards.csv 中，则自动创建记录。
        这样视频管理界面的"设备编号"下拉框能自动显示这些设备。
        """
        import csv
        
        if getattr(sys, 'frozen', False):
            sd_cards_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "sd_cards.csv")
        else:
            sd_cards_path = os.path.join(RUNTIME_DIR, "data", "sd_cards.csv")
        
        # Read existing sd_cards
        existing_rows = []
        existing_device_ids = set()
        schema = ["volume_serial", "volume_label", "device_id", "device_name", "notes"]
        
        if os.path.exists(sd_cards_path):
            try:
                with open(sd_cards_path, "r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        existing_rows.append(row)
                        if row.get("device_id"):
                            existing_device_ids.add(row["device_id"])
            except Exception as e:
                logger.debug(f"读取 sd_cards.csv 失败: {e}")
        
        # Collect unique device IDs from data_sources
        added = False
        for data_source in data_sources:
            for session in data_source.get("sessions", []):
                dev_short = session.get("device_id_short", "")
                hostname = session.get("hostname", "")
                
                if not dev_short or dev_short in existing_device_ids:
                    continue
                
                # Use device_short as device_id, hostname as device_name
                device_id = dev_short
                device_name = hostname or f"Data-{dev_short}"
                
                # Ensure device_id is unique
                candidate_id = device_id
                suffix = 1
                while candidate_id in existing_device_ids:
                    suffix += 1
                    candidate_id = f"{device_id}_{suffix}"
                
                # For Data devices, use device_id as volume_serial (no real volume serial)
                new_row = {
                    "volume_serial": candidate_id,
                    "volume_label": "",
                    "device_id": candidate_id,
                    "device_name": device_name,
                    "notes": f"auto-created from data device scan (session: {session['session_name']})",
                }
                existing_rows.append(new_row)
                existing_device_ids.add(candidate_id)
                added = True
                logger.info(f"已注册 Data 设备到 sd_cards.csv: {candidate_id} ({device_name})")
        
        if added:
            # Atomic write
            tmp_path = sd_cards_path + ".tmp"
            try:
                with open(tmp_path, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.DictWriter(f, fieldnames=schema)
                    writer.writeheader()
                    writer.writerows(existing_rows)
                os.replace(tmp_path, sd_cards_path)
                logger.info(f"sd_cards.csv 已更新，新增 Data 设备记录")
            except Exception as e:
                logger.error(f"写入 sd_cards.csv 失败: {e}")
                try:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                except Exception:
                    pass

    def _check_disk_space(self, required_bytes):
        """检查目标磁盘是否有足够空间来存放新文件。
        
        考虑到预处理会产生中间文件，要求可用空间 ≥ SD卡内容 × 2。
        
        返回 (ok: bool, free_gb: float, needed_gb: float, required_x2_gb: float)
        - ok: 空间是否充足
        - free_gb: 当前可用空间（GB）
        - needed_gb: 本次需要的空间（GB）
        - required_x2_gb: 2倍所需空间（GB），即最低门槛
        """
        dest_base = self.config["destination_base"]
        try:
            usage = shutil.disk_usage(dest_base)
        except Exception as e:
            logger.error(f"无法获取磁盘空间信息: {e}")
            return True, 0, 0, 0  # 获取失败时放行，避免误拦
        
        free_bytes = usage.free
        free_gb = free_bytes / (1024 ** 3)
        needed_gb = required_bytes / (1024 ** 3) if required_bytes > 0 else 0
        required_x2_bytes = required_bytes * self._disk_space_ratio
        required_x2_gb = required_x2_bytes / (1024 ** 3)
        
        # 检查：可用空间 ≥ SD卡内容 × 2（预处理需要额外空间）
        ok = free_bytes >= required_x2_bytes
        return ok, free_gb, needed_gb, required_x2_gb
    
    def _enter_low_space_state(self, free_gb, needed_gb, required_bytes, required_x2_gb):
        """进入磁盘空间不足暂停状态，记录警告信息。"""
        self._paused_for_space = True
        self._paused_at = datetime.now()
        self._last_required_bytes = required_bytes  # 记住触发暂停的视频总量，用于恢复判断
        self._last_space_warning = {
            "free_gb": round(free_gb, 2),
            "needed_gb": round(needed_gb, 2),
            "required_x2_gb": round(required_x2_gb, 2),
            "paused_at": self._paused_at.isoformat(),
        }
        msg = (
            f"⚠ 磁盘空间不足，暂停扫描和复制！"
            f" 可用: {free_gb:.2f} GB，"
            f" 本次需要: {needed_gb:.2f} GB，"
            f" 预处理需 ×{self._disk_space_ratio:.0f} 倍空间，最低需要: {required_x2_gb:.2f} GB。"
            f" 请先上传视频到 frameforge，然后删除已上传的视频释放空间。"
        )
        logger.warning(msg)
    
    def is_paused_for_space(self):
        """返回是否因磁盘空间不足而暂停。"""
        return self._paused_for_space
    
    def get_disk_space_status(self):
        """返回完整的磁盘空间和暂停状态信息。"""
        dest_base = self.config["destination_base"]
        try:
            usage = shutil.disk_usage(dest_base)
            free_gb = usage.free / (1024 ** 3)
            total_gb = usage.total / (1024 ** 3)
            used_gb = usage.used / (1024 ** 3)
        except Exception:
            free_gb = -1
            total_gb = -1
            used_gb = -1
        
        return {
            "paused_for_space": self._paused_for_space,
            "free_gb": round(free_gb, 2),
            "total_gb": round(total_gb, 2),
            "used_gb": round(used_gb, 2),
            "disk_space_ratio": self._disk_space_ratio,
            "last_warning": self._last_space_warning,
            "paused_at": self._paused_at.isoformat() if self._paused_at else None,
            "monitor_running": self.is_running(),
            "monitor_scanning": self.is_scanning(),
        }
    
    def resume_check(self):
        """检查磁盘空间是否已恢复，若恢复则清除暂停状态，返回 True 表示已恢复。"""
        if not self._paused_for_space:
            return True  # 未暂停，无需恢复
        
        dest_base = self.config["destination_base"]
        try:
            usage = shutil.disk_usage(dest_base)
            free_gb = usage.free / (1024 ** 3)
        except Exception:
            return False  # 无法获取状态，保持暂停
        
        # 恢复条件：可用空间 ≥ 上次导致暂停的视频大小 × 倍数（预处理需要额外空间）
        if self._last_required_bytes <= 0:
            min_to_resume_gb = 10.0  # 兜底：至少需要 10 GB
        else:
            min_to_resume_gb = (self._last_required_bytes * self._disk_space_ratio) / (1024 ** 3)
        if free_gb >= min_to_resume_gb:
            self._paused_for_space = False
            self._paused_at = None
            self._last_space_warning = None
            self._last_required_bytes = 0
            logger.info(f"磁盘空间已恢复 ({free_gb:.1f} GB)，恢复扫描和复制")
            return True
        
        # 空间仍未恢复
        logger.debug(
            f"磁盘空间仍然不足: {free_gb:.1f} GB 可用，"
            f"需要 ≥ {min_to_resume_gb:.1f} GB 才能恢复"
        )
        return False

    def process_drive(self, drive):
        """处理一个驱动器：同时处理单目(MP4)和双目(HMD)设备数据"""
        if self.scanning:
            logger.debug(f"正在扫描中，跳过驱动器 {drive}")
            return
        
        # ── 检查是否因磁盘空间不足而暂停 ──
        if self._paused_for_space:
            # 尝试恢复
            if self.resume_check():
                logger.info(f"磁盘空间已恢复，继续处理驱动器 {drive}")
            else:
                logger.info(f"磁盘空间不足，跳过驱动器 {drive}（处于暂停状态）")
                return
        
        with self.lock:
            self.scanning = True
        
        try:
            logger.info(f"=== 开始扫描驱动器: {drive} ===")
            
            # ── 磁盘空间总预检：先扫描全部类型，累加总需求 ──
            all_mp4_sources = self.find_video_sources(drive)
            all_hmd_sources = self.find_hmd_sources(drive)
            all_data_sources = self.find_data_sources(drive)
            
            total_mp4_bytes = sum(s["total_size"] for s in all_mp4_sources)
            total_hmd_bytes = sum(s["total_size"] for s in all_hmd_sources)
            total_data_bytes = sum(s["total_size"] for s in all_data_sources)
            grand_total_bytes = total_mp4_bytes + total_hmd_bytes + total_data_bytes
            
            if grand_total_bytes > 0:
                ok, free_gb, needed_gb, required_x2_gb = self._check_disk_space(grand_total_bytes)
                if not ok:
                    self._enter_low_space_state(free_gb, needed_gb, grand_total_bytes, required_x2_gb)
                    logger.info(
                        f"驱动器 {drive} 跳过处理：磁盘空间不足 "
                        f"(可用 {free_gb:.2f} GB，需要 {required_x2_gb:.2f} GB（×{self._disk_space_ratio:.0f} 倍）)"
                    )
                    return
            
            # ── 单目设备 (MP4) ──
            sources = all_mp4_sources
            if sources:
                dest_dir = self.get_destination_dir()
                for source in sources:
                    source_path = source["path"]
                    source_files = source["files"]
                    total_files = len(source_files)
                    total_size = source["total_size"] / (1024 * 1024)
                    
                    logger.info(f"[单目] 开始处理: {source_path}, 文件数: {total_files}, 总大小: {total_size:.1f} MB")
                    
                    # 自动注册 SD 卡信息到 sd_cards.csv
                    self._auto_register_mp4_device(drive, source_path)
                    
                    copied, skipped, failed = self.copy_files(source_files, dest_dir, source_path)
                    
                    # copied: 新复制的文件; skipped: 已存在跳过的文件; failed: 复制失败的文件
                    all_handled = copied + skipped
                    if copied:
                        logger.info(f"[单目] 复制完成: 新增 {len(copied)}, 跳过(已存在) {len(skipped)}, 失败 {len(failed)}")
                        self.register_to_csv(dest_dir, copied)
                    
                    # 无论是新复制还是已存在，都要从 SD 卡删除源文件（防止重复存储）
                    if self.config.get("delete_after_copy", True) and all_handled:
                        deleted, del_failed = self.clear_source_directory(source_path, all_handled)
                        logger.info(f"[单目] 清理完成: 已删除 {len(deleted)}, 失败 {len(del_failed)}")
                    
                    if failed:
                        logger.warning(f"[单目] 部分文件复制失败: {len(failed)} 个")
            else:
                logger.info(f"驱动器 {drive} 未找到单目(MP4)视频源")
            
            # ── 双目设备 (HMD) ──
            hmd_sources = all_hmd_sources
            if hmd_sources:
                dest_dir = self.get_destination_dir()
                for hmd_source in hmd_sources:
                    total_sessions = len(hmd_source["sessions"])
                    total_size_mb = hmd_source["total_size"] / (1024 * 1024)
                    
                    logger.info(f"[双目] 开始处理 HMD: {hmd_source['path']}, session数: {total_sessions}, 总大小: {total_size_mb:.1f} MB")
                    
                    # 获取进度窗口
                    pw = _get_progress_window()
                    if pw:
                        pw["show"]()
                    
                    copied_sessions, failed_sessions = self.copy_hmd_sessions(
                        [hmd_source], dest_dir, drive
                    )
                    
                    if copied_sessions:
                        logger.info(f"[双目] HMD处理完成: {len(copied_sessions)}/{total_sessions} 个session")
                        self.register_hmd_to_csv(dest_dir, copied_sessions)
                        
                        # ── 自动触发 HMD 预处理 ──
                        # 只对本次新复制的 session 触发预处理（去重跳过的不再重复处理）
                        # DISABLED: 磁盘满时禁止自动预处理
                        # newly_copied = [s for s in copied_sessions if not s.get("skipped")]
                        # if newly_copied:
                        #     self._start_hmd_preprocess(newly_copied)
                        
                        if self.config.get("delete_after_copy", True):
                            # 删除已复制的源 session 目录
                            for session in copied_sessions:
                                try:
                                    shutil.rmtree(session["source_path"])
                                    logger.info(f"[双目] 已删除源 session: {session['source_path']}")
                                except Exception as e:
                                    logger.warning(f"[双目] 删除源 session 失败 {session['source_path']}: {e}")
                            # 清理空目录
                            try:
                                hmd_root = hmd_source["path"]
                                if os.path.isdir(hmd_root) and not os.listdir(hmd_root):
                                    os.rmdir(hmd_root)
                                    logger.info(f"[双目] 已删除空 HMD 根目录: {hmd_root}")
                            except Exception:
                                pass
                    
                    if failed_sessions:
                        logger.warning(f"[双目] 部分 HMD session 复制失败: {len(failed_sessions)} 个")
            else:
                logger.info(f"驱动器 {drive} 未找到双目(HMD)数据源")
            
            # ── 数据设备 (Data) ──
            data_sources = all_data_sources
            if data_sources:
                # 自动注册 Data 设备到 recorders.csv
                self._auto_register_data_devices(data_sources)
                
                dest_dir = self.get_destination_dir()
                for data_source in data_sources:
                    total_sessions = len(data_source["sessions"])
                    total_size_mb = data_source["total_size"] / (1024 * 1024)
                    
                    logger.info(f"[数据] 开始处理 data: {data_source['path']}, session数: {total_sessions}, 总大小: {total_size_mb:.1f} MB")
                    
                    # 获取进度窗口
                    pw = _get_progress_window()
                    if pw:
                        pw["show"]()
                    
                    copied_sessions, failed_sessions = self.copy_data_sessions(
                        [data_source], dest_dir, drive
                    )
                    
                    if copied_sessions:
                        logger.info(f"[数据] Data处理完成: {len(copied_sessions)}/{total_sessions} 个session")
                        self.register_data_to_csv(dest_dir, copied_sessions)
                        
                        if self.config.get("delete_after_copy", True):
                            # 删除已复制的源 session 目录
                            for session in copied_sessions:
                                try:
                                    shutil.rmtree(session["source_path"])
                                    logger.info(f"[数据] 已删除源 session: {session['source_path']}")
                                except Exception as e:
                                    logger.warning(f"[数据] 删除源 session 失败 {session['source_path']}: {e}")
                            # 清理空目录
                            try:
                                data_root = data_source["path"]
                                if os.path.isdir(data_root) and not os.listdir(data_root):
                                    os.rmdir(data_root)
                                    logger.info(f"[数据] 已删除空 data 根目录: {data_root}")
                            except Exception:
                                pass
                    
                    if failed_sessions:
                        logger.warning(f"[数据] 部分 data session 复制失败: {len(failed_sessions)} 个")
            else:
                logger.info(f"驱动器 {drive} 未找到数据(data)数据源")
                    
        except Exception as e:
            logger.error(f"处理驱动器 {drive} 时出错: {e}", exc_info=True)
        finally:
            with self.lock:
                self.scanning = False
    
    def scan_once(self):
        """执行一次扫描"""
        if self.scanning:
            logger.debug("上一次扫描尚未完成，跳过")
            return
        
        # ── 检查磁盘空间暂停状态 ──
        if self._paused_for_space:
            if self.resume_check():
                logger.info("磁盘空间已恢复，恢复扫描")
            else:
                logger.debug("磁盘空间不足，跳过扫描（处于暂停状态）")
                return
        
        drives = self.get_available_drives()
        
        if not drives:
            logger.debug("未检测到可用的外部驱动器")
            return
        
        logger.info(f"检测到 {len(drives)} 个可用驱动器: {drives}")
        
        for drive in drives:
            self.process_drive(drive)
    
    def _scan_loop(self):
        """扫描循环"""
        logger.info(f"设备监控已启动，扫描间隔: {self.config['scan_interval']} 秒")
        
        while self.running:
            try:
                # ── 定时检查磁盘空间恢复 ──
                if self._paused_for_space:
                    self.resume_check()  # 尝试恢复
                self.scan_once()
            except Exception as e:
                logger.error(f"扫描循环出错: {e}", exc_info=True)
            
            # 分段睡眠，以便能更快响应停止信号
            for _ in range(self.config["scan_interval"]):
                if not self.running:
                    break
                time.sleep(1)
        
        logger.info("设备监控已停止")
    
    def start(self):
        """启动监控线程"""
        if self.running:
            logger.warning("监控线程已在运行中")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._scan_loop, daemon=True)
        self.thread.start()
        logger.info("设备监控线程已启动")
    
    def stop(self):
        """停止监控线程"""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        logger.info("设备监控线程已停止")
    
    def is_running(self):
        """检查是否正在运行"""
        return self.running and self.thread and self.thread.is_alive()
    
    def is_scanning(self):
        """检查是否正在扫描"""
        return self.scanning
    
    def get_status(self):
        """获取当前状态"""
        status = {
            "running": self.is_running(),
            "scanning": self.is_scanning(),
            "paused_for_space": self._paused_for_space,
            "config": {
                "destination_base": self.config["destination_base"],
                "scan_interval": self.config["scan_interval"],
                "exclude_drives": self.config["exclude_drives"]
            }
        }
        # 附加磁盘空间信息
        if self._paused_for_space:
            status["disk_space"] = self.get_disk_space_status()
        return status


# 单例实例
_monitor = None


def get_monitor():
    """获取监控器单例"""
    global _monitor
    if _monitor is None:
        _monitor = DeviceMonitor()
    return _monitor


def start_monitor():
    """启动监控"""
    monitor = get_monitor()
    if not monitor.config.get("enabled", True):
        logger.info("设备监控已被 config.json 的 deviceMonitor.enabled 关闭")
        return monitor.get_status()
    if not monitor.is_running():
        monitor.start()
    return monitor.get_status()


def stop_monitor():
    """停止监控"""
    monitor = get_monitor()
    monitor.stop()
    return {"running": False}


def get_monitor_status():
    """获取监控状态"""
    return get_monitor().get_status()


def get_monitor_disk_space_status():
    """获取磁盘空间状态"""
    return get_monitor().get_disk_space_status()


def resume_monitor():
    """尝试从磁盘空间不足暂停状态恢复"""
    return get_monitor().resume_check()
