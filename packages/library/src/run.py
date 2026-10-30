"""
统一启动脚本
同时启动 Flask Web 应用和设备监控线程
"""

import os
import sys
import threading
import webbrowser
import time
import logging
import shutil
from datetime import datetime

# 确保当前目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入应用模块（device_monitor 的 basicConfig 在此处首次配置 root logger）
from app import app as flask_app
from device_monitor import start_monitor, stop_monitor, get_monitor_status

logger = logging.getLogger(__name__)

# ── 确保 CMD 窗口有日志输出 ──
# device_monitor.py 的 basicConfig 会同时添加 FileHandler 和 StreamHandler，
# 但如果 basicConfig 因某些原因没生效，这里做兜底。
_root = logging.getLogger()
_has_stream = any(
    isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
    for h in _root.handlers
)
if not _has_stream:
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S',
    ))
    _root.addHandler(_handler)
    _root.setLevel(logging.INFO)


def _check_disk_space_for_preprocess():
    """检查磁盘空间是否足够完成所有未预处理 HMD 的预处理。

    预估：每个未处理 HMD session 需要约 2x 源文件大小的空间
    （h265 原始流 + mp4 封装 + 预览帧 + 封面）。

    Returns:
        (sufficient: bool, total_source_gb: float, free_gb: float, needed_gb: float, pending_count: int)
    """
    try:
        from config import RUNTIME_DIR, USE_PG
        if USE_PG:
            from models.pg_store import read_csv
        else:
            from models.csv_store import read_csv
        from tools.hmd_fast import get_output_dir as _get_fast_output, check_fast_done

        rows = read_csv()
        hmd_rows = [r for r in rows if r.get("file_type") == "hmd"]

        total_source_bytes = 0
        pending_count = 0
        for r in hmd_rows:
            folder = r.get("path", "")
            if not folder or not os.path.isdir(folder):
                continue
            # 已完成预处理的跳过
            if check_fast_done(folder):
                continue
            # 计算源文件夹大小
            try:
                folder_size = 0
                for dirpath, dirnames, filenames in os.walk(folder):
                    for fn in filenames:
                        fp = os.path.join(dirpath, fn)
                        try:
                            folder_size += os.path.getsize(fp)
                        except OSError:
                            pass
                total_source_bytes += folder_size
                pending_count += 1
            except Exception:
                pass

        if pending_count == 0 or total_source_bytes == 0:
            return True, 0, 0, 0, 0

        # 预处理需要约 2x 源文件大小
        needed_bytes = total_source_bytes * 2
        total_source_gb = total_source_bytes / (1024**3)
        needed_gb = needed_bytes / (1024**3)

        # 检查 runtime 所在磁盘的可用空间
        dest_dir = RUNTIME_DIR
        usage = shutil.disk_usage(dest_dir)
        free_gb = usage.free / (1024**3)

        sufficient = usage.free >= needed_bytes
        return sufficient, total_source_gb, free_gb, needed_gb, pending_count

    except Exception as e:
        print(f"\n  [警告] 磁盘空间检查失败: {e}，默认允许自动预处理")
        return True, 0, 0, 0, 0


def start_flask():
    """启动 Flask 应用"""
    logger.info("启动 Flask Web 应用...")
    flask_app.run(debug=False, host="0.0.0.0", port=5000, use_reloader=False)


def main():
    """主函数"""
    print("=" * 60)
    print("  视频管理系统启动中...")
    print("=" * 60)

    # ── 检查命令行参数 ──
    auto_preprocess = False
    skip_preprocess = "--no-preprocess" in sys.argv

    if skip_preprocess:
        print("\n[预处理] 已通过参数跳过自动预处理，可在 Web 界面手动触发")
    else:
        # ── 自动预处理：磁盘空间检查 ──
        sufficient, src_gb, free_gb, need_gb, pending = _check_disk_space_for_preprocess()

        if pending > 0:
            if sufficient:
                auto_preprocess = True
                print(f"\n[预处理] 磁盘空间充足（可用 {free_gb:.1f} GB，需要约 {need_gb:.1f} GB）")
                print(f"          将自动预处理 {pending} 个未完成的 HMD session（源文件共 {src_gb:.1f} GB）")
            else:
                # 空间不够，询问用户
                print(f"\n  ⚠ 磁盘空间不足！")
                print(f"    未处理 session: {pending} 个（源文件 {src_gb:.1f} GB）")
                print(f"    预处理约需:     {need_gb:.1f} GB（含 .h265 + .mp4 + 预览帧）")
                print(f"    磁盘可用空间:   {free_gb:.1f} GB（{os.path.dirname(os.path.join(os.path.dirname(__file__), '..', 'runtime'))}）")
                print(f"\n    预处理完成后会自动删除 .h265 原始流来释放空间。")
                print(f"    如果空间严重不足，建议先手动清理或扩展磁盘。")
                choice = input(f"\n  是否开启自动预处理？(y/N): ").strip().lower()
                auto_preprocess = choice in ("y", "yes")
                if auto_preprocess:
                    print(f"    已开启自动预处理（风险自负）")
                else:
                    print(f"    已跳过自动预处理，可在 Web 界面手动触发")

    # 通过环境变量传递决定给 app.py
    os.environ["AUTO_PREPROCESS_ENABLED"] = "1" if auto_preprocess else "0"

    # 启动设备监控
    print("\n[1/2] 启动设备监控服务...")
    monitor_status = start_monitor()
    print(f"      监控状态: {'运行中' if monitor_status['running'] else '未运行'}")
    print(f"      扫描间隔: {monitor_status['config']['scan_interval']} 秒")
    print(f"      目标目录: {monitor_status['config']['destination_base']}")

    # 在浏览器中打开 Web 应用
    print("\n[2/2] 启动 Web 服务...")
    print("      访问地址: http://localhost:5000")
    print("      按 Ctrl+C 停止所有服务")

    # 延迟打开浏览器
    def open_browser():
        time.sleep(1.5)
        webbrowser.open("http://localhost:5000")

    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()

    print("\n" + "=" * 60)
    print("  系统已启动！")
    print("=" * 60)

    try:
        # 启动 Flask（在主线程中运行）
        start_flask()
    except KeyboardInterrupt:
        print("\n\n正在停止服务...")
    finally:
        # 停止设备监控
        print("停止设备监控...")
        stop_monitor()
        print("服务已全部停止")


if __name__ == "__main__":
    main()
