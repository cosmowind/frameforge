#!/usr/bin/env python
"""
HMD 预处理管理器 - 批量重新生成所有本地视频的预处理文件。

功能：
1. 扫描 video_manager.csv 中所有本地 HMD session
2. 创建独立的管理 CSV（preprocess_manager.csv），追踪每个 session 的预处理状态
3. 依次执行：fast_preprocess（h265 + frames + cover）→ hmd_preprocess（mp4）
4. 全程状态持久化 + 进度 + 预计剩余时间
5. 处理完成后清理冗余 h265（mp4 验证完好后）

管理 CSV 字段：
  pm_id              - 唯一标识（UUID）
  video_id           - video_manager.csv 对应行索引（跨表查询用）
  session_path       - HMD session 源文件夹路径
  session_name       - session 目录名
  status             - pending / processing_fast / processing_mp4 / done / error
  has_h265           - Y/N
  has_frames         - Y/N
  has_cover          - Y/N
  has_mp4            - Y/N
  frames_count       - frames 数量
  cache_dir          - hmd_cache 路径
  mp4_path           - mp4 完整路径
  cover_path         - cover.jpg 完整路径
  h265_path          - h265 完整路径
  frames_dir         - frames 目录完整路径
  progress_pct       - 总进度 0-100
  error_msg          - 错误信息
  fast_stage         - fast 阶段标记
  mp4_stage          - mp4 阶段标记
  created_at         - 记录创建时间
  started_at         - fast 处理开始时间
  finished_at        - 完成时间

Usage:
    python preprocess_manager.py --dry-run   # 只扫描不处理
    python preprocess_manager.py --fast-only  # 只做 fast（h265+frames+cover），不做 mp4
    python preprocess_manager.py              # 完整管线
    python preprocess_manager.py --force      # 强制重跑已完成的项目
"""
import os
import sys
import time
import uuid

# 项目路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src", "tools"))

from scripts.pm_helpers import (
    CSV_PATH, PM_CSV, PM_FIELDS, EST_FAST_SEC, EST_MP4_SEC,
    now_iso, parse_args, ensure_pm_csv, read_pm_csv, write_pm_csv,
    read_video_csv, get_local_hmd_sessions,
    get_hmd_fast, get_hmd, get_cache_dir,
    check_session_actual_state, mp4_is_playable,
)


# ───────────────────────────────────────────────────────────────
# 单 session 处理
# ───────────────────────────────────────────────────────────────

