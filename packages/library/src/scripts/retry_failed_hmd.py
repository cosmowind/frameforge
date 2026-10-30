#!/usr/bin/env python
"""批量重试所有失败的 HMD 预处理 session。
读取 hmd_cache/<sess>/.hmd_process.json，状态为 error 的清除后重新启动。
"""
import os, json, sys, glob, threading, time, subprocess

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE_DIR, "src", "tools"))
import hmd_preprocess

cache_root = hmd_preprocess.get_cache_root()
video_csv = os.path.join(BASE_DIR, "runtime", "data", "video_manager.csv")

# 读取 CSV 获取所有 HMD session 的源路径
path_to_source = {}
import csv
with open(video_csv, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row.get("file_type", "") == "hmd":
            p = row.get("path", "").strip()
            if p:
                path_to_source[os.path.basename(p)] = p

print(f"CSV 中有 {len(path_to_source)} 个 HMD session")

# 找出需要重试的
need_retry = []
for sess in sorted(os.listdir(cache_root)):
    sdir = os.path.join(cache_root, sess)
    if not os.path.isdir(sdir):
        continue
    status_file = os.path.join(sdir, ".hmd_process.json")
    # 新旧命名兼容：优先新命名 mp4，回退旧命名
    left_mp4 = os.path.join(sdir, f"{sess}.mp4")
    if not os.path.isfile(left_mp4):
        left_mp4 = os.path.join(sdir, "left.mp4")
    # 已经成功
    if os.path.isfile(left_mp4):
        continue
    # 状态文件存在且是 error
    if os.path.isfile(status_file):
        try:
            d = json.load(open(status_file, encoding="utf-8"))
            if d.get("status") != "error":
                continue
        except Exception:
            pass
    # 找到源路径
    source = path_to_source.get(sess, "")
    if source and os.path.isdir(source) and glob.glob(os.path.join(source, "part_*.hmd")):
        need_retry.append((sess, source))
    else:
        print(f"SKIP {sess}: source not found or no part_*.hmd")

print(f"\n需要重试: {len(need_retry)} 个 session")

# 批量启动（后台线程）
started = 0
for sess, source in need_retry:
    # 清除旧状态（新旧命名兼容）
    for f in (os.path.join(cache_root, sess, f"{sess}.mp4"),
               os.path.join(cache_root, sess, f"{sess}.h265"),
               os.path.join(cache_root, sess, "left.mp4"),
               os.path.join(cache_root, sess, "left.h265"),
               os.path.join(cache_root, sess, ".hmd_process.json")):
        if os.path.isfile(f):
            try:
                os.unlink(f)
            except Exception:
                pass
    hmd_preprocess.start_async(source)
    started += 1
    print(f"  STARTED [{started}/{len(need_retry)}] {sess}")
    time.sleep(0.1)  # 避免瞬间起太多线程

print(f"\n全部 {started} 个已启动，后台处理中...")
print("可在浏览器中打开主界面 → 预处理面板查看进度")
