# -*- coding: utf-8 -*-
"""
fix_video_durations.py — 修复 video_manager.csv 中所有已预处理 HMD session 的 duration_sec。

策略（按优先级）：
  1) 如果 runtime/hmd_cache/<date>/<session>/left.mp4 存在 → ffprobe 获取真实容器时长（秒，整数）
  2) 如果无 left.mp4 但有 .hmd_fast.json (status=done) → 读 duration_sec
  3) 如果无 fast.json 但有 .hmd_process.json (status=done) → 读 duration_sec
  4) 如果都没有 → 保持原值不变，输出提醒

用法：
  python fix_video_durations.py          # 干跑（只查看变更）
  python fix_video_durations.py --apply  # 实际写入 CSV
"""
import os, sys, json, subprocess, re, csv, shutil
from datetime import datetime

# ── 路径 ──
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CSV_PATH = os.path.join(ROOT, "runtime", "data", "video_manager.csv")
CACHE_ROOT = os.path.join(ROOT, "runtime", "hmd_cache")
BACKUP_DIR = os.path.join(ROOT, "runtime", "csv_backups")

FFPROBE = os.path.join(ROOT, "tools", "ffmpeg", "bin", "ffprobe.exe")

# ── 从 path 提取日期 & session 名 ──
# 例如 /media\0619\hmd\4aa45c_session_00000 → date=2026-06-19, session=4aa45c_session_00000
_DATE_RE = re.compile(r'\\(0[1-9]|1[0-2])([0-3]\d)\\')  # \MMDD\
_SESSION_RE = re.compile(r'([^\\/]+)$')  # 路径末尾的 session 名


def parse_date_and_session(path):
    """从 CSV 的 path 列提取 YYYY-MM-DD 日期和 session 文件夹名"""
    path_norm = path.replace('/', '\\')
    m = _DATE_RE.search('\\' + path_norm + '\\')  # 确保前后有反斜杠
    if not m:
        return None, None
    mmdd = m.group(0).strip('\\')
    month = mmdd[:2]
    day = mmdd[2:4]
    year = "2026"  # 项目数据年份
    date_str = f"{year}-{month}-{day}"
    session = _SESSION_RE.search(path_norm)
    session = session.group(1) if session else None
    return date_str, session


def probe_mp4_duration(mp4_path):
    """用 ffprobe 获取 MP4 容器时长（秒，整数舍入）"""
    try:
        r = subprocess.run(
            [FFPROBE, "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", mp4_path],
            capture_output=True, text=True, timeout=20,
        )
        val = r.stdout.strip()
        if val:
            return int(round(float(val)))
    except Exception as e:
        print(f"  [WARN] ffprobe {mp4_path}: {e}")
    return None


def read_json_duration(json_path):
    """从状态 JSON 读取 duration_sec"""
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("status") == "done":
            sec = data.get("duration_sec")
            if isinstance(sec, (int, float)) and sec > 0:
                return int(round(float(sec)))
    except Exception:
        pass
    return None


def read_csv_rows(path):
    """读取 CSV，返回 (fieldnames, rows)"""
    if not os.path.exists(path):
        print(f"[ERROR] CSV not found: {path}")
        return None, []
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    return fieldnames, rows


def write_csv_rows(path, fieldnames, rows, encoding="utf-8-sig"):
    """原子写入 CSV"""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding=encoding, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, path)


def backup_csv(path):
    """备份 CSV 到 csv_backups 目录"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = os.path.join(BACKUP_DIR, f"video_manager_before_durfix_{ts}.csv")
    shutil.copy2(path, bak)
    print(f"[BACKUP] {bak}")


def main():
    # Fix Windows console encoding
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    apply = "--apply" in sys.argv
    mode = "APPLY" if apply else "DRY-RUN"

    print(f"=== Fix Video Durations ({mode}) ===\n")

    fieldnames, rows = read_csv_rows(CSV_PATH)
    if fieldnames is None:
        return 1

    updated = 0
    unchanged = 0
    skipped_no_cache = 0

    for i, r in enumerate(rows):
        path = r.get("path", "")
        ftype = r.get("file_type", "")
        if ftype != "hmd":
            unchanged += 1
            continue

        date_str, session = parse_date_and_session(path)
        if not date_str or not session:
            unchanged += 1
            continue

        old_dur = (r.get("duration_sec") or "").strip()
        new_dur = None
        source = ""

        cache_dir = os.path.join(CACHE_ROOT, date_str, session)
        # 新旧命名兼容：优先新命名 mp4，回退旧命名
        _mp4_new = os.path.join(cache_dir, f"{session}.mp4")
        _mp4_old = os.path.join(cache_dir, "left.mp4")
        mp4_path = _mp4_new if os.path.isfile(_mp4_new) else _mp4_old
        fast_json = os.path.join(cache_dir, ".hmd_fast.json")
        proc_json = os.path.join(cache_dir, ".hmd_process.json")

        # 策略 1: ffprobe left.mp4（最准确）
        if os.path.isfile(mp4_path):
            new_dur = probe_mp4_duration(mp4_path)
            if new_dur is not None:
                source = "ffprobe(mp4)"
        else:
            # 策略 2: .hmd_fast.json
            if os.path.isfile(fast_json):
                new_dur = read_json_duration(fast_json)
                if new_dur is not None:
                    source = "fast.json"
            # 策略 3: .hmd_process.json
            if new_dur is None and os.path.isfile(proc_json):
                new_dur = read_json_duration(proc_json)
                if new_dur is not None:
                    source = "process.json"

        # 没有新的时长数据
        if new_dur is None:
            if not old_dur:
                print(f"  [SKIP] {path} — 无缓存/MP4，原值为空")
            else:
                unchanged += 1  # 保持原值
            skipped_no_cache += 1
            continue

        new_dur_str = str(new_dur)

        # 对比
        if old_dur == new_dur_str:
            unchanged += 1
            continue

        # 数值接近（±2秒内）视为一致
        try:
            if abs(int(round(float(old_dur))) - new_dur) <= 2:
                unchanged += 1
                continue
        except Exception:
            pass

        # 需要更新
        old_label = old_dur if old_dur else "(empty)"
        print(f"  [FIX] {session} ({date_str})")
        print(f"       old: {old_label}  ->  new: {new_dur_str}  [{source}]")

        if apply:
            r["duration_sec"] = new_dur_str
        updated += 1

    print(f"\n--- Summary ---")
    print(f"  to fix: {updated}")
    print(f"  ok:     {unchanged}")
    print(f"  no data: {skipped_no_cache}")

    if updated > 0:
        if apply:
            backup_csv(CSV_PATH)
            write_csv_rows(CSV_PATH, fieldnames, rows, encoding="utf-8-sig")
            print(f"\n[DONE] Written to {CSV_PATH} ({updated} rows updated)")
        else:
            print(f"\n[DRY-RUN] Review above, then run:")
            print(f"   python fix_video_durations.py --apply")
    else:
        print(f"\n[OK] All durations are correct, no changes needed.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
