"""惰性导入 + 预处理共享状态 — 供所有 service 模块使用，避免循环导入。"""
import json
import os
import sys
import threading
import time

from config import (
    BASE_DIR, _TOOLS_DIR, THUMBNAILS_DIR,
)
from utils.path_utils import get_hmd_cache_dir as _get_hmd_cache_dir
from config import USE_PG
if USE_PG:
    from models.pg_store import read_csv
else:
    from models.csv_store import read_csv


# ── 工具模块惰性导入 ──────────────────────────────────────────────

_tools_cache = {}

def _get_hmd_preprocess():
    """Lazy import hmd_preprocess from tools/."""
    if "hmd_preprocess" not in _tools_cache:
        try:
            if _TOOLS_DIR not in sys.path:
                sys.path.insert(0, _TOOLS_DIR)
            import hmd_preprocess
            _tools_cache["hmd_preprocess"] = hmd_preprocess
        except ImportError as e:
            print(f"[warn] hmd_preprocess not available: {e}", file=sys.stderr)
            _tools_cache["hmd_preprocess"] = None
    return _tools_cache["hmd_preprocess"]


def _get_hmd_fast_preprocess():
    """Lazy import hmd_fast package from tools/."""
    if "hmd_fast_preprocess" not in _tools_cache:
        try:
            _src_dir = os.path.dirname(_TOOLS_DIR)  # src/
            if _src_dir not in sys.path:
                sys.path.insert(0, _src_dir)
            from tools import hmd_fast as _uf
            _tools_cache["hmd_fast_preprocess"] = _uf
        except ImportError as e:
            print(f"[warn] hmd_fast not available: {e}", file=sys.stderr)
            _tools_cache["hmd_fast_preprocess"] = None
    return _tools_cache["hmd_fast_preprocess"]


def _get_video_frames_helper():
    """Lazy import video_frames_helper from utils/."""
    if "video_frames_helper" not in _tools_cache:
        try:
            from utils import video_frames_helper
            _tools_cache["video_frames_helper"] = video_frames_helper
        except ImportError as e:
            print(f"[warn] video_frames_helper not available: {e}", file=sys.stderr)
            _tools_cache["video_frames_helper"] = None
    return _tools_cache["video_frames_helper"]


def _get_device_monitor():
    """Lazy import device_monitor."""
    if "device_monitor" not in _tools_cache:
        try:
            import device_monitor as dm
            _tools_cache["device_monitor"] = dm
        except ImportError as e:
            print(f"[warn] device_monitor not available: {e}", file=sys.stderr)
            _tools_cache["device_monitor"] = None
    return _tools_cache["device_monitor"]


# ── 预处理共享状态 ──────────────────────────────────────────────────

_PREPROCESS_STATUS: dict = {}
_PREPROCESS_LOCK = threading.Lock()


def _update_preprocess_status(path, **kwargs):
    """线程安全更新某个视频的预处理状态。"""
    with _PREPROCESS_LOCK:
        if path not in _PREPROCESS_STATUS:
            _PREPROCESS_STATUS[path] = {}
        _PREPROCESS_STATUS[path].update(kwargs)
        _PREPROCESS_STATUS[path]["updated_at"] = time.time()
