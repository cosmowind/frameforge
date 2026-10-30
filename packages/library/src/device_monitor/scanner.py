"""Drive discovery and source scanning mixin."""

import json
import logging
import os

logger = logging.getLogger(__name__)

_progress_window = None

def _get_progress_window():
    """获取进度窗口（延迟导入）"""
    global _progress_window
    if _progress_window is None:
        try:
            from copy_progress_window import show_copy_progress, update_copy_progress, complete_copy_progress, close_copy_progress, get_progress_manager
            _progress_window = {
                "show": show_copy_progress,
                "update": update_copy_progress,
                "complete": complete_copy_progress,
                "close": close_copy_progress,
                "device_disconnected": get_progress_manager().device_disconnected
            }
        except Exception as e:
            logger.warning(f"无法加载进度窗口: {e}")
            return None
    return _progress_window


class DriveScannerMixin:
    """Mixin for drive discovery and source scanning."""

    def get_available_drives(self):
        """获取可用的非系统盘"""
        drives = []
        exclude = self.config["exclude_drives"]
        
        # Windows 下获取所有盘符
        for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            drive = f"{letter}:\\"
            if os.path.exists(drive) and letter.upper() not in exclude:
                try:
                    # 检查是否为可移动媒体或网络驱动器
                    if self._is_removable_or_external(drive):
                        drives.append(drive)
                except:
                    pass
        return drives
    
    def _is_removable_or_external(self, drive):
        """检查是否为可移动或外部驱动器"""
        try:
            import ctypes
            
            # 获取驱动器类型
            drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive)
            
            # DRIVE_REMOVABLE = 2, DRIVE_FIXED = 3, DRIVE_REMOTE = 4
            # 可移动媒体(2)或网络驱动器(4)认为是外部设备
            if drive_type in [2, 4]:
                return True
            
            # 额外检查：如果不是固定硬盘（C/D通常是固定盘）
            # 如果驱动器类型是固定盘但不是C或D，也可能是外部硬盘
            if drive_type == 3:
                return True
                
        except Exception as e:
            logger.debug(f"检查驱动器 {drive} 类型失败: {e}")
        
        return False
    
    def find_video_sources(self, drive):
        """在驱动器中查找视频源目录"""
        sources = []
        
        for pattern in self.config["video_patterns"]:
            for subpattern in self.config["subdir_patterns"]:
                if subpattern:
                    path = os.path.join(drive, pattern, subpattern)
                else:
                    path = os.path.join(drive, pattern)
                
                try:
                    if not (os.path.exists(path) and os.path.isdir(path)):
                        continue
                except Exception:
                    continue
                
                mp4_files = self._find_mp4_files(path)
                if not mp4_files:
                    continue
                
                # 计算总大小（容错处理）
                total_size = 0
                for f in mp4_files:
                    try:
                        total_size += os.path.getsize(f)
                    except PermissionError:
                        logger.warning(f"无法获取文件大小（设备可能已断开）: {drive}")
                        return []  # 设备不稳定，放弃该驱动器
                    except Exception as e:
                        logger.debug(f"获取文件大小失败 {f}: {e}")
                
                sources.append({
                    "path": path,
                    "files": mp4_files,
                    "total_size": total_size
                })
                logger.info(f"找到视频源: {path}, 文件数: {len(mp4_files)}")
        
        return sources
    
    # ────────────────────────────────────────────────────────────────
    # HMD 双目设备扫描与复制
    # ────────────────────────────────────────────────────────────────
    
    def find_hmd_sources(self, drive):
        """在驱动器中查找 HMD 双目设备的 session 数据。
        
        HMD 设备的 SD 卡数据结构：
          <drive>/hmd/session_00000/part_*.hmd + metadata.json
          <drive>/hmd/session_00001/...
        
        也可能出现在其他目录下（如 /mnt/sdcard/hmd 已挂载到根目录），
        所以扫描 drive 下所有包含 hmd 子目录的路径。
        """
        hmd_sources = []  # list of dicts: {path, sessions, total_size}
        
        for pattern in self.config.get("hmd_patterns", ["hmd"]):
            # 直接在 drive 根目录下找 hmd 目录
            hmd_root = os.path.join(drive, pattern)
            if not os.path.isdir(hmd_root):
                continue
            
            sessions = []
            try:
                for entry in os.listdir(hmd_root):
                    session_path = os.path.join(hmd_root, entry)
                    if not os.path.isdir(session_path):
                        continue
                    # 验证是 HMD session: 包含 metadata.json + part_*.hmd
                    try:
                        files_in_session = os.listdir(session_path)
                    except Exception:
                        continue
                    has_parts = any(f.startswith("part_") and f.endswith(".hmd") for f in files_in_session)
                    has_meta = "metadata.json" in files_in_session
                    if not (has_parts and has_meta):
                        continue
                    
                    # 读取 metadata.json 获取设备信息
                    metadata = None
                    device_id_short = ""
                    hostname = ""
                    try:
                        with open(os.path.join(session_path, "metadata.json"), "r", encoding="utf-8") as f:
                            metadata = json.load(f)
                        dev = (metadata.get("devices") or [{}])[0]
                        full_dev_id = dev.get("identity", {}).get("device_id", "") or ""
                        device_id_short = full_dev_id[-6:] if full_dev_id else ""
                        hostname = dev.get("identity", {}).get("hostname", "") or ""
                    except Exception as e:
                        logger.warning(f"读取 metadata.json 失败: {session_path}: {e}")
                    
                    # 计算总大小
                    total_size = 0
                    for fname in files_in_session:
                        if fname.startswith("part_") and fname.endswith(".hmd"):
                            try:
                                total_size += os.path.getsize(os.path.join(session_path, fname))
                            except Exception:
                                pass
                    
                    sessions.append({
                        "source_path": session_path,
                        "session_name": entry,  # e.g. "session_00000"
                        "device_id_short": device_id_short,
                        "hostname": hostname,
                        "metadata": metadata,
                        "total_size": total_size,
                        "parts_count": sum(1 for f in files_in_session if f.startswith("part_") and f.endswith(".hmd")),
                    })
            except PermissionError:
                logger.warning(f"无法访问 HMD 目录（设备可能已断开）: {drive}")
                return []
            except Exception as e:
                logger.error(f"扫描 HMD 目录失败 {hmd_root}: {e}")
                continue
            
            if sessions:
                total_all = sum(s["total_size"] for s in sessions)
                hmd_sources.append({
                    "path": hmd_root,
                    "sessions": sessions,
                    "total_size": total_all,
                })
                logger.info(f"找到 HMD 数据源: {hmd_root}, session 数: {len(sessions)}, 总大小: {total_all/1024/1024:.1f} MB")
        
        return hmd_sources
    
    # ────────────────────────────────────────────────────────────────
    # Data 设备扫描与复制
    # ────────────────────────────────────────────────────────────────
    
    def find_data_sources(self, drive):
        """在驱动器中查找 data 目录下的 session 数据。
        
        Data 设备的 SD 卡数据结构：
          <drive>/data/session_00000/video files + metadata.json
          <drive>/data/session_00001/...
        
        类似 HMD 的处理方式，但 data 目录下的文件可能是视频文件。
        """
        data_sources = []  # list of dicts: {path, sessions, total_size}
        
        # 获取驱动器卷序列号，作为设备ID的后备方案
        volume_serial, volume_label = self._get_drive_volume_info(drive)
        fallback_device_id = volume_serial[-6:] if volume_serial else "unknown"
        
        for pattern in self.config.get("data_patterns", ["data"]):
            # 直接在 drive 根目录下找 data 目录
            data_root = os.path.join(drive, pattern)
            if not os.path.isdir(data_root):
                continue
            
            sessions = []
            try:
                for entry in os.listdir(data_root):
                    session_path = os.path.join(data_root, entry)
                    if not os.path.isdir(session_path):
                        continue
                    
                    # 读取 session.json 或 metadata.json 获取设备信息（如果存在）
                    metadata = None
                    device_id_short = ""
                    hostname = ""
                    session_json_path = os.path.join(session_path, "session.json")
                    metadata_path = os.path.join(session_path, "metadata.json")
                    
                    # 优先读取 session.json，如果不存在则尝试 metadata.json
                    config_file_path = session_json_path if os.path.isfile(session_json_path) else metadata_path
                    
                    if os.path.isfile(config_file_path):
                        try:
                            with open(config_file_path, "r", encoding="utf-8") as f:
                                metadata = json.load(f)
                            
                            # 尝试多种可能的设备ID字段路径
                            dev = None
                            if "devices" in metadata:
                                dev = (metadata.get("devices") or [{}])[0]
                            elif "device" in metadata:
                                dev = metadata.get("device") or {}
                            elif "device_id" in metadata:
                                # 直接包含 device_id 字段
                                full_dev_id = metadata.get("device_id", "") or ""
                                device_id_short = full_dev_id[-6:] if full_dev_id else ""
                            
                            if dev:
                                full_dev_id = dev.get("identity", {}).get("device_id", "") or ""
                                if not full_dev_id and "device_id" in dev:
                                    full_dev_id = dev.get("device_id", "") or ""
                                device_id_short = full_dev_id[-6:] if full_dev_id else ""
                                hostname = dev.get("identity", {}).get("hostname", "") or ""
                                if not hostname and "hostname" in dev:
                                    hostname = dev.get("hostname", "") or ""
                                    
                        except Exception as e:
                            logger.debug(f"读取 {os.path.basename(config_file_path)} 失败: {session_path}: {e}")
                    
                    # 如果 metadata.json 中没有设备ID，使用卷序列号作为后备
                    if not device_id_short:
                        device_id_short = fallback_device_id
                        logger.info(f"使用卷序列号作为设备ID: {device_id_short} (session: {entry})")
                    
                    # 计算总大小（扫描 session 目录下的所有文件）
                    total_size = 0
                    file_count = 0
                    try:
                        for root, dirs, files in os.walk(session_path):
                            for f in files:
                                try:
                                    total_size += os.path.getsize(os.path.join(root, f))
                                    file_count += 1
                                except Exception:
                                    pass
                    except Exception:
                        continue
                    
                    if file_count == 0:
                        continue  # 空目录，跳过
                    
                    sessions.append({
                        "source_path": session_path,
                        "session_name": entry,  # e.g. "session_00000"
                        "device_id_short": device_id_short,
                        "hostname": hostname,
                        "metadata": metadata,
                        "total_size": total_size,
                        "file_count": file_count,
                    })
            except PermissionError:
                logger.warning(f"无法访问 data 目录（设备可能已断开）: {drive}")
                return []
            except Exception as e:
                logger.error(f"扫描 data 目录失败 {data_root}: {e}")
                continue
            
            if sessions:
                total_all = sum(s["total_size"] for s in sessions)
                data_sources.append({
                    "path": data_root,
                    "sessions": sessions,
                    "total_size": total_all,
                })
                logger.info(f"找到 data 数据源: {data_root}, session 数: {len(sessions)}, 总大小: {total_all/1024/1024:.1f} MB")
        
        return data_sources
