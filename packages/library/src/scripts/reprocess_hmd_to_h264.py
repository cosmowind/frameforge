#!/usr/bin/env python
"""重新处理所有已预处理的 HMD 文件夹，生成 H.264 编码的 MP4 文件。"""
import os
import sys
import subprocess

# 添加 tools 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'tools'))

from hmd_preprocess import get_cache_root, list_parts, ffmpeg_to_h264_mp4, get_h265_path, get_mp4_path

def main():
    cache_root = get_cache_root()
    print(f"Cache root: {cache_root}")
    
    # 遍历所有已处理的文件夹
    if not os.path.isdir(cache_root):
        print(f"Cache root does not exist: {cache_root}")
        return
    
    for folder_name in os.listdir(cache_root):
        folder_path = os.path.join(cache_root, folder_name)
        if not os.path.isdir(folder_path):
            continue
        
        # 检查是否有 left.mp4
        left_mp4 = os.path.join(folder_path, 'left.mp4')
        left_h265 = os.path.join(folder_path, 'left.h265')
        
        # 如果 left.mp4 存在但 HEVC 版本不存在，需要重新生成
        hevc_mp4 = os.path.join(folder_path, 'left.hevc.mp4')
        
        if os.path.isfile(left_mp4) and not os.path.isfile(hevc_mp4):
            print(f"\nProcessing: {folder_name}")
            print(f"  - Backing up existing left.mp4 to left.hevc.mp4")
            
            # 备份现有的 HEVC MP4 为 .hevc.mp4
            import shutil
            shutil.move(left_mp4, hevc_mp4)
            print(f"  - Backup complete")
        
        # 如果 left.h265 存在但 left.mp4 不是 H.264，重新生成
        if os.path.isfile(left_h265):
            print(f"\nRe-encoding: {folder_name}")
            print(f"  - Input: {left_h265}")
            print(f"  - Output: {left_mp4}")
            
            # 删除旧的 left.mp4 (如果是 HEVC)
            if os.path.isfile(left_mp4):
                os.remove(left_mp4)
            
            # 重新生成 H.264 版本
            try:
                ffmpeg_to_h264_mp4(left_h265, left_mp4)
                print(f"  - Success: {left_mp4}")
            except Exception as e:
                print(f"  - Error: {e}")
                # 如果失败，恢复备份
                if os.path.isfile(hevc_mp4) and not os.path.isfile(left_mp4):
                    print(f"  - Restoring backup...")
                    shutil.copy2(hevc_mp4, left_mp4)
        
        # 检查 right.mp4 (如果存在)
        right_mp4 = os.path.join(folder_path, 'right.mp4')
        right_h265 = os.path.join(folder_path, 'right.h265')
        
        if os.path.isfile(right_h265):
            print(f"\nRe-encoding right: {folder_name}")
            try:
                ffmpeg_to_h264_mp4(right_h265, right_mp4)
                print(f"  - Success: {right_mp4}")
            except Exception as e:
                print(f"  - Error: {e}")
    
    print("\nDone!")

if __name__ == '__main__':
    main()
