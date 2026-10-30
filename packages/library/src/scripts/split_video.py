import os
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


def get_keyframes(video_path):
    """用 ffprobe 提取视频所有关键帧的时间戳（秒）"""
    import json
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "packet=pts_time,flags",
        "-of", "json",
        video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)
    return [float(p["pts_time"]) for p in data.get("packets", []) if "K" in p.get("flags", "")]


def get_duration(video_path):
    """获取视频总时长（秒）"""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return float(result.stdout.strip())


def find_split_points(keyframes, duration, n):
    """在关键帧中找最接近等分点的位置"""
    if not keyframes:
        return []

    segment_dur = duration / n
    split_points = []
    for i in range(1, n):
        target = segment_dur * i
        # 找离目标最近的关键帧（不超过目标太多）
        best = min(keyframes, key=lambda t: abs(t - target))
        # 如果最近的关键帧比目标晚太多，往前提一个
        if best > target + segment_dur * 0.1:
            earlier = [t for t in keyframes if t <= target]
            if earlier:
                best = earlier[-1]
        if best not in split_points:
            split_points.append(best)

    return sorted(split_points)


def split_video(video_path, n, progress_cb=None):
    """将视频无损切割为 n 等份"""
    duration = get_duration(video_path)
    keyframes = get_keyframes(video_path)

    if not keyframes:
        # 没有关键帧信息，用固定时间切割（可能在非关键帧处切，ffmpeg 会自动处理）
        segment_dur = duration / n
        split_points = [segment_dur * i for i in range(1, n)]
    else:
        split_points = find_split_points(keyframes, duration, n)

    # 构建切割区间
    boundaries = [0.0] + split_points + [duration]
    base, ext = os.path.splitext(video_path)
    output_dir = os.path.dirname(video_path)

    total = len(boundaries) - 1
    for i in range(total):
        start = boundaries[i]
        end = boundaries[i + 1]
        out_path = os.path.join(output_dir, f"{os.path.basename(base)}-{i + 1}{ext}")

        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{start:.6f}",
            "-i", video_path,
            "-t", f"{end - start:.6f}",
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            "-movflags", "+faststart",
            out_path
        ]

        if progress_cb:
            progress_cb(i + 1, total, os.path.basename(out_path))

        subprocess.run(cmd, capture_output=True)

    return total


# ── GUI ──

class App:
    def __init__(self, root):
        self.root = root
        root.title("视频等分切割器")
        root.geometry("520x220")
        root.resizable(False, False)

        pad = {"padx": 12, "pady": 6}

        # 文件选择
        row1 = tk.Frame(root)
        row1.pack(fill="x", **pad)
        tk.Label(row1, text="视频文件：").pack(side="left")
        self.path_var = tk.StringVar()
        tk.Entry(row1, textvariable=self.path_var, width=42).pack(side="left", padx=4)
        tk.Button(row1, text="选择", command=self.browse).pack(side="left")

        # 分割数
        row2 = tk.Frame(root)
        row2.pack(fill="x", **pad)
        tk.Label(row2, text="分割份数：").pack(side="left")
        self.n_var = tk.IntVar(value=3)
        spin = tk.Spinbox(row2, from_=2, to=50, textvariable=self.n_var, width=6)
        spin.pack(side="left", padx=4)

        # 按钮
        row3 = tk.Frame(root)
        row3.pack(fill="x", **pad)
        self.btn = tk.Button(row3, text="开始切割", command=self.run, width=16)
        self.btn.pack(side="left")

        # 进度
        row4 = tk.Frame(root)
        row4.pack(fill="x", **pad)
        self.progress = ttk.Progressbar(row4, length=480, mode="determinate")
        self.progress.pack(fill="x")
        self.status = tk.Label(root, text="", fg="#888")
        self.status.pack(pady=4)

    def browse(self):
        path = filedialog.askopenfilename(
            title="选择视频文件",
            filetypes=[("视频文件", "*.mp4 *.MP4 *.mkv *.avi *.mov *.flv *.wmv"), ("所有文件", "*.*")]
        )
        if path:
            self.path_var.set(path)

    def run(self):
        path = self.path_var.get().strip()
        n = self.n_var.get()
        if not path or not os.path.isfile(path):
            messagebox.showerror("错误", "请选择有效的视频文件")
            return
        if n < 2:
            messagebox.showerror("错误", "分割份数至少为 2")
            return

        self.btn.config(state="disabled")
        self.progress["value"] = 0
        self.status.config(text="正在分析关键帧...")

        def progress_cb(cur, total, name):
            self.progress["value"] = cur / total * 100
            self.status.config(text=f"切割中 ({cur}/{total})：{name}")
            self.root.update_idletasks()

        def work():
            try:
                total = split_video(path, n, progress_cb)
                self.progress["value"] = 100
                self.status.config(text=f"完成！共生成 {total} 个文件")
                messagebox.showinfo("完成", f"已将视频切割为 {total} 份\n保存在原文件同目录")
            except Exception as e:
                self.status.config(text="切割失败")
                messagebox.showerror("错误", str(e))
            finally:
                self.btn.config(state="normal")

        import threading
        threading.Thread(target=work, daemon=True).start()


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
