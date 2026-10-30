#!/usr/bin/env python3
"""
[SPECIAL] 把 0701-0705 批次从"占位 ID"回填为真实标注
======================================================

读 ``runtime/data/random_uploads_20260707.json`` 里上传条目,
按 CLI 或 mapping CSV 给出的真实参数, 直接改写 ``video_manager.csv``
对应行 (upload_run_id=20260707_random, source=RANDOM_PLACEHOLDER).

**主要工作**
- recorder_id / task_id / env_id / device_id → 真实值
- extra_description (如果有需要)
- source / upload_run_id 标志清掉

**不动 PG**
本脚本只改本地 CSV。PG 的 videos 表同步需要单独跑:
- 已上传状态:  ``scripts/sync_uploaded_to_cloud.py``
- 维度 ID 同步: 目前无现成脚本, 后续可能用 ``scripts/_sync_dim_ids_to_pg.py``
  (先用 ``SELECT * FROM videos WHERE uploaded='Yes' AND task_id IN (... random 占位 ...)``
   列出 cloud 上那 57 行, 然后用 SQL UPDATE 批量覆盖)

两种用法:

A) 整批统一一套真实参数 (多数 0701-0705 都是同一个 task 的多次重复录制时用)

    python scripts/repair_random_uploads_20260707.py \\
        --recorder-id op1 --task-id 4ad1_xxx --env-id env_yyy \\
        --device-id 9df5dc

B) 每个 session 一一对应 (按 session_path 匹配)

    python scripts/repair_random_uploads_20260707.py \\
        --mapping runtime/data/_real_annotations.csv

  mapping CSV 模板: runtime/data/_real_annotations_template.csv
  必填列: session_path
  其余列留空 = 保留原占位 ID; 填值 = 用真实值覆盖

C) 只打印预览不改文件

    python scripts/repair_random_uploads_20260707.py \\
        --mapping xxx.csv --dry-run
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path


# ── Windows console ──
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


_SELF = Path(__file__).resolve().parent
_ROOT = _SELF.parent
_RUNTIME_DATA = _ROOT / "runtime" / "data"

RUN_TAG = "20260707_random"
SOURCE_TAG = "RANDOM_PLACEHOLDER"
LOG_JSON = _RUNTIME_DATA / "random_uploads_20260707.json"
CSV_PATH = _RUNTIME_DATA / "video_manager.csv"


def log(msg: str) -> None:
    print(f"[REPAIR] {msg}", flush=True)


# ── 加载 ──
def load_log() -> dict:
    if not LOG_JSON.exists():
        sys.exit(f"ERROR: 找不到 {LOG_JSON}, 先跑 random_batch_upload_0701_0705.py")
    with open(LOG_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def load_csv() -> tuple[list[dict], list[str]]:
    if not CSV_PATH.exists():
        sys.exit(f"ERROR: 找不到 {CSV_PATH}")
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    fieldnames = list(rows[0].keys()) if rows else []
    return rows, fieldnames


def load_mapping(path: Path) -> dict[str, dict]:
    """session_path → 行 dict. 忽略以 # 开头的注释行."""
    if not path.exists():
        sys.exit(f"ERROR: 找不到 mapping 文件 {path}")
    out: dict[str, dict] = {}
    with open(path, "r", encoding="utf-8-sig") as f:
        # 先去掉注释行（以 # 开头）
        lines = [ln for ln in f if not ln.lstrip().startswith("#")]
    reader = csv.DictReader(lines)
    for row in reader:
        sp = (row.get("session_path") or "").strip()
        if sp:
            out[sp] = {k: (v or "").strip() for k, v in row.items()}
    return out


# ── 合并 CLI 全局 + mapping ──
def build_overrides(
    args: argparse.Namespace, mapping: dict[str, dict], entries: list[dict],
) -> dict[str, dict]:
    overrides: dict[str, dict] = {}

    cli_keys = [
        ("recorder_id", "real_recorder_id"),
        ("task_id", "real_task_id"),
        ("env_id", "real_env_id"),
        ("device_id", "real_device_id"),
        ("extra_description", "real_extra_description"),
    ]
    cli_provided = any(getattr(args, k, None) for k, _, in cli_keys)
    if cli_provided and mapping:
        log("WARN: 同时给了 CLI 全局参数和 mapping.csv, 优先用 mapping.csv, "
            "CLI 仅作 fallback")

    for e in entries:
        sp = e["session_path"]
        o: dict[str, str] = {}

        # mapping 优先
        if sp in mapping:
            for k, v in mapping[sp].items():
                if k == "session_path":
                    continue
                if v:
                    o[k] = v

        # CLI fallback
        for arg_k, real_k in cli_keys:
            val = getattr(args, arg_k, None)
            if val and real_k not in o:
                o[real_k] = val

        if o:
            overrides[sp] = o

    return overrides


