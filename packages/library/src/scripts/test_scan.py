"""
独立测试：扫描并复制视频文件
只执行一次扫描，不启动监控循环
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from device_monitor import DeviceMonitor

print("=" * 50)
print("  视频扫描复制测试")
print("=" * 50)

monitor = DeviceMonitor()

# 1. 显示配置
print("\n[配置]")
print(f"  目标目录: {monitor.config['destination_base']}")
print(f"  今天路径: {monitor.get_destination_dir()}")

# 2. 查找可用驱动器
drives = monitor.get_available_drives()
print(f"\n[可用驱动器] {drives if drives else '无'}")

if not drives:
    print("\n没有可用的外部驱动器，测试结束。")
    sys.exit(0)

# 3. 扫描视频源
print(f"\n[扫描视频源]")
all_sources = []
for drive in drives:
    sources = monitor.find_video_sources(drive)
    if sources:
        for s in sources:
            total_mb = s['total_size'] / (1024 * 1024)
            print(f"  {s['path']} -> {len(s['files'])} 个视频, {total_mb:.1f} MB")
            for f in s['files']:
                print(f"    - {os.path.basename(f)}")
        all_sources.extend(sources)
    else:
        print(f"  {drive} 未找到视频源")

if not all_sources:
    print("\n未找到任何视频文件，测试结束。")
    sys.exit(0)

# 4. 确认执行
print(f"\n[即将执行]")
print(f"  将复制 {sum(len(s['files']) for s in all_sources)} 个视频到 {monitor.get_destination_dir()}")
print(f"  复制完成后将删除源文件")

# 直接执行扫描
print("\n" + "=" * 50)
print("  开始复制...")
print("=" * 50)
monitor.scan_once()

input("\n按 Enter 退出...")
