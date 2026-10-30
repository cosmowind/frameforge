#!/usr/bin/env python
"""Path utilities, decode, and transcode operations for HMD preprocessing.

Extracted from hmd_preprocess.py to keep the module focused:
  - Path/cache helpers:  _project_root, get_cache_root, _extract_date_from_path,
    get_output_dir, get_status_path, get_mp4_path, get_h265_path
  - Status I/O:          _get_folder_lock, write_status
  - Parts / check:       list_parts, check_done, _both_eyes
  - Decode:              run_python_decode, run_node_decode
  - Transcode:           ffmpeg_to_mp4, ffmpeg_to_h264_mp4
"""
import sys
import os
import json
import time
import subprocess
import threading
import glob
import re

STATUS_FILE = ".hmd_process.json"
FRAME_RATE = 30  # splitStereo output per-eye frame rate

# ── Output location ──────────────────────────────────────────────
# CACHE_ROOT is resolved lazily so this module can be imported from
# anywhere (Flask app, CLI, tests). Override with env HMD_CACHE_ROOT.
# Default: <project>/hmd_cache/  (i.e. <video-sort-package>/hmd_cache/)
def _project_root():
    """Return the video-sort-package project root (parent of src/)."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_cache_root():
    return os.environ.get("HMD_CACHE_ROOT") or os.path.join(_project_root(), "runtime", "hmd_cache")


def _extract_date_from_path(path):
    """从源路径中提取日期目录名 (MMDD 格式)，返回 'YYYY-MM-DD' 或 'unknown'。

    路径示例: /media\\0619\\hmd\\4aa45c_session_00000 → '2026-06-19'
    策略: 从路径中查找第一个 4 位数字的目录名作为日期。
    """
    import datetime as _dt
    parts = os.path.normpath(path).split(os.sep)
    for part in reversed(parts):
        if len(part) == 4 and part.isdigit():
            month = part[:2]
            day = part[2:]
            year = _dt.datetime.now().year
            return f"{year}-{month}-{day}"
    return "unknown"


def get_output_dir(source_folder):
    """Cache directory: <CACHE_ROOT>/<date>/<session_basename>/

    使用日期前缀避免不同日期同名 session 的文件覆盖问题。
    """
    date_key = _extract_date_from_path(source_folder)
    basename = os.path.basename(os.path.normpath(source_folder))
    return os.path.join(get_cache_root(), date_key, basename)

def get_status_path(source_folder):
    return os.path.join(get_output_dir(source_folder), STATUS_FILE)

def get_mp4_path(source_folder, eye):
    assert eye in ("left", "right"), eye
    session_basename = os.path.basename(os.path.normpath(source_folder))
    basename = f"{session_basename}_right" if eye == "right" else session_basename
    new_path = os.path.join(get_output_dir(source_folder), f"{basename}.mp4")
    old_path = os.path.join(get_output_dir(source_folder), f"{eye}.mp4")
    # 兼容旧命名：旧文件存在且新文件不存在时返回旧路径
    if os.path.isfile(old_path) and not os.path.isfile(new_path):
        return old_path
    return new_path

def get_h265_path(source_folder, eye):
    assert eye in ("left", "right"), eye
    session_basename = os.path.basename(os.path.normpath(source_folder))
    basename = f"{session_basename}_right" if eye == "right" else session_basename
    new_path = os.path.join(get_output_dir(source_folder), f"{basename}.h265")
    old_path = os.path.join(get_output_dir(source_folder), f"{eye}.h265")
    # 兼容旧命名
    if os.path.isfile(old_path) and not os.path.isfile(new_path):
        return old_path
    return new_path

# Per-folder lock to prevent concurrent .tmp → .json replace collisions on Windows
_folder_locks = {}
_folder_locks_lock = threading.Lock()

def _get_folder_lock(folder):
    with _folder_locks_lock:
        if folder not in _folder_locks:
            _folder_locks[folder] = threading.Lock()
        return _folder_locks[folder]

def write_status(folder, status):
    """Atomically write status JSON for the API to poll.
    Uses a per-folder lock to avoid WinError 32 when multiple threads
    write status for the same folder concurrently."""
    path = get_status_path(folder)
    os.makedirs(get_output_dir(folder), exist_ok=True)
    lock = _get_folder_lock(folder)
    with lock:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(status, f, ensure_ascii=False, indent=2)
        # On Windows, os.replace may fail if another thread holds a handle;
        # retry a few times with short sleep.
        for attempt in range(5):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                time.sleep(0.1 * (attempt + 1))
        # Final attempt: fall back to direct write (non-atomic but better than crash)
        try:
            os.unlink(tmp)
        except OSError:
            pass
        with open(path, "w", encoding="utf-8") as f:
            json.dump(status, f, ensure_ascii=False, indent=2)


def list_parts(folder):
    return sorted(glob.glob(os.path.join(folder, "part_*.hmd")))


def check_done(folder):
    """Done = left.mp4 exists. (Right.mp4 only generated when HMD_PROCESS_BOTH_EYES=1.)"""
    return os.path.isfile(get_mp4_path(folder, "left"))


def _both_eyes():
    """Whether to also produce right.mp4. Default: off (speed)."""
    return os.environ.get("HMD_PROCESS_BOTH_EYES", "").strip() in ("1", "true", "yes")


def run_python_decode(parts, out_left_h265, out_right_h265, status_cb):
    """Pure-Python HMD decoder (bypasses Node.js memory limit).
    Calls tools/hmd_decode_py.py as a subprocess.
    Reports progress via status_cb.
    Returns (left_frames, right_frames).
    """
    import tempfile, json
    parts_json = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8')
    json.dump(parts, parts_json)
    parts_json.close()
    parts_file = parts_json.name

    # Build command: python hmd_decode_py.py <left_out> [right_out] part1 part2 ...
    script = os.path.join(os.path.dirname(__file__), "hmd_decode_py.py")
    cmd = [sys.executable, script, out_left_h265]
    if out_right_h265:
        cmd.append(out_right_h265)
    cmd.extend(parts)

    env = os.environ.copy()
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace", env=env
    )
    try:
        last_progress = 0
        for line in proc.stdout:
            line = line.strip()
            m = re.match(r"PROGRESS:([\d.]+)", line)
            if m:
                pct = float(m.group(1))
                if pct > last_progress:
                    last_progress = pct
                    status_cb({"progress": pct, "stage": "py-decode+split"})
            elif line.startswith("DONE:"):
                parts = line[5:].split(":")
                return int(parts[0]), int(parts[1])
        proc.wait()
        if proc.returncode != 0:
            stderr = proc.stderr.read()
            raise RuntimeError(f"Python decode failed (exit {proc.returncode}): {stderr[:500]}")
        raise RuntimeError("Python decode completed without DONE marker")
    finally:
        try: os.unlink(parts_file)
        except Exception: pass


def run_node_decode(parts, out_left_h265, out_right_h265, status_cb):
    """Invoke hmd-decode.js via Node to produce left.h265 (and right.h265 if requested).

    Writes parts list to a temp JSON file (paths only) and passes that file
    as argv[3] so Node doesn't try to require() a piped string.

    When `out_right_h265` is None, only the left eye is decoded (saves ~50% time).
    """
    # Search order: bundled .cjs → bundled .esm.js → external codec-hmd
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "static", "hmd", "hmd-decode.cjs"),
        os.path.join(os.path.dirname(__file__), "..", "static", "hmd", "hmd-decode.esm.js"),
        os.path.join(os.path.dirname(__file__), "..", "..", "codec-hmd", "hmd-decode.js"),
    ]
    hmd_decode_js = next((c for c in candidates if os.path.isfile(c)), None)
    if not hmd_decode_js:
        raise FileNotFoundError(f"hmd-decode.js not found, tried: {candidates}")

    # Pass parts via a temp JSON file (env var HMD_PARTS_FILE) so we don't
    # depend on process.argv indexing (which differs between `node -e` modes).
    import tempfile, json as _json
    parts_json = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8')
    _json.dump(parts, parts_json)
    parts_json.close()
    parts_file = parts_json.name

    # Determine if the module is ESM (.esm.js) or CJS (.cjs / .js without export).
    # ESM modules use `export` syntax and must be loaded via dynamic import().
    is_esm = os.path.basename(hmd_decode_js).endswith(".esm.js")

    # Write a temporary script file (avoids `node -e` argv quirks).
    # NOTE: in the f-string below, every '\\n' becomes '\n' in the .js file.
    # When rightOut is empty string, we skip writing right.h265.
    if is_esm:
        # ESM loader script: must itself be ESM so import() works.
        # We use .mjs extension so Node treats it as ESM module.
        script_text = (
            "import fs from 'fs';\n"
            "import { createRequire } from 'module';\n"
            "const require = createRequire(import.meta.url);\n"
            "const parts = JSON.parse(fs.readFileSync(process.env.HMD_PARTS_FILE, 'utf-8'))\n"
            "  .map(p => new Uint8Array(fs.readFileSync(p)));\n"
            "const leftOut = process.env.HMD_LEFT_OUT;\n"
            "const rightOut = process.env.HMD_RIGHT_OUT;\n"
            "const { parse, splitStereo, dedupParamSets } = await import(" + _json.dumps(hmd_decode_js) + ");\n"
            "const r = await parse(parts, { onProgress: pct =>\n"
            "  process.stdout.write('PROGRESS:' + (pct*100).toFixed(1) + '\\n') });\n"
            "const hevc = dedupParamSets(r.video[0].hevc);\n"
            "process.stdout.write('PROGRESS:90\\n');\n"
            "const stereo = splitStereo(hevc);\n"
            "process.stdout.write('PROGRESS:95\\n');\n"
            "fs.writeFileSync(leftOut, stereo.left);\n"
            "if (rightOut) {\n"
            "  fs.writeFileSync(rightOut, stereo.right);\n"
            "  process.stdout.write('PROGRESS:100\\nDONE:' + stereo.stats.leftFrames + ':' + stereo.stats.rightFrames + '\\n');\n"
            "} else {\n"
            "  process.stdout.write('PROGRESS:100\\nDONE:' + stereo.stats.leftFrames + ':0\\n');\n"
            "}\n"
        )
        script_file = tempfile.NamedTemporaryFile(mode='w', suffix='.mjs', delete=False, encoding='utf-8')
        script_file.write(script_text)
        script_file.close()
    else:
        # CJS: require() the module.  The bundled hmd-decode.cjs wrapper
        # uses dynamic import() to bridge to .esm.js, so its exported methods
        # are async (each internally awaits the ESM load).
        # Runtime guard: if require() returns a function (legacy init-only wrapper),
        # call await hmdDecode() to get the real module object; otherwise use it
        # directly (async-wrapper object pattern).
        script_text = (
            "const _raw = require(" + _json.dumps(hmd_decode_js) + ");\n"
            "const fs = require('fs');\n"
            "const parts = JSON.parse(fs.readFileSync(process.env.HMD_PARTS_FILE, 'utf-8'))\n"
            "  .map(p => new Uint8Array(fs.readFileSync(p)));\n"
            "const leftOut = process.env.HMD_LEFT_OUT;\n"
            "const rightOut = process.env.HMD_RIGHT_OUT;\n"
            "(async () => {\n"
            "  // If _raw is a function (init wrapper), call it to get the module;\n"
            "  // otherwise it's already the async-methods object.\n"
            "  const mod = typeof _raw === 'function' ? await _raw() : _raw;\n"
            "  const { parse, splitStereo, dedupParamSets } = mod;\n"
            "  const r = await parse(parts, { onProgress: pct =>\n"
            "    process.stdout.write('PROGRESS:' + (pct*100).toFixed(1) + '\\n') });\n"
            "  const hevc = await dedupParamSets(r.video[0].hevc);\n"
            "  process.stdout.write('PROGRESS:90\\n');\n"
            "  const stereo = await splitStereo(hevc);\n"
            "  process.stdout.write('PROGRESS:95\\n');\n"
            "  fs.writeFileSync(leftOut, stereo.left);\n"
            "  if (rightOut) {\n"
            "    fs.writeFileSync(rightOut, stereo.right);\n"
            "    process.stdout.write('PROGRESS:100\\nDONE:' + stereo.stats.leftFrames + ':' + stereo.stats.rightFrames + '\\n');\n"
            "  } else {\n"
            "    process.stdout.write('PROGRESS:100\\nDONE:' + stereo.stats.leftFrames + ':0\\n');\n"
            "  }\n"
            "})().catch(e => { console.error(e); process.exit(1); });\n"
        )
        script_file = tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8')
        script_file.write(script_text)
        script_file.close()

    env = os.environ.copy()
    env["HMD_PARTS_FILE"] = parts_file
    env["HMD_LEFT_OUT"] = out_left_h265
    env["HMD_RIGHT_OUT"] = out_right_h265 or ""
    # Increase Node.js memory limit to avoid Array buffer allocation failed
    # for large HMD sessions (default ~1.5GB is often insufficient)
    # Each part_*.hmd is ~256MB; a 31-part session = ~7.9GB raw data.
    # ArrayBuffer allocation happens in V8's C++ heap (not old-space), so
    # we need both --max-old-space-size AND sufficient system RAM.
    # Default raised to 32GB; override via env HMD_NODE_MEM (MB).
    node_mem = os.environ.get("HMD_NODE_MEM", "32768")
    cmd = ["node", f"--max-old-space-size={node_mem}", script_file.name]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace", env=env)
    try:
        last_progress = 0
        for line in proc.stdout:
            line = line.strip()
            m = re.match(r"PROGRESS:([\d.]+)", line)
            if m:
                pct = float(m.group(1))
                if pct > last_progress:
                    last_progress = pct
                    status_cb({"progress": pct, "stage": "decode+split"})
            elif line.startswith("DONE:"):
                l, r = line[5:].split(":")
                return int(l), int(r)
        proc.wait()
        if proc.returncode != 0:
            stderr = proc.stderr.read()
            raise RuntimeError(f"Node decode failed (exit {proc.returncode}): {stderr}")
        raise RuntimeError("Node decode completed without DONE marker")
    finally:
        try: os.unlink(parts_file)
        except Exception: pass
        try: os.unlink(script_file.name)
        except Exception: pass


def ffmpeg_to_mp4(h265_path, mp4_path):
    """Remux H.265 raw stream into MP4 container (stream copy, no re-encode).
    Preview is played in local video player (outside browser), which supports HEVC natively."""
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-i", h265_path,
        "-c:v", "copy", "-tag:v", "hvc1", "-f", "mp4", "-movflags", "+faststart",
        mp4_path
    ]
    p = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                       text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg MP4 failed: {p.stderr[-500:]}")


def ffmpeg_to_h264_mp4(h265_path, mp4_path):
    """Re-encode H.265 to H.264 (AVC) for broad browser compatibility.
    Kept for future use when browser playback is needed."""
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-i", h265_path,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-f", "mp4", "-movflags", "+faststart",
        mp4_path
    ]
    p = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                       text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg H.264 failed: {p.stderr[-500:]}")
