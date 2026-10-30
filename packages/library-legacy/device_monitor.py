"""
存储卡自动导入模块
- 扫描非系统盘（排除C/D盘）的可移动存储设备
- 从 DCIM/DJI001 等目录复制 mp4 文件
- 复制完成后清空源目录
- 每分钟自动扫描一次
"""

import os
import shutil
import sys
import time
import threading
import logging
from datetime import datetime
from pathlib import Path

# 延迟导入进度窗口，避免 tkinter 在非 GUI 环境下报错
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

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('device_monitor.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 默认配置
DEFAULT_CONFIG = {
    "destination_base": r"/media",
    "exclude_drives": ["C", "D", "c", "d"],
    "video_patterns": ["DCIM", "MP_ROOT", "PRIVATE"],
    "subdir_patterns": ["DJI001", "DJI002", "DJI003", "100GOPRO", "GOPRO", ""],
    "scan_interval": 60,  # 扫描间隔（秒）
    "delete_after_copy": True,  # 复制后删除源文件
    "file_extensions": [".mp4", ".MP4", ".mov", ".MOV", ".m4v", ".M4V"]
}


class DeviceMonitor:
    """存储卡监控器"""
    
    def __init__(self, config=None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.running = False
        self.scanning = False
        self.thread = None
        self.lock = threading.Lock()
        # 从 config.json 读取全局 scanDirectory 作为目标目录
        self._load_scan_directory()
        
    def _load_scan_directory(self):
        """从 config.json 读取全局 scanDirectory，更新 destination_base"""
        import json
        if getattr(sys, 'frozen', False):
            _base = os.path.dirname(os.path.abspath(sys.argv[0]))
        else:
            _base = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(_base, "config.json")
        try:
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                scan_dir = cfg.get("scanDirectory", "").strip()
                if scan_dir and os.path.isdir(scan_dir):
                    self.config["destination_base"] = scan_dir
                    logger.info(f"已加载扫描目录: {scan_dir}")
        except Exception as e:
            logger.debug(f"加载扫描目录失败: {e}")

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
            _base = os.path.dirname(os.path.abspath(sys.argv[0]))
        else:
            _base = os.path.dirname(os.path.abspath(__file__))
        csv_path = os.path.join(_base, "video_manager.csv")
        
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
                # Use source file's creation date as scan_date
                try:
                    ctime = os.path.getctime(src_path)
                    file_date = datetime.fromtimestamp(ctime).strftime("%Y-%m-%d")
                except Exception:
                    file_date = datetime.now().strftime("%Y-%m-%d")
                new_row = {fn: "" for fn in fieldnames}
                new_row["path"] = dest_path
                new_row["location_status"] = "local"
                new_row["scan_date"] = file_date
                new_row["uploaded"] = "No"
                existing_map[dest_path] = new_row
                new_count += 1
                logger.info(f"已注册到 CSV: {dest_path}")
        
        # 更新所有文件的状态
        for path, row in existing_map.items():
            if os.path.isfile(path):
                row["location_status"] = "local"
            else:
                row["location_status"] = "history"
        
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
            backup_dir = os.path.join(os.path.dirname(csv_path), "csv_backups")
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
    
    def copy_files(self, source_files, dest_dir, source_root):
        """复制文件到目标目录（失败时自动清理残留文件）"""
        copied = []
        failed = []
        total = len(source_files)
        source_drive = os.path.splitdrive(source_root)[0] + "\\"
        
        # 获取进度窗口
        pw = _get_progress_window()
        if pw:
            pw["show"]()
        
        for i, src in enumerate(source_files, 1):
            dest = None  # 用于记录目标路径（失败时清理）
            
            # 检查源驱动器是否仍然存在（设备是否断开）
            if not os.path.exists(source_drive):
                logger.warning(f"设备已断开: {source_drive}")
                if pw:
                    pw["complete"](False, f"设备已断开！已复制 {len(copied)}/{total} 个文件")
                return copied, failed
            
            try:
                filename = os.path.basename(src)
                dest = os.path.join(dest_dir, filename)
                
                # 处理文件名冲突
                counter = 1
                while os.path.exists(dest):
                    name, ext = os.path.splitext(filename)
                    filename = f"{name}_{counter}{ext}"
                    dest = os.path.join(dest_dir, filename)
                    counter += 1
                
                # 复制文件
                shutil.copy2(src, dest)
                
                # 验证复制完整性（比较文件大小）
                src_size = os.path.getsize(src)
                dest_size = os.path.getsize(dest)
                if src_size != dest_size:
                    raise IOError(f"文件大小不一致: 源={src_size}, 目标={dest_size}")
                
                copied.append(src)
                size_mb = dest_size / (1024 * 1024)
                logger.info(f"已复制: {filename} ({size_mb:.1f} MB)")
                
                # 更新进度窗口
                if pw:
                    pw["update"](i, total, filename)
                
            except PermissionError as e:
                logger.error(f"权限不足，复制失败 {src}: {e}")
                failed.append(src)
                # 清理残留的目标文件
                if dest and os.path.exists(dest):
                    try:
                        os.remove(dest)
                        logger.info(f"已清理残留文件: {dest}")
                    except:
                        pass
                if pw:
                    pw["update"](i, total, os.path.basename(src))
                    
            except Exception as e:
                logger.error(f"复制失败 {src}: {e}")
                failed.append(src)
                # 清理残留的目标文件（不完整或损坏的文件）
                if dest and os.path.exists(dest):
                    try:
                        os.remove(dest)
                        logger.info(f"已清理残留文件: {dest}")
                    except Exception as ce:
                        logger.debug(f"清理残留文件失败: {ce}")
                if pw:
                    pw["update"](i, total, os.path.basename(src))
        
        # 完成进度
        if pw:
            if failed:
                pw["complete"](False, f"成功 {len(copied)}/{total} 个文件")
            else:
                pw["complete"](True, f"已复制 {len(copied)} 个文件到 {dest_dir}")
        
        return copied, failed
    
    def _notify_device_disconnected(self, drive):
        """通知设备已断开"""
        pw = _get_progress_window()
        if pw:
            try:
                pw["device_disconnected"]()
            except:
                pass
    
    def clear_source_directory(self, source_path, source_files):
        """清空源目录（复制成功后），同时清理同名 .lrf，但保留 .jpg 照片文件"""
        deleted = []
        failed = []
        
        # 确保所有文件都已成功复制
        confirmed_copied = set(source_files)
        
        # 1. 删除已复制的 mp4 文件，同时删除同名 .lrf
        for src in confirmed_copied:
            # 删 mp4
            try:
                os.remove(src)
                deleted.append(src)
                logger.info(f"已删除源文件: {src}")
            except Exception as e:
                logger.error(f"删除失败 {src}: {e}")
                failed.append(src)
                continue
            
            # 删同名 .lrf 文件（DJI 低分辨率代理文件）
            lrf_path = os.path.splitext(src)[0] + ".LRF"
            if os.path.isfile(lrf_path):
                try:
                    os.remove(lrf_path)
                    deleted.append(lrf_path)
                    logger.info(f"已删除同名 LRF: {lrf_path}")
                except Exception as e:
                    logger.error(f"删除 LRF 失败 {lrf_path}: {e}")
        
        # 2. 清理与已复制视频同名的 .lrf 文件（即使视频不在列表中也尝试清理）
        lrf_cleaned = 0
        try:
            video_exts = {".mp4", ".mov", ".m4v", ".MP4", ".MOV", ".M4V"}
            for root, dirs, files in os.walk(source_path):
                for f in files:
                    name, ext = os.path.splitext(f)
                    if ext.lower() == ".lrf":
                        # 检查是否有同名视频文件存在（可能未被扫描到）
                        lrf_path = os.path.join(root, f)
                        has_video = any(
                            os.path.isfile(os.path.join(root, name + vext))
                            for vext in video_exts
                        )
                        if not has_video:
                            # 孤立的 LRF 文件（视频已被删除），清理掉
                            try:
                                os.remove(lrf_path)
                                lrf_cleaned += 1
                                logger.debug(f"已删除孤立 LRF: {lrf_path}")
                            except Exception as e:
                                logger.error(f"删除 LRF 失败 {lrf_path}: {e}")
            if lrf_cleaned > 0:
                logger.info(f"已删除 {lrf_cleaned} 个孤立 LRF 文件")
        except Exception as e:
            logger.error(f"扫描清理 LRF 失败: {e}")
        
        # 注意：不再删除 .jpg/.jpeg 照片文件，保留用户照片数据
        
        # 3. 尝试删除空目录
        self._cleanup_empty_dirs(source_path)
        
        return deleted, failed
    
    def _cleanup_empty_dirs(self, directory):
        """递归清理空目录"""
        try:
            # 先清理子目录
            for item in os.listdir(directory):
                item_path = os.path.join(directory, item)
                if os.path.isdir(item_path):
                    self._cleanup_empty_dirs(item_path)
            
            # 再尝试删除当前目录（如果为空）
            if os.path.exists(directory) and os.path.isdir(directory):
                if not os.listdir(directory):
                    os.rmdir(directory)
                    logger.info(f"已删除空目录: {directory}")
        except Exception as e:
            logger.debug(f"删除目录失败 {directory}: {e}")
    
    def process_drive(self, drive):
        """处理一个驱动器"""
        if self.scanning:
            logger.debug(f"正在扫描中，跳过驱动器 {drive}")
            return
        
        with self.lock:
            self.scanning = True
        
        try:
            logger.info(f"=== 开始扫描驱动器: {drive} ===")
            sources = self.find_video_sources(drive)
            
            if not sources:
                logger.info(f"驱动器 {drive} 未找到视频源")
                return
            
            dest_dir = self.get_destination_dir()
            today_str = datetime.now().strftime("%m%d")
            
            for source in sources:
                source_path = source["path"]
                source_files = source["files"]
                total_files = len(source_files)
                total_size = source["total_size"] / (1024 * 1024)
                
                logger.info(f"开始处理: {source_path}")
                logger.info(f"文件数量: {total_files}, 总大小: {total_size:.1f} MB")
                
                # 复制文件
                copied, failed = self.copy_files(source_files, dest_dir, source_path)
                
                if copied:
                    logger.info(f"复制完成: 成功 {len(copied)}/{total_files}")
                    
                    # 自动注册到 video_manager.csv
                    self.register_to_csv(dest_dir, source_files)
                    
                    # 删除源文件
                    if self.config.get("delete_after_copy", True):
                        deleted, del_failed = self.clear_source_directory(source_path, copied)
                        logger.info(f"清理完成: 已删除 {len(deleted)}, 失败 {len(del_failed)}")
                
                if failed:
                    logger.warning(f"部分文件复制失败: {len(failed)} 个")
                    
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
        return {
            "running": self.is_running(),
            "scanning": self.is_scanning(),
            "config": {
                "destination_base": self.config["destination_base"],
                "scan_interval": self.config["scan_interval"],
                "exclude_drives": self.config["exclude_drives"]
            }
        }


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


if __name__ == "__main__":
    # 测试模式
    print("设备监控测试模式")
    print("=" * 50)
    
    monitor = DeviceMonitor()
    
    # 显示当前配置
    print(f"\n当前配置:")
    print(f"  目标目录: {monitor.config['destination_base']}")
    print(f"  排除盘符: {monitor.config['exclude_drives']}")
    print(f"  扫描间隔: {monitor.config['scan_interval']} 秒")
    
    # 显示可用驱动器
    print(f"\n可用驱动器:")
    drives = monitor.get_available_drives()
    if drives:
        for d in drives:
            print(f"  {d}")
    else:
        print("  未检测到外部驱动器")
    
    # 立即执行一次扫描
    print("\n执行一次扫描...")
    monitor.scan_once()
