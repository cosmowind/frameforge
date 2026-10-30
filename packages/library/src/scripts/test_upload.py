#!/usr/bin/env python3
"""
自动上传测试脚本 — 以第一条已填写内容的记录做测试
用法: python test_upload.py [--dry-run] [--execute]
  --dry-run    只构建并显示上传模板，不实际执行上传
  --execute    执行实际上传（需要浏览器）
"""

import argparse
import asyncio
import csv
import json
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))


def load_csv_rows():
    csv_path = BASE_DIR / "video_manager.csv"
    if not csv_path.exists():
        return []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def find_first_filled_record(rows):
    """找到第一条已填写内容的记录（有 device_id + recorder_id + task_id）"""
    for idx, row in enumerate(rows):
        did = (row.get("device_id") or "").strip()
        cid = (row.get("recorder_id") or "").strip()
        tid = (row.get("task_id") or "").strip()
        uploaded = (row.get("uploaded") or "").strip()
        if did and cid and tid and uploaded != "Yes":
            return idx, row
    return None, None


def show_template(template: dict):
    """显示上传模板的关键字段"""
    print("\n" + "=" * 60)
    print("  上传模板预览")
    print("=" * 60)

    # 分组显示
    groups = {
        "Task Attributes": [
            "operator_name", "operator_job", "operator_consent",
            "task_difficulty", "task_description", "environment_description",
        ],
        "Environment & Location": [
            "country", "state_province", "city", "location_address",
            "environment", "facility_venue", "scene",
            "business_type", "business_name",
        ],
        "Operator": [
            "age_range", "gender", "handedness", "gloves",
            "workforce_type", "role_experience", "task_experience",
            "collection_hours_today", "collection_experience_days",
            "hand_size_cm",
        ],
        "Other": [],
    }

    # 收集未分类的字段
    shown = set()
    for group_fields in groups.values():
        shown.update(group_fields)

    for group_name, fields in groups.items():
        if group_name == "Other":
            fields = [k for k in template if k not in shown]
        if not fields:
            continue
        print(f"\n  [{group_name}]")
        for f in fields:
            val = template.get(f, "")
            if val:
                # 检测中文
                import re
                has_cn = bool(re.search(r'[\u4e00-\u9fff]', str(val)))
                flag = " ⚠ 含中文!" if has_cn else ""
                print(f"    {f:30s} = {str(val)[:80]}{flag}")
            else:
                print(f"    {f:30s} = (空)")

    print("\n" + "=" * 60)


def main():
    ap = argparse.ArgumentParser(description="自动上传测试")
    ap.add_argument("--dry-run", action="store_true", help="只显示模板，不执行上传")
    ap.add_argument("--execute", action="store_true", help="执行实际上传")
    args = ap.parse_args()

    if not args.dry_run and not args.execute:
        ap.print_help()
        print("\n请指定 --dry-run（预览）或 --execute（执行上传）")
        return 1

    # 1) 加载 CSV 并找到测试记录
    rows = load_csv_rows()
    print(f"已加载 {len(rows)} 条记录")

    idx, row = find_first_filled_record(rows)
    if row is None:
        print("✗ 未找到已填写内容的未上传记录")
        return 1

    print(f"\n测试记录 (行 {idx}):")
    print(f"  路径:     {row['path']}")
    print(f"  设备:     {row.get('device_id', '')}")
    print(f"  录入员:   {row.get('recorder_id', '')}")
    print(f"  任务:     {row.get('task_id', '')}")
    print(f"  时长:     {row.get('duration_sec', '')} 秒")
    print(f"  已上传:   {row.get('uploaded', '')}")

    # 2) 构建上传模板
    from auto_upload import _build_template_from_row

    template = _build_template_from_row(row, idx)
    show_template(template)

    # 3) 检查是否需要翻译
    from auto_upload import _auto_translate_template
    _auto_translate_template(template)

    # 显示翻译后结果
    print("\n[翻译后模板]")
    show_template(template)

    # 4) 最终中文检测
    import re
    cn = re.compile(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]')
    bad_fields = []
    for f, v in template.items():
        if v and isinstance(v, str) and cn.search(v):
            bad_fields.append(f)

    if bad_fields:
        print(f"\n✗ 仍有 {len(bad_fields)} 个字段包含中文: {bad_fields}")
        if not args.execute:
            return 1
        print("⚠ 将继续执行上传（翻译已尽力），但可能被预检查拒绝")
    else:
        print("\n✓ 所有字段均为英文，可以安全上传")

    if args.dry_run:
        print("\n[dry-run] 模板检查完成，未执行实际上传")
        return 0

    # 5) 执行实际上传
    print("\n>>> 开始执行上传...")
    from auto_upload import AutoUploader, LOG_DIR, _resolve_hmd_video, _is_hmd_session
    from datetime import datetime

    original_path = row.get("path", "").strip()
    is_hmd = _is_hmd_session(original_path)
    video_path = original_path      # 用于日志/备用
    hmd_folder: str | None = None   # HMD 原始会话文件夹

    if is_hmd:
        # 保留原始文件夹路径，用于注入到 Preview 区
        hmd_folder = original_path
        resolved = _resolve_hmd_video(original_path)
        if not resolved:
            print(f"✗ HMD 会话无可用视频: {original_path}")
            return 1
        video_path = resolved
        print(f"HMD 会话，原始文件夹: {hmd_folder}")
        print(f"HMD 会话，备用视频:  {video_path}")

    log_path = LOG_DIR / f"test_upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    async def do_upload():
        uploader = AutoUploader(log_path=log_path)

        try:
            if not await uploader.start():
                print("✗ 浏览器启动失败/登录未完成")
                await uploader.cleanup()
                return 1

            success = await uploader.upload_one(video_path, template,
                                                hmd_folder=hmd_folder)

            if success:
                print("✓ 上传成功！")
                from auto_upload import mark_uploaded, load_state, save_state
                mark_uploaded(idx)
                state = load_state()
                state.setdefault("uploaded", []).append(
                    video_path.replace("\\", "/")
                )
                save_state(state)
            else:
                print("✗ 上传失败")
                from auto_upload import load_state, save_state
                state = load_state()
                state.setdefault("failed", []).append(
                    video_path.replace("\\", "/")
                )
                save_state(state)

            await uploader.cleanup()
            return 0 if success else 1

        except KeyboardInterrupt:
            print("⏹ 用户取消")
            await uploader.cleanup()
            return 130
        except Exception as e:
            print(f"✗ 异常: {type(e).__name__}: {e}")
            await uploader.cleanup()
            return 1

    return asyncio.run(do_upload())


if __name__ == "__main__":
    sys.exit(main())
