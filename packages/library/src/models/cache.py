# ────────────────────────────────────────────────────────────────
# cache.py — 服务端内存缓存层，减少 PG 重复查询
# ────────────────────────────────────────────────────────────────
"""
提供三类缓存：
1. 视频列表缓存 — 30 秒 TTL，写操作后自动失效
2. 路径查找索引 — O(1) 路径校验，随视频缓存一起刷新
3. 维表缓存 — 60 秒 TTL，写操作后自动失效

所有缓存均为进程级单例，线程安全。
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Callable

logger = logging.getLogger(__name__)

# ── TTL 配置 ────────────────────────────────────────────────────
CACHE_TTL = int(os.environ.get("CACHE_TTL", "30"))
DIM_CACHE_TTL = int(os.environ.get("DIM_CACHE_TTL", "60"))

# ── 视频列表缓存 ────────────────────────────────────────────────
_videos_lock = threading.Lock()
_videos_cache: list[dict] | None = None
_videos_ts: float = 0.0

# ── 路径索引（从视频列表构建） ───────────────────────────────────
_path_index: set[str] = set()


def get_videos(loader: Callable[[], list[dict]]) -> list[dict]:
    """返回缓存的视频列表。过期则调 loader() 刷新。"""
    global _videos_cache, _videos_ts, _path_index
    now = time.time()
    if _videos_cache is not None and (now - _videos_ts) < CACHE_TTL:
        return _videos_cache
    with _videos_lock:
        # double-check
        now = time.time()
        if _videos_cache is not None and (now - _videos_ts) < CACHE_TTL:
            return _videos_cache
        rows = loader()
        _videos_cache = rows
        _videos_ts = now
        # 重建路径索引
        _path_index.clear()
        for r in rows:
            p = (r.get("path") or "").strip()
            if p:
                _path_index.add(os.path.normpath(p).lower())
        logger.debug("视频缓存已刷新，共 %d 条，路径索引 %d 条", len(rows), len(_path_index))
        return rows


def get_videos_cached() -> list[dict] | None:
    """返回当前缓存（不过期检查），用于写操作前读取。"""
    return _videos_cache


def fill_videos(rows: list[dict]) -> None:
    """手动填充视频缓存和路径索引（用于本地 CSV 读取后同步内存）。"""
    global _videos_cache, _videos_ts, _path_index
    with _videos_lock:
        _videos_cache = rows
        _videos_ts = time.time()
        _path_index.clear()
        for r in rows:
            p = (r.get("path") or "").strip()
            if p:
                _path_index.add(os.path.normpath(p).lower())


def invalidate_videos() -> None:
    """写操作后调用，清除视频缓存和路径索引。"""
    global _videos_cache, _videos_ts, _path_index
    with _videos_lock:
        _videos_cache = None
        _videos_ts = 0.0
        _path_index.clear()
    logger.debug("视频缓存已失效")


def is_registered_path(path: str) -> bool:
    """O(1) 路径校验，基于内存 set。缓存为空时返回 False。"""
    if not path:
        return False
    norm = os.path.normpath(path).lower()
    return norm in _path_index


# ── 维表缓存 ────────────────────────────────────────────────────
_dim_lock = threading.Lock()
_dim_cache: dict[str, tuple[list[dict], float]] = {}


def get_dim(name: str, loader: Callable[[], list[dict]]) -> list[dict]:
    """返回缓存的维表数据。过期则调 loader() 刷新。"""
    now = time.time()
    entry = _dim_cache.get(name)
    if entry is not None:
        rows, ts = entry
        if (now - ts) < DIM_CACHE_TTL:
            return rows
    with _dim_lock:
        # double-check
        entry = _dim_cache.get(name)
        now = time.time()
        if entry is not None:
            rows, ts = entry
            if (now - ts) < DIM_CACHE_TTL:
                return rows
        rows = loader()
        _dim_cache[name] = (rows, now)
        logger.debug("维表缓存已刷新: %s, %d 条", name, len(rows))
        return rows


def get_dim_cached(name: str) -> list[dict] | None:
    """返回当前缓存（不过期检查）。"""
    entry = _dim_cache.get(name)
    if entry is not None:
        return entry[0]
    return None


def invalidate_dim(name: str | None = None) -> None:
    """清除指定维表或全部维表缓存。"""
    with _dim_lock:
        if name is None:
            _dim_cache.clear()
        else:
            _dim_cache.pop(name, None)
    logger.debug("维表缓存已失效: %s", name or "全部")


def invalidate_all() -> None:
    """清除所有缓存（视频 + 维表）。"""
    invalidate_videos()
    invalidate_dim()
