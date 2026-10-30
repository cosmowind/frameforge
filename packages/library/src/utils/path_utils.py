# ────────────────────────────────────────────────────────────────
# path_utils.py — 路径/目录相关纯工具函数
# 拆分自 app.py（S2）
# ────────────────────────────────────────────────────────────────

import os
from datetime import datetime

from config import RUNTIME_DIR

# 电脑标识常量（用于 location_status 字段）
THIS_PC = "thisPC"    # 本机 /media/videos/
OTHER_PC = "otherPC"  # 其他电脑 /media/


def canon_path(path):
    """统一的文件系统 path 规范化：用作 dict key / SQL UPSERT key。

    - 反斜杠 → 正斜杠
    - os.path.normpath 折叠冗余分隔符

    **注意：不要做 .lower()** —— PG 中现有 row 保留原始大小写（D:/sp/...），
    save_rows 一旦把新写入路径 lower 化，ON CONFLICT (path) 就不匹配，反而每次
    save 都新建一行（导致 724 行 vs 296 unique 这种 dup 灾难）。
    Windows 文件系统大小写不敏感，但 PG 默认 collation 是 case-sensitive，
    故规范化只动分隔符，保留原大小写。

    注意：不要用于文件系统 I/O（os.walk / open），那里需要 OS 原生形态。
    """
    if not isinstance(path, str):
        return path
    return os.path.normpath(path).replace("\\", "/")


def get_computer_from_path(path):
    """根据路径判断所属电脑。
    返回 THIS_PC ("thisPC") 或 OTHER_PC ("otherPC")。
    """
    normalized = path.replace("\\", "/")
    if "/media/videos" in normalized:
        return THIS_PC
    return OTHER_PC


def get_location_status(path, exists):
    """返回带电脑标识的 location_status 值。

    4种状态：
      thisPC_local   — 本机，文件存在
      thisPC_history — 本机，文件已删除
      otherPC_local  — 其他电脑，文件存在
      otherPC_history— 其他电脑，文件已删除
    """
    computer = get_computer_from_path(path)
    status = "local" if exists else "history"
    return f"{computer}_{status}"


