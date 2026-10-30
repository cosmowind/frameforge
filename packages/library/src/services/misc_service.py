import logging
import os
import json
import glob
import shutil
import subprocess
import threading
import time
from datetime import datetime
from typing import Optional
from config import *
from config import USE_PG, DATABASE_DSN

logger = logging.getLogger(__name__)
_AUTOFILL_CLIPBOARD_PATH = os.path.join(RUNTIME_DIR, "data", "_autofill_clipboard.json")

def get_fieldnames_cached():
    return get_fieldnames()



def _get_fieldnames():
    return get_fieldnames()


# ── 以下函数已迁移至 models/pg_store.py / csv_store.py，此处保留空壳以兼容旧引用 ──


def read_csv():
    raise RuntimeError("read_csv 已迁移，请通过 models.pg_store / csv_store 调用")



def write_csv(rows):
    raise RuntimeError("write_csv 已迁移，请通过 models.pg_store / csv_store 调用")



def mark_uploaded(csv_index):
    raise RuntimeError("mark_uploaded 已迁移，请通过 models.pg_store / csv_store 调用")



def check_file(video_path):
    raise RuntimeError("check_file 已迁移，请通过 models.pg_store / csv_store 调用")



def marker_path(video_path):
    raise RuntimeError("marker_path 已迁移，请通过 models.pg_store / csv_store 调用")



def has_marker(video_path):
    """Check if the marker file exists, indicating the video was already uploaded."""
    return os.path.isfile(marker_path(video_path))



def write_marker(video_path):
    """Write a marker file to record that this video has been uploaded."""
    with open(marker_path(video_path), "w") as f:
        f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))



def _extract_date(vpath):
    """Extract MMDD date from path, returns YYYY-MM-DD or 'unknown'."""
    parts = os.path.normpath(vpath).split(os.sep)
    for part in reversed(parts):
        if len(part) == 4 and part.isdigit():
            m, d = part[:2], part[2:]
            return f"{{datetime.now().year}}-{{m}}-{{d}}"
    return "unknown"



def cleanup_after_upload(video_path):
    """Delete local files after upload: HMD sources + preview videos + frames + thumbnails.
    Keeps cover.jpg."""
    if not DELETE_AFTER:
        return

    date_key = _extract_date(video_path)
    session_name = os.path.basename(video_path.rstrip("\\\\/"))
    deleted_total = 0

    # 1) Delete HMD source files
    if os.path.isdir(video_path):
        try:
            for fname in os.listdir(video_path):
                if fname.lower().endswith(".hmd") or fname == "metadata.json":
                    fp = os.path.join(video_path, fname)
                    try:
                        size = os.path.getsize(fp)
                        os.remove(fp)
                        deleted_total += size
                        tee_print(f"    🧹 已删除: {{fname}} ({{size/1024/1024:.1f}} MB)")
                    except Exception as ex:
                        tee_print(f"    ⚠ 删除 {{fname}} 失败: {{ex}}")
            try:
                if not os.listdir(video_path):
                    os.rmdir(video_path)
                    tee_print(f"    🧹 已删除空目录: {{session_name}}")
            except Exception:
                pass
        except Exception as ex:
            tee_print(f"    ⚠ 清理源文件失败: {{ex}}")

    # 2) Delete preview videos in hmd_cache (keep cover.jpg)
    cache_dir = os.path.join(RUNTIME_DIR, "hmd_cache", date_key, session_name)
    if os.path.isdir(cache_dir):
        # 新旧命名兼容
        _sn = session_name
        _all_vf = (f"{_sn}.mp4", f"{_sn}_right.mp4", f"{_sn}.h265", f"{_sn}_right.h265",
                    "left.mp4", "right.mp4", "left.h265", "right.h265")
        for vf in _all_vf:
            vp = os.path.join(cache_dir, vf)
            if os.path.isfile(vp):
                try:
                    size = os.path.getsize(vp)
                    os.remove(vp)
                    deleted_total += size
                    tee_print(f"    🧹 已删除预览: {{vf}} ({{size/1024/1024:.1f}} MB)")
                except Exception as ex:
                    tee_print(f"    ⚠ 删除 {{vf}} 失败: {{ex}}")

        # 3) Delete preview frames
        frames_dir = os.path.join(cache_dir, "frames")
        if os.path.isdir(frames_dir):
            try:
                cnt = 0
                for f in os.listdir(frames_dir):
                    if f.lower().endswith(".jpg"):
                        fp = os.path.join(frames_dir, f)
                        size = os.path.getsize(fp)
                        os.remove(fp)
                        deleted_total += size
                        cnt += 1
                if cnt:
                    tee_print(f"    🧹 已删除预览帧: {{cnt}} 个文件")
            except Exception as ex:
                tee_print(f"    ⚠ 清理帧文件失败: {{ex}}")

    # 4) Delete thumbnails
    thumb_dir = os.path.join(RUNTIME_DIR, "thumbnails")
    if os.path.isdir(thumb_dir):
        for pat in (f"{{session_name}}_*.jpg", f"{{session_name}}_*.png"):
            for thumb in _glob.glob(os.path.join(thumb_dir, pat)):
                try:
                    size = os.path.getsize(thumb)
                    os.remove(thumb)
                    deleted_total += size
                    tee_print(f"    🧹 已删除缩略图: {{os.path.basename(thumb)}}")
                except Exception as ex:
                    tee_print(f"    ⚠ 删除缩略图失败: {{ex}}")

    if deleted_total > 0:
        tee_print(f"    ✓ 已释放 {{deleted_total/1024/1024:.1f}} MB")
