#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
server.py  —  mcap -> mp4 「浏览器上传 → 云端转码 → 下载」模式

设计要点：
  - 每个访问建一个 job（uuid），工作目录  <MCAP_DATA_ROOT>/jobs/<uuid>/{uploads,out}
  - 后端复用同目录下的 mcap2mp4_app（未修改）：
        parse / compute_new_name / process_session
  - 文件用 multipart 流式写盘（shutil.copyfileobj），不在内存里读整个 mcap
  - 转换在后台线程跑，前端轮询 /api/jobs/{id}/status 拿到实时进度
  - /api/jobs/{id}/files/{name} 下载 mp4，支持 Range，做路径穿越防护
  - 端点列表见 README / 前端 HTML 注释

环境变量：
  HOST              监听地址（默认 0.0.0.0，所有接口）
  PORT              端口（默认 8756）
  MCAP_DATA_ROOT    工作根目录（默认 $TMPDIR 或 /tmp 下的 mcap2mp4_jobs）
  JOB_TTL_HOURS     job 目录过期时间（小时，默认 48；过期可被清理）
  JOB_MAX_KEEP      保留 job 数量上限（默认 50；超出最旧的会被清理）
  MAX_UPLOAD_MB     单文件大小上限 MB（默认 8192；nginx 前端需要更大则改 nginx.conf）