def process_single_session(pm_row, force=False, fast_only=False, progress_callback=None):
    """处理单个 session 的完整预处理管线。

    返回更新后的 pm_row dict。
    """
    session_path = pm_row["session_path"]
    base = os.path.basename(os.path.normpath(session_path))
    from tools import hmd_fast as uf
    import hmd_preprocess as up

    # 检查当前实际状态
    state = check_session_actual_state(session_path)

    # 更新 pm_row 基础字段
    pm_row["cache_dir"] = state["cache_dir"]
    pm_row["h265_path"] = state["h265_path"]
    pm_row["mp4_path"] = state["mp4_path"]
    pm_row["cover_path"] = state["cover_path"]
    pm_row["frames_dir"] = state["frames_dir"]
    pm_row["has_h265"] = "Y" if state["has_h265"] else "N"
    pm_row["has_mp4"] = "Y" if state["has_mp4"] else "N"
    pm_row["has_cover"] = "Y" if state["has_cover"] else "N"
    pm_row["has_frames"] = "Y" if state["has_frames"] else "N"
    pm_row["frames_count"] = state["frames_count"]

    # 决定是否需要处理
    already_done = (
        state["has_mp4"] and state["has_cover"] and state["has_frames"] and
        mp4_is_playable(state["mp4_path"])
    )

    if already_done and not force:
        pm_row["status"] = "done"
        pm_row["progress_pct"] = "100"
        pm_row["finished_at"] = now_iso()
        pm_row["error_msg"] = ""
        return pm_row

    # ── Stage 1: Fast Preprocess ──────────────────────────────
    if not state["has_mp4"] or not state["has_cover"] or not state["has_frames"] or force:
        pm_row["status"] = "processing_fast"
        pm_row["started_at"] = pm_row["started_at"] or now_iso()
        pm_row["error_msg"] = ""
        if progress_callback:
            progress_callback(pm_row, "fast_start", "开始快速预处理...")

        try:
            # 清除旧状态文件（强制重跑时）
            if force:
                for f in [os.path.join(state["cache_dir"], ".hmd_fast.json")]:
                    if os.path.isfile(f):
                        os.unlink(f)

            # 执行 fast
            print(f"  [FAST] {base}")
            uf.process_fast(session_path, extract_frames=True, extract_cover=True)

            # 重新检查
            state = check_session_actual_state(session_path)
            pm_row["has_h265"] = "Y" if state["has_h265"] else "N"
            pm_row["has_mp4"] = "Y" if state["has_mp4"] else "N"
            pm_row["has_cover"] = "Y" if state["has_cover"] else "N"
            pm_row["has_frames"] = "Y" if state["has_frames"] else "N"
            pm_row["frames_count"] = state["frames_count"]
            pm_row["h265_path"] = state["h265_path"]
            pm_row["cover_path"] = state["cover_path"]
            pm_row["frames_dir"] = state["frames_dir"]

            if state["fast_status"]:
                pm_row["fast_stage"] = state["fast_status"].get("stage", "")

            if progress_callback:
                progress_callback(pm_row, "fast_done", f"fast 完成: cover={state['has_cover']} frames={state['frames_count']}/6")

        except Exception as e:
            pm_row["error_msg"] = str(e)
            pm_row["status"] = "error"
            return pm_row

    # ── 完成后验证 mp4 ──────────────────────────────────────
    # 注意：process_fast 已经完成了 h265→mp4 的 remux，
    #       且会删除 left.h265，所以 has_h265 在此时通常是 "N"。
    state = check_session_actual_state(session_path)
    pm_row["has_h265"] = "Y" if state["has_h265"] else "N"
    pm_row["has_mp4"] = "Y" if state["has_mp4"] else "N"
    pm_row["mp4_path"] = state["mp4_path"]

    # 允许 5/6 帧（短视频可能总帧数不足 6）
    has_enough_frames = state["frames_count"] >= 3

    if state["has_mp4"] and state["has_cover"] and has_enough_frames:
        # 进一步用 ffprobe 验证 mp4 可播放
        if mp4_is_playable(state["mp4_path"]):
            pm_row["status"] = "done"
            pm_row["progress_pct"] = "100"
            pm_row["finished_at"] = now_iso()
            pm_row["error_msg"] = ""
        else:
            pm_row["status"] = "error"
            pm_row["error_msg"] = "mp4 不可播放（ffprobe 验证失败）"
            pm_row["progress_pct"] = "80"
    elif state["has_mp4"] and (state["has_cover"] or has_enough_frames):
        # 有 mp4 但缺封面或帧不足，标记为部分完成，等待下次处理
        pm_row["status"] = "pending"
        pm_row["progress_pct"] = "80"
    else:
        # mp4 还没生成
        pm_row["status"] = "pending"
        pm_row["progress_pct"] = "50" if state["has_cover"] else "0"

    return pm_row


# ───────────────────────────────────────────────────────────────
# 主程序
# ───────────────────────────────────────────────────────────────

