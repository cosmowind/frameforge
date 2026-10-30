"""
存储卡自动导入模块
- 扫描非系统盘（排除C/D盘）的可移动存储设备
- 从 DCIM/DJI001 等目录复制 mp4 文件（单目设备：DJI/GoPro）
- 从 hmd/ 目录复制 HMD session 文件夹（双目设备：HMD gripper）
- HMD session 自动加设备ID前缀，避免不同设备 session 编号冲突
- 复制完成后清空源目录
- 每分钟自动扫描一次
"""

from device_monitor.monitor import (
    DeviceMonitor,
    get_monitor,
    start_monitor,
    stop_monitor,
    get_monitor_status,
    get_monitor_disk_space_status,
    resume_monitor,
)