"""
import os
import sys
import json
import time
import uuid
import shutil
import tempfile
import threading
import traceback
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles

# 让 mcap2mp4_app 能被 import（本部署包把它放在与 server.py 同目录）
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import mcap2mp4_app as core  # noqa: E402  复用 parse / compute_new_name / process_session


# ----------------------------- 配置 -----------------------------
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8756"))
JOB_TTL_HOURS = float(os.environ.get("JOB_TTL_HOURS", "48"))
JOB_MAX_KEEP = int(os.environ.get("JOB_MAX_KEEP", "50"))
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "8192"))
DATA_ROOT = Path(os.environ.get("MCAP_DATA_ROOT")
                 or os.path.join(tempfile.gettempdir(), "mcap2mp4_jobs")).resolve()
DATA_ROOT.mkdir(parents=True, exist_ok=True)

ALLOWED_EXT = {".mcap", ".json"}

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("mcap2mp4-web")


# ----------------------------- Job 存储 -----------------------------
class Job:
    """单 job 的内存状态（只追加最近 N 条日志）。"""

    def __init__(self, job_id: str, root: Path):
        self.id = job_id
        self.root = root            # .../jobs/<uuid>
        self.uploads = root / "uploads"
        self.out = root / "out"
        self.lock = threading.Lock()
        self.state = "pending"      # pending | running | done | error
        self.created = time.time()
        self.updated = time.time()
        self.uploaded_files: list[str] = []   # relpath 列表（每个 push 一次成功上传）
        self.uploaded_bytes: int = 0
        self.total = 0              # 转码总 session 数
        self.done = 0
        self.failed = 0
        self.current = ""
        self.results: list[dict] = []
        self.log_lines: list[str] = []
        self.error = ""

    def append_log(self, msg: str, max_lines: int = 500):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        with self.lock:
            self.updated = time.time()
            self.log_lines.append(line)
            if len(self.log_lines) > max_lines:
                del self.log_lines[: len(self.log_lines) - max_lines]
        log.info("[%s] %s", self.id[:8], msg)

    def snap(self) -> dict:
        with self.lock:
            out_dir = self.out
            files = []
            if out_dir.is_dir():
                for p in sorted(out_dir.iterdir()):
                    if p.is_file() and p.suffix.lower() == ".mp4":
                        try:
                            st = p.stat()
                        except OSError:
                            continue
                        files.append({"name": p.name, "size": st.st_size,
                                      "mtime": int(st.st_mtime)})
            return {
                "id": self.id,
                "state": self.state,
                "created": self.created,
                "updated": self.updated,
                "uploaded_files": len(self.uploaded_files),
                "uploaded_bytes": self.uploaded_bytes,
                "total": self.total,
                "done": self.done,
                "failed": self.failed,
                "current": self.current,
                "results": list(self.results),
                "files": files,
                "log": list(self.log_lines[-200:]),
                "error": self.error,
            }


_jobs: dict[str, Job] = {}
_jobs_lock = threading.Lock()


def _gc_jobs():
    """垃圾回收：清理过期 job；保留数量不超过 JOB_MAX_KEEP。"""
    try:
        with _jobs_lock:
            now = time.time()
            # 过期清理
            for jid, j in list(_jobs.items()):
                if j.state in ("pending", "running"):
                    continue
                age_h = (now - j.updated) / 3600
                if age_h > JOB_TTL_HOURS:
                    log.info("GC: ttl expired job=%s age=%.1fh", jid[:8], age_h)
                    try:
                        shutil.rmtree(j.root, ignore_errors=True)
                    except OSError:
                        pass
                    _jobs.pop(jid, None)
            # 数量超限清理（删最旧 finished）
            finished = [(j.updated, jid) for jid, j in _jobs.items()
                        if j.state in ("done", "error")]
            finished.sort()
            while len(finished) + sum(1 for j in _jobs.values()
                                       if j.state in ("pending", "running")) > JOB_MAX_KEEP:
                _, old = finished.pop(0)
                log.info("GC: over-quota job=%s", old[:8])
                try:
                    shutil.rmtree(_jobs[old].root, ignore_errors=True)
                except OSError:
                    pass
                _jobs.pop(old, None)
        # 顺便清理磁盘目录里有但内存里没有的孤立目录
        jobs_dir = DATA_ROOT / "jobs"
        if jobs_dir.is_dir():
            for d in jobs_dir.iterdir():
                if d.is_dir() and d.name not in _jobs:
                    if (time.time() - d.stat().st_mtime) / 3600 > JOB_TTL_HOURS:
                        shutil.rmtree(d, ignore_errors=True)
                        log.info("GC: orphan dir=%s", d.name[:8])
    except Exception:
        log.exception("GC error")


def _new_job() -> Job:
    jid = uuid.uuid4().hex
    jroot = DATA_ROOT / "jobs" / jid
    jroot.mkdir(parents=True, exist_ok=True)
    (jroot / "uploads").mkdir(exist_ok=True)
    (jroot / "out").mkdir(exist_ok=True)
    j = Job(jid, jroot)
    j.append_log(f"job created, root={jroot}")
    with _jobs_lock:
        _jobs[jid] = j
    _gc_jobs()
    return j


def _get_job(jid: str) -> Job:
    if not jid or len(jid) > 64:
        raise HTTPException(400, "bad job id")
    j = _jobs.get(jid)
    if not j:
        # 进程重启后会丢内存；磁盘目录若存在就重建一个只读 view
        root = DATA_ROOT / "jobs" / jid
        if root.is_dir():
            j = Job(jid, root)
            j.state = "error"
            j.error = "进程重启后丢失内存状态，请重新上传并转码。"
            with _jobs_lock:
                _jobs[jid] = j
            return j
        raise HTTPException(404, "job 不存在")
    return j


# ----------------------------- 转换 worker -----------------------------
def _scan_sessions(uploads_dir: Path):
    """枚举含 session.json 或 .mcap 的直接子文件夹。"""
    out = []
    if not uploads_dir.is_dir():
        return out
    for d in sorted(uploads_dir.iterdir()):
        if not d.is_dir():
            continue
        try:
            entries = list(d.iterdir())
        except OSError:
            continue
        has_json = any(p.is_file() and p.name == "session.json" for p in entries)
        has_mcap = any(p.is_file() and p.suffix.lower() == ".mcap" for p in entries)
        if has_json or has_mcap:
            out.append(d)
    return out


def _convert_worker(j: Job):
    """对 uploads 目录跑：重命名 + 转码；产出 mp4 到 out。"""
    try:
        sessions = _scan_sessions(j.uploads)
        with j.lock:
            j.total = len(sessions)
            j.state = "running"
        j.append_log(f"发现 {len(sessions)} 个 session")
        if not sessions:
            j.append_log("没有可处理的 session，结束")
            with j.lock:
                j.state = "done"
                j.updated = time.time()
            return

        tmp_root = tempfile.mkdtemp(prefix=f"job_{j.id[:8]}_")
        try:
            for sd in sessions:
                with j.lock:
                    j.current = sd.name
                # 1) 重命名（复用 compute_new_name + 已命名格式判断）
                if core.RENAMED_RE.match(sd.name):
                    new_dir = sd
                    j.append_log(f"{sd.name} (已是目标格式)")
                else:
                    new_name = core.compute_new_name(str(sd))
                    if not new_name:
                        j.append_log(f"{sd.name}: 无法读 session.json，跳过重命名")
                        new_dir = sd
                    else:
                        new_dir = sd.parent / new_name
                        if new_dir == sd:
                            j.append_log(f"{sd.name} (无需改名)")
                        elif new_dir.exists():
                            j.append_log(f"{sd.name} -> {new_name} (目标已存在，跳过)")
                            new_dir = sd
                        else:
                            sd.rename(new_dir)
                            j.append_log(f"{sd.name} -> {new_name}")
                # 2) 转码（复用 process_session）
                t0 = time.time()
                try:
                    ok = core.process_session(str(new_dir), str(j.out), tmp_root)
                    seconds = round(time.time() - t0, 1)
                    tag = new_dir.name
                    expected = j.out / f"{tag}.mp4"
                    status = "ok" if (ok and expected.is_file()) else "skipped"
                    err = "" if status == "ok" else "无可用 camera/0 帧"
                    with j.lock:
                        if status == "ok":
                            j.done += 1
                        else:
                            j.failed += 1
                        j.results.append({
                            "name": tag, "status": status, "error": err,
                            "seconds": seconds,
                        })
                        j.updated = time.time()
                except Exception as e:
                    seconds = round(time.time() - t0, 1)
                    err = f"{type(e).__name__}: {e}"
                    j.append_log(f"[错误] {new_dir.name}: {err}")
                    with j.lock:
                        j.failed += 1
                        j.results.append({
                            "name": new_dir.name, "status": "error",
                            "error": err, "seconds": seconds,
                        })
                        j.updated = time.time()
                    log.exception("convert error in job=%s sess=%s", j.id[:8], new_dir.name)
        finally:
            shutil.rmtree(tmp_root, ignore_errors=True)

        with j.lock:
            j.state = "done"
            j.current = ""
            j.updated = time.time()
        j.append_log(f"全部完成：成功 {j.done} 个，失败/跳过 {j.failed} 个")
    except Exception as e:
        with j.lock:
            j.state = "error"
            j.error = f"{type(e).__name__}: {e}"
            j.updated = time.time()
        j.append_log(f"[致命] {j.error}")
        log.exception("job=%s fatal", j.id[:8])


# ----------------------------- FastAPI app -----------------------------
app = FastAPI(title="mcap2mp4 web (upload mode)", version="2.0.0",
              docs_url="/api/docs", redoc_url=None)
STATIC_DIR = HERE / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    t0 = time.time()
    resp = await call_next(request)
    if request.url.path.startswith("/api/"):
        try:
            ms = int((time.time() - t0) * 1000)
            log.info("%s %s -> %s (%dms)", request.method, request.url.path,
                     getattr(resp, "status_code", "?"), ms)
        except Exception:
            pass
    return resp


@app.get("/", response_class=HTMLResponse)
def index():
    f = STATIC_DIR / "index.html"
    if not f.is_file():
        return HTMLResponse("<h1>index.html missing</h1>", status_code=500)
    return HTMLResponse(f.read_text(encoding="utf-8"))


@app.get("/api/health")
def health():
    return {"ok": True, "version": app.version, "data_root": str(DATA_ROOT)}


@app.post("/api/jobs")
def create_job():
    j = _new_job()
    return {"id": j.id, "root": str(j.root), "max_upload_mb": MAX_UPLOAD_MB}


@app.get("/api/jobs")
def list_jobs():
    """列出所有 job（只元信息，不返回日志/文件列表，保持精简）。"""
    items = []
    with _jobs_lock:
        for j in _jobs.values():
            items.append({
                "id": j.id,
                "state": j.state,
                "uploaded_files": len(j.uploaded_files),
                "uploaded_bytes": j.uploaded_bytes,
                "total": j.total,
                "done": j.done,
                "failed": j.failed,
                "created": j.created,
                "updated": j.updated,
            })
    items.sort(key=lambda x: x["created"], reverse=True)
    return {"jobs": items, "data_root": str(DATA_ROOT)}


@app.post("/api/jobs/{jid}/upload")
async def upload_file(jid: str, relpath: str = Form(...),
                      file: UploadFile = File(...)):
    """流式接收单个文件，写到 <uploads>/<relpath>。
    relpath 形如 sample_session_00000/ego_0000.mcap，相对 uploads 根；防穿越。
    """
    j = _get_job(jid)
    # 防路径穿越
    rel = relpath.replace("\\", "/").lstrip("/")
    if not rel or rel.startswith("..") or "/../" in ("/" + rel) or "\x00" in rel:
        raise HTTPException(400, "非法的 relpath")
    target = (j.uploads / rel).resolve()
    if j.uploads.resolve() not in target.parents and target != j.uploads.resolve():
        raise HTTPException(400, "非法的 relpath")
    target.parent.mkdir(parents=True, exist_ok=True)

    suffix = target.suffix.lower()
    if suffix and suffix not in ALLOWED_EXT:
        raise HTTPException(400, f"不允许的文件类型: {suffix}")
    # 流式写盘
    bytes_written = 0
    max_bytes = MAX_UPLOAD_MB * 1024 * 1024
    try:
        with open(target, "wb") as fout:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > max_bytes:
                    fout.close()
                    try:
                        target.unlink()
                    except OSError:
                        pass
                    raise HTTPException(413, f"文件超过 {MAX_UPLOAD_MB} MB 上限")
                fout.write(chunk)
    finally:
        await file.close()

    with j.lock:
        if rel not in j.uploaded_files:
            j.uploaded_files.append(rel)
        j.uploaded_bytes += bytes_written
        j.updated = time.time()
    j.append_log(f"uploaded {rel} ({bytes_written} bytes)")
    return {"ok": True, "relpath": rel, "bytes": bytes_written}


@app.post("/api/jobs/{jid}/convert")
def start_convert(jid: str):
    j = _get_job(jid)
    if j.state == "running":
        raise HTTPException(409, "已在转换中")
    j.results.clear()
    j.log_lines.clear()
    j.error = ""
    with j.lock:
        j.state = "pending"
        j.total = j.done = j.failed = 0
        j.current = ""
        j.updated = time.time()
    j.append_log("convert requested")
    th = threading.Thread(target=_convert_worker, args=(j,),
                          name=f"convert-{jid[:8]}", daemon=True)
    th.start()
    return {"ok": True, "id": j.id}


@app.get("/api/jobs/{jid}/status")
def get_status(jid: str):
    j = _get_job(jid)
    return j.snap()


@app.get("/api/jobs/{jid}/files/{name}")
def download_file(jid: str, name: str):
    """下载 mp4。name 必须直接落在 j.out 下（防穿越）。"""
    j = _get_job(jid)
    if not name or "/" in name or "\\" in name or name.startswith("."):
        raise HTTPException(400, "非法的文件名")
    target = (j.out / name).resolve()
    if j.out.resolve() not in target.parents and target != j.out.resolve():
        raise HTTPException(400, "非法的路径")
    if not target.is_file():
        raise HTTPException(404, f"文件不存在: {name}")
    return FileResponse(
        str(target),
        media_type="video/mp4",
        filename=name,
        headers={"Accept-Ranges": "bytes"},
    )


@app.delete("/api/jobs/{jid}")
def delete_job(jid: str):
    """清理一个 job 的 uploads + out + 内存条目。"""
    j = _get_job(jid)
    if j.state == "running":
        raise HTTPException(409, "转码进行中，不能删除")
    try:
        shutil.rmtree(j.root, ignore_errors=True)
    except OSError as e:
        raise HTTPException(500, f"清理失败: {e}")
    with _jobs_lock:
        _jobs.pop(jid, None)
    return {"ok": True}


# 默认 index 路由（static 路径下也兼容）
@app.get("/healthz")
def healthz():
    return "ok"


if __name__ == "__main__":
    import uvicorn
    log.info("starting on %s:%d, DATA_ROOT=%s", HOST, PORT, DATA_ROOT)
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")