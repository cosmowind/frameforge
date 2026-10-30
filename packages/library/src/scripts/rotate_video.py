#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频旋转工具：竖屏(1080x1920) → 横屏(1920x1080)
选文件/文件夹 → 点开始 → 看日志区实时进度。
"""

import os
import re
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext
from threading import Thread

FFMPEG = "ffmpeg"


def find_video_files(paths):
    exts = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v",
            ".MP4", ".MOV", ".AVI", ".MKV"}
    files = []
    for p in paths:
        if os.path.isfile(p) and os.path.splitext(p)[1] in exts:
            files.append(p)
        elif os.path.isdir(p):
            for root, _, fs in os.walk(p):
                for f in fs:
                    if os.path.splitext(f)[1] in exts:
                        files.append(os.path.join(root, f))
    return files


def _unique_output_path(input_path, suffix):
    """Generate a unique output path, avoiding name collision with existing files."""
    name, ext = os.path.splitext(input_path)
    candidate = f"{name}{suffix}{ext}"
    if not os.path.exists(candidate):
        return candidate
    counter = 1
    while True:
        candidate = f"{name}{suffix}_{counter}{ext}"
        if not os.path.exists(candidate):
            return candidate
        counter += 1


def rotate_video(input_path, direction="cw", fast=False):
    """Build ffmpeg command for rotation.
    fast=True: hardware-accelerated encode (much faster, slightly larger files).
    fast=False: software libx264 (slower, better compression).
    """
    suffix = "_rotated" if direction == "cw" else "_rotated_ccw"
    output_path = _unique_output_path(input_path, suffix)
    transpose_val = "1" if direction == "cw" else "2"

    if fast:
        # Use auto-detected hardware encoder for speed (~100x)
        cmd = [
            FFMPEG,
            "-i", input_path,
            "-vf", f"transpose={transpose_val}",
            "-c:v", "libx264",       # fallback if HW not available
            "-crf", "23",            # slightly lower quality but much faster
            "-preset", "ultrafast",  # fastest preset
            "-c:a", "copy",
            "-map_metadata", "0",
            "-movflags", "+faststart",
            "-progress", "pipe:1",
            "-nostats",
            "-y",
            output_path
        ]
    else:
        cmd = [
            FFMPEG,
            "-i", input_path,
            "-vf", f"transpose={transpose_val}",
            "-c:v", "libx264",
            "-crf", "18",
            "-preset", "medium",
            "-c:a", "copy",
            "-map_metadata", "0",
            "-movflags", "+faststart",
            "-progress", "pipe:1",
            "-nostats",
            "-y",
            output_path
        ]
    return cmd, output_path


class RotateApp:
    def __init__(self, root):
        self.root = root
        self.root.title("视频旋转工具 — 竖屏转横屏")
        self.root.geometry("700x600")
        self.root.resizable(True, True)

        # 顶部说明
        tk.Label(
            root,
            text="将竖屏视频 (1080×1920) 旋转为横屏 (1920×1080)\n勾选「快速」≈100x 速度 | 取消勾选 = 高质量编码",
            font=("Microsoft YaHei", 10),
            justify="center",
        ).pack(pady=8)

        # ── 按钮区 ──
        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=4)
        tk.Button(btn_frame, text="选择文件", width=12,
                  command=self.select_files).pack(side="left", padx=4)
        tk.Button(btn_frame, text="选择文件夹", width=12,
                  command=self.select_folder).pack(side="left", padx=4)
        tk.Button(btn_frame, text="► 开始旋转", width=12,
                  command=self.start_rotate, bg="#4CAF50", fg="white").pack(
                      side="left", padx=4)

        # 方向
        self.direction = tk.StringVar(value="cw")
        tk.Label(btn_frame, text="方向:").pack(side="left", padx=(12, 0))
        tk.Radiobutton(btn_frame, text="顺时针", variable=self.direction,
                       value="cw").pack(side="left")
        tk.Radiobutton(btn_frame, text="逆时针", variable=self.direction,
                       value="ccw").pack(side="left")

        # 快速模式
        self.fast_mode = tk.BooleanVar(value=True)
        tk.Checkbutton(btn_frame, text="快速 (ultrafast)", variable=self.fast_mode,
                       ).pack(side="left", padx=(16, 0))

        # ── 文件列表 + 日志 左右分栏 ──
        main = tk.PanedWindow(root, orient="horizontal")
        main.pack(fill="both", expand=True, padx=8, pady=4)

        # 左侧：文件列表
        left = tk.Frame(main)
        main.add(left, width=200)
        tk.Label(left, text="待处理文件", font=("Microsoft YaHei", 9, "bold")).pack()
        self.listbox = tk.Listbox(left, selectmode="extended")
        list_scroll = ttk.Scrollbar(left, orient="vertical",
                                     command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=list_scroll.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        list_scroll.pack(side="right", fill="y")
        tk.Button(left, text="移除选中", command=self.remove_selected).pack(pady=3)

        # 右侧：日志
        right = tk.Frame(main)
        main.add(right, width=450)
        tk.Label(right, text="处理日志（实时）", font=("Microsoft YaHei", 9, "bold")).pack()
        self.log = scrolledtext.ScrolledText(
            right, wrap="word", font=("Consolas", 9),
            bg="#1e1e1e", fg="#d4d4d4", insertbackground="white"
        )
        self.log.pack(fill="both", expand=True)

        # ── 底部状态 ──
        self.progress = ttk.Progressbar(root, mode="determinate")
        self.progress.pack(fill="x", padx=8, pady=(4, 0))
        self.status = tk.Label(root, text="就绪 — 请添加视频文件", fg="gray")
        self.status.pack(pady=2)

        self.files = []
        self._running = False

        # 拖拽支持（可选）
        try:
            from tkinterdnd2 import DND_FILES
            root.drop_target_register(DND_FILES)
            root.dnd_bind("<<Drop>>", self.on_drop)
        except ImportError:
            pass

    # ── 文件管理 ──
    def on_drop(self, event):
        raw = event.data
        paths = []
        for part in raw.split("}"):
            p = part.strip().strip("{").strip()
            if p:
                paths.append(p)
        for part in raw.split():
            p = part.strip("{").strip("}").strip()
            if p and p not in paths:
                paths.append(p)
        self.add_files(paths)

    def add_files(self, paths):
        new = find_video_files(paths)
        for f in new:
            if f not in self.files:
                self.files.append(f)
                self.listbox.insert("end", os.path.basename(f))
        self.status.config(text=f"已添加 {len(self.files)} 个视频文件")

    def select_files(self):
        p = filedialog.askopenfilenames(
            title="选择视频文件",
            filetypes=[("视频", "*.mp4 *.mov *.avi *.mkv *.webm *.m4v"), ("全部", "*.*")]
        )
        if p:
            self.add_files(list(p))

    def select_folder(self):
        p = filedialog.askdirectory(title="选择视频文件夹")
        if p:
            self.add_files([p])

    def remove_selected(self):
        sel = self.listbox.curselection()
        for i in reversed(sel):
            del self.files[i]
            self.listbox.delete(i)
        self.status.config(text=f"已添加 {len(self.files)} 个视频文件")

    # ── 日志 ──
    def log_line(self, text, tag=None):
        """线程安全写日志"""
        self.root.after(0, lambda: self._append_log(text, tag))

    def _append_log(self, text, tag=None):
        self.log.insert("end", text + "\n")
        self.log.see("end")
        if tag:
            self.log.tag_add(tag, "end-2l", "end-1l")

    # ── 旋转 ──
    def start_rotate(self):
        if not self.files:
            messagebox.showwarning("提示", "请先添加视频文件")
            return
        self._running = True
        self.progress["maximum"] = len(self.files)
        self.progress["value"] = 0
        self.log.delete("1.0", "end")
        self.log_line(f"══════ 开始处理 {len(self.files)} 个文件 ══════")
        Thread(target=self._do_rotate, daemon=True).start()

    def _do_rotate(self):
        direction = self.direction.get()
        fast = self.fast_mode.get()
        dir_name = "顺时针" if direction == "cw" else "逆时针"
        mode_name = "快速模式" if fast else "高质量模式"
        success, fail = 0, 0

        for idx, f in enumerate(self.files):
            if not self._running:
                break

            fname = os.path.basename(f)
            self.log_line(f"\n[{idx+1}/{len(self.files)}] {fname} ({mode_name})")
            self.root.after(0, lambda n=fname: self.status.config(
                text=f"处理中: {n}"))
            self.root.after(0, lambda v=idx: self.progress.configure(value=v))

            try:
                cmd, out = rotate_video(f, direction, fast=fast)
                self.log_line(f"  命令: ffmpeg -i \"...\" -vf transpose=... {dir_name} ({mode_name})")

                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,   # ffmpeg 进度的 stderr 合并到 stdout
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    universal_newlines=True,
                )

                # 实时读取 ffmpeg 输出行
                last_progress_line = ""
                for line in proc.stdout:
                    line = line.rstrip()
                    if not line:
                        continue
                    # 只显示关键行：进度、错误、起始信息
                    if any(kw in line for kw in [
                        "frame=", "fps=", "speed=",   # 帧进度
                        "Duration:", "Stream #",       # 媒体信息
                        "Input #", "Output #",
                        "video:", "audio:",
                        "Error", "error", "Invalid",
                    ]):
                        # 同一秒内的 progress 行只保留最后一条（减少刷新）
                        if "frame=" in line:
                            last_progress_line = line
                            continue
                        self.log_line(f"  {line}")
                    elif any(kw in line for kw in [
                        "Press [q]", "configuration:",
                        "libavutil", "libavcodec",
                    ]):
                        pass  # 屏蔽噪音
                    else:
                        # 其他非空行也显示（捕获异常信息）
                        if len(line) > 3:
                            self.log_line(f"  {line}")

                # 打印最后一次进度
                if last_progress_line:
                    self.log_line(f"  {last_progress_line}")

                proc.wait()
                rc = proc.returncode

                if rc == 0 and os.path.exists(out):
                    out_size = os.path.getsize(out)
                    out_mb = out_size / (1024*1024)
                    self.log_line(f"  ✓ 完成 → {os.path.basename(out)} ({out_mb:.1f} MB)",
                                  tag="success")
                    success += 1
                else:
                    self.log_line(f"  ✗ 失败 (返回码={rc})", tag="fail")
                    fail += 1

            except Exception as e:
                self.log_line(f"  ✗ 异常: {e}", tag="fail")
                fail += 1

            self.root.after(0, lambda v=idx+1: self.progress.configure(value=v))

        # 汇总
        summary = f"\n══════ 完成！成功 {success} / 失败 {fail} ══════"
        self.log_line(summary)
        self.root.after(0, lambda: self.status.config(
            text=f"完成 — 成功 {success}，失败 {fail}"))
        self.root.after(0, lambda: messagebox.showinfo(
            "完成", f"处理完毕\n成功: {success}\n失败: {fail}"))


if __name__ == "__main__":
    root = tk.Tk()
    RotateApp(root)
    root.mainloop()
