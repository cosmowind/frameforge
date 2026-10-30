"""
整合 hmd 和 umi1 目录到 hmd 目录下
- 将 umi1 中的 session 移动到 hmd 目录
- 检查并删除重复的 session
- 确保所有 session 都有正确的设备前缀
"""
import os
import json
import shutil
import hashlib

def calculate_file_hash(filepath):
    """计算文件的 MD5 哈希值，用于检测重复文件"""
    hash_md5 = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        print(f"计算文件哈希失败: {filepath}: {e}")
        return None

def get_session_device_id(session_path):
    """从 session 的 metadata.json 中获取设备ID"""
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

def merge_hmd_directories(base_dir):
    """整合 hmd 和 umi1 目录"""
    hmd_dir = os.path.join(base_dir, "hmd")
    umi1_dir = os.path.join(base_dir, "umi1")
    
    # 检查目录是否存在
    if not os.path.isdir(hmd_dir):
        print(f"hmd 目录不存在: {hmd_dir}")
        return
    
    if not os.path.isdir(umi1_dir):
        print(f"umi1 目录不存在: {umi1_dir}，无需整合")
        return
    
    print(f"开始整合: {umi1_dir} → {hmd_dir}")
    print("=" * 60)
    
    # 遍历 umi1 目录下的所有 session
    moved_count = 0
    skipped_count = 0
    
    for session_name in os.listdir(umi1_dir):
        session_path = os.path.join(umi1_dir, session_name)
        
        if not os.path.isdir(session_path):
            continue
        
        # 确保 session 名称有设备前缀
        if "_" not in session_name or len(session_name.split("_")[0]) != 6:
            # 没有设备前缀，尝试从 metadata.json 获取
            device_prefix = get_session_device_id(session_path)
            if device_prefix:
                new_session_name = f"{device_prefix}_{session_name}"
            else:
                print(f"跳过（无法获取设备ID）: {session_name}")
                skipped_count += 1
                continue
        else:
            new_session_name = session_name
        
        target_path = os.path.join(hmd_dir, new_session_name)
        
        # 检查目标是否已存在
        if os.path.exists(target_path):
            print(f"目标已存在，检查是否重复: {new_session_name}")
            
            # 比较源和目标的内容
            if compare_sessions(session_path, target_path):
                print(f"  → 内容相同，删除源 session: {session_name}")
                shutil.rmtree(session_path)
                moved_count += 1
                continue
            else:
                print(f"  → 内容不同，重命名后移动")
                counter = 1
                while os.path.exists(target_path):
                    target_path = os.path.join(hmd_dir, f"{new_session_name}_{counter}")
                    counter += 1
        
        # 移动 session
        try:
            shutil.move(session_path, target_path)
            print(f"已移动: {session_name} → {os.path.basename(target_path)}")
            moved_count += 1
        except Exception as e:
            print(f"移动失败: {session_name}: {e}")
            skipped_count += 1
    
    # 尝试删除空的 umi1 目录
    try:
        if not os.listdir(umi1_dir):
            os.rmdir(umi1_dir)
            print(f"\n已删除空目录: {umi1_dir}")
        else:
            print(f"\numi1 目录非空，保留: {umi1_dir}")
    except Exception as e:
        print(f"删除 umi1 目录失败: {e}")
    
    print("\n" + "=" * 60)
    print(f"整合完成！移动: {moved_count} 个，跳过: {skipped_count} 个")

def compare_sessions(session1_path, session2_path):
    """比较两个 session 是否相同（比较 part_*.hmd 文件）"""
    try:
        # 获取 session1 的文件列表和哈希值
        files1 = {}
        for f in os.listdir(session1_path):
            if f.startswith("part_") and f.endswith(".hmd"):
                filepath1 = os.path.join(session1_path, f)
                files1[f] = calculate_file_hash(filepath1)
        
        # 获取 session2 的文件列表和哈希值
        files2 = {}
        for f in os.listdir(session2_path):
            if f.startswith("part_") and f.endswith(".hmd"):
                filepath2 = os.path.join(session2_path, f)
                files2[f] = calculate_file_hash(filepath2)
        
        # 比较文件数量和哈希值
        if len(files1) != len(files2):
            return False
        
        for f, hash1 in files1.items():
            if f not in files2:
                return False
            if files2[f] != hash1:
                return False
        
        return True
    except Exception as e:
        print(f"比较 session 失败: {e}")
        return False

if __name__ == "__main__":
    # 整合 /media\0621 目录下的 hmd 和 umi1
    base_dir = r"/media\0621"
    merge_hmd_directories(base_dir)
