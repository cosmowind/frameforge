# ────────────────────────────────────────────────────────────────
# config.py — 项目级全局常量、路径、配置
# 拆分自 app.py（S1），不依赖其他项目模块
# 位于 src/ 内，路径计算基于 ROOT_DIR（项目根目录）
# ────────────────────────────────────────────────────────────────

import os
import sys

# 加载 .env 文件（必须在读取环境变量之前）
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
except ImportError:
    pass

# ── 路径常量 ──
# 兼容 PyInstaller 打包：sys._MEIPASS 是临时解压目录，exe 实际路径用 sys.argv[0]
# PyInstaller 打包后 flat 结构：exe 与 data/模板 在同一层，ROOT_DIR = exe 所在目录
if getattr(sys, 'frozen', False):
    ROOT_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
    RUNTIME_DIR = ROOT_DIR           # frozen 模式：数据文件平铺在 exe 同层
    SRC_DIR = ROOT_DIR               # frozen 模式：代码被打包，无 src/ 子目录
else:
    _THIS_FILE = os.path.abspath(__file__)   # src/config.py
    SRC_DIR = os.path.dirname(_THIS_FILE)    # src/
    ROOT_DIR = os.path.dirname(SRC_DIR)      # 项目根目录
    RUNTIME_DIR = os.path.join(ROOT_DIR, "runtime")

# 保持 BASE_DIR 向后兼容（指向项目根目录）
BASE_DIR = ROOT_DIR

# ── 数据文件（运行时状态，存放于 runtime/data/） ──
CSV_PATH = os.path.join(RUNTIME_DIR, "data", "video_manager.csv")
CONFIG_PATH = os.path.join(RUNTIME_DIR, "data", "config.json")
ARCHIVE_DIR = os.path.join(RUNTIME_DIR, "archive")

# ── 数据库配置 ──
DATABASE_DSN = os.environ.get("VIDEO_MANAGER_DB_DSN", "")
USE_PG = bool(DATABASE_DSN)

# ── 来源设备名（自动接入本机 hostname，可通过环境变量 SOURCE_DEVICE 覆盖） ──
import socket
SOURCE_DEVICE = os.environ.get("SOURCE_DEVICE", "") or socket.gethostname()

# ── MiniMax 翻译 API ──
_MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
_MINIMAX_URL = os.environ.get("MINIMAX_URL", "https://api.minimax.chat/v1/text/chatcompletion_v2")
_MINIMAX_MODEL = os.environ.get("MINIMAX_MODEL", "MiniMax-Text-01")

# ── 代码目录（位于 src/ 内） ──
UPLOAD_PKG_DIR = os.path.join(SRC_DIR, "vendor-upload-pkg")
_TOOLS_DIR = os.path.join(SRC_DIR, "tools")

# ── 缓存目录（运行时生成，存放于 runtime/） ──
THUMBNAILS_DIR = os.path.join(RUNTIME_DIR, "thumbnails")

# ── CSV 列定义 ──
DEFAULT_FIELDNAMES = [
    "path", "location_status", "scan_date", "original_history_date",
    "uploaded", "extra_description", "score",
    "duration_sec",         # 视频时长（秒，整数；前端展示时 _fmt_duration 格式化）
    # ── added for HMD integration (kept as "" for legacy rows) ──
    "file_type",            # "mp4" / "hmd"
    "device_id",            # 设备编号（metadata 末 6 位或 sd_cards.csv 匹配）
    "recorder_id",         # 引用 recorders.csv（原 recorder 字段已合并到这里）
    "task_id",              # 引用 tasks.csv
    "env_id",               # 引用 environments.csv（环境描述对应）
    "source_device",        # 上传来源设备（电脑名/hostname，自动接入）
]

# ── 默认上传配置 ──
UPLOAD_CONFIG = {
    "country": "CN",
    "region": "Shanghai",
    "recorder": "lingxu zhou",
    "category": "industrial_manufacturing",
    "subcategory": "mfg_other",
}

# ── HMD 常量 ──
SESSION_MARKER = "metadata.json"
HMD_FILE_EXTS = {".hmd"}

# ── 维表注册表 ──
_DIM_REGISTRY = {
    "recorders": {
        "path": os.path.join(RUNTIME_DIR, "data", "recorders.csv"),
        "schema": ["id", "name", "phone",
                   "operator_job", "operator_consent",
                   "age_range", "gender", "handedness", "gloves", "workforce_type",
                   "role_experience", "task_experience",
                   "collection_hours_today", "collection_experience_days",
                   "hand_size_cm", "notes"],
        "key": "id",
        "create_if_missing": True,
        "validators": {
            "id": r"^[a-zA-Z0-9_\-]{1,16}$",
            "name_required": True,
        },
    },
    "sd_cards": {
        "path": os.path.join(RUNTIME_DIR, "data", "sd_cards.csv"),
        "schema": ["volume_serial", "volume_label", "device_id", "device_name",
                   "capture_mode",
                   "country_code", "region", "city",
                   "stable_site_identifier",
                   "notes"],
        "key": "volume_serial",
        "create_if_missing": True,
        "validators": {
            "volume_serial_required": True,
            "device_id_required": True,
        },
    },
    "tasks": {
        "path": os.path.join(RUNTIME_DIR, "data", "tasks.csv"),
        "schema": ["task_id", "scene", "product", "task", "tool", "process", "process_en",
                   "difficulty", "quota_min",
                   "location_address",
                   "business_type", "business_name",
                   "environment",
                   "environment_description", "environment_description_en",
                   "facility_venue",
                   "notes"],
        "key": "task_id",
        "create_if_missing": True,
        "validators": {
            "task_id": r"^[a-z0-9]+_[a-z0-9]+_[a-z0-9]+_\d{3}$",
            "task_id_required": True,
            "product_required": True,
        },
    },
    "environments": {
        "path": os.path.join(RUNTIME_DIR, "data", "environments.csv"),
        "schema": ["env_id", "scene", "location_address",
                   "environment", "environment_description", "environment_description_en", "facility_venue",
                   "notes"],
        "key": "env_id",
        "create_if_missing": True,
        "validators": {
            "env_id": r"^[a-z0-9_]{4,32}$",
            "environment_description_required": True,
        },
    },
}

