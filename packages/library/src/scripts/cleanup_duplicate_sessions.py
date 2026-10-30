"""
清理重复的 HMD session
- 检测不带设备前缀的 session 是否有对应的带前缀版本
- 比较内容是否相同
- 如果相同，删除不带前缀的旧版本
"""
import os
import json
import shutil
import filecmp

def get_session_device_id(session_path):
    """从 session 的 metadata.json 中获取设备ID后缀（后6位）"""
    metadata_path = os.path.join(session_path, "metadata.json")
    if not os.path.isfile(metadata_path):
        return None
    
    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        
        devices = metadata.get("devices", [])
        if not devices:
            return None
        
        device_id = devices[0].get("identity", {}).get("device_id", "")
        if device_id:
            return device_id[-6:].lower()
    except Exception as e:
        print(f"读取设备ID失败: {metadata_path}: {e}")
    
    return None

def compare_sessions_dir(session1_path, session2_path):
    """比较两个 session 目录是否包含相同的文件（按文件名和大小）"""
    try:
        # 获取 session1 的文件列表
        files1 = set()
        for f in os.listdir(session1_path):
            if os.path.isfile(os.path.join(session1_path, f)):
                files1.add(f)
        
        # 获取 session2 的文件列表
        files2 = set()
        for f in os.listdir(session2_path):
            if os.path.isfile(os.path.join(session2_path, f)):
                files2.add(f)
        
        # 比较文件列表
        if files1 != files2:
            return False
        
        # 比较每个文件的大小
        for f in files1:
            file1 = os.path.join(session1_path, f)
            file2 = os.path.join(session2_path, f)
            
            if os.path.getsize(file1) != os.path.getsize(file2):
                return False
        
        return True
    except Exception as e:
        print(f"比较 session 失败: {e}")
        return False

def cleanup_duplicates(hmd_dir):
    """清理重复的 session"""
    if not os.path.isdir(hmd_dir):
        print(f"目录不存在: {hmd_dir}")
        return
    
    print(f"开始清理重复 session: {hmd_dir}")
    print("=" * 60)
    
    # 找到所有不带设备前缀的 session
    orphan_sessions = []
    for session_name in os.listdir(hmd_dir):
        session_path = os.path.join(hmd_dir, session_name)
        
        if not os.path.isdir(session_path):
            continue
        
        # 检查是否包含设备前缀（形如 "4aa45c_session_00000"）
        if "_" not in session_name or len(session_name.split("_")[0]) != 6:
            orphan_sessions.append(session_name)
    
    if not orphan_sessions:
        print("未找到不带设备前缀的 session")
        return
    
    print(f"找到 {len(orphan_sessions)} 个不带设备前缀的 session")
    print()
    
    deleted_count = 0
    kept_count = 0
    
    for session_name in orphan_sessions:
        session_path = os.path.join(hmd_dir, session_name)
        
        # 获取设备ID
        device_prefix = get_session_device_id(session_path)
        if not device_prefix:
            print(f"⚠️  无法获取设备ID，保留: {session_name}")
            kept_count += 1
            continue
        
        # 构建带前缀的 session 名称
        prefixed_name = f"{device_prefix}_{session_name}"
        prefixed_path = os.path.join(hmd_dir, prefixed_name)
        
        # 检查带前缀的版本是否存在
        if not os.path.exists(prefixed_path):
            print(f"⚠️  未找到对应版本，保留: {session_name} (期望: {prefixed_name})")
            kept_count += 1
            continue
        
        # 比较内容
        print(f"检查: {session_name} <-> {prefixed_name}")
        if compare_sessions_dir(session_path, prefixed_path):
            print(f"  [OK] 内容相同，删除: {session_name}")
            try:
                shutil.rmtree(session_path)
                deleted_count += 1
            except Exception as e:
                print(f"  [FAIL] 删除失败: {e}")
                kept_count += 1
        else:
            print(f"  [DIFF] 内容不同，保留: {session_name}")
            kept_count += 1
        print()
    
    print("=" * 60)
    print(f"清理完成！删除: {deleted_count} 个，保留: {kept_count} 个")

if __name__ == "__main__":
    # 清理 /media\0621\hmd 目录下的重复 session
    hmd_dir = r"/media\0621\hmd"
    cleanup_duplicates(hmd_dir)
