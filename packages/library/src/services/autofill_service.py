"""
autofill_service.py — 视频补录参数助手（核心匹配/补全服务）

业务场景：
  用户在 publish.example.com 上传页面手填 3 个 free-text 字段：
    1. operator-name           （录入员 ID/匿名代码，如 "op1"）
    2. task-description        （工序文字，如 "faucet assembly"）
    3. environment-description （环境描述，如 "faucet factory workshop"）
  本服务用这 3 个字段到 4 个维表（recorders / sd_cards / tasks / environments）里
  查匹配记录，输出可填到 publish.example.com 表单的完整字段集合。

匹配策略（按优先级，回退链）：
  - operator_name  → recorders.id 精确 → name 精确 → name 包含（忽略大小写）
  - task_desc      → tasks.process / process_en / task / product 精确
                      → 包含（中文走 substr，英文走 lower-contains）
  - env_desc       → environments.environment_description / environment_description_en
                      精确 → 包含
  - device_id      → sd_cards.volume_serial / device_id 精确（用户提供）

未匹配的字段会出现在响应里的 `unmatched` 列表，UI 提示用户去维表管理
（POST /api/dim/tasks 或 /api/dim/environments）添加新记录。
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable

from config import _DIM_REGISTRY, USE_PG
from models import cache as _cache
if USE_PG:
    from models.pg_store import read_csv
    from models.pg_dim import read_dim_rows as _read_dim_rows
else:
    from models.csv_store import read_csv
    from models.dim_registry import read_dim_rows as _read_dim_rows


def _load_dim(name: str) -> list[dict]:
    """读全表，使用统一缓存层。"""
    spec = _DIM_REGISTRY.get(name)
    if not spec:
        return []
    # pg_dim.read_dim_rows 已内置缓存，此处直接调用即可
    return _read_dim_rows(spec["path"], spec["schema"], spec["key"],
                          create_if_missing=False) or []


def invalidate_cache(name: str | None = None) -> None:
    """清缓存（CRUD 后调用）。委托给统一缓存层。"""
    _cache.invalidate_dim(name)


# ── 匹配工具 ──

def _norm(s: str) -> str:
    """大小写无关 + 去空格 + 兼容全/半角括号。"""
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", str(s)).strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def _match_exact(rows: Iterable[dict], field: str, value: str) -> dict | None:
    target = _norm(value)
    if not target:
        return None
    for r in rows:
        if _norm(r.get(field, "")) == target:
            return r
    return None


def _match_contains(rows: Iterable[dict], fields: list[str], value: str) -> dict | None:
    """在多个字段中找第一条包含 value 的记录。"""
    target = _norm(value)
    if not target:
        return None
    # 第一次扫描：value 是行字段的子串（用于 "faucet assembly" → process_en 含 "faucet"）
    for r in rows:
        for f in fields:
            cell = _norm(r.get(f, ""))
            if cell and (target in cell or cell in target):
                return r
    return None


# ── 公开匹配函数 ──

def match_recorder(operator_name: str) -> dict | None:
    """按 id 或 name 匹配录入员。"""
    rows = _load_dim("recorders")
    if not operator_name:
        return None
    # 1) id 精确
    hit = _match_exact(rows, "id", operator_name)
    if hit:
        return hit
    # 2) name 精确
    hit = _match_exact(rows, "name", operator_name)
    if hit:
        return hit
    # 3) name 包含（容错：op1 ↔ op10，op1 ↔ op_1 等）
    target = _norm(operator_name)
    for r in rows:
        for f in ("id", "name"):
            cell = _norm(r.get(f, ""))
            if cell and (target in cell or cell in target):
                return r
    return None


def match_task(task_desc: str) -> dict | None:
    """按工序/任务文字匹配任务。"""
    rows = _load_dim("tasks")
    if not task_desc:
        return None
    fields = ["process", "process_en", "task", "product", "tool"]
    # 1) 任一字段精确
    for f in fields:
        hit = _match_exact(rows, f, task_desc)
        if hit:
            return hit
    # 2) 包含
    return _match_contains(rows, fields, task_desc)


def match_environment(env_desc: str) -> dict | None:
    """按环境描述匹配环境。"""
    rows = _load_dim("environments")
    if not env_desc:
        return None
    fields = ["environment_description", "environment_description_en",
              "environment", "scene"]
    for f in fields:
        hit = _match_exact(rows, f, env_desc)
        if hit:
            return hit
    return _match_contains(rows, fields, env_desc)


def match_device(device_id: str) -> dict | None:
    """按 volume_serial 或 device_id 匹配设备。"""
    rows = _load_dim("sd_cards")
    if not device_id:
        return None
    target = _norm(device_id)
    for r in rows:
        for f in ("volume_serial", "device_id"):
            cell = _norm(r.get(f, ""))
            if cell and cell == target:
                return r
    # 退化匹配
    for r in rows:
        for f in ("device_name",):
            cell = _norm(r.get(f, ""))
            if cell and (target in cell or cell in target):
                return r
    return None


# ── 候选列表（typeahead / 调试用） ──

def suggest_recorders(prefix: str, limit: int = 8) -> list[dict]:
    """按 prefix 模糊给候选（id/name 前缀匹配）。"""
    rows = _load_dim("recorders")
    if not prefix:
        return rows[:limit]
    target = _norm(prefix)
    out = []
    for r in rows:
        for f in ("id", "name"):
            cell = _norm(r.get(f, ""))
            if cell.startswith(target) or target in cell:
                out.append(r)
                break
        if len(out) >= limit:
            break
    return out


def suggest_tasks(prefix: str, limit: int = 8) -> list[dict]:
    """按 prefix 模糊给候选（process / task / product 任意字段含 prefix）。"""
    rows = _load_dim("tasks")
    if not prefix:
        return rows[:limit]
    target = _norm(prefix)
    out = []
    for r in rows:
        for f in ("process", "process_en", "task", "product", "tool"):
            cell = _norm(r.get(f, ""))
            if cell and target in cell:
                out.append(r)
                break
        if len(out) >= limit:
            break
    return out


def suggest_environments(prefix: str, limit: int = 8) -> list[dict]:
    """按 prefix 模糊给候选。"""
    rows = _load_dim("environments")
    if not prefix:
        return rows[:limit]
    target = _norm(prefix)
    out = []
    for r in rows:
        for f in ("environment_description", "environment_description_en",
                  "environment", "scene"):
            cell = _norm(r.get(f, ""))
            if cell and target in cell:
                out.append(r)
                break
        if len(out) >= limit:
            break
    return out


# ── 补全主入口 ──

def autofill(operator_name: str = "", task_desc: str = "",
             env_desc: str = "", device_id: str = "",
             video_path: str = "",
             upload_template_defaults: dict | None = None) -> dict:
    """
    给定 3 个 free-text 输入，输出 publish.example.com 表单所需完整字段集合。

    返回结构：
      {
        "ok": True,
        "fields": {key: value, ...},  # 可直接填到表单的字段
        "matched": {
            "recorder_id": "op1" | None,
            "task_id": "..." | None,
            "env_id": "..." | None,
            "device_id": "f83c30" | None,
        },
        "unmatched": ["task_description", ...],   # 哪些输入没匹配到
        "diagnostic": [   # 详细诊断信息，便于排查
            {"input": "task-description", "value": "...",
             "matched_field": "process_en" | None, "matched_value": "..." | None,
             "candidates": [{"task_id": "...", "process": "..."}, ...]},
            ...
        ],
        "video_path": "..."  # 透传回来
      }
    """
    # 1) 匹配
    c_info = match_recorder(operator_name)
    t_info = match_task(task_desc)
    e_info = match_environment(env_desc)
    d_info = match_device(device_id) if device_id else None

    unmatched = []
    if operator_name and not c_info:
        unmatched.append("operator_name")
    if task_desc and not t_info:
        unmatched.append("task_description")
    if env_desc and not e_info:
        unmatched.append("environment_description")
    if device_id and not d_info:
        unmatched.append("device_id")

    # 2) 拼装 fields —— 与 /api/upload-template/<row> 同结构，便于前端复用渲染
    fields: dict = dict(upload_template_defaults or {})

    # 2.1 用户输入直接回填（input 是圣旨，覆盖默认值）
    if operator_name:
        fields["operator_name"] = operator_name
    if task_desc:
        fields["task_description"] = task_desc
    if env_desc:
        fields["environment_description"] = env_desc

    # 2.2 Recorder 字段
    if c_info:
        for f in ("operator_job", "operator_consent", "age_range", "gender",
                  "handedness", "gloves", "workforce_type", "role_experience",
                  "task_experience", "collection_hours_today",
                  "collection_experience_days", "hand_size_cm"):
            v = (c_info.get(f) or "").strip()
            if v and not fields.get(f):
                fields[f] = v

    # 2.3 SD card / 地理位置
    if d_info:
        mapping = {
            "capture_mode": "captureMode",
            "country_code": "country",
            "region": "state_province",
            "city": "city",
        }
        for csv_key, tpl_key in mapping.items():
            v = (d_info.get(csv_key) or "").strip()
            if v and not fields.get(tpl_key):
                fields[tpl_key] = v

    # 2.4 Task 字段
    if t_info:
        if t_info.get("difficulty") and not fields.get("task_difficulty"):
            fields["task_difficulty"] = t_info["difficulty"]
        # task_description 已在 2.1 设置为用户原文，不覆盖
        for f in ("business_type", "business_name", "location_address",
                  "environment", "facility_venue", "scene"):
            v = (t_info.get(f) or "").strip()
            if v and not fields.get(f):
                fields[f] = v
        # 任务的 process_en 优先作为 task_description 的翻译版（双版本）
        if t_info.get("process_en"):
            fields.setdefault("_task_description_translated", t_info["process_en"])
        if t_info.get("process"):
            fields.setdefault("_task_description_cn", t_info["process"])

    # 2.5 Environment 字段
    if e_info:
        # environment_description 已在 2.1 设置
        for f in ("location_address", "environment", "facility_venue", "scene"):
            v = (e_info.get(f) or "").strip()
            if v and not fields.get(f):
                fields[f] = v
        if e_info.get("environment_description_en"):
            fields.setdefault("_environment_description_translated",
                              e_info["environment_description_en"])
        if e_info.get("environment_description"):
            fields.setdefault("_environment_description_cn",
                              e_info["environment_description"])

    # 3) 诊断信息
    diagnostic = [
        _diag("operator_name", operator_name,
              c_info, "name" if c_info else None,
              suggest_recorders(operator_name, 5)),
        _diag("task_description", task_desc,
              t_info, "process" if t_info else None,
              suggest_tasks(task_desc, 5)),
        _diag("environment_description", env_desc,
              e_info, "environment_description" if e_info else None,
              suggest_environments(env_desc, 5)),
        _diag("device_id", device_id,
              d_info, "device_id" if d_info else None,
              [r for r in _load_dim("sd_cards") if not device_id or _norm(device_id) in _norm(r.get("device_id", "") + r.get("device_name", ""))][:5]),
    ]

    return {
        "ok": True,
        "fields": fields,
        "matched": {
            "recorder_id": (c_info or {}).get("id", "") if c_info else None,
            "task_id": (t_info or {}).get("task_id", "") if t_info else None,
            "env_id": (e_info or {}).get("env_id", "") if e_info else None,
            "device_id": (d_info or {}).get("device_id", "") if d_info else None,
        },
        "unmatched": unmatched,
        "diagnostic": diagnostic,
        "video_path": video_path,
        "hints": _build_hints(unmatched, c_info, t_info, e_info),
    }


def _diag(input_name: str, value: str, hit: dict | None,
          matched_field: str | None,
          candidates: list[dict]) -> dict:
    return {
        "input": input_name,
        "value": value,
        "matched": hit is not None,
        "matched_field": matched_field,
        "matched_value": (hit or {}).get(matched_field, "") if hit else None,
        "candidates": [
            {
                "task_id": c.get("task_id"),
                "process": c.get("process", ""),
                "id": c.get("id"),
                "name": c.get("name", ""),
                "env_id": c.get("env_id"),
                "environment_description": c.get("environment_description", ""),
                "device_id": c.get("device_id"),
                "device_name": c.get("device_name", ""),
            }
            for c in (candidates or [])
        ],
    }


def _build_hints(unmatched: list, c_info, t_info, e_info) -> list[str]:
    """给前端的人话提示。"""
    out = []
    if "operator_name" in unmatched:
        out.append("operator_name 未匹配到录入员，请去「员工/录入员」管理页添加新记录")
    if "task_description" in unmatched:
        out.append("task_description 未匹配到任务，请去「任务」管理页添加新记录")
    if "environment_description" in unmatched:
        out.append("environment_description 未匹配到环境，请去「环境」管理页添加新记录")
    if "device_id" in unmatched:
        out.append("device_id 未匹配到设备，请去「设备」管理页添加新记录")
    if not unmatched:
        out.append("全部 4 个字段已匹配，可一键填表。")
    return out


# ── 持久化（可选：把匹配结果写回 video_manager.csv） ──

def apply_to_video_row(video_path: str, matched: dict) -> bool:
    """把 matched 写回 video_manager.csv 对应行（用 *_id 字段）。"""
    if not video_path:
        return False
    rows = read_csv()
    target = video_path.strip()
    found = False
    for r in rows:
        if (r.get("path") or "").strip() == target:
            for k, v in matched.items():
                if v:
                    r[k] = v
            found = True
            break
    if found:
        if USE_PG:
            from models.pg_store import write_csv
        else:
            from models.csv_store import write_csv
        write_csv(rows)
        return True
    return False
