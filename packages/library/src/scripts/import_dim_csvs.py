# ────────────────────────────────────────────────────────────────
# import_dim_csvs.py — 把 runtime/data_维表汇总_<date>/ 下的 4 个 CSV
# 合并 / 复制到 runtime/data/，使 _DIM_REGISTRY 可以直接读取
#
# 业务背景：用户在 2026-06-26 提供了一份"维表汇总"打包，把所有已经维护好的
# 任务/环境/录入员/设备数据导出来放在 runtime/data_维表汇总_20260626/ 下。
# 本脚本做一次性导入，使新开 branch 后能立即用上这些数据。
#
# 用法：
#   python src/scripts/import_dim_csvs.py
#   python src/scripts/import_dim_csvs.py --src runtime/data_维表汇总_20260626 --yes
#
# 行为：
#   - 4 个 dim（recorders / sd_cards / tasks / environments）按 _DIM_REGISTRY["schema"]
#     字段顺序重写，缺失列填空，CSV-injection 防御
#   - 如果目标 runtime/data/<dim>.csv 已有内容，询问用户合并策略：
#       * merge  : 按主键去重合并（新增为主，已有保留）
#       * replace: 覆盖（先备份原文件）
#   - 完成后打印每个 dim 的 (已存在, 新增, 总数)
# ────────────────────────────────────────────────────────────────

import argparse
import csv
import os
import re
import shutil
import sys
from datetime import datetime

# ── 路径 ──
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "src"))

from config import RUNTIME_DIR, _DIM_REGISTRY, _CSV_INJECTION_LEAD  # noqa: E402


# 4 个维表的标准输入文件名
DIM_INPUT_FILENAME = {
    "recorders":   "recorders.csv",
    "sd_cards":     "sd_cards.csv",
    "tasks":        "tasks.csv",
    "environments": "environments.csv",
}


def _sanitize_value(v):
    """CSV-injection 防御 + strip。"""
    if v is None:
        return ""
    if isinstance(v, str):
        v = v.strip()
        if v and v[0] in _CSV_INJECTION_LEAD:
            v = "'" + v
    return v if v is not None else ""


def _read_source_csv(path):
    """读取源 CSV（utf-8-sig 兼容 BOM），返回 list[dict]。"""
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return [(row or {}) for row in reader]


def _read_target_csv(path, schema):
    """读取目标 CSV（已存在时）。不存在返回空。"""
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return [{fn: row.get(fn, "") for fn in schema} for row in reader]


def _atomic_write(path, rows, schema):
    """原样写入（不重排字段顺序，调用方需保证 schema 对齐）。"""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=schema, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({fn: row.get(fn, "") for fn in schema})
    os.replace(tmp, path)


def _backup_file(path, tag):
    """把已有文件备份到 runtime/csv_backups/<tag>_<ts>.csv。"""
    if not os.path.exists(path):
        return None
    backup_dir = os.path.join(RUNTIME_DIR, "csv_backups")
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"{tag}_{ts}.csv")
    shutil.copy2(path, backup_path)
    return backup_path


def _normalize_row(row, schema):
    """按 schema 顺序补齐缺失字段，并清洗所有字符串值。"""
    out = {}
    for fn in schema:
        v = row.get(fn, "")
        out[fn] = _sanitize_value(v)
    return out


def import_one_dim(name, src_path, dst_path, schema, key, mode):
    """导入单个维表。返回 (existing_count, new_count, total_count)。"""
    src_rows_raw = _read_source_csv(src_path)
    src_rows = [_normalize_row(r, schema) for r in src_rows_raw]
    # 丢掉主键为空的行（避免 import 时插入空记录）
    src_rows = [r for r in src_rows if r.get(key, "").strip()]
    src_keys = {r.get(key, "") for r in src_rows}

    if not os.path.exists(dst_path):
        # 全新：直接写入
        _atomic_write(dst_path, src_rows, schema)
        return 0, len(src_rows), len(src_rows)

    if mode == "replace":
        # 覆盖前先备份
        backup = _backup_file(dst_path, f"dim_{name}_before_replace")
        if backup:
            print(f"  [backup] {backup}")
        _atomic_write(dst_path, src_rows, schema)
        return 0, len(src_rows), len(src_rows)

    # mode == "merge"：按主键去重合并（src 覆盖 dst，dst 保留 src 没有的）
    dst_rows = _read_target_csv(dst_path, schema)
    dst_by_key = {r.get(key, ""): r for r in dst_rows}
    existing_in_src = 0
    added = 0
    for r in src_rows:
        k = r.get(key, "")
        if k in dst_by_key:
            dst_by_key[k] = r
            existing_in_src += 1
        else:
            dst_by_key[k] = r
            added += 1
    merged = list(dst_by_key.values())
    _atomic_write(dst_path, merged, schema)
    return existing_in_src, added, len(merged)