def main():
    args = parse_args()

    print("=" * 70)
    print("HMD 预处理管理器")
    print("=" * 70)
    print(f"视频管理 CSV: {CSV_PATH}")
    print(f"预处理管理 CSV: {PM_CSV}")
    print(f"模式: {'dry-run' if args.dry_run else 'live'}", end="")
    if args.fast_only:
        print(" | fast-only (跳过 mp4)", end="")
    if args.force:
        print(" | force (重跑已完成)", end="")
    print()
    print()

    # ── Step 1: 扫描 video_manager.csv ──────────────────────
    print("[1/5] 扫描 video_manager.csv ...")
    video_rows = read_video_csv()
    local_sessions = get_local_hmd_sessions(video_rows)

    # 过滤掉 extra_description 匹配的项目
    if args.skip_extra_desc is not None:
        skip_val = args.skip_extra_desc.strip()
        before = len(local_sessions)
        local_sessions = [r for r in local_sessions if r.get("extra_description", "").strip() != skip_val]
        print(f"      本地 HMD session 数量: {before} → {len(local_sessions)} (跳过 extra_description={skip_val!r})")
    else:
        print(f"      本地 HMD session 数量: {len(local_sessions)}")

    if not local_sessions:
        print("没有找到本地 HMD session，退出。")
        return 0

    # ── Step 2: 读取/初始化管理 CSV ────────────────────────
    print("[2/5] 初始化预处理管理 CSV ...")
    ensure_pm_csv()
    pm_rows = read_pm_csv()

    # 建立 video_index → video_row 的映射
    video_path_to_index = {r["path"]: r["index"] for r in video_rows}

    # 初始化新 session（不在管理 CSV 中的）
    new_count = 0
    for vs in local_sessions:
        sp = vs["path"]
        if sp not in pm_rows:
            pm_id = str(uuid.uuid4())[:8]
            video_idx = video_path_to_index.get(sp, "")
            pm_rows[sp] = {
                "pm_id": pm_id,
                "video_id": str(video_idx),
                "session_path": sp,
                "session_name": os.path.basename(os.path.normpath(sp)),
                "status": "pending",
                "has_h265": "N", "has_frames": "N", "has_cover": "N", "has_mp4": "N",
                "frames_count": "0",
                "cache_dir": "",
                "mp4_path": "", "cover_path": "", "h265_path": "", "frames_dir": "",
                "progress_pct": "0",
                "error_msg": "",
                "fast_stage": "",
                "mp4_stage": "",
                "created_at": now_iso(),
                "started_at": "",
                "finished_at": "",
            }
            new_count += 1

    print(f"      管理 CSV 已有: {len(pm_rows)} 个 | 新增: {new_count} 个")

    # ── Step 3: 估算时间 ──────────────────────────────────
    print("[3/5] 计算处理计划 ...")
    pending = [r for r in pm_rows.values()
               if r["status"] in ("pending", "error") or
               (args.force and r["status"] == "done")]
    total_count = len(pending)

    if total_count == 0:
        print("      所有 session 均已完成，无需处理。")
        all_done = all(r["status"] == "done" for r in pm_rows.values())
        print(f"      当前状态: {'全部完成 ✓' if all_done else '有错误'}")
        write_pm_csv(pm_rows)
        return 0 if all_done else 1

    est_fast = total_count * EST_FAST_SEC
    est_mp4 = total_count * EST_MP4_SEC
    total_est = est_fast + (0 if args.fast_only else est_mp4)

    print(f"      待处理: {total_count} 个 session")
    print(f"      预计时间: {total_count}×fast({EST_FAST_SEC}s) = {est_fast}s", end="")
    if not args.fast_only:
        print(f" + {total_count}×mp4({EST_MP4_SEC}s) = {total_est}s")
        print(f"             约 {total_est/60:.0f} 分钟")
    else:
        print(f" (跳过 mp4)")

    # ── Step 4: 统计当前状态 ────────────────────────────────
    stats = {"total": len(pm_rows), "done": 0, "pending": 0,
             "processing": 0, "error": 0, "done_h265": 0,
             "done_frames": 0, "done_cover": 0, "done_mp4": 0}
    for r in pm_rows.values():
        stats[r["status"]] = stats.get(r["status"], 0) + 1
        if r["has_h265"] == "Y":
            stats["done_h265"] += 1
        if r["has_frames"] == "Y":
            stats["done_frames"] += 1
        if r["has_cover"] == "Y":
            stats["done_cover"] += 1
        if r["has_mp4"] == "Y":
            stats["done_mp4"] += 1

    print()
    print("      当前状态总览:")
    print(f"        总 session: {stats['total']}")
    print(f"        已完成: {stats['done']}  |  待处理: {stats['pending']}  |  处理中: {stats.get('processing_fast',0)+stats.get('processing_mp4',0)}  |  错误: {stats['error']}")
    print(f"        h265: {stats['done_h265']}  |  frames: {stats['done_frames']}  |  cover: {stats['done_cover']}  |  mp4: {stats['done_mp4']}")
    print()

    if args.dry_run:
        print("[DRY-RUN] 以下 session 将被处理:")
        for r in pending:
            print(f"  [{r['status']}] {r['session_name']}")
        write_pm_csv(pm_rows)
        return 0

    # ── Step 5: 逐个处理 ───────────────────────────────────
    print("[4/5] 开始批量预处理 ...")
    print("=" * 70)

    done_count = 0
    start_time = time.time()
    errors = []

    def progress_cb(pm_row, stage, msg):
        elapsed = time.time() - start_time
        done_so_far = done_count
        remaining = total_count - done_so_far - 1
        if remaining > 0 and elapsed > 0:
            rate = elapsed / max(done_so_far, 1)
            eta = remaining * rate
            eta_str = f"ETA {eta/60:.0f}min"
        else:
            eta_str = ""
        pct = pm_row.get("progress_pct", "0")
        print(f"  [{done_so_far+1}/{total_count}] {pm_row['session_name']} | {stage} | {msg} {eta_str}")

    for i, pm_row in enumerate(pending):
        sp = pm_row["session_path"]
        base = pm_row["session_name"]

        # 再次检查状态（可能其他进程更新过）
        state = check_session_actual_state(sp)
        pm_row["cache_dir"] = state["cache_dir"]
        pm_row["h265_path"] = state["h265_path"]
        pm_row["mp4_path"] = state["mp4_path"]
        pm_row["cover_path"] = state["cover_path"]
        pm_row["frames_dir"] = state["frames_dir"]
        pm_row["has_h265"] = "Y" if state["has_h265"] else "N"
        pm_row["has_mp4"] = "Y" if state["has_mp4"] else "N"
        pm_row["has_cover"] = "Y" if state["has_cover"] else "N"
        pm_row["has_frames"] = "Y" if state["has_frames"] else "N"
        pm_row["frames_count"] = state["frames_count"]

        already_done = (
            state["has_mp4"] and state["has_cover"] and state["has_frames"] and
            mp4_is_playable(state["mp4_path"])
        )
        if already_done and not args.force:
            pm_row["status"] = "done"
            pm_row["progress_pct"] = "100"
            pm_row["finished_at"] = pm_row["finished_at"] or now_iso()
            write_pm_csv(pm_rows)
            done_count += 1
            print(f"  [SKIP] {base} (已完好)")
            continue

        print(f"\n[{i+1}/{total_count}] 处理: {base}")
        done_count += 1

        try:
            pm_row = process_single_session(
                pm_row,
                force=args.force,
                fast_only=args.fast_only,
                progress_callback=progress_cb,
            )
        except Exception as e:
            pm_row["status"] = "error"
            pm_row["error_msg"] = str(e)
            errors.append((base, str(e)))

        write_pm_csv(pm_rows)

        # 进度展示
        elapsed = time.time() - start_time
        done_total = sum(1 for r in pm_rows.values() if r["status"] == "done")
        pct = int(done_total / len(pm_rows) * 100) if pm_rows else 0
        remaining = total_count - i - 1
        if remaining > 0 and elapsed > 0:
            rate = elapsed / max(i + 1, 1)
            eta = remaining * rate
            print(f"  -> 进度: {pct}% | ETA: {eta/60:.0f}min | 错误: {len(errors)}")

    # ── Step 6: 最终报告 ────────────────────────────────────
    print()
    print("[5/5] 生成最终报告 ...")
    print("=" * 70)

    final_stats = {"total": len(pm_rows), "done": 0, "pending": 0,
                   "processing_fast": 0, "processing_mp4": 0, "error": 0}
    for r in pm_rows.values():
        final_stats[r["status"]] = final_stats.get(r["status"], 0) + 1

    elapsed_total = time.time() - start_time

    print(f"处理完成！总耗时: {elapsed_total:.0f}s ({elapsed_total/60:.1f}min)")
    print()
    print(f"  总 session:  {final_stats['total']}")
    print(f"  ✓ 已完成:   {final_stats['done']}")
    print(f"  ⏳ 待处理:   {final_stats['pending']}")
    print(f"  🔄 Fast:    {final_stats.get('processing_fast', 0)}")
    print(f"  🔄 MP4:     {final_stats.get('processing_mp4', 0)}")
    print(f"  ✗ 错误:     {final_stats['error']}")

    if errors:
        print()
        print("错误列表:")
        for name, err in errors:
            print(f"  [{name}] {err}")

    write_pm_csv(pm_rows)
    print(f"\n管理 CSV 已更新: {PM_CSV}")
    return 0 if final_stats["error"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
