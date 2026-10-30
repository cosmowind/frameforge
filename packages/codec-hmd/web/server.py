#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
web/server.py  —  本地 web 端的 mcap -> mp4 转换服务

设计要点：
  - 复用 mcap2mp4_app.py 里的 parse / compute_new_name / process_session / run，
    仅作为模块 import，不复制解析逻辑，也不修改源文件。
  - 用户在网页里填写【服务器端能访问的】输入 / 输出文件夹路径（就像 exe 的命令行参数那样），
    不做浏览器大文件上传 —— 这是一个本地服务。
  - 转换在后台线程跑；前端通过 /api/status 轮询显示进度（处理中/完成/失败）。
  - 输出目录里现成的 mp4 提供：
        /api/files/{name}      下载（Content-Disposition: attachment）
        /api/preview/{name}    HTML5 <video> 预览（Range 支持，Content-Disposition: inline）
    HEVC 浏览器大概率放不了，但下载到本地用播放器看是通的。
"""
import os
import sys
import json
import time
import shutil
import tempfile
import threading
import traceback
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# 把仓库根目录加进 sys.path，让 mcap2mp4_app 能被 import
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import mcap2mp4_app as core  # noqa: E402  复用现有解析/转码逻辑


# ----------------------------- 任务状态（单实例模型） -----------------------------
# 故意做成单 job：避免后台并发把磁盘/IO 吃满。
_job_lock = threading.Lock()
_job = {
    "state": "idle",          # idle | running | done | error
    "input_dir": "",
    "output_dir": "",
    "started_at": 0,
    "finished_at": 0,
    "total": 0,
    "done": 0,
    "failed": 0,
    "current": "",            # 正在处理的 session 子文件夹名
    "results": [],            # [{name, status, output, error, seconds}]
    "log": [],                # 最近若干条日志（前端展示用）
    "error": "",
}


def _append_log(msg: str, max_lines: int = 500) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    _job["log"].append(line)
    if len(_job["log"]) > max_lines:
        del _job["log"][: len(_job["log"]) - max_lines]


def _scan_sessions(input_dir: str):
    """枚举 input_dir 下含 session.json 或 .mcap 的子文件夹。"""
    sessions = []
    for d in sorted(os.listdir(input_dir)):
        full = os.path.join(input_dir, d)
        if not os.path.isdir(full):
            continue
        try:
            entries = os.listdir(full)
        except OSError:
            continue
        has = os.path.isfile(os.path.join(full, 'session.json')) or \
            any(f.lower().endswith('.mcap') for f in entries)
        if has:
            sessions.append(d)
    return sessions


def _job_worker(input_dir: str, output_dir: str):
    """后台线程：遍历 sessions，重命名 + process_session。"""
    try:
        os.makedirs(output_dir, exist_ok=True)
        sessions = _scan_sessions(input_dir)
        _job["total"] = len(sessions)
        _append_log(f"发现 {len(sessions)} 个 session")
        if not sessions:
            _job["state"] = "done"
            _job["finished_at"] = time.time()
            _append_log("没有可处理的 session，结束")
            return

        tmp_root = tempfile.mkdtemp(prefix='mcap2mp4_web_')
        try:
            for d in sessions:
                src = os.path.join(input_dir, d)
                _job["current"] = d

                # 1) 重命名（复用 compute_new_name + 已命名格式判断）
                if core.RENAMED_RE.match(d):
                    new_dir = src
                    _append_log(f"{d} (已是目标格式)")
                else:
                    new_name = core.compute_new_name(src)
                    if not new_name:
                        _append_log(f"{d}: 无法读 session.json，跳过重命名")
                        new_dir = src
                    else:
                        new_dir = os.path.join(input_dir, new_name)
                        if os.path.abspath(new_dir) == os.path.abspath(src):
                            _append_log(f"{d} (无需改名)")
                        elif os.path.exists(new_dir):
                            _append_log(f"{d} -> {new_name} (目标已存在，跳过)")
                            new_dir = src
                        else:
                            os.rename(src, new_dir)
                            _append_log(f"{d} -> {new_name}")

                # 2) 转码（复用 process_session）
                t0 = time.time()
                try:
                    ok = core.process_session(new_dir, output_dir, tmp_root)
                    seconds = round(time.time() - t0, 1)
                    tag = os.path.basename(new_dir.rstrip('\\/'))
                    expected = os.path.join(output_dir, f'{tag}.mp4')
                    if ok and os.path.isfile(expected):
                        _job["results"].append({
                            "name": tag,
                            "status": "ok",
                            "output": expected,
                            "error": "",
                            "seconds": seconds,
                        })
                        _job["done"] += 1
                    else:
                        _job["results"].append({
                            "name": tag,
                            "status": "skipped",
                            "output": expected if os.path.isfile(expected) else "",
                            "error": "无可用 camera/0 帧",
                            "seconds": seconds,
                        })
                        _job["failed"] += 1
                except Exception as e:
                    seconds = round(time.time() - t0, 1)
                    err = f"{type(e).__name__}: {e}"
                    _append_log(f"[错误] {os.path.basename(new_dir)}: {err}")
                    _job["results"].append({
                        "name": os.path.basename(new_dir.rstrip('\\/')),
                        "status": "error",
                        "output": "",
                        "error": err,
                        "seconds": seconds,
                    })
                    _job["failed"] += 1
                    traceback.print_exc()
        finally:
            shutil.rmtree(tmp_root, ignore_errors=True)

        _job["state"] = "done"
        _job["finished_at"] = time.time()
        _append_log(f"全部完成：成功 {_job['done']} 个，失败/跳过 {_job['failed']} 个")
    except Exception as e:
        _job["state"] = "error"
        _job["error"] = f"{type(e).__name__}: {e}"
        _job["finished_at"] = time.time()
        _append_log(f"[致命] {e}")
        traceback.print_exc()


# ----------------------------- FastAPI app -----------------------------
app = FastAPI(title="mcap2mp4 web", version="1.0.0")

WEB_DIR = Path(__file__).resolve().parent
STATIC_DIR = WEB_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
def index():
    """返回内置的单页前端（也可以放 web/static/index.html 覆盖）。"""
    f = STATIC_DIR / "index.html"
    if f.is_file():
        return HTMLResponse(f.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>web/static/index.html missing</h1>", status_code=500)


class ConvertRequest(BaseModel):
    input_dir: str
    output_dir: Optional[str] = None


@app.post("/api/convert")
def api_convert(req: ConvertRequest):
    input_dir = req.input_dir.strip().strip('"').strip("'")
    if not input_dir:
        raise HTTPException(400, "input_dir 不能为空")
    input_dir = os.path.abspath(input_dir)
    if not os.path.isdir(input_dir):
        raise HTTPException(400, f"输入目录不存在: {input_dir}")

    output_dir = (req.output_dir or "").strip().strip('"').strip("'")
    if not output_dir:
        output_dir = os.path.join(input_dir, "_mp4")
    output_dir = os.path.abspath(output_dir)

    with _job_lock:
        if _job["state"] == "running":
            raise HTTPException(409, "已有任务在运行，请先等它完成或刷新页面")
        _job.update({
            "state": "running",
            "input_dir": input_dir,
            "output_dir": output_dir,
            "started_at": time.time(),
            "finished_at": 0,
            "total": 0,
            "done": 0,
            "failed": 0,
            "current": "",
            "results": [],
            "log": [],
            "error": "",
        })
        _append_log(f"任务启动：{input_dir} -> {output_dir}")

    th = threading.Thread(target=_job_worker, args=(input_dir, output_dir),
                          name="mcap2mp4-worker", daemon=True)
    th.start()
    return {"ok": True, "input_dir": input_dir, "output_dir": output_dir}


@app.get("/api/status")
def api_status():
    """前端轮询这个端点拿当前任务进度 + 输出目录里的成品。"""
    with _job_lock:
        snap = dict(_job)
    snap["log"] = list(_job["log"])[-200:]
    # 顺手把当前 output_dir 里已存在的 mp4 也列出来，方便前端先看老产物
    snap["existing_files"] = _list_mp4(snap.get("output_dir", ""))
    return snap


@app.get("/api/outputs")
def api_outputs(dir: str = Query("", description="输出目录绝对路径")):
    """独立列出某个目录里的 mp4（无需任务跑过）。"""
    d = (dir or "").strip().strip('"').strip("'")
    if not d:
        return {"dir": "", "files": []}
    d = os.path.abspath(d)
    return {"dir": d, "files": _list_mp4(d)}


def _list_mp4(dir_path: str):
    if not dir_path or not os.path.isdir(dir_path):
        return []
    items = []
    try:
        for name in sorted(os.listdir(dir_path)):
            if not name.lower().endswith('.mp4'):
                continue
            full = os.path.join(dir_path, name)
            try:
                st = os.stat(full)
            except OSError:
                continue
            items.append({
                "name": name,
                "path": full,
                "size": st.st_size,
                "mtime": int(st.st_mtime),
            })
    except OSError as e:
        return {"error": str(e)}
    return items


def _safe_resolve(output_dir: str, name: str) -> str:
    """防止路径穿越：name 必须是 output_dir 直接子项。"""
    # 取当前任务 output_dir（或参数指定）
    base = output_dir or _job.get("output_dir", "")
    base = os.path.abspath(base)
    target = os.path.abspath(os.path.join(base, name))
    if os.path.commonpath([base, target]) != base:
        raise HTTPException(400, "非法的文件名")
    if not os.path.isfile(target):
        raise HTTPException(404, f"文件不存在: {name}")
    return target


@app.get("/api/files/{name}")
def api_download(name: str):
    """下载端点：返回 mp4，触发浏览器下载。"""
    target = _safe_resolve(_job.get("output_dir", ""), name)
    return FileResponse(
        target,
        media_type="video/mp4",
        filename=name,
        headers={"Accept-Ranges": "bytes"},
    )


@app.get("/api/preview/{name}")
def api_preview(name: str):
    """预览端点：HTML5 <video> 用，Content-Disposition: inline。
    FastAPI 的 FileResponse 已自动支持 HTTP Range，可流式 seek。"""
    target = _safe_resolve(_job.get("output_dir", ""), name)
    return FileResponse(
        target,
        media_type="video/mp4",
        headers={
            "Accept-Ranges": "bytes",
            "Content-Disposition": f'inline; filename="{name}"',
        },
    )


@app.post("/api/reset")
def api_reset():
    """清空当前 job 状态。正在跑的任务不会被中断（daemon 线程）。"""
    with _job_lock:
        if _job["state"] == "running":
            raise HTTPException(409, "任务进行中，不能 reset")
        _job.update({
            "state": "idle", "input_dir": "", "output_dir": "",
            "started_at": 0, "finished_at": 0,
            "total": 0, "done": 0, "failed": 0,
            "current": "", "results": [], "log": [], "error": "",
        })
    return {"ok": True}


@app.get("/api/health")
def api_health():
    return {"ok": True, "version": app.version}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8756"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")