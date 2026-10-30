import os
import json
import glob
import re
import shutil
from datetime import datetime
from typing import Optional, Dict, List, Any
from config import *


def _migrate_tasks_env_to_environments():
    """One-shot: 从 tasks.csv 中提取环境字段，写入 environments.csv，
    并回填 video_manager.csv 的 env_id 列。

    适用范围：重构前 tasks 表单中内置了 scene/location_address/environment/
    environment_description/environment_description_en/facility_venue 等环境字段。
    重构后这些字段移到独立的 environments 维表。本迁移：

    1. 扫描 tasks.csv，按 environment_description 去重提取环境记录
    2. 生成 env_id（基于描述哈希）写入 environments.csv
    3. 构建 task_id → env_id 映射
    4. 更新 video_manager.csv：加入 env_id 列并回填，同时清理已废弃的旧列
    """
    import hashlib

    tasks_path = os.path.join(RUNTIME_DIR, "data", "tasks.csv")
    env_path = os.path.join(RUNTIME_DIR, "data", "environments.csv")

    # ── 1. 读取 tasks.csv ──
    if not os.path.exists(tasks_path):
        print("[migrate:env] tasks.csv not found, skip")
        return {}
    with open(tasks_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        tasks_all = list(reader)
    if not tasks_all:
        print("[migrate:env] tasks.csv empty, skip")
        return {}

    env_fields = ["scene", "location_address", "environment",
                  "environment_description", "environment_description_en",
                  "facility_venue"]
    if not all(f in (reader.fieldnames or []) for f in env_fields):
        print("[migrate:env] tasks.csv lacks env columns, skip")
        return {}

    # ── 2. 去重提取环境记录（以 environment_description 为唯一键） ──
    env_groups = {}       # desc → env_data dict
    task_env_map = {}     # task_id → env_id

    for t in tasks_all:
        desc = (t.get("environment_description") or "").strip()
        if not desc:
            continue
        if desc not in env_groups:
            # 生成确定性 env_id: "env_" + md5(desc)[:10]
            h = hashlib.md5(desc.encode("utf-8")).hexdigest()[:10]
            env_id = "env_" + h
            env_groups[desc] = {
                "env_id": env_id,
                "scene": (t.get("scene") or "").strip(),
                "location_address": (t.get("location_address") or "").strip(),
                "environment": (t.get("environment") or "").strip(),
                "environment_description": desc,
                "environment_description_en": (t.get("environment_description_en") or "").strip(),
                "facility_venue": (t.get("facility_venue") or "").strip(),
                "notes": "auto-migrated from tasks",
            }
        tid = (t.get("task_id") or "").strip()
        if tid:
            task_env_map[tid] = env_groups[desc]["env_id"]

    if not env_groups:
        print("[migrate:env] no env data found in tasks, skip")
        return {}

    # ── 3. 写入 environments.csv ──
    env_schema = ["env_id", "scene", "location_address",
                  "environment", "environment_description",
                  "environment_description_en", "facility_venue", "notes"]
    # 读取已有 environments（可能已有表头空文件或仅部分记录）
    existing_env = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8-sig") as f:
            er = csv.DictReader(f)
            for erow in er:
                eid = (erow.get("env_id") or "").strip()
                if eid:
                    existing_env[eid] = erow
    for _desc, edata in env_groups.items():
        if edata["env_id"] not in existing_env:
            existing_env[edata["env_id"]] = edata
    # 按 env_id 排序写入
    sorted_envs = sorted(existing_env.values(), key=lambda x: x["env_id"])
    with open(env_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=env_schema)
        writer.writeheader()
        for row in sorted_envs:
            writer.writerow({k: row.get(k, "") for k in env_schema})
    print(f"[migrate:env] wrote {len(sorted_envs)} environments to environments.csv")

    # ── 4. 更新 video_manager.csv ──
    video_path = os.path.join(RUNTIME_DIR, "data", "video_manager.csv")
    if not os.path.exists(video_path):
        print("[migrate:env] video_manager.csv not found, skip video backfill")
        return task_env_map

    # 读取视频表
    with open(video_path, "r", encoding="utf-8-sig") as f:
        vr = csv.DictReader(f)
        videos = list(vr)
        old_fields = list(vr.fieldnames or [])

    # 定义新的列顺序（来自 config.py DEFAULT_FIELDNAMES），排除已废弃的旧列
    _deprecated_fields = {"work_content_cn", "work_content_en", "category",
                          "upload_feasibility", "task_name"}
    new_fields = [
        "path", "location_status", "scan_date", "original_history_date",
        "uploaded", "extra_description", "score",
        "duration_sec", "file_type", "device_id", "recorder_id",
        "task_id", "env_id",
    ]
    # 保留不在新旧定义中的字段（如用户自定义），但排除已废弃列
    for f in old_fields:
        if f not in new_fields and f not in _deprecated_fields:
            new_fields.append(f)

    # 回填 env_id
    updated_count = 0
    for v in videos:
        tid = (v.get("task_id") or "").strip()
        if tid and tid in task_env_map:
            v["env_id"] = task_env_map[tid]
            updated_count += 1
        elif "env_id" not in v:
            v["env_id"] = ""

    # 备份原 CSV
    try:
        backup_dir = os.path.join(RUNTIME_DIR, "csv_backups")
        os.makedirs(backup_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"video_manager_before_env_migration_{ts}.csv")
        shutil.copy2(video_path, backup_path)
        print(f"[migrate:env] video backup → {backup_path}")
    except Exception as e:
        print(f"[migrate:env] backup warning: {e}")

    # 写回（新列顺序）
    with open(video_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=new_fields, extrasaction="ignore")
        writer.writeheader()
        for v in videos:
            writer.writerow({k: v.get(k, "") for k in new_fields})

    print(f"[migrate:env] backfilled env_id for {updated_count}/{len(videos)} videos")
    return task_env_map