# CSV 注入防护：以下字符开头的字符串在自由文本字段中被拒绝
_CSV_INJECTION_LEAD = ("=", "+", "-", "@", "\t", "\r")

# ── 上传模板默认值 ──
UPLOAD_TEMPLATE_DEFAULTS = {
    "operator_name": "",           # → recorder_id 查 recorders.csv name
    "operator_job": "生产工人",
    "operator_consent": "是",
    "task_difficulty": "",         # → tasks.csv difficulty (easy/medium/hard)
    "task_description": "",        # → tasks.csv process
    "environment_description": "", # → tasks.csv environment_description
    "country": "CN",
    "state_province": "示例省",
    "city": "示例",
    "location_address": "南安市辉煌工业园区",
    "environment": "工业制造",
    "facility_venue": "工厂",
    "scene": "",
    "business_type": "",
    "business_name": "",
    "age_range": "",
    "gender": "",
    "handedness": "",
    "gloves": "",
    "workforce_type": "",
    "role_experience": "",
    "task_experience": "",
    "collection_hours_today": "",
    "collection_experience_days": "",
    "hand_size_cm": "",
}

UPLOAD_TEMPLATE_LABELS = {
    "operator_name": "Operator Name *",
    "operator_job": "Operator Job *",
    "operator_consent": "Operator Consent *",
    "task_difficulty": "Task Difficulty *",
    "task_description": "Task Description *",
    "environment_description": "Environment Description *",
    "city": "City *",
    "state_province": "State/Province *",
    "country": "Country *",
    "location_address": "Location Address *",
    "environment": "Environment *",
    "facility_venue": "Facility / Venue *",
    "scene": "Scene *",
    "business_type": "Business Type *",
    "business_name": "Business Name *",
    "age_range": "Age Range *",
    "gender": "Gender *",
    "handedness": "Handedness *",
    "gloves": "Gloves *",
    "workforce_type": "Workforce Type *",
    "role_experience": "Role Experience (months/years)",
    "task_experience": "Task Experience (months/years)",
    "collection_hours_today": "Collection Hours Today",
    "collection_experience_days": "Collection Experience Days",
    "hand_size_cm": "Hand Size (cm)",
    "source_device": "Source Device",
}

# ── 缩略图常量 ──
THUMB_WIDTH = 240
THUMB_HEIGHT = 135
# 缩略图截取时间点尝试列表（按顺序，首个亮度 >= LUMA_MIN 的帧被选中）
THUMB_SEEK_TRY = [3.0, 1.0, 5.0, 10.0]
LUMA_MIN = 8.0  # 0-255; 低于此值视为"有效黑帧"
THUMB_MAX_CONCURRENT = 2
_PLACEHOLDER_THUMB_PATH = os.path.join(THUMBNAILS_DIR, "_placeholder.jpg")

# ── 时长估算 ──
DEFAULT_SIZE_MB_PER_MIN = 45.74  # 根据现有 HMD session 数据分析的中位数

# ── 启动预热标志文件 ──
_startup_warm_flag = os.path.join(RUNTIME_DIR, ".startup_warm_done")

# ── 确保缩略图目录存在（import 时执行一次） ──
os.makedirs(THUMBNAILS_DIR, exist_ok=True)

# ── __all__ 用于 from config import * ──
__all__ = [
    "ROOT_DIR", "SRC_DIR", "RUNTIME_DIR",
    "BASE_DIR", "CSV_PATH", "CONFIG_PATH", "ARCHIVE_DIR", "UPLOAD_PKG_DIR",
    "_TOOLS_DIR",
    "DEFAULT_FIELDNAMES", "UPLOAD_CONFIG",
    "SESSION_MARKER", "HMD_FILE_EXTS",
    "_DIM_REGISTRY", "_CSV_INJECTION_LEAD",
    "UPLOAD_TEMPLATE_DEFAULTS", "UPLOAD_TEMPLATE_LABELS",
    "THUMBNAILS_DIR", "THUMB_WIDTH", "THUMB_HEIGHT",
    "THUMB_SEEK_TRY", "LUMA_MIN", "THUMB_MAX_CONCURRENT",
    "_PLACEHOLDER_THUMB_PATH",
    "DEFAULT_SIZE_MB_PER_MIN",
    "_startup_warm_flag",
    # 数据库配置
    "DATABASE_DSN", "USE_PG",
    "SOURCE_DEVICE",
    "_MINIMAX_API_KEY", "_MINIMAX_URL", "_MINIMAX_MODEL",
]
