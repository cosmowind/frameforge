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
from datetime import datetime

# 确保当前目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入应用模块
from app import app as flask_app
from device_monitor import start_monitor, stop_monitor, get_monitor_status

logger = logging.getLogger(__name__)


def start_flask():
    """启动 Flask 应用"""
    logger.info("启动 Flask Web 应用...")
    flask_app.run(debug=False, host="0.0.0.0", port=5000, use_reloader=False)


def main():
    """主函数"""
    print("=" * 60)
    print("  视频管理系统启动中...")
    print("=" * 60)
    
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
