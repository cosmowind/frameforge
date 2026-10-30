"""Upload & Auto-Upload Service

Extracted from src/app.py.
"""

import csv
import glob
import io
import json
import logging
import os
import queue
import re
import requests
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
from datetime import datetime
from typing import Optional

from flask import jsonify

from config import *
from config import USE_PG, DATABASE_DSN

if USE_PG:
    from models.pg_store import (
        get_fieldnames, load_config, read_csv, write_csv,
        _atomic_write_csv, mark_uploaded, check_file, marker_path,
    )
    from models.pg_dim import (
        resolve_dim as _resolve_dim,
        read_dim_rows as _read_dim_rows,
        validate_dim_row as _validate_dim_row,
        atomic_write_dim as _atomic_write_dim,
    )
else:
    from models.csv_store import (
        get_fieldnames, load_config, read_csv, write_csv,
        _atomic_write_csv,
    )
    from services.misc_service import (
        mark_uploaded, check_file, marker_path, has_marker, write_marker,
        cleanup_after_upload,
    )
    from models.dim_registry import (
        resolve_dim as _resolve_dim,
        read_dim_rows as _read_dim_rows,
        validate_dim_row as _validate_dim_row,
        atomic_write_dim as _atomic_write_dim,
    )

from utils.path_utils import extract_date_from_path as _extract_date_from_path
from utils.path_utils import get_hmd_cache_dir as _get_hmd_cache_dir
from utils.path_utils import extract_mmdd_from_path as _extract_mmdd_from_path
from utils.path_utils import should_add_date_prefix as _should_add_date_prefix
from utils.format_utils import fmt_duration as _fmt_duration
from utils.format_utils import parse_duration_to_sec as _parse_duration_to_sec

logger = logging.getLogger(__name__)


def _escape_py_str(s):
    """Escape a string for embedding inside a Python triple-quoted string."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("'", "\\'")


def _translate_zh_to_en(text: str) -> Optional[str]:
    """Translate Chinese text to English."""
    # TODO: implement actual translation
    return None


def _load_env_info(env_id):
    """Load environment info from environments dim table (CSV or PG)."""
    if not env_id:
        return None
    abs_path, schema, key = _resolve_dim("environments")
    rows = _read_dim_rows(abs_path, schema, key, create_if_missing=False)
    if not rows:
        return None
    for r in rows:
        if (r.get(key) or "").strip() == env_id.strip():
            return r
    return None


def _load_recorder_info(recorder_id):
    """Load recorder info from recorders dim table (CSV or PG)."""
    if not recorder_id:
        return None
    abs_path, schema, key = _resolve_dim("recorders")
    rows = _read_dim_rows(abs_path, schema, key, create_if_missing=False)
    if not rows:
        return None
    for r in rows:
        if (r.get(key) or "").strip() == recorder_id.strip():
            return r
    return None


def _load_sd_card_info(device_id):
    """Load SD card info from sd_cards dim table (CSV or PG)."""
    if not device_id:
        return None
    abs_path, schema, key = _resolve_dim("sd_cards")
    rows = _read_dim_rows(abs_path, schema, key, create_if_missing=False)
    if not rows:
        return None
    for r in rows:
        vs = (r.get("volume_serial") or "").strip()
        did = (r.get("device_id") or "").strip()
        if vs == device_id.strip() or did == device_id.strip():
            return r
    return None


def _load_task_info(task_id):
    """Load task info from tasks dim table (CSV or PG)."""
    if not task_id:
        return None
    abs_path, schema, key = _resolve_dim("tasks")
    rows = _read_dim_rows(abs_path, schema, key, create_if_missing=False)
    if not rows:
        return None
    for r in rows:
        if (r.get(key) or "").strip() == task_id.strip():
            return r
    return None


def _is_hmd_session(video_path):
    """Check if a path is a HMD session directory."""
    if not os.path.isdir(video_path):
        return False
    try:
        return any(
            f.endswith('.hmd') or f.endswith('.HMD')
            for f in os.listdir(video_path)
        )
    except (PermissionError, OSError):
        logger.warning(f"_is_hmd_session: 无法读取目录 {video_path}")
        return False


