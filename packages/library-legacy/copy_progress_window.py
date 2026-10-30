"""
复制进度弹窗（multiprocessing 版）
- 将 tkinter 窗口运行在独立进程中，避免 "Tcl_AsyncDelete: async handler deleted by the wrong thread"
- 主进程通过 multiprocessing.Queue 向子进程发送更新指令
"""

import multiprocessing
import threading
import logging
import os
import sys
import time

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 子进程入口：在独立进程中运行 tkinter 窗口
# 这是模块级函数，必须可被 multiprocessing pickle
# ---------------------------------------------------------------------------

def _run_tk_progress_window(queue):
    """在独立进程中运行 tkinter 进度窗口（此为主进程的子进程入口）"""

    import tkinter as tk
    from tkinter import ttk

    class _ProgressWindow:
        def __init__(self):
            self.root = tk.Tk()
            self.root.title("正在复制文件")
            w, h = 420, 190
            self.root.geometry(f"{w}x{h}")
            self.root.resizable(False, False)
            self.root.attributes("-topmost", True)

            # 居中
            self.root.update_idletasks()
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            self.root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

            self.root.protocol("WM_DELETE_WINDOW", lambda: None)

            main_frame = ttk.Frame(self.root, padding=20)
            main_frame.pack(fill=tk.BOTH, expand=True)

            self.info_label = ttk.Label(
                main_frame,
                text="正在复制视频文件，请勿断开设备...",
                font=("Microsoft YaHei", 11),
            )
            self.info_label.pack(pady=(0, 10))

            self.progress = ttk.Progressbar(main_frame, mode="determinate", length=380)
            self.progress.pack(pady=(0, 5))

            self.percent_label = ttk.Label(
                main_frame, text="0%", font=("Microsoft YaHei", 10)
            )
            self.percent_label.pack(pady=(0, 5))

            self.file_label = ttk.Label(
                main_frame, text="准备中...", font=("Microsoft YaHei", 9), foreground="gray"
            )
            self.file_label.pack(pady=(0, 10))

            btn_frame = ttk.Frame(main_frame)
            btn_frame.pack(fill=tk.X)

            self.ok_button = ttk.Button(
                btn_frame, text="我知道了", command=self._close, state=tk.DISABLED
            )
            self.ok_button.pack(side=tk.RIGHT)

            self._closed = False
            self._auto_close_id = None

        def update_progress(self, current, total, filename=""):
            if self._closed:
                return
            percent = (current / total * 100) if total > 0 else 0
            self.progress["value"] = percent
            self.percent_label.config(text=f"{percent:.1f}% ({current}/{total})")
            if filename:
                short = filename if len(filename) < 40 else "..." + filename[-37:]
                self.file_label.config(text=f"正在复制: {short}")
            self.root.update()

        def complete(self, success=True, message=""):
            if self._closed:
                return
            if success:
                self.info_label.config(
                    text="✅ 复制完成！可以安全断开设备连接了。", foreground="green"
                )
                self.progress["value"] = 100
                self.percent_label.config(text="100% (完成)")
                self.file_label.config(text=message or "所有文件已成功复制", foreground="green")
            else:
                self.info_label.config(
                    text="⚠ 复制完成（部分失败）", foreground="orange"
                )
                self.progress["value"] = 100
                self.file_label.config(text=message or "部分文件复制失败，请检查日志", foreground="orange")
            self.ok_button.config(state=tk.NORMAL)
            self.root.update()
            # 5 分钟后自动关闭
            self._auto_close_id = self.root.after(300_000, self._close)

        def close_window(self):
            if self._closed:
                return
            self._close()

        def _close(self):
            if self._closed:
                return
            self._closed = True
            if self._auto_close_id is not None:
                try:
                    self.root.after_cancel(self._auto_close_id)
                except Exception:
                    pass
            try:
                self.root.destroy()
            except Exception:
                pass

    # --- 创建窗口并轮询队列 ---
    window = _ProgressWindow()

    def poll():
        """每隔 200ms 检查队列中的消息"""
        try:
            while True:
                msg = queue.get_nowait()
                typ = msg.get("type", "")
                if typ == "update":
                    window.update_progress(
                        msg["current"], msg["total"], msg.get("filename", "")
                    )
                elif typ == "complete":
                    window.complete(msg.get("success", True), msg.get("message", ""))
                elif typ == "close":
                    window.close_window()
                    return  # 停止轮询
        except Exception:
            pass
        if not window._closed:
            window.root.after(200, poll)

    window.root.after(100, poll)
    window.root.mainloop()


