#!/usr/bin/env python
"""全面检查 hmd_cache 中所有预处理视频的完整性。

检查项：
1. mp4 容器结构是否完整（moov atom 是否存在）
2. h265 是否有 HEVC 编码错误（如 POC 断裂）
3. h265 与 mp4 文件大小是否匹配（流拷贝模式下应接近）
4. .hmd_fast.json 状态标记是否正确

输出：问题列表，并可自动修复。
"""
import os
import sys
import json
import subprocess
import glob

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE_ROOT = os.path.join(PROJECT_ROOT, "runtime", "hmd_cache")


def check_mp4_integrity(mp4_path):
    """检查 mp4 容器是否完整（moov atom、可解析、可读取时长）。
    
    Returns: (ok: bool, duration: float|None, error: str|None, info: dict)
    """
    if not os.path.isfile(mp4_path):
        return False, None, "file_missing", {}
    
    size = os.path.getsize(mp4_path)
    if size == 0:
        return False, None, "zero_size", {}
    
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration,nb_streams:stream=codec_name,width,height,nb_frames",
             "-of", "json", mp4_path],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30
        )
    except subprocess.TimeoutExpired:
        return False, None, "ffprobe_timeout", {}
    except FileNotFoundError:
        return False, None, "ffprobe_not_found", {}
    
    if r.returncode != 0:
        stderr = r.stderr.strip()
        if "moov atom not found" in stderr:
            return False, None, "moov_atom_missing", {}
        if "Invalid data found" in stderr:
            return False, None, "invalid_data", {"stderr": stderr[:200]}
        return False, None, f"ffprobe_exit_{r.returncode}", {"stderr": stderr[:200]}
    
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        return False, None, "ffprobe_json_error", {}
    
    fmt = data.get("format", {})
    duration = float(fmt.get("duration", 0)) if fmt.get("duration") else None
    nb_streams = int(fmt.get("nb_streams", 0))
    
    if nb_streams == 0:
        return False, None, "no_streams", {}
    
    streams = data.get("streams", [])
    video_stream = None
    for s in streams:
        if s.get("codec_type") == "video":
            video_stream = s
            break
    
    info = {
        "size": size,
        "duration": duration,
        "nb_streams": nb_streams,
        "codec": video_stream.get("codec_name") if video_stream else None,
        "width": video_stream.get("width") if video_stream else None,
        "height": video_stream.get("height") if video_stream else None,
        "frames": int(video_stream.get("nb_frames", 0)) if video_stream else 0,
    }
    
    return True, duration, None, info


def check_h265_errors(h265_path):
    """检查 h265 裸流是否有 HEVC 解码错误（POC/GOP 问题）。
    
    Returns: (has_errors: bool, frame_count: int|None, errors: list)
    """
    if not os.path.isfile(h265_path):
        return False, None, []
    
    size = os.path.getsize(h265_path)
    if size == 0:
        return False, None, []
    
    errors = []
    frame_count = None
    
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-count_frames",
             "-show_entries", "stream=nb_read_frames",
             "-of", "json", h265_path],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60
        )
    except subprocess.TimeoutExpired:
        return True, None, ["ffprobe_timeout"]
    except FileNotFoundError:
        return True, None, ["ffprobe_not_found"]
    
    # Parse stderr for HEVC errors
    stderr_lines = r.stderr.strip().split('\n') if r.stderr else []
    error_keywords = [
        "Could not find ref with POC",
        "Error constructing the frame RPS",
        "Duplicate POC",
        "corrupted",
        "Invalid NAL unit",
        "decode_slice_header error",
        "no frame!",
    ]
    
    for line in stderr_lines:
        for kw in error_keywords:
            if kw in line:
                errors.append(line.strip())
                break
    
    # Try to get frame count from stdout
    if r.returncode == 0 and r.stdout.strip():
        try:
            data = json.loads(r.stdout)
            for s in data.get("streams", []):
                if "nb_read_frames" in s:
                    frame_count = int(s["nb_read_frames"])
        except (json.JSONDecodeError, ValueError):
            pass
    
    has_errors = len(errors) > 0
    
    return has_errors, frame_count, errors


