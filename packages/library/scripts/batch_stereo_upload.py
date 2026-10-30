#!/usr/bin/env python3
"""
批量立体上传脚本 — 直接通过 API 上传 HMD 会话（不经过浏览器表单）

流程：
  1. 从 video_manager.csv 读取待上传视频
  2. 查维表（recorders / tasks / environments / sd_cards）补全元数据
  3. 调用 upload_pkg.py 的 stereo 流程：HMD → MCAP → task-box → S3 上传
  4. 成功后在 CSV 中标记 uploaded=Yes

用法：
  # 上传前 2 个未上传的视频
  python scripts/batch_stereo_upload.py --limit 2

  # 指定 cookie 文件
  python scripts/batch_stereo_upload.py --limit 2 --cookie-file cookie.txt

  # 只测试不实际上传
  python scripts/batch_stereo_upload.py --limit 2 --dry-run
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding for Chinese + Unicode
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ── 路径设置 ──
_SELF_DIR = Path(__file__).resolve().parent
_ROOT_DIR = _SELF_DIR.parent
_SRC_DIR = _ROOT_DIR / "src"
_RUNTIME_DIR = _ROOT_DIR / "runtime" / "data"

sys.path.insert(0, str(_SRC_DIR))
sys.path.insert(0, str(_SRC_DIR / "vendor-upload-pkg"))

from upload import CookieSource, log
from upload_pkg import (
    StereoTaskBoxClient,
    upload_stereo_session,
    validate_session_dir,
)


# ── 维表加载 ──

def load_dim(name: str) -> list[dict]:
    path = _RUNTIME_DIR / f"{name}.csv"
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def lookup(rows: list[dict], key: str, value: str) -> dict | None:
    for r in rows:
        if (r.get(key) or "").strip() == value.strip():
            return r
    return None


# ── 主流程 ──

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=2,
                    help="最多上传几个视频（默认 2）")
    ap.add_argument("--cookie-file",
                    default=os.environ.get("FF_COOKIE_FILE"),
                    help="cookie 文件路径（SESSION=... 格式）")
    ap.add_argument("--node-path", default="node",
                    help="node 可执行文件路径")
    ap.add_argument("--dry-run", action="store_true",
                    help="只打印计划，不实际上传")
    ap.add_argument("--row-index", type=int, nargs="*",
                    help="指定 CSV 行索引（不指定则自动选前 N 个未上传的）")
    args = ap.parse_args()

    # ── 加载维表 ──
    recorders = load_dim("recorders")
    tasks = load_dim("tasks")
    environments = load_dim("environments")
    sd_cards = load_dim("sd_cards")

    # ── 加载视频列表 ──
    csv_path = _RUNTIME_DIR / "video_manager.csv"
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        videos = list(csv.DictReader(f))
        fieldnames = list(videos[0].keys()) if videos else []

    # ── 选择待上传视频 ──
    if args.row_index:
        targets = [(i, videos[i]) for i in args.row_index
                   if 0 <= i < len(videos)]
    else:
        targets = []
        for i, v in enumerate(videos):
            if len(targets) >= args.limit:
                break
            if (v.get("uploaded") or "").strip() == "Yes":
                continue
            if (v.get("file_type") or "").strip() != "hmd":
                continue
            # 必须有完整的三维表 ID
            if not (v.get("recorder_id") and v.get("task_id") and v.get("env_id")):
                log(f"[SKIP] row {i}: 缺少 recorder_id/task_id/env_id")
                continue
            targets.append((i, v))

    if not targets:
        log("没有待上传的视频")
        return

    log(f"计划上传 {len(targets)} 个视频:")
    for idx, v in targets:
        log(f"  [{idx}] {v['path']}  "
            f"recorder={v.get('recorder_id','')}  "
            f"task={v.get('task_id','')}  "
            f"env={v.get('env_id','')}")

    if args.dry_run:
        log("[dry-run] 结束")
        return

    # ── 认证 ──
    if args.cookie_file:
        cookie_source = CookieSource(file=args.cookie_file)
        cookie_source.load()
    else:
        cookie = os.environ.get("FF_COOKIE")
        if not cookie:
            sys.exit("ERROR: 请设置 FF_COOKIE 环境变量或 --cookie-file")
        cookie_source = CookieSource(session=cookie)

    client = StereoTaskBoxClient(cookie_source)

    # ── 逐个上传 ──
    success = 0
    fail = 0
    work_dir = Path(tempfile.mkdtemp(prefix="batch-stereo-"))
    log_path = _ROOT_DIR / "runtime" / "logs" / f"batch-upload-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    for task_num, (idx, v) in enumerate(targets, 1):
        session_path = v["path"]
        session_name = os.path.basename(session_path.rstrip("\\/"))

        log(f"\n{'='*50}")
        log(f"[{task_num}/{len(targets)}] {session_name}")

        # ── 查维表补全元数据 ──
        recorder = lookup(recorders, "id", v.get("recorder_id", ""))
        task = lookup(tasks, "task_id", v.get("task_id", ""))
        env = lookup(environments, "env_id", v.get("env_id", ""))
        device = lookup(sd_cards, "volume_serial", v.get("device_id", ""))

        if not recorder:
            log(f"  ✗ recorder_id={v.get('recorder_id')} 未找到")
            fail += 1
            continue
        if not task:
            log(f"  ✗ task_id={v.get('task_id')} 未找到")
            fail += 1
            continue
        if not env:
            log(f"  ✗ env_id={v.get('env_id')} 未找到")
            fail += 1
            continue

        # 构建 task-box 参数
        scenario = (env.get("scene") or task.get("scene") or "Workshop").strip()
        task_desc = (task.get("process_en") or task.get("process") or "").strip()
        env_desc = (env.get("environment_description_en") or
                    env.get("environment_description") or "").strip()
        operator = (recorder.get("name") or recorder.get("id") or "").strip()
        capture_mode = (device.get("capture_mode") or "stereo").strip()

        log(f"  scenario: {scenario}")
        log(f"  task: {task_desc}")
        log(f"  env: {env_desc}")
        log(f"  operator: {operator}")
        log(f"  capture: {capture_mode}")

        # 验证 session 目录
        session_dir = Path(session_path)
        if not session_dir.is_dir():
            # 尝试 Windows 路径
            session_dir = Path(session_path.replace("/", "\\"))
        if not session_dir.is_dir():
            log(f"  ✗ 目录不存在: {session_path}")
            fail += 1
            continue

        try:
            parts, _ = validate_session_dir(session_dir)
            log(f"  ✓ {len(parts)} 个 .hmd 分片")
        except Exception as e:
            log(f"  ✗ 验证失败: {e}")
            fail += 1
            continue

        # ── 上传 ──
        try:
            row = upload_stereo_session(
                client,
                scenario=scenario,
                task_description=task_desc,
                environment=env_desc,
                operator=operator,
                session_dir=session_dir,
                folder_name=session_name,
                work_dir=work_dir,
                node_path=args.node_path,
                log_path=log_path,
            )
            if row["status"] == "complete":
                log(f"  ✓ 上传成功！ videoId={row['videoId']}")
                # 标记 CSV
                videos[idx]["uploaded"] = "Yes"
                success += 1
            else:
                log(f"  ✗ 上传失败: {row.get('error', 'unknown')}")
                fail += 1
        except Exception as e:
            log(f"  ✗ 异常: {e}")
            fail += 1

    # ── 回写 CSV ──
    if success > 0:
        tmp = str(csv_path) + ".tmp"
        with open(tmp, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(videos)
        os.replace(tmp, str(csv_path))
        log(f"\n已回写 CSV，标记 {success} 个视频为已上传")

    log(f"\n{'='*50}")
    log(f"完成: {success} 成功, {fail} 失败")
    log(f"日志: {log_path}")


if __name__ == "__main__":
    main()
