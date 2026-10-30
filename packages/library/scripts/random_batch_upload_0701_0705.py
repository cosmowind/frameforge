#!/usr/bin/env python3
"""
[SPECIAL] 0701-0704 占位参数批量上传（临时绕过方案, 走 auto_upload.py）
======================================================================

📊 **状态 (2026-07-08 收尾)**: 0701-0704 共 **56 / 56 = 100%** 已上传
   - 50 条 RANDOM_PLACEHOLDER 占位
   - 6 条历史已上传
   详见 ``runtime/data/RANDOM_UPLOADS_TODO.md`` 的"完成报告"段

⚠️ **为什么有这个脚本 (背景)**
platform 表单填写功能在修复中, 无法手动给 recorder/task/env 元数据填真实值。
本脚本让 0701-0704 的 session **照样走前端 Playwright 填表流程**上传,
但用 *现有维度表* 里**随机抽取**的真实 ID 当占位参数上传。
明日在 platform 修复后用 ``scripts/repair_random_uploads_20260707.py`` 一键覆盖回去。

⚠️ **已迁移到 auto_upload.py 流水线**
- 不再直接打 StereoTaskBoxClient (那是 batch_stereo_upload.py 的方式)
- 调用的是 ``auto_upload.py --pipeline --row-index ...``
- 浏览器用 runtime/browser_data/ 持久化 session, 需要你先登过一次

**输出物**
- ``runtime/data/random_uploads_20260707.json`` ← 每条 session 的随机 ID + CSV row_index + 平台结果
- ``runtime/data/video_manager.csv``            ← upsert N 行, ``source=RANDOM_PLACEHOLDER``, ``upload_run_id=20260707_random``
- ``runtime/logs/random-upload-YYYYMMDD-HHMMSS.log`` ← auto_upload.py 自身写

**用法**

    # 1. dry-run: 只看每条 session 会被分配到什么占位 ID, 不动 CSV, 不传
    python scripts/random_batch_upload_0701_0705.py --dry-run

    # 2. 写 CSV + 触发现实上传 (auto_upload.py --pipeline)
    python scripts/random_batch_upload_0701_0705.py

    # 3. 自定义目录 / 调试
    python scripts/random_batch_upload_0701_0705.py --roots /media/videos/0701/hmd --limit 2

    # 4. 与上次运行 diff: 上次存在但这次目录已消失的会被列出但不上传
    python scripts/random_batch_upload_0701_0705.py --diff-prev --dry-run

    # 5. 离线预览 template (不打开浏览器, 不上传, 输出 JSON)
    python scripts/random_batch_upload_0701_0705.py --print-template --limit 1

    # 6. 填表但不点 Upload (auto_upload.py --no-submit), Chrome 保持打开供目测
    python scripts/random_batch_upload_0701_0705.py --test-form

    # 7. 只挑小文件 (调试用, 1-.hmd 优先)
    python scripts/random_batch_upload_0701_0705.py --max-hmd 1 --limit 5

    # 8. 强制覆盖已 uploaded=Yes 的行 (谨慎使用!)
    python scripts/random_batch_upload_0701_0705.py --force-rewrite-uploaded --limit 1

⚠️ **新发现的坑 (调大文件必看)**
``--limit N`` 是按 .hmd 数排序后截断——**1-.hmd 排最前会把大文件挤掉**。
要全跑大文件时**不要加 --limit**, 或加足够大的值。
本脚本默认 ``--limit 0`` (不限)。Sort 用的是 .hmd 数升序, 所以默认从小到大传。

**只上传本地还存在的 session**

脚本的 discover 阶段只接入两类目录:
  1. 整个 root 目录 (/media/videos/0701/hmd 等) 必须 exists + 是 directory
  2. 每个 root 下的直接子目录里必须含 **≥1 个 .hmd 分片**
其它情况 (目录整个没了 / 子目录里没有 .hmd) 全部跳过并打印 [SKIP-NO-HMD] 日志。
auto_upload.py 自身也会再校验 metadata.json 缺不缺, 缺了就报错不上传。

**前置**
- Flask 应用不必启动 (auto_upload.py 是独立 subprocess)
- Chrome 用户目录里已有的 frameforge 登录 cookie 必须有效
  (不然 auto_upload.py 会停在那里等你手动登录, 然后我们的脚本也会卡住)
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


# ── Windows console 中文输出 ──
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ── 路径 ──
_SELF = Path(__file__).resolve().parent
_ROOT = _SELF.parent
_SRC = _ROOT / "src"
_RUNTIME_DATA = _ROOT / "runtime" / "data"

CSV_PATH = _RUNTIME_DATA / "video_manager.csv"
AUTO_UPLOAD_PY = _SRC / "auto_upload.py"
LOG_JSON = _RUNTIME_DATA / "random_uploads_20260707.json"

RUN_TAG = "20260707_random"
SOURCE_TAG = "RANDOM_PLACEHOLDER"

DEFAULT_ROOTS = [
    Path("/media/videos/0701"),
    Path("/media/videos/0702"),
    Path("/media/videos/0703"),
    Path("/media/videos/0704"),
]


def log(msg: str) -> None:
    print(f"[RANDOM-UPLOAD] {msg}", flush=True)


# ── 维度加载 ──
def _load_dim(name: str) -> list[dict]:
    p = _RUNTIME_DATA / f"{name}.csv"
    if not p.exists():
        return []
    with open(p, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


# ── 离线模板预览 (不会动网络/浏览器/平台) ──
def _load_template_defaults() -> dict:
    """复用 auto_upload.py 的 config.json 默认值加载."""
    cfg_path = _ROOT / "config.json"
    if not cfg_path.exists():
        return {}
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        out = {}
        for k, v in cfg.items():
            if isinstance(v, (str, int)):
                out[k] = v
        return out
    except Exception:
        return {}


def _build_preview_template(
    row: dict,
    coll: dict,
    t: dict,
    env: dict,
    dvc: dict,
) -> tuple[dict, list[str]]:
    """镜像 src/auto_upload.py:_build_template_from_row 的合并顺序, 仅在内存里构建.

    与真上传流保持一致:
      - 中文优先: task_description / environment_description 用中文
      - 上传页是中文页面 → 中文是主, 英文只作 fallback
      - 录制员抽到一条 → 完整地把它 19+ 字段都填上 (来自 recorders.csv)

    Returns:
      (template, warnings)
        warnings: 中文为空回退英文时记录的提示 (供 log)
    """
    warnings: list[str] = []

    template = {
        "operator_consent": "yes",
        "operator_job": "生产工人",
        "location_address": "南安市辉煌工业园区",
        "environment": "工业制造",
        "facility_venue": "工厂",
    }
    template.update(_load_template_defaults())

    # ── 录制员: 整条接入到 template ──
    if (coll.get("id") or "").strip():
        template["operator_name"] = (coll.get("id") or "").strip()
        for src, dst in [
            ("operator_job", "operator_job"),
            ("operator_consent", "operator_consent"),
            ("age_range", "age_range"),
            ("gender", "gender"),
            ("handedness", "handedness"),
            ("gloves", "gloves"),
            ("workforce_type", "workforce_type"),
            ("role_experience", "role_experience"),
            ("task_experience", "task_experience"),
            ("collection_hours_today", "collection_hours_today"),
            ("collection_experience_days", "collection_experience_days"),
            ("hand_size_cm", "hand_size_cm"),
        ]:
            val = (coll.get(src) or "").strip()
            if val:
                template[dst] = val

    # ── 设备: captureMode ──
    if (dvc.get("capture_mode") or "").strip():
        template["captureMode"] = (dvc.get("capture_mode") or "").strip()

    # ── 任务: 中文 process 优先, 英文仅 fallback ──
    if t:
        scene = (t.get("scene") or "").strip()
        if scene:
            template["scene"] = scene

        process_cn = (t.get("process") or "").strip()
        process_en = (t.get("process_en") or "").strip()
        if process_cn:
            template["task_description"] = process_cn
        elif process_en:
            template["task_description"] = process_en
            warnings.append(
                f"task_id={t.get('task_id')} 中文工序描述为空, 暂时用英文"
            )
        else:
            warnings.append(
                f"task_id={t.get('task_id')} 工序描述 (process / process_en) 全空"
            )

        difficulty = (t.get("difficulty") or "").strip()
        if difficulty:
            template["task_difficulty"] = difficulty
        if (t.get("business_type") or "").strip():
            template["business_type"] = t["business_type"]
        if (t.get("business_name") or "").strip():
            template["business_name"] = t["business_name"]

    # ── 环境: 中文 environment_description 优先 ──
    if env:
        env_desc_cn = (env.get("environment_description") or "").strip()
        env_desc_en = (env.get("environment_description_en") or "").strip()
        if env_desc_cn:
            template["environment_description"] = env_desc_cn
        elif env_desc_en:
            template["environment_description"] = env_desc_en
            warnings.append(
                f"env_id={env.get('env_id')} 中文环境描述为空, 暂时用英文"
            )
        else:
            warnings.append(
                f"env_id={env.get('env_id')} 环境描述全空"
            )

        for k_csv, k_tmpl in [
            ("scene", "scene"),
            ("location_address", "location_address"),
            ("environment", "environment"),
            ("facility_venue", "facility_venue"),
        ]:
            v = (env.get(k_csv) or "").strip()
            if v:
                template[k_tmpl] = v

    # ── row 上的 source_device (如果有) ──
    sd = (row.get("source_device") or "").strip()
    if sd:
        template["source_device"] = sd

    # ── GPS 国家/省/市 固定 ──
    template.setdefault("country", "CN")
    template.setdefault("state_province", "示例省省")
    template.setdefault("city", "示例市")

    # ── row 上其它非空字段覆盖 ──
    for k, v in row.items():
        if v and str(v).strip():
            template[k] = str(v).strip()

    return template, warnings


# ── 发现 session 目录 (只取本地还存在的) ──
def discover_sessions(
    roots: list[Path],
    min_hmd: int = 1,
    max_hmd: int = 0,
) -> tuple[list[Path], dict]:
    """在每个 root 下找本地存在且含 ≥1 个 .hmd 文件的直接子目录.

    返回:
      sessions:              满足条件的 session 目录
      scan_summary:          { root → {exists, missing, n_sessions} } 供 dry-run / 日志使用

    过滤:
      min_hmd (默认 1):  至少含 N 个 .hmd 分片
      max_hmd (默认 0=不限):  最多含 N 个 .hmd 分片 (调试用, 选小文件加速)
    """
    sessions: list[Path] = []
    summary: dict[str, dict] = {}
    rejected_by_size = 0

    for root in roots:
        info = {"exists": False, "is_dir": False, "n_sessions": 0, "n_skipped_no_hmd": 0,
                "n_skipped_other": 0, "n_skipped_too_big": 0}
        if not root.exists():
            log(f"[ROOT-MISSING] {root} (整个目录不存在, 跳过)")
            summary[str(root)] = info
            continue
        info["exists"] = True
        if not root.is_dir():
            log(f"[ROOT-NOT-DIR] {root} (存在但不是目录, 跳过)")
            summary[str(root)] = info
            continue
        info["is_dir"] = True

        try:
            entries_in_root = list(root.iterdir())
        except OSError as e:
            log(f"[ROOT-READ-FAIL] {root}: {e}")
            summary[str(root)] = info
            continue

        for child in sorted(entries_in_root):
            if not child.is_dir():
                info["n_skipped_other"] += 1
                continue
            try:
                hmd_files = [
                    p for p in child.iterdir()
                    if p.is_file() and p.suffix.lower() == ".hmd"
                ]
            except OSError:
                info["n_skipped_other"] += 1
                continue
            n = len(hmd_files)
            if not hmd_files or n < min_hmd:
                log(f"  [SKIP-NO-HMD] {child.name} ({n} 个, 少于 {min_hmd})")
                info["n_skipped_no_hmd"] += 1
                continue
            if max_hmd and n > max_hmd:
                log(f"  [SKIP-TOO-BIG] {child.name} ({n} 个 .hmd, 超过 --max-hmd={max_hmd})")
                info["n_skipped_too_big"] += 1
                rejected_by_size += 1
                continue
            sessions.append(child)
            info["n_sessions"] += 1
            log(f"  [FOUND] {child.name} ({n} 个 .hmd 分片)")

        summary[str(root)] = info

    if rejected_by_size:
        log(f"[FILTER] 共 {rejected_by_size} 个 session 因 --max-hmd={max_hmd} 被排除")

    # ── 按 .hmd 数升序排序 (smallest first) ──
    def _count_hmd(p: Path) -> int:
        try:
            return sum(1 for q in p.iterdir() if q.is_file() and q.suffix.lower() == ".hmd")
        except OSError:
            return 0

    sessions.sort(key=lambda p: (_count_hmd(p), str(p)))

    return sessions, summary


def _diff_with_prev_log(prev_json: Path | None,
                        current_sessions: list[Path]) -> tuple[list[str], list[str]]:
    """对比上一次 run 的 JSON, 列出新增/消失的 session."""
    if not prev_json or not prev_json.exists():
        return [], []
    try:
        with open(prev_json, "r", encoding="utf-8") as f:
            prev = json.load(f)
    except Exception:
        return [], []
    prev_paths = {e["session_path"] for e in prev.get("entries", [])}
    curr_paths = {str(p) for p in current_sessions}
    return (
        sorted(curr_paths - prev_paths),       # 新出现 (上次不存在, 这次有)
        sorted(prev_paths - curr_paths),       # 消失 (上次在, 这次目录没了)
    )


# ── 读 CSV ──
def _read_csv() -> tuple[list[dict], list[str]]:
    if not CSV_PATH.exists():
        return [], []
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    fieldnames = list(rows[0].keys()) if rows else []
    for extra in ("source", "upload_run_id"):
        if extra not in fieldnames:
            fieldnames.append(extra)
    return rows, fieldnames


def _write_csv(rows: list[dict], fieldnames: list[str]) -> None:
    tmp = str(CSV_PATH) + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, str(CSV_PATH))


def _norm(p: str) -> str:
    return os.path.normpath(p).replace("\\", "/").lower()


# ── 给 sessions 分配 (随机) 维度 ID + (创建或更新) CSV 行 ──
def upsert_rows(
    sessions: list[Path],
    recorders: list[dict],
    tasks: list[dict],
    environments: list[dict],
    sd_cards: list[dict],
    force_rewrite_uploaded: bool = False,
) -> tuple[list[dict], list[str], dict[str, dict]]:
    """
    返回:
      rows:        改写后的 CSV 行
      fieldnames:  CSV 列名
      entries:     {session_path → {csv_index, ... assigned IDs/desc ...}}
    """
    rows, fieldnames = _read_csv()
    if not fieldnames:
        fieldnames = [
            "path", "file_type", "location_status", "uploaded",
            "recorder_id", "task_id", "env_id", "device_id",
            "extra_description", "source", "upload_run_id",
        ]
        rows = []

    # 已有 path → index 索引
    existing: dict[str, int] = {}
    for i, r in enumerate(rows):
        p = (r.get("path") or "").strip()
        if p:
            existing[_norm(p)] = i

    rnd = random.SystemRandom()
    entries: dict[str, dict] = {}
    skipped_already_uploaded: list[tuple[str, int]] = []

    for sp in sessions:
        sp_norm = _norm(str(sp))

        # 1) 抽 4 个维度的占位
        coll = rnd.choice(recorders)
        t = rnd.choice(tasks)
        env = rnd.choice(environments)
        dvc = rnd.choice(sd_cards) if sd_cards else {}

        # 2) 找/插行
        if sp_norm in existing:
            idx = existing[sp_norm]
            row = rows[idx]
            # ★ 已 uploaded=Yes 的行 — 不覆盖, 不放进 entries, 让 auto_upload.py 跳过
            if (row.get("uploaded") or "").strip() == "Yes" and not force_rewrite_uploaded:
                skipped_already_uploaded.append((str(sp), idx))
                log(f"  [SKIP-UPLOADED] {sp.name} (row {idx} 已 Yes — "
                    f"想强制覆盖加 --force-rewrite-uploaded)")
                continue
        else:
            idx = len(rows)
            existing[sp_norm] = idx
            row = {fn: "" for fn in fieldnames}
            rows.append(row)

        # 总是覆写源字段 (即便行原本就有别的 source)
        row["path"] = str(sp)
        row["file_type"] = "hmd"
        row["location_status"] = "thisPC_local"
        row["uploaded"] = ""           # 仅对未上传的清空 (防止重跑重复触发)
        row["source"] = SOURCE_TAG
        row["upload_run_id"] = RUN_TAG
        row["recorder_id"] = (coll.get("id") or "").strip()
        row["task_id"] = (t.get("task_id") or "").strip()
        row["env_id"] = (env.get("env_id") or "").strip()
        row["device_id"] = (dvc.get("volume_serial") or "").strip()

        entries[str(sp)] = {
            "csv_index": idx,
            "session_path": str(sp),
            "session_name": sp.name,
            "assigned_recorder_id": row["recorder_id"],
            "assigned_recorder_name": (coll.get("name") or "").strip(),
            "assigned_task_id": row["task_id"],
            "assigned_task_scene": (t.get("scene") or "Workshop").strip() or "Workshop",
            "assigned_task_desc": (
                (t.get("process_en") or t.get("process") or "").strip()
            ),
            "assigned_env_id": row["env_id"],
            "assigned_env_desc": (
                (env.get("environment_description_en")
                 or env.get("environment_description")
                 or "").strip()
            ),
            "assigned_device_id": row["device_id"],
            "assigned_capture_mode": (dvc.get("capture_mode") or "stereo").strip(),
        }

    if skipped_already_uploaded:
        log(f"[SKIP] 共 {len(skipped_already_uploaded)} 个 session "
            f"因 uploaded=Yes 被跳过, 不会被上传")

    return rows, fieldnames, entries


# ── 触发 auto_upload.py --pipeline --row-index ──
def run_auto_upload(row_indices: list[int], extra_args: list[str]) -> int:
    """
    subprocess 调 auto_upload.py --pipeline --row-index ....

    auto_upload.py 的 --row-index 接受重复参数, 每多一个加一个视频.
    """
    if not row_indices:
        return 0  # 没有需要传的直接成功

    cmd = [
        sys.executable,
        str(AUTO_UPLOAD_PY),
        "--pipeline",
        # auto_upload.py 把 --row-index 定义成 nargs='+', 单 flag 多值
        "--row-index",
        *map(str, row_indices),  # 多值平铺在同一个 --row-index 后
    ]
    cmd.extend(extra_args)

    log(f"[SUBPROCESS] {' '.join(cmd)[:300]}{'...' if len(' '.join(cmd))>300 else ''}")
    log("[SUBPROCESS] (auto_upload.py 会启动浏览器, 你会看到 Chrome 弹窗, "
        "若掉线请在 Chrome 里手动登录)")

    try:
        proc = subprocess.run(cmd, cwd=str(_SRC))
        return proc.returncode
    except KeyboardInterrupt:
        log("[INTERRUPTED] 中断 auto_upload.py 子进程")
        return 130
    except Exception as e:
        log(f"[ERROR] auto_upload.py 启动失败: {e}")
        return 1


# ── 主流程 ──
def main():
    ap = argparse.ArgumentParser(
        description="0701-0705 占位参数批量上传（走 auto_upload.py 流水线）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--roots", nargs="*", type=Path, default=DEFAULT_ROOTS,
                    help="session 根目录列表（默认 0701~0704）")
    ap.add_argument("--limit", type=int, default=0,
                    help="最多上传几个 session（0=全部, 调试用）")
    ap.add_argument("--skip-upload", action="store_true",
                    help="只写 CSV + JSON, 不触发 auto_upload.py（便于先校对）")
    ap.add_argument("--dry-run", action="store_true",
                    help="= --skip-upload + 不写 CSV/JSON, 只打印计划")
    ap.add_argument(
        "--print-template", action="store_true",
        help="离线打印会被传给 auto_upload.py 的 template JSON，"
             "便于人工核对字段（不打开浏览器/不上传）",
    )
    ap.add_argument(
        "--test-form", action="store_true",
        help="= --limit 1 + 写 CSV + 调用 auto_upload.py --no-submit；"
             "浏览器保持打开供你目测表单, 但不点 Upload to server",
    )
    ap.add_argument(
        "--diff-prev", action="store_true",
        help="对比上次 random_uploads_20260707.json, 列出新增 / 消失的 session "
             "(消失的不会被上传, 但你能看到)",
    )
    ap.add_argument(
        "--max-hmd", type=int, default=0,
        help="只保留含 ≤ N 个 .hmd 分片的 session（0=不限, "
             "调试用 — 选小文件加速单次测试）",
    )
    ap.add_argument(
        "--min-hmd", type=int, default=1,
        help="只保留含 ≥ N 个 .hmd 分片的 session（默认 1, "
             "排除空目录）",
    )
    ap.add_argument(
        "--strict-empty", action="store_true",
        help="当没有任何 session 可处理时, 报错并退出 1 (默认仅警告)",
    )
    ap.add_argument(
        "--force-rewrite-uploaded", action="store_true",
        help="强制覆盖已 uploaded=Yes 的行 (默认跳过, 防重传)",
    )
    args = ap.parse_args()

    roots_str = [str(r) for r in args.roots]
    log(f"[CONFIG] roots = {roots_str}")
    log(f"[CONFIG] limit = {args.limit or 'all'}")
    log(f"[CONFIG] dry_run = {args.dry_run}, skip_upload = {args.skip_upload}")

    # ── 维度 ──
    recorders = _load_dim("recorders")
    tasks = _load_dim("tasks")
    environments = _load_dim("environments")
    sd_cards = _load_dim("sd_cards")

    if not (recorders and tasks and environments):
        sys.exit(
            "ERROR: recorders / tasks / environments 至少有一个维度表为空, "
            "无法随机抽取. 先确认 runtime/data/*.csv 有内容."
        )

    # ── 发现 (只取本地还存在的 session) ──
    sessions, scan_summary = discover_sessions(
        args.roots,
        min_hmd=args.min_hmd,
        max_hmd=args.max_hmd,
    )
    log(f"[SCAN] 发现 {len(sessions)} 个本地存在的 session 目录")

    # 与上次 JSON log 对比, 列出新增/消失 (上次在, 这次目录没了)
    if args.diff_prev and not args.dry_run:
        prev_log = LOG_JSON  # 默认是对比本批次 JSON
        added, removed = _diff_with_prev_log(prev_log, sessions)
        if added:
            log(f"[DIFF] 比上次多了 {len(added)} 个新 session:")
            for p in added[:10]:
                log(f"  + {p}")
            if len(added) > 10:
                log(f"  ... 还有 {len(added) - 10} 个")
        if removed:
            log(f"[DIFF] 上次存在但这次目录已消失 {len(removed)} 个, 不会被上传:")
            for p in removed[:10]:
                log(f"  - {p}")
            if len(removed) > 10:
                log(f"  ... 还有 {len(removed) - 10} 个")
        if not added and not removed:
            log(f"[DIFF] 与上次 JSON 完全一致")

    if args.limit and args.limit > 0:
        sessions = sessions[: args.limit]
        log(f"[LIMIT] 仅处理 {len(sessions)} 条")

    if not sessions:
        # 比 missing root 错误更常见的原因: 整体目录都没了 / 全是非-HMD 文件
        log("[EMPTY] 没有本地存在的 session 可处理; 不上传任何东西, 退出")
        if args.strict_empty:
            sys.exit("ERROR: --strict-empty 指定: 没有 session 视为错误, 退出 1")
        return

    # ── 随机分配 + CSV upsert ──
    rows, fieldnames, entries = upsert_rows(
        sessions, recorders, tasks, environments, sd_cards,
        force_rewrite_uploaded=args.force_rewrite_uploaded,
    )

    if args.dry_run:
        log("[DRY-RUN] 计划覆盖的行:")
        for sp, e in entries.items():
            log(
                f"  {e['session_name']}: coll={e['assigned_recorder_id']} "
                f"task={e['assigned_task_id']} env={e['assigned_env_id']} "
                f"dev={e['assigned_device_id'] or '(none)'} → row[{e['csv_index']}]"
            )
        log("[DRY-RUN] 退出 (未动文件)")
        return

    # ── 离线 template 预览（不写盘也不动浏览器） ──
    if args.print_template and len(entries) == 1:
        e = list(entries.values())[0]
        # 反查各维度表行
        coll = next((c for c in recorders if (c.get("id") or "").strip()
                     == e["assigned_recorder_id"]), {})
        t = next((row for row in tasks if (row.get("task_id") or "").strip()
                  == e["assigned_task_id"]), {})
        env = next((row for row in environments if (row.get("env_id") or "").strip()
                    == e["assigned_env_id"]), {})
        dvc = next((row for row in sd_cards if (row.get("volume_serial") or "").strip()
                    == e["assigned_device_id"]), {})

        template, warnings = _build_preview_template(
            rows[e["csv_index"]], coll, t, env, dvc,
        )
        log("[TEMPLATE 预览] auto_upload.py 将拿到以下 template (中文优先):")
        print(json.dumps(template, ensure_ascii=False, indent=2))
        if warnings:
            log("[WARN] " + "; ".join(warnings))
        else:
            log("[OK] 工序描述/环境描述全部为中文, 无 fallback")
        return

    # ── --test-form: 改 limit=1 + 不上传按钮 ──
    if args.test_form:
        args.limit = 1
        sessions = sessions[:1]
        log(f"[TEST-FORM] 仅取 {len(sessions)} 个 session, "
            f"auto_upload.py 会以 --no-submit 方式启动 (不点 Upload)")

    # ── 写 CSV ──
    _write_csv(rows, fieldnames)
    log(f"[CSV] 已写入 ({len(rows)} 行, 新 upsert {len(entries)})")

    # ── 写日志 JSON ──
    log_payload = {
        "run_tag": RUN_TAG,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "live" if not args.skip_upload else "skipped-upload",
        "roots": roots_str,
        "total_sessions": len(entries),
        "csv_row_indices": sorted(e["csv_index"] for e in entries.values()),
        "entries": list(entries.values()),
    }
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_JSON, "w", encoding="utf-8") as f:
        json.dump(log_payload, f, ensure_ascii=False, indent=2)
    log(f"[LOG-JSON] {LOG_JSON}")

    # ── 触发 auto_upload.py ──
    row_indices = sorted({e["csv_index"] for e in entries.values()})

    if args.skip_upload:
        log("[SKIP-UPLOAD] 已写 CSV/JSON, 不触发上传. 后续手动:")
        log(f"   python src/auto_upload.py --pipeline {' '.join(f'--row-index {i}' for i in row_indices)}")
        return

    log(f"[UPLOAD] 准备上传 {len(row_indices)} 行 (CSV index: {row_indices[:10]}"
        f"{'...' if len(row_indices) > 10 else ''})")

    rc = run_auto_upload(
        row_indices,
        ["--no-submit"] if (os.environ.get("RANDOM_NO_SUBMIT") or args.test_form) else [],
    )
    log(f"[UPLOAD] auto_upload.py exit code = {rc}")

    # ── 检查最终状态 ──
    after_rows, _ = _read_csv()
    success = 0
    failed_sessions = []
    for e in entries.values():
        idx = e["csv_index"]
        if idx < len(after_rows):
            if (after_rows[idx].get("uploaded") or "").strip() == "Yes":
                success += 1
            else:
                failed_sessions.append(e["session_name"])

    log(f"\n{'=' * 50}")
    log(f"完成: {success}/{len(entries)} 个已上传标记为 Yes")
    log(f"   失败/未完成: {len(failed_sessions)}")
    for name in failed_sessions[:20]:
        log(f"     - {name}")

    # ── 更新日志 JSON 记录最终上传结果 ──
    log_payload["after"] = {
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "auto_upload_exit_code": rc,
        "success_count": success,
        "fail_count": len(failed_sessions),
        "failed_sessions": failed_sessions,
    }
    with open(LOG_JSON, "w", encoding="utf-8") as f:
        json.dump(log_payload, f, ensure_ascii=False, indent=2)
    log(f"[LOG-JSON] (updated) {LOG_JSON}")

    log(f"\n⚠️ 善后: 明日在 platform 表单修复后跑:")
    log(f"   python scripts/repair_random_uploads_20260707.py --mapping <real_annotations.csv>")
    log(f"⚠️ 详情见 runtime/data/RANDOM_UPLOADS_TODO.md")


if __name__ == "__main__":
    main()
