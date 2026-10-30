import os
import json
import glob
import re
import shutil
from datetime import datetime
from typing import Optional, Dict, List, Any
from config import *


def _load_task_info(task_id: str) -> Optional[dict]:
    """从 tasks.csv 加载任务信息，用于上传模板填充。"""
    abs_path, schema, key = _resolve_dim("tasks")
    if not abs_path:
        return None
    rows = _read_dim_rows(abs_path, schema, key, create_if_missing=False)
    if not rows:
        return None
    for r in rows:
        if r.get("task_id", "").strip() == task_id.strip():
            return r
    return None