def _load_upload_template_config():
    """Load user-customized upload template defaults from config.json, if present."""
    cfg = load_config()
    ut = cfg.get("uploadTemplate", {})
    merged = dict(UPLOAD_TEMPLATE_DEFAULTS)
    merged.update(ut)
    return merged



def _save_upload_template_config(data: dict):
    """Save upload template defaults to config.json."""
    cfg = load_config()
    cfg["uploadTemplate"] = data
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ── 中译英缓存（用于上传模板 Task Description 字段）──
_TRANSLATION_CACHE: dict = {}



def _translate_zh_to_en(text: str) -> Optional[str]:
    """将中文文本翻译为英文，带内存缓存。失败返回 None。"""
    import re
    if not text or not text.strip():
        return None
    # 检测是否含中文
    if not re.search(r'[\u4e00-\u9fff]', text):
        return None
    cache_key = text.strip()[:200]
    if cache_key in _TRANSLATION_CACHE:
        return _TRANSLATION_CACHE[cache_key]
    try:
        from deep_translator import GoogleTranslator
        translator = GoogleTranslator(source="zh-CN", target="en")
        result = translator.translate(cache_key)
        _TRANSLATION_CACHE[cache_key] = result
        return result
    except Exception:
        return None



def _load_env_info(env_id):
    """从 environments.csv 加载单个环境信息。"""
    spec = _DIM_REGISTRY.get("environments")
    if not spec:
        return None
    abs_path = spec["path"]
    rows = _read_dim_rows(abs_path, spec["schema"], spec["key"], create_if_missing=False)
    if rows is None:
        return None
    for r in rows:
        if r.get("env_id") == env_id:
            return r
    return None



def _read_clipboard() -> dict:
    """读取全局 autofill clipboard。"""
    if not os.path.exists(_AUTOFILL_CLIPBOARD_PATH):
        return {"operator_name": "", "task_description": "",
                "environment_description": "", "updated_at": ""}
    try:
        with open(_AUTOFILL_CLIPBOARD_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"operator_name": "", "task_description": "",
                "environment_description": "", "updated_at": ""}



def _write_clipboard(payload: dict) -> dict:
    """写入全局 autofill clipboard。"""
    cleaned = {
        "operator_name": (payload.get("operator_name") or "").strip(),
        "task_description": (payload.get("task_description") or "").strip(),
        "environment_description": (payload.get("environment_description") or "").strip(),
        "device_id": (payload.get("device_id") or "").strip(),
        "source": (payload.get("source") or "").strip(),  # 哪个维表行触发的
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    os.makedirs(os.path.dirname(_AUTOFILL_CLIPBOARD_PATH), exist_ok=True)
    # 原子写入：先写 .tmp 再 os.replace
    tmp = _AUTOFILL_CLIPBOARD_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _AUTOFILL_CLIPBOARD_PATH)
    return cleaned



def _slugify_segment(s, fallback):
    """Make a lowercase ASCII slug from one Chinese/English word.
    Strategy: keep ASCII alnum, lowercase. Strip everything else.
    Chinese characters fall back to a stable short hex hash."""
    if not s:
        return ""
    # Pure ASCII → just lowercase + strip non-alnum
    ascii_only = re.sub(r"[^a-zA-Z0-9]", "", s).lower()
    if ascii_only:
        return ascii_only[:6]  # 每个段最多 6 字符，避免 task_id 超长
    # 纯中文 → 用 unicode 码点哈希生成稳定短码（不依赖外部库）
    h = 0
    for ch in s.encode("utf-8"):
        h = (h * 31 + ch) & 0xFFFF
    # 用纯 hex（a-f + 0-9）— 与 [a-z0-9]+ 匹配，无需 'x' 前缀
    return f"{h:04x}"[:6]





def _extract_date_from_path(path: str) -> str:
    """从路径中提取 MMDD 日期，返回 YYYY-MM-DD 格式。"""
    parts = os.path.normpath(path).split(os.sep)
    for part in reversed(parts):
        if len(part) == 4 and part.isdigit():
            month = part[:2]
            day = part[2:]
            year = datetime.now().year
            return f"{year}-{month}-{day}"
    return "unknown"


