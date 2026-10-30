"""Copy operations and file operations mixin."""

import csv
import logging
import os
import shutil
import sys
from datetime import datetime

from config import RUNTIME_DIR
from utils.path_utils import extract_mmdd_from_path, should_add_date_prefix, get_location_status

from .scanner import _get_progress_window

logger = logging.getLogger(__name__)


class FileCopierMixin:
    """Mixin for copy and file operations."""

    def copy_data_sessions(self, data_sources, dest_dir, drive):
        """复制 data session 文件夹到目标目录，自动添加设备ID前缀重命名。
        
        目标结构：
          /media/0615/data/<device_id>_session_00000/video files + metadata.json
          /media/0615/data/<device_id>_session_00001/...
        
        同一设备的所有 sessions 放在同一个 data 子目录下。
        不同设备的 sessions 通过 device_id 前缀区分。
        """
        pw = _get_progress_window()
        copied_sessions = []  # list of dicts for CSV registration
        failed_sessions = []
        
        for source in data_sources:
            sessions = source["sessions"]
            total_sessions = len(sessions)
            
            # 按设备ID分组
            device_groups = {}
            for s in sessions:
                dev_id = s["device_id_short"] or "unknown"
                if dev_id not in device_groups:
                    device_groups[dev_id] = []
                device_groups[dev_id].append(s)
            
            for dev_id, dev_sessions in device_groups.items():
                # 目标子目录: /media\0615\data
                data_dest = os.path.join(dest_dir, "data")
                os.makedirs(data_dest, exist_ok=True)
                
                for idx, session in enumerate(dev_sessions):
                    # 检查源驱动器是否仍然存在
                    source_drive = os.path.splitdrive(session["source_path"])[0] + "\\"
                    if not os.path.exists(source_drive):
                        logger.warning(f"设备已断开: {source_drive}")
                        if pw:
                            pw["complete"](False, f"设备已断开！已复制 {len(copied_sessions)}/{total_sessions} 个session")
                        return copied_sessions, failed_sessions
                    
                    # 计算目标 session 名（带设备ID + 时间前缀）
                    new_name = self._rename_session_with_device_prefix(
                        session["session_name"], session["device_id_short"],
                        dest_path=data_dest,
                    )
                    target_session_dir = os.path.join(data_dest, new_name)
                    
                    # 处理目标目录名冲突
                    counter = 1
                    while os.path.exists(target_session_dir):
                        target_session_dir = os.path.join(data_dest, f"{new_name}_{counter}")
                        counter += 1
                    
                    try:
                        # 复制整个 session 目录
                        shutil.copytree(session["source_path"], target_session_dir)
                        
                        copied_sessions.append({
                            "source_path": session["source_path"],
                            "dest_path": target_session_dir,
                            "device_id_short": session["device_id_short"],
                            "hostname": session["hostname"],
                            "metadata": session["metadata"],
                            "file_count": session["file_count"],
                            "total_size": session["total_size"],
                        })
                        size_mb = session["total_size"] / (1024 * 1024)
                        logger.info(f"已复制 data session: {new_name} ({size_mb:.1f} MB, {session['file_count']} files)")
                        
                        if pw:
                            pw["update"](idx + 1, total_sessions, new_name)
                            
                    except PermissionError as e:
                        logger.error(f"权限不足，复制 data session 失败 {session['source_path']}: {e}")
                        failed_sessions.append(session["source_path"])
                        if os.path.exists(target_session_dir):
                            try:
                                shutil.rmtree(target_session_dir)
                            except Exception:
                                pass
                        if pw:
                            pw["update"](idx + 1, total_sessions, session["session_name"])
                            
                    except Exception as e:
                        logger.error(f"复制 data session 失败 {session['source_path']}: {e}")
                        failed_sessions.append(session["source_path"])
                        if os.path.exists(target_session_dir):
                            try:
                                shutil.rmtree(target_session_dir)
                                logger.info(f"已清理残留目录: {target_session_dir}")
                            except Exception as ce:
                                logger.debug(f"清理残留目录失败: {ce}")
                        if pw:
                            pw["update"](idx + 1, total_sessions, session["session_name"])
        
        # 完成进度
        if pw:
            if failed_sessions:
                pw["complete"](False, f"Data: 成功 {len(copied_sessions)}/{total_sessions} 个session")
            else:
                pw["complete"](True, f"Data: 已复制 {len(copied_sessions)} 个session到 {dest_dir}")
        
        return copied_sessions, failed_sessions
    
    def register_data_to_csv(self, dest_dir, copied_sessions):
        """将复制的 data session 注册到 video_manager.csv。"""
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
                            if path not in existing_map:
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
                    "uploaded", "extra_description", "score",
                    "duration_sec", "file_type", "device_id", "recorder_id",
                    "task_id", "env_id",
                ]
        
        # Ensure data fields exist in fieldnames
        for fn in ["file_type", "device_id", "duration_sec", "recorder_id", "task_id", "env_id"]:
            if fn not in fieldnames:
                fieldnames.append(fn)
        
        new_count = 0
        for session in copied_sessions:
            dest_path = os.path.normpath(session["dest_path"])
            
            if dest_path not in existing_map:
                dev_short = session["device_id_short"]
                size_mb = session["total_size"] / (1024 * 1024)
                # 获取真实录制日期
                data_date = self._get_hmd_original_date(
                    session["source_path"], session.get("metadata"), dest_dir
                )
                new_row = {fn: "" for fn in fieldnames}
                new_row["path"] = dest_path
                new_row["location_status"] = get_location_status(dest_path, True)
                new_row["scan_date"] = datetime.now().strftime("%Y-%m-%d")
                new_row["original_history_date"] = data_date
                new_row["uploaded"] = "No"
                new_row["file_type"] = "data"
                new_row["device_id"] = dev_short
                new_row["extra_description"] = f"Data session · {session['file_count']} files · {size_mb:.0f} MB"
                existing_map[dest_path] = new_row
                new_count += 1
                logger.info(f"已注册 data session 到 CSV: {dest_path}")
        
        # Update location status for all rows
        for path, row in existing_map.items():
            is_data = (row.get("file_type") or "") == "data"
            exists = os.path.isdir(path) if is_data else os.path.isfile(path)
            row["location_status"] = get_location_status(path, exists)
        
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
            logger.info(f"CSV 已更新，新增 {new_count} 条 data 记录，总计 {len(result)} 条")
        except Exception as e:
            logger.error(f"写入 CSV 失败: {e}")
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
    
    def _rename_session_with_device_prefix(self, session_name, device_id_short, dest_path=None):
        """将裸 session 名添加设备ID前缀。
        
        e.g. "session_00000" → "0625_4aa45c_session_00000"（统一加时间前缀）
        
        如果 session 名已经包含正确前缀，则不再重复添加。
        
        Args:
            session_name: 原始 session 名
            device_id_short: 设备ID末尾6位
            dest_path: 目标路径（用于提取日期判断是否加时间前缀）
        """
        if not device_id_short:
            return session_name
        # 构建前缀名（统一加时间前缀）
        prefix = device_id_short
        if dest_path and should_add_date_prefix(dest_path):
            mmdd = extract_mmdd_from_path(dest_path)
            if mmdd:
                target_prefix = f"{mmdd}_{device_id_short}_"
                if session_name.startswith(target_prefix):
                    # 已经是正确格式，跳过
                    return session_name
                if not session_name.startswith(mmdd + "_"):
                    prefix = f"{mmdd}_{device_id_short}"
                else:
                    # 有 mmdd 前缀但没有 deviceIdShort → 插入 deviceIdShort
                    rest = session_name[len(mmdd) + 1:]
                    return f"{mmdd}_{device_id_short}_{rest}"
        # 如果已有前缀，不重复添加
        if session_name.startswith(prefix + "_"):
            return session_name
        return f"{prefix}_{session_name}"
    
    def copy_hmd_sessions(self, hmd_sources, dest_dir, drive):
        """复制 HMD session 文件夹到目标目录，自动添加设备ID前缀重命名。
        
        目标结构：
          /media/0615/hmd/<device_id>_session_00000/part_*.hmd + metadata.json
          /media/0615/hmd/<device_id>_session_00001/...
        
        同一设备的所有 sessions 放在同一个 hmd 子目录下。
        不同设备的 sessions 通过 device_id 前缀区分，避免编号冲突。
        """
        pw = _get_progress_window()
        copied_sessions = []  # list of dicts for CSV registration
        failed_sessions = []
        
        for source in hmd_sources:
            sessions = source["sessions"]
            total_sessions = len(sessions)
            
            # 按设备ID分组，每组 sessions 放在同一个 hmd 子目录下
            # 如果有多个设备（极少见），各自一个子目录
            device_groups = {}
            for s in sessions:
                dev_id = s["device_id_short"] or "unknown"
                if dev_id not in device_groups:
                    device_groups[dev_id] = []
                device_groups[dev_id].append(s)
            
            for dev_id, dev_sessions in device_groups.items():
                # 目标子目录: /media\0615\hmd
                # 所有同设备的 sessions 放在这个目录下，通过前缀区分
                hmd_dest = os.path.join(dest_dir, "hmd")
                os.makedirs(hmd_dest, exist_ok=True)
                
                for idx, session in enumerate(dev_sessions):
                    # 检查源驱动器是否仍然存在
                    source_drive = os.path.splitdrive(session["source_path"])[0] + "\\"
                    if not os.path.exists(source_drive):
                        logger.warning(f"设备已断开: {source_drive}")
                        if pw:
                            pw["complete"](False, f"设备已断开！已复制 {len(copied_sessions)}/{total_sessions} 个session")
                        return copied_sessions, failed_sessions
                    
                    # ── 去重检查：session 是否已存在于目标目录下 ──
                    existing = self._check_hmd_already_exists(session, dest_dir)
                    if existing:
                        logger.info(f"HMD session 已存在，跳过复制: {session['session_name']} → {existing}")
                        # 跳过但仍记入 copied_sessions（指向已有路径），以便 CSV 注册和 SD 卡删除
                        copied_sessions.append({
                            "source_path": session["source_path"],
                            "dest_path": existing,
                            "device_id_short": session["device_id_short"],
                            "hostname": session["hostname"],
                            "metadata": session["metadata"],
                            "parts_count": session["parts_count"],
                            "total_size": session["total_size"],
                            "skipped": True,  # 标记为去重跳过
                        })
                        if pw:
                            pw["update"](idx + 1, total_sessions, f"{session['session_name']} (已存在)")
                        continue
                    
                    # 计算目标 session 名（带设备ID + 时间前缀）
                    new_name = self._rename_session_with_device_prefix(
                        session["session_name"], session["device_id_short"],
                        dest_path=dest_dir,
                    )
                    target_session_dir = os.path.join(hmd_dest, new_name)
                    
                    # 处理目标目录名冲突
                    counter = 1
                    while os.path.exists(target_session_dir):
                        # 如果目标已存在，追加编号
                        target_session_dir = os.path.join(hmd_dest, f"{new_name}_{counter}")
                        counter += 1
                    
                    try:
                        # 复制整个 session 目录（保留 metadata.json + 所有 part_*.hmd）
                        shutil.copytree(session["source_path"], target_session_dir)
                        
                        # 验证复制完整性：检查 metadata.json 存在 + part_*.hmd 文件数一致
                        dest_files = os.listdir(target_session_dir)
                        dest_parts = sum(1 for f in dest_files if f.startswith("part_") and f.endswith(".hmd"))
                        src_parts = session["parts_count"]
                        
                        if dest_parts != src_parts:
                            raise IOError(f"HMD session 文件数不一致: 源={src_parts}, 目标={dest_parts}")
                        
                        copied_sessions.append({
                            "source_path": session["source_path"],
                            "dest_path": target_session_dir,
                            "device_id_short": session["device_id_short"],
                            "hostname": session["hostname"],
                            "metadata": session["metadata"],
                            "parts_count": dest_parts,
                            "total_size": session["total_size"],
                        })
                        size_mb = session["total_size"] / (1024 * 1024)
                        logger.info(f"已复制 HMD session: {new_name} ({size_mb:.1f} MB, {dest_parts} parts)")
                        
                        if pw:
                            pw["update"](idx + 1, total_sessions, new_name)
                            
                    except PermissionError as e:
                        logger.error(f"权限不足，复制 HMD session 失败 {session['source_path']}: {e}")
                        failed_sessions.append(session["source_path"])
                        # 清理残留
                        if os.path.exists(target_session_dir):
                            try:
                                shutil.rmtree(target_session_dir)
                            except Exception:
                                pass
                        if pw:
                            pw["update"](idx + 1, total_sessions, session["session_name"])
                            
                    except Exception as e:
                        logger.error(f"复制 HMD session 失败 {session['source_path']}: {e}")
                        failed_sessions.append(session["source_path"])
                        if os.path.exists(target_session_dir):
                            try:
                                shutil.rmtree(target_session_dir)
                                logger.info(f"已清理残留目录: {target_session_dir}")
                            except Exception as ce:
                                logger.debug(f"清理残留目录失败: {ce}")
                        if pw:
                            pw["update"](idx + 1, total_sessions, session["session_name"])
        
        # 完成进度
        if pw:
            if failed_sessions:
                pw["complete"](False, f"HMD: 成功 {len(copied_sessions)}/{total_sessions} 个session")
            else:
                pw["complete"](True, f"HMD: 已复制 {len(copied_sessions)} 个session到 {dest_dir}")
        
        return copied_sessions, failed_sessions

    def copy_files(self, source_files, dest_dir, source_root):
        """复制文件到目标目录（失败时自动清理残留文件）
        
        去重逻辑：如果目标目录下已有同名同大小的文件，跳过复制，
        防止同一视频被重复存储。
        """
        copied = []
        skipped = []  # 已存在，跳过复制
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
                return copied, skipped, failed
            
            try:
                # ── 去重检查：文件是否已存在于目标目录下 ──
                existing = self._check_mp4_already_exists(src, dest_dir)
                if existing:
                    logger.info(f"文件已存在，跳过复制: {os.path.basename(src)} → {existing}")
                    skipped.append(src)
                    if pw:
                        pw["update"](i, total, f"{os.path.basename(src)} (已存在)")
                    continue
                
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
            if skipped:
                msg = f"复制 {len(copied)}, 跳过 {len(skipped)}, 失败 {len(failed)}"
                pw["complete"](len(failed) == 0, msg)
            elif failed:
                pw["complete"](False, f"成功 {len(copied)}/{total} 个文件")
            else:
                pw["complete"](True, f"已复制 {len(copied)} 个文件到 {dest_dir}")
        
        return copied, skipped, failed
    
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