def main():
    p = argparse.ArgumentParser(description="把维表汇总目录的 4 个 CSV 合并到 runtime/data/")
    p.add_argument("--src", default=None,
                   help="源目录（默认自动选 runtime/ 下最新的 data_维表汇总_*）")
    p.add_argument("--yes", action="store_true",
                   help="跳过交互确认，默认 replace 模式")
    p.add_argument("--mode", choices=["merge", "replace"], default="merge",
                   help="目标文件已存在时的策略：merge=按主键合并（默认）/ replace=覆盖（先备份）")
    args = p.parse_args()

    # ── 自动选最新汇总目录 ──
    if args.src:
        src_dir = args.src
    else:
        candidates = []
        if os.path.isdir(RUNTIME_DIR):
            for fn in os.listdir(RUNTIME_DIR):
                if fn.startswith("data_维表汇总_") and os.path.isdir(os.path.join(RUNTIME_DIR, fn)):
                    candidates.append(os.path.join(RUNTIME_DIR, fn))
        if not candidates:
            print("未找到 runtime/data_维表汇总_*/ 目录；请用 --src 指定。", file=sys.stderr)
            return 1
        candidates.sort(key=os.path.getmtime, reverse=True)
        src_dir = candidates[0]
    print(f"[import] 源目录: {src_dir}")

    data_dir = os.path.join(RUNTIME_DIR, "data")
    os.makedirs(data_dir, exist_ok=True)

    # ── 逐表导入 ──
    summary = []
    for name in ("recorders", "sd_cards", "tasks", "environments"):
        spec = _DIM_REGISTRY.get(name)
        if not spec:
            continue
        schema = spec["schema"]
        key = spec["key"]
        dst_path = spec["path"]
        input_name = DIM_INPUT_FILENAME.get(name)
        src_path = os.path.join(src_dir, input_name) if input_name else None
        if not src_path or not os.path.exists(src_path):
            print(f"  [{name}] 源文件不存在，跳过: {src_path}")
            continue

        # 模式选择
        target_exists = os.path.exists(dst_path)
        if target_exists and not args.yes:
            # 交互：merge / replace / skip
            prompt = (f"  [{name}] 目标已存在: {dst_path} ({len(_read_target_csv(dst_path, schema))} 行)\n"
                      f"    merge=按主键合并 / replace=覆盖（备份原文件） / skip=跳过  [m/r/s]: ")
            try:
                ans = input(prompt).strip().lower()
            except EOFError:
                ans = "m"
            if ans in ("r", "replace"):
                mode = "replace"
            elif ans in ("s", "skip"):
                print(f"    [{name}] 跳过")
                continue
            else:
                mode = "merge"
        else:
            mode = args.mode if target_exists else "merge"

        existing, added, total = import_one_dim(name, src_path, dst_path, schema, key, mode)
        print(f"  [{name:13s}] mode={mode:7s} | 已存在 {existing:3d} | 新增 {added:3d} | 总数 {total:3d}")
        summary.append((name, mode, existing, added, total))

    print()
    print("─" * 56)
    print(f"{'dim':15s} {'mode':10s} {'existing':>8s} {'added':>8s} {'total':>8s}")
    for name, mode, existing, added, total in summary:
        print(f"{name:15s} {mode:10s} {existing:8d} {added:8d} {total:8d}")
    print("─" * 56)
    print(f"[import] 完成。目标目录: {data_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