def scan_all_caches():
    """扫描所有缓存目录，返回 session 列表。"""
    sessions = []
    
    if not os.path.isdir(CACHE_ROOT):
        print(f"[ERROR] Cache root not found: {CACHE_ROOT}")
        return sessions
    
    for date_dir in sorted(os.listdir(CACHE_ROOT)):
        date_path = os.path.join(CACHE_ROOT, date_dir)
        if not os.path.isdir(date_path):
            continue
        
        for session_name in sorted(os.listdir(date_path)):
            session_path = os.path.join(date_path, session_name)
            if not os.path.isdir(session_path):
                continue
            
            sessions.append({
                "date": date_dir,
                "name": session_name,
                "path": session_path,
            })
    
    return sessions


def check_session(session):
    """检查单个 session 的完整性。
    
    Returns: dict with status and details.
    """
    session_path = session["path"]
    
    result = {
        **session,
        "issues": [],
        "ok": True,
        "has_h265": False,
        "has_mp4": False,
        "h265_size": 0,
        "mp4_size": 0,
        "mp4_duration": None,
        "h265_frame_count": None,
        "mp4_frame_count": 0,
        "fast_status": None,
    }
    
    # 检查 .hmd_fast.json
    fast_json = os.path.join(session_path, ".hmd_fast.json")
    if os.path.isfile(fast_json):
        try:
            with open(fast_json, "r", encoding="utf-8") as f:
                result["fast_status"] = json.load(f)
        except Exception:
            pass
    
    # 检查 h265
    h265_path = os.path.join(session_path, "left.h265")
    if os.path.isfile(h265_path):
        result["has_h265"] = True
        result["h265_size"] = os.path.getsize(h265_path)
        
        has_errors, frame_count, errors = check_h265_errors(h265_path)
        result["h265_frame_count"] = frame_count
        
        if has_errors:
            error_types = set()
            for e in errors:
                if "POC" in e:
                    error_types.add("hevc_poc_error")
                elif "RPS" in e:
                    error_types.add("hevc_rps_error")
                elif "Duplicate POC" in e:
                    error_types.add("hevc_dup_poc")
                elif "corrupted" in e.lower():
                    error_types.add("hevc_corrupted")
            for et in error_types:
                result["issues"].append(et)
                result["ok"] = False
    
    # 检查 mp4（新旧命名兼容）
    sess_name = os.path.basename(os.path.normpath(session_path))
    mp4_path = os.path.join(session_path, f"{sess_name}.mp4")
    if not os.path.isfile(mp4_path):
        mp4_path = os.path.join(session_path, "left.mp4")
    if os.path.isfile(mp4_path):
        result["has_mp4"] = True
        result["mp4_size"] = os.path.getsize(mp4_path)
        
        mp4_ok, duration, error, info = check_mp4_integrity(mp4_path)
        result["mp4_duration"] = duration
        result["mp4_frame_count"] = info.get("frames", 0)
        
        if not mp4_ok:
            result["issues"].append(f"mp4_{error}")
            result["ok"] = False
    
    # 检查 h265/mp4 大小一致性（流拷贝模式下应接近）
    if result["has_h265"] and result["has_mp4"] and result["mp4_size"] > 0:
        ratio = result["mp4_size"] / max(result["h265_size"], 1)
        if ratio < 0.7:  # mp4 明显小于 h265，可能是封装中断
            result["issues"].append(f"mp4_partial_remux(ratio={ratio:.2f})")
            result["ok"] = False
    
    # 检查 fast_status 标记与实际文件是否一致
    if result["fast_status"]:
        fs = result["fast_status"]
        if fs.get("mp4_ready") and not result["has_mp4"]:
            result["issues"].append("status_says_mp4_ready_but_missing")
            result["ok"] = False
        if fs.get("status") == "done" and not result["has_mp4"]:
            result["issues"].append("status_done_but_no_mp4")
            result["ok"] = False
        if fs.get("status") == "error":
            result["issues"].append(f"status_error: {fs.get('error', 'unknown')}")
            result["ok"] = False
    
    # 检查是否有部分产物（有 h265 但没有 mp4）
    if result["has_h265"] and not result["has_mp4"]:
        result["issues"].append("h265_exists_no_mp4")
        result["ok"] = False
    
    return result


