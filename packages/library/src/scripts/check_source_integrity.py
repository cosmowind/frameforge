#!/usr/bin/env python
"""
HMD 源文件完整性检查 - 预处理前置检查。

检查项：
1. session 目录存在
2. metadata.json 存在且有效
3. 至少一个 part_*.hmd 文件存在
4. 每个 part_*.hmd 文件大小 > 0

输出：完整 / 警告 / 错误 三级列表
"""
import os
import sys
import csv
import json
import glob

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CSV_PATH = os.path.join(PROJECT_ROOT, "runtime", "data", "video_manager.csv")


def check_session(path):
    """检查单个 session 源文件完整性。

    Returns: (level, issues, details)
      level: "ok" | "warn" | "error"
      issues: list of problem strings
      details: dict with file info
    """
    issues = []
    details = {}

    # 1. 目录存在
    if not os.path.isdir(path):
        return "error", ["目录不存在"], details

    files = os.listdir(path)

    # 2. metadata.json
    meta_ok = False
    if "metadata.json" in files:
        meta_path = os.path.join(path, "metadata.json")
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                json.load(f)
            meta_ok = True
        except Exception as e:
            issues.append(f"metadata.json 无效: {e}")
    else:
        issues.append("metadata.json 缺失")

    # 3. part_*.hmd 文件
    parts = glob.glob(os.path.join(path, "part_*.hmd"))
    parts = [p for p in parts if os.path.isfile(p)]

    if not parts:
        issues.append("没有 part_*.hmd 文件")
        return "error", issues, details

    # 4. 检查每个 part 文件大小
    empty_parts = []
    tiny_parts = []  # < 1MB 视为可疑
    total_size = 0
    for p in parts:
        sz = os.path.getsize(p)
        total_size += sz
        if sz == 0:
            empty_parts.append(os.path.basename(p))
        elif sz < 1024 * 1024:
            tiny_parts.append((os.path.basename(p), sz))

    if empty_parts:
        for ep in empty_parts:
            issues.append(f"空文件: {ep}")
        return "error", issues, details

    if tiny_parts:
        for tp, sz in tiny_parts:
            issues.append(f"文件过小 (<1MB): {tp} ({sz/1024:.0f}KB)")

    # 综合判断
    level = "ok"
    if issues:
        level = "warn"
    if not meta_ok:
        level = "error"

    details = {
        "parts": [os.path.basename(p) for p in parts],
        "part_count": len(parts),
        "total_size_mb": total_size / 1024 / 1024,
        "has_metadata": meta_ok,
    }

    return level, issues, details


def main():
    print("=" * 70)
    print("HMD 源文件完整性检查")
    print("=" * 70)
    print(f"CSV: {CSV_PATH}\n")

    rows = []
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    local_hmd = [
        r for r in rows
        if r.get("file_type", "").strip().lower() == "hmd"
        and (r.get("location_status") or '').endswith('_local')
    ]

    print(f"本地 HMD session 总数: {len(local_hmd)}\n")

    ok_sessions = []
    warn_sessions = []
    error_sessions = []

    for r in local_hmd:
        path = r.get("path", "").strip()
        if not path:
            continue
        level, issues, details = check_session(path)
        entry = {
            "path": path,
            "name": os.path.basename(os.path.normpath(path)),
            "issues": issues,
            "details": details,
        }
        if level == "ok":
            ok_sessions.append(entry)
        elif level == "warn":
            warn_sessions.append(entry)
        else:
            error_sessions.append(entry)

    # 输出
    if error_sessions:
        print(f"[错误] {len(error_sessions)} 个 session 源文件不完整，无法预处理:")
        for e in error_sessions:
            print(f"  ✗ {e['name']}")
            for iss in e["issues"]:
                print(f"      {iss}")
        print()

    if warn_sessions:
        print(f"[警告] {len(warn_sessions)} 个 session 有小问题（可尝试预处理）:")
        for w in warn_sessions:
            print(f"  ⚠ {w['name']}")
            for iss in w["issues"]:
                print(f"      {iss}")
        print()

    print(f"[正常] {len(ok_sessions)} 个 session 源文件完整，可以预处理")

    # 输出汇总 CSV
    summary_path = os.path.join(PROJECT_ROOT, "runtime", "source_integrity_check.csv")
    with open(summary_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["status", "session_name", "path", "issues", "part_count", "size_mb", "has_metadata"])
        for e in error_sessions:
            writer.writerow([
                "ERROR", e["name"], e["path"],
                "; ".join(e["issues"]),
                e["details"].get("part_count", ""),
                f"{e['details'].get('total_size_mb', 0):.1f}",
                e["details"].get("has_metadata", ""),
            ])
        for w in warn_sessions:
            writer.writerow([
                "WARN", w["name"], w["path"],
                "; ".join(w["issues"]),
                w["details"].get("part_count", ""),
                f"{w['details'].get('total_size_mb', 0):.1f}",
                w["details"].get("has_metadata", ""),
            ])
        for o in ok_sessions:
            writer.writerow([
                "OK", o["name"], o["path"],
                "",
                o["details"].get("part_count", ""),
                f"{o['details'].get('total_size_mb', 0):.1f}",
                o["details"].get("has_metadata", ""),
            ])
    print(f"\n详细报告: {summary_path}")

    # 返回码：error 数量
    return 0 if len(error_sessions) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
