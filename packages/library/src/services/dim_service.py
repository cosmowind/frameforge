"""
维表辅助服务。
提供接入人/设备/任务信息的加载、历史数据迁移、工序翻译、task_id 生成等。
"""

import os
import re
import sys
import time as _time
from config import BASE_DIR, _DIM_REGISTRY, USE_PG
if USE_PG:
    from models.pg_store import read_csv
    from models.pg_dim import (
        read_dim_rows as _read_dim_rows,
        atomic_write_dim as _atomic_write_dim,
        validate_dim_row as _validate_dim_row,
    )
else:
    from models.csv_store import read_csv
    from models.dim_registry import (
        read_dim_rows as _read_dim_rows,
        atomic_write_dim as _atomic_write_dim,
        validate_dim_row as _validate_dim_row,
    )


# ────────────────────────────────────────────────────────────────
# 维表信息加载
# ────────────────────────────────────────────────────────────────

def load_recorder_info(recorder_id):
    """从 recorders.csv 加载单个接入人信息。"""
    spec = _DIM_REGISTRY.get("recorders")
    if not spec:
        return None
    abs_path = os.path.join(BASE_DIR, spec["path"])
    rows = _read_dim_rows(abs_path, spec["schema"], spec["key"],
                          create_if_missing=False)
    if rows is None:
        return None
    for r in rows:
        if r.get("id") == recorder_id:
            return r
    return None


def load_sd_card_info(device_id):
    """从 sd_cards.csv 加载单个 SD 卡/设备信息。"""
    spec = _DIM_REGISTRY.get("sd_cards")
    if not spec:
        return None
    abs_path = os.path.join(BASE_DIR, spec["path"])
    rows = _read_dim_rows(abs_path, spec["schema"], spec["key"],
                          create_if_missing=False)
    if rows is None:
        return None
    for r in rows:
        if r.get("device_id") == device_id:
            return r
    return None


def load_task_info(task_id):
    """从 tasks.csv 加载单个任务信息。"""
    spec = _DIM_REGISTRY.get("tasks")
    if not spec:
        return None
    abs_path = os.path.join(BASE_DIR, spec["path"])
    rows = _read_dim_rows(abs_path, spec["schema"], spec["key"],
                          create_if_missing=False)
    if rows is None:
        return None
    for r in rows:
        if r.get("task_id") == task_id:
            return r
    return None


def load_env_info(env_id):
    """从 environments.csv 加载单个环境信息。"""
    spec = _DIM_REGISTRY.get("environments")
    if not spec:
        return None
    abs_path = os.path.join(BASE_DIR, spec["path"])
    rows = _read_dim_rows(abs_path, spec["schema"], spec["key"],
                          create_if_missing=False)
    if rows is None:
        return None
    for r in rows:
        if r.get("env_id") == env_id:
            return r
    return None


# ────────────────────────────────────────────────────────────────
# 工序翻译
# ────────────────────────────────────────────────────────────────

_CH_RE = re.compile(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]')


def translate_process_to_en(chinese_text: str) -> str:
    """将中文工序文本翻译为英文。

    优先使用 MiniMax API；未配置时使用 Google Translator（需安装 deep-translator）。
    """
    if not chinese_text or not chinese_text.strip():
        return ""
    if all(ord(c) < 128 for c in chinese_text):
        return chinese_text.strip()
    if not _CH_RE.search(chinese_text):
        return chinese_text.strip()

    # ── 优先 MiniMax API ──
    try:
        from config import _MINIMAX_API_KEY as _key, _MINIMAX_URL as _url, _MINIMAX_MODEL as _model
        if _key:
            result = _translate_via_minimax(chinese_text, _key, _url, _model)
            if result:
                return result
    except Exception as e:
        print(f"[translate] MiniMax 翻译异常: {e}", flush=True)

    # ── 备用 Google Translate ──
    last_error = None
    for attempt in range(3):
        try:
            from deep_translator import GoogleTranslator
            t = GoogleTranslator(source='auto', target='en')
            result = t.translate(chinese_text)
            if result and result.strip():
                return result.strip()
        except ImportError:
            stripped = _CH_RE.sub('', chinese_text).strip()
            return stripped
        except Exception as e:
            last_error = e
            if attempt < 2:
                wait = 2 ** attempt
                _time.sleep(wait)
    if last_error:
        print(f"[translate] 工序翻译失败 (3次重试): {last_error}", flush=True)
    return ""


