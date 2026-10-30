"""
修复 HMD session 文件夹，添加设备ID前缀
读取 metadata.json 中的 device_id 字段，重命名文件夹
"""
import os
import json
import shutil

def fix_hmd_sessions(hmd_dir):
    """修复 hmd 目录下的 session 文件夹，添加设备ID前缀"""
    
    if not os.path.isdir(hmd_dir):
        print(f"目录不存在: {hmd_dir}")
        return
    
    # 遍历 hmd 目录下的所有 session 文件夹
    for session_name in os.listdir(hmd_dir):
        session_path = os.path.join(hmd_dir, session_name)
        
        if not os.path.isdir(session_path):
            continue
        
        # 如果已经包含设备ID前缀（形如 "4aa45c_session_00000"），跳过
        if "_" in session_name and len(session_name.split("_")[0]) == 6:
            print(f"已包含设备前缀，跳过: {session_name}")
            continue
        
        # 读取 metadata.json
        metadata_path = os.path.join(session_path, "metadata.json")
        if not os.path.isfile(metadata_path):
            print(f"未找到 metadata.json，跳过: {session_name}")
            continue
        
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            
            # 获取设备ID
            devices = metadata.get("devices", [])
            if not devices:
                print(f"metadata.json 中未找到 devices，跳过: {session_name}")
                continue
            
            device_id = devices[0].get("identity", {}).get("device_id", "")
            if not device_id:
                print(f"未找到 device_id，跳过: {session_name}")
                continue
            
            # 取设备ID的后6位作为前缀
            device_prefix = device_id[-6:].lower()
            
            # 构建新的文件夹名称
            new_session_name = f"{device_prefix}_{session_name}"
            new_session_path = os.path.join(hmd_dir, new_session_name)
            
            # 检查目标是否已存在
            if os.path.exists(new_session_path):
                print(f"目标已存在，跳过: {new_session_name}")
                continue
            
            # 重命名文件夹
            shutil.move(session_path, new_session_path)
            print(f"已重命名: {session_name} → {new_session_name}")
            
        except Exception as e:
            print(f"处理失败 {session_name}: {e}")
            continue
    
    print("\n修复完成！")

if __name__ == "__main__":
    # 修复 /media\0621\hmd 目录
    hmd_dir = r"/media\0621\hmd"
    fix_hmd_sessions(hmd_dir)
    
    # 如果需要修复其他日期的 hmd 目录，取消下面的注释并修改日期
    # fix_hmd_sessions(r"/media\0620\hmd")
    # fix_hmd_sessions(r"/media\0619\hmd")