def parse_location_status(status):
    """解析 location_status，返回 (computer, state) 或 (None, None)。"""
    if not status:
        return None, None
    parts = status.rsplit("_", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return None, None


def is_local_status(status):
    """判断 location_status 是否表示本地存在的文件。"""
    _, state = parse_location_status(status)
    return state == "local"


def extract_date_from_path(path):
    """从源路径中提取日期目录名 (MMDD 格式)，返回 'YYYY-MM-DD' 或 'unknown'。

    路径示例: /media\\0619\\hmd\\4aa45c_session_00000 → '2026-06-19'
    """
    parts = os.path.normpath(path).split(os.sep)
    for part in reversed(parts):
        if len(part) == 4 and part.isdigit():
            month = part[:2]
            day = part[2:]
            year = datetime.now().year
            return f"{year}-{month}-{day}"
    return "unknown"


def extract_mmdd_from_path(path):
    """从路径中提取日期 (MMDD)，仅返回合法范围（01-12月, 01-31日）的4位数字。
    路径示例: /media\\0625\\hmd\\... → '0625'
    """
    parts = os.path.normpath(path).split(os.sep)
    for part in reversed(parts):
        if len(part) == 4 and part.isdigit():
            month = int(part[:2])
            day = int(part[2:])
            if 1 <= month <= 12 and 1 <= day <= 31:
                return part
    return None


def should_add_date_prefix(path):
    """判断路径是否包含合法 MMDD，始终返回是否有日期（不再有 cutoff 限制）。
    所有视频统一使用 mmdd_设备id_session_xxxx 格式，便于区分。
    """
    mmdd = extract_mmdd_from_path(path)
    return mmdd is not None


def get_hmd_cache_dir(session_path):
    """获取 HMD session 的日期分级缓存目录。

    新结构: hmd_cache/<date>/<session_basename>/
    避免不同日期同名 session 的文件覆盖问题。

    与 tools.hmd_fast 和 tools/hmd_preprocess.py 的 get_output_dir 保持一致：
    支持 HMD_CACHE_ROOT 环境变量覆盖。
    """
    base = os.path.basename(os.path.normpath(session_path))
    date_key = extract_date_from_path(session_path)
    cache_root = os.environ.get("HMD_CACHE_ROOT") or os.path.join(RUNTIME_DIR, "hmd_cache")
    return os.path.join(cache_root, date_key, base)


# ── 视频文件命名辅助函数 ──
# 统一命名规则：
#   左眼主视频：  {session_basename}.mp4  / {session_basename}.h265
#   右眼视频：    {session_basename}_right.mp4 / {session_basename}_right.h265
#   封面：        cover.jpg（不变）
#   预览帧：      frames/frame_00.jpg ~ frame_05.jpg（不变）

def get_video_basename(session_basename, eye="left"):
    """返回视频文件的基础名（不含路径）。
    session_basename: 如 '0625_f83c30_session_00007'
    eye: 'left' | 'right'
    """
    if eye == "right":
        return f"{session_basename}_right"
    return session_basename


def get_mp4_filename(session_basename, eye="left"):
    """返回 mp4 文件名（不含路径）。
    例: '0625_f83c30_session_00007.mp4' 或 '0625_f83c30_session_00007_right.mp4'
    """
    return f"{get_video_basename(session_basename, eye)}.mp4"


def get_h265_filename(session_basename, eye="left"):
    """返回 h265 文件名（不含路径）。
    例: '0625_f83c30_session_00007.h265' 或 '0625_f83c30_session_00007_right.h265'
    """
    return f"{get_video_basename(session_basename, eye)}.h265"


def resolve_video_path(cache_dir, session_basename, eye="left", ext=".mp4"):
    """在指定缓存目录中查找视频文件（兼容新旧命名）。
    优先查找新命名，回退到旧命名（left.mp4 / right.mp4），确保平滑迁移。

    Returns: (filepath, found) — filepath 是期望路径，found 是实际存在的路径（或 None）
    """
    if ext == ".mp4":
        new_name = get_mp4_filename(session_basename, eye)
        old_name = f"{eye}.mp4"
    elif ext == ".h265":
        new_name = get_h265_filename(session_basename, eye)
        old_name = f"{eye}.h265"
    else:
        new_name = f"{get_video_basename(session_basename, eye)}{ext}"
        old_name = f"{eye}{ext}"

    new_path = os.path.join(cache_dir, new_name)
    old_path = os.path.join(cache_dir, old_name)

    if os.path.isfile(new_path):
        return new_path, new_path
    if os.path.isfile(old_path):
        return new_path, old_path
    return new_path, None


def find_any_video_file(cache_dir, session_basename):
    """在缓存目录中查找任一可用的视频源文件。
    优先级：新命名 mp4 → 旧命名 mp4 → 新命名 h265 → 旧命名 h265
    Returns: (filepath, is_new_naming) 或 (None, False)
    """
    # mp4 candidates (left eye only, right is secondary)
    for eye in ("left", "right"):
        for (name_fn, ext) in [(get_mp4_filename, ".mp4"), (get_h265_filename, ".h265")]:
            new_name = name_fn(session_basename, eye)
            new_path = os.path.join(cache_dir, new_name)
            if os.path.isfile(new_path):
                return new_path, True
            old_name = f"{eye}{ext}"
            old_path = os.path.join(cache_dir, old_name)
            if os.path.isfile(old_path):
                return old_path, False
    return None, False


def find_all_video_files(cache_dir, session_basename):
    """在缓存目录中查找所有视频源文件（兼容新旧命名）。
    Returns: list of full paths that actually exist.
    """
    results = []
    for eye in ("left", "right"):
        for ext in (".mp4", ".h265"):
            new_name = get_mp4_filename(session_basename, eye) if ext == ".mp4" else get_h265_filename(session_basename, eye)
            old_name = f"{eye}{ext}"
            for name in (new_name, old_name):
                p = os.path.join(cache_dir, name)
                if os.path.isfile(p):
                    results.append(p)
                    break
    return results


def is_preview_artifact(name):
    """检查文件名是否为预处理产物（新旧命名均识别）。
    用于扫描时排除这些文件。
    """
    lower = name.lower()
    # 旧命名：left.mp4, right.mp4, left.h265, right.h265
    if lower in ("left.mp4", "right.mp4", "left.h265", "right.h265"):
        return True
    # 新命名（session_basename 结尾）：xxx_session_NNNNN.mp4 或 _right.mp4
    return False  # 新命名不会被误判为独立视频