def _translate_via_minimax(text: str, api_key: str, url: str, model: str) -> str:
    """调用 MiniMax API 将中文翻译为英文。"""
    import json as _json
    try:
        payload = _json.dumps({
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a translator. Translate the user's Chinese text to English. Output ONLY the English translation, no explanations."},
                {"role": "user", "content": text}
            ],
            "temperature": 0.3
        }).encode("utf-8")
        import urllib.request
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
        result = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if result and result.strip():
            return result.strip()
    except Exception:
        pass
    return ""


# ────────────────────────────────────────────────────────────────
# 历史数据迁移
# ────────────────────────────────────────────────────────────────

def migrate_recorders_into_recorders():
    """一次性迁移：将 video_manager.csv 中的 recorder_id 导入到 recorders.csv。"""
    rows = read_csv()
    distinct = []
    seen = set()
    for r in rows:
        rec = (r.get("recorder_id") or "").strip()
        if rec and rec not in seen:
            seen.add(rec)
            distinct.append(rec)
    if not distinct:
        return []
    distinct.sort()
    existing = _read_dim_rows(
        os.path.join(BASE_DIR, _DIM_REGISTRY["recorders"]["path"]),
        _DIM_REGISTRY["recorders"]["schema"],
        _DIM_REGISTRY["recorders"]["key"],
        create_if_missing=False,
    ) or []
    existing_ids = {r["id"] for r in existing}
    existing_names = {r["name"] for r in existing}
    added = []
    for idx, name in enumerate(distinct, 1):
        if name in existing_names:
            continue
        base = re.sub(r"[^a-zA-Z0-9_\-]", "", name).lower()
        if not base:
            base = ""
        candidate = base[:16] if base else ""
        if not candidate:
            candidate = f"r{idx:03d}"
        unique = candidate
        suffix = 1
        while unique in existing_ids:
            suffix += 1
            tail = f"_{suffix}"
            unique = (candidate[: 16 - len(tail)] + tail)
        existing_ids.add(unique)
        existing.append({"id": unique, "name": name,
                         "notes": "auto-migrated"})
        added.append({"id": unique, "name": name,
                      "notes": "auto-migrated"})
    if added:
        _atomic_write_dim("recorders",
                          os.path.join(BASE_DIR, _DIM_REGISTRY["recorders"]["path"]),
                          existing, _DIM_REGISTRY["recorders"]["schema"])
    return added


# ────────────────────────────────────────────────────────────────
# 辅助函数
# ────────────────────────────────────────────────────────────────

def resolve_row_range(row_range_str, data_len):
    """解析 'xx-xx' 格式范围字符串为 0-based 索引列表。"""
    if not row_range_str:
        return []
    try:
        parts = row_range_str.strip().split("-")
        if len(parts) != 2:
            return []
        start = int(parts[0].strip()) - 1
        end = int(parts[1].strip()) - 1
        if start < 0 or end < 0 or start > end:
            return []
        end = min(end, data_len - 1)
        return list(range(start, end + 1))
    except (ValueError, IndexError):
        return []


def slugify_segment(s, fallback):
    """生成小写 ASCII slug（中文 → hex hash）。"""
    if not s:
        return ""
    ascii_only = re.sub(r"[^a-zA-Z0-9]", "", s).lower()
    if ascii_only:
        return ascii_only[:6]
    h = 0
    for ch in s.encode("utf-8"):
        h = (h * 31 + ch) & 0xFFFF
    return f"{h:04x}"[:6]


def generate_next_task_id(product, task, tool, process):
    """根据 4 元组 (product, task, tool, process) 生成下一个可用的 task_id。
    
    task_id 格式: product_task+tool_process_NNN
    """
    a = slugify_segment(product, "prod")
    b = (slugify_segment(task, "task") + slugify_segment(tool, ""))[:16]
    c = slugify_segment(process, "")
    if not all([a, b, c]):
        return None, "4 个字段都必填且需含字母或数字"

    spec = _DIM_REGISTRY["tasks"]
    abs_path = os.path.join(BASE_DIR, spec["path"])
    existing_rows = _read_dim_rows(abs_path, spec["schema"], spec["key"],
                                   create_if_missing=False) or []
    existing_ids = {r.get("task_id", "") for r in existing_rows}
    for r in read_csv():
        tid = (r.get("task_id") or "").strip()
        if tid:
            existing_ids.add(tid)

    prefix = f"{a}_{b}_{c}_"
    pattern = re.compile(r"^" + re.escape(prefix) + r"(\d{3})$")
    used_nums = set()
    for tid in existing_ids:
        m = pattern.match(tid)
        if m:
            used_nums.add(int(m.group(1)))
    for n in range(1, 1000):
        if n not in used_nums:
            return prefix + f"{n:03d}", None

    return None, "该 4 元组下已用满 999 个 task_id"