# ── 写回 CSV ──
def repair_csv(
    rows: list[dict], fieldnames: list[str],
    entry_by_csv_index: dict[int, dict],
    entry_by_path: dict[str, dict],
    overrides: dict[str, dict],
    dry_run: bool = False,
) -> tuple[int, int, int]:
    matched = 0
    no_override = 0
    modified = 0

    real_to_csv_col = {
        "real_recorder_id": "recorder_id",
        "real_task_id": "task_id",
        "real_env_id": "env_id",
        "real_device_id": "device_id",
        "real_extra_description": "extra_description",
    }

    for i, row in enumerate(rows):
        if (row.get("upload_run_id") or "").strip() != RUN_TAG:
            continue
        matched += 1

        path = (row.get("path") or "").strip()
        ov = overrides.get(path)
        if not ov:
            no_override += 1
            log(f"  [NO-OVERRIDE] {Path(path).name} (保留占位)")
            continue

        changes = []
        for real_key, csv_col in real_to_csv_col.items():
            if real_key in ov and ov[real_key]:
                old = (row.get(csv_col) or "").strip()
                new = ov[real_key]
                if old != new:
                    row[csv_col] = new
                    changes.append(f"{csv_col}: {old!r}→{new!r}")

        # 清掉占位标记
        if row.get("source") == SOURCE_TAG:
            row["source"] = ""
            changes.append("source: 'RANDOM_PLACEHOLDER' → ''")
        if row.get("upload_run_id") == RUN_TAG:
            row["upload_run_id"] = ""
            changes.append("upload_run_id: '20260707_random' → ''")

        # 审计字段 (如果 CSV 已经预置)
        for k, v in [("repaired_at", datetime.now().isoformat(timespec="seconds")),
                     ("repaired_from_run", RUN_TAG)]:
            if k in fieldnames:
                row[k] = v

        if changes:
            modified += 1
            log(f"  [FIX] {Path(path).name}")
            for c in changes:
                log(f"      · {c}")

    if matched == 0:
        log(f"⚠ 没在 CSV 里找到任何 upload_run_id={RUN_TAG} 的行, "
            f"是不是已经修过了? 或 upload_run_id 字段被改过?")

    if not dry_run and modified:
        tmp = str(CSV_PATH) + ".tmp"
        with open(tmp, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)
        os.replace(tmp, str(CSV_PATH))
        log(f"[CSV] 已写回 {CSV_PATH}")

    return matched, no_override, modified


# ── 主流程 ──
def main():
    ap = argparse.ArgumentParser(
        description="把 0701-0705 批次从占位回填为真实标注",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--mapping", type=Path,
                    help="真实标注 CSV 路径（每行一个 session 的真实 ID）")
    ap.add_argument("--recorder-id", help="整批统一 recorder_id")
    ap.add_argument("--task-id", help="整批统一 task_id")
    ap.add_argument("--env-id", help="整批统一 env_id")
    ap.add_argument("--device-id", help="整批统一 device_id")
    ap.add_argument("--extra-description", help="extra_description 统一值")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.mapping and not any([
        args.recorder_id, args.task_id, args.env_id,
        args.device_id, args.extra_description,
    ]):
        sys.exit("ERROR: 必须提供 --mapping 或至少一个 "
                 "--recorder-id / --task-id / --env-id / --device-id")

    log_data = load_log()
    entries = log_data.get("entries", [])
    if not entries:
        sys.exit(f"ERROR: {LOG_JSON} 里没有 entries")
    log(f"[LOG] {LOG_JSON}: {len(entries)} 条")
    entry_by_csv_index = {e["csv_index"]: e for e in entries}
    entry_by_path = {e["session_path"]: e for e in entries}

    mapping: dict[str, dict] = {}
    if args.mapping:
        mapping = load_mapping(args.mapping)
        log(f"[MAPPING] {args.mapping}: {len(mapping)} 行")

    overrides = build_overrides(args, mapping, entries)
    log(f"[OVERRIDE] 将覆盖 {len(overrides)} 条 session")

    rows, fieldnames = load_csv()
    log(f"[CSV] {CSV_PATH}: {len(rows)} 行")

    if args.dry_run:
        log("[DRY-RUN] 只打印, 不改文件")

    matched, no_override, modified = repair_csv(
        rows, fieldnames,
        entry_by_csv_index, entry_by_path,
        overrides, dry_run=args.dry_run,
    )

    log(f"\n总结: matched={matched} no_override={no_override} modified={modified}")

    if not args.dry_run and modified:
        log("✅ 本地 CSV 已修复")
        log("⚠️ PG 端还需要:")
        log("   1) 跑 scripts/sync_uploaded_to_cloud.py "
            "(仅同步 uploaded=Yes 状态)")
        log("   2) 真实 ID 同步 PG 目前无现成脚本, 临时方案:")
        log("      - 从 random_uploads_20260707.json 里得到 csv_index 列表")
        log("      - 在 PG 上先 SELECT path WHERE uploaded='Yes' AND recorder_id='op_<旧占位>'...")
        log("      - UPDATE videos SET recorder_id=..., task_id=..., env_id=... WHERE path IN (...)")
        log("")
        log("⚠️ 如果 PC 端的真实值需要再同步到 platform (平台 UI 改填写后),")
        log("   还需要你跑一遍 auto_upload.py 或用 platform 后台接口批量覆盖")


if __name__ == "__main__":
    main()