# ---------------------------------------------------------------------------
# 主进程侧管理器
# ---------------------------------------------------------------------------

class CopyProgressManager:
    """复制进度管理器（使用独立进程运行 tkinter）"""

    def __init__(self):
        self._queue = None       # multiprocessing.Queue
        self._process = None     # multiprocessing.Process
        self._lock = threading.Lock()
        self._closed = False

    def start(self):
        """启动进度窗口（仅第一次创建进程，后续复用）"""
        with self._lock:
            if self._closed:
                return
            if self._process and self._process.is_alive():
                return  # 已经在运行
            try:
                ctx = multiprocessing.get_context("spawn")
                self._queue = ctx.Queue()
                self._process = ctx.Process(
                    target=_run_tk_progress_window,
                    args=(self._queue,),
                    daemon=True,
                )
                self._process.start()
                logger.info("进度窗口已启动（独立进程 pid=%d）", self._process.pid)
            except Exception as e:
                logger.warning("无法启动进度窗口进程: %s", e)
                self._queue = None
                self._process = None

    def _send(self, msg):
        """向子进程发送消息（非阻塞）"""
        if self._queue and not self._closed:
            try:
                self._queue.put_nowait(msg)
            except Exception:
                pass

    def update(self, current, total, filename=""):
        """更新进度"""
        self._send({"type": "update", "current": current, "total": total, "filename": filename})

    def complete(self, success=True, message=""):
        """复制完成"""
        self._send({"type": "complete", "success": success, "message": message})

    def device_disconnected(self):
        """设备断开时关闭窗口"""
        self.close()

    def close(self):
        """关闭进度窗口"""
        with self._lock:
            self._closed = True
            # 发送关闭指令
            if self._queue:
                try:
                    self._queue.put_nowait({"type": "close"})
                except Exception:
                    pass
            # 等待子进程退出
            if self._process and self._process.is_alive():
                self._process.join(timeout=3)
                if self._process.is_alive():
                    logger.debug("进度窗口进程未响应，强制终止")
                    self._process.terminate()
                    self._process.join(timeout=1)
            self._queue = None
            self._process = None


# ---------------------------------------------------------------------------
# 全局单例 + 便捷函数（保持 API 兼容）
# ---------------------------------------------------------------------------

_progress_manager = None


def get_progress_manager():
    """获取进度管理器单例"""
    global _progress_manager
    if _progress_manager is None:
        _progress_manager = CopyProgressManager()
    return _progress_manager


def show_copy_progress():
    get_progress_manager().start()


def update_copy_progress(current, total, filename=""):
    get_progress_manager().update(current, total, filename)


def complete_copy_progress(success=True, message=""):
    get_progress_manager().complete(success, message)


def close_copy_progress():
    get_progress_manager().close()


# ---------------------------------------------------------------------------
# 测试
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("测试复制进度窗口（multiprocessing 模式）...")

    manager = get_progress_manager()
    manager.start()

    # 模拟复制进度
    for i in range(1, 11):
        manager.update(i, 10, f"video_{i}.mp4")
        time.sleep(0.3)

    time.sleep(0.5)
    manager.complete(True, "已复制 10 个文件到 /media\\0521")
    print("测试完成！窗口会在 5 分钟后自动关闭，或点「我知道了」手动关闭。")
