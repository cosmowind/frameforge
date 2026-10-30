#!/usr/bin/env python3
"""Concatenate MP4 files (H.265) into one per session using PyAV."""
import os, subprocess, shutil, re

def concat_mp4(input_paths, output_path):
    if not input_paths:
        print("No input files")
        return
    temp_list = r'C:\temp_hmd\concat.txt'
    os.makedirs(r'C:\temp_hmd', exist_ok=True)
    with open(temp_list, 'w', encoding='utf-8') as f:
        for p in input_paths:
            f.write(f"file '{p.replace(chr(92), '/')}'\n")
    # Use subprocess with list args to avoid shell path issues
    subprocess.run([
        'ffmpeg', '-y',
        '-f', 'concat', '-safe', '0',
        '-i', temp_list,
        '-c', 'copy',
        output_path
    ], check=True)
    os.remove(temp_list)
    print(f"Written: {output_path}")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('input_dir', help='Directory containing session_*_ego_camera_0.mp4 files')
    parser.add_argument('--camera', type=int, default=0, choices=[0,1])
    args = parser.parse_args()

    root = args.input_dir
    # Group by session
    groups = {}
    for fn in os.listdir(root):
        if not fn.startswith('session_') or not fn.endswith('.mp4'):
            continue
        m = re.match(r'^session_(\d+)_ego_\d+_ego_camera_(\d)\.mp4$', fn)
        if not m:
            continue
        sess, cam = m.group(1), int(m.group(2))
        if cam != args.camera:
            continue
        groups.setdefault(sess, []).append(fn)

    # Sort clips by ego number within each session
    for sess, clips in groups.items():
        clips.sort(key=lambda f: int(re.search(r'ego_(\d+)_', f).group(1)))
        paths = [os.path.join(root, c) for c in clips]
        out = os.path.join(root, f'session_{sess}_merged.mp4')
        print(f"[{sess}] {len(clips)} clips -> session_{sess}_merged.mp4")
        temp_out = os.path.join(r'C:\temp_hmd', f'session_{sess}_merged.mp4')
        concat_mp4(paths, temp_out)
        shutil.move(temp_out, out)
        # Remove original clip files
        for p in paths:
            os.remove(p)
    print("Done.")