def format_size(size_bytes):
    """格式化文件大小。"""
    if size_bytes >= 1024 * 1024 * 1024:
        return f"{size_bytes / (1024**3):.1f} GB"
    elif size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024**2):.1f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes} B"


def main():
    print("=" * 80)
    print("HMD Cache 完整性检查")
    print("=" * 80)
    
    sessions = scan_all_caches()
    print(f"\n扫描到 {len(sessions)} 个 session 目录\n")
    
    ok_sessions = []
    broken_sessions = []
    stats = {
        "total": len(sessions),
        "ok": 0,
        "broken": 0,
        "has_mp4": 0,
        "has_h265": 0,
        "has_both": 0,
        "mp4_broken": 0,
        "h265_with_errors": 0,
        "mp4_partial_remux": 0,
        "h265_no_mp4": 0,
    }
    
    for i, session in enumerate(sessions):
        result = check_session(session)
        
        stats["has_mp4"] += 1 if result["has_mp4"] else 0
        stats["has_h265"] += 1 if result["has_h265"] else 0
        stats["has_both"] += 1 if (result["has_mp4"] and result["has_h265"]) else 0
        
        for issue in result["issues"]:
            if issue.startswith("mp4_"):
                stats["mp4_broken"] += 1
            if issue.startswith("hevc_"):
                stats["h265_with_errors"] += 1
            if issue.startswith("mp4_partial"):
                stats["mp4_partial_remux"] += 1
            if issue == "h265_exists_no_mp4":
                stats["h265_no_mp4"] += 1
        
        if result["ok"]:
            ok_sessions.append(result)
            stats["ok"] += 1
        else:
            broken_sessions.append(result)
            stats["broken"] += 1
        
        # 打印进度
        status_icon = "OK" if result["ok"] else "!!"
        mp4_info = ""
        if result["has_mp4"]:
            mp4_info = f" mp4={format_size(result['mp4_size'])}"
            if result["mp4_duration"]:
                mp4_info += f" {result['mp4_duration']:.0f}s"
        h265_info = ""
        if result["has_h265"]:
            h265_info = f" h265={format_size(result['h265_size'])}"
            if result["h265_frame_count"]:
                h265_info += f" {result['h265_frame_count']}f"
        
        print(f"  [{status_icon}] {result['date']}/{result['name']}{mp4_info}{h265_info}")
        if result["issues"]:
            for issue in result["issues"]:
                print(f"         -> {issue}")
    
    # 汇总
    print("\n" + "=" * 80)
    print("汇总")
    print("=" * 80)
    print(f"  总计: {stats['total']} 个 session")
    print(f"  完好: {stats['ok']} 个")
    print(f"  异常: {stats['broken']} 个")
    print()
    print(f"  有 mp4: {stats['has_mp4']} 个")
    print(f"  有 h265: {stats['has_h265']} 个")
    print(f"  同时有: {stats['has_both']} 个")
    print()
    print(f"  mp4 结构损坏: {stats['mp4_broken']} 个")
    print(f"  mp4 封装不完整(大小<70%h265): {stats['mp4_partial_remux']} 个")
    print(f"  h265 有 HEVC 错误: {stats['h265_with_errors']} 个")
    print(f"  有 h265 无 mp4: {stats['h265_no_mp4']} 个")
    
    # 输出异常列表供修复
    if broken_sessions:
        print("\n" + "=" * 80)
        print("需要修复的 session 列表:")
        print("=" * 80)
        for s in broken_sessions:
            print(f"  {s['date']}/{s['name']}")
            for issue in s["issues"]:
                print(f"    - {issue}")
    
    # 输出 JSON 格式结果
    output_json_path = os.path.join(PROJECT_ROOT, "runtime", "cache_check_result.json")
    try:
        os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
        report = {
            "stats": stats,
            "broken": [
                {
                    "date": s["date"],
                    "name": s["name"],
                    "path": s["path"],
                    "issues": s["issues"],
                    "has_h265": s["has_h265"],
                    "has_mp4": s["has_mp4"],
                    "h265_size": s["h265_size"],
                    "mp4_size": s["mp4_size"],
                }
                for s in broken_sessions
            ],
        }
        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\n详细报告已保存到: {output_json_path}")
    except Exception as e:
        print(f"\n[WARN] 保存报告失败: {e}")
    
    return 0 if stats["broken"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
