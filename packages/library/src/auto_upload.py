#!/usr/bin/env python3
"""
FrameForge 自动上传工具（新版：表单填写模式）

基于 Playwright 异步 API 模拟浏览器操作：
- 导航到 https://publish.example.com/vendors?tab=upload
- 自动检测登录状态（掉线自动停止，等待用户重新登录）
- 填写上传表单的 19+ 个必填字段
- 选择并上传视频文件
- 完成后在本地日志记录 + CSV 标记已完成
- 自动跳过已完成的视频

用法：
  1. 从 Flask app 触发（推荐）：
     auto_upload.py --row-index 5
  2. 直接运行单个视频：
     auto_upload.py --video "/media/0615/video.mp4" --data '{"operator_name":"lx",...}'

参考项目：./vendor
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import datetime
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# 修复 Windows 控制台中文输出乱码
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ==================== 路径配置（使用 config.py 的路径） ====================
# 添加 src 目录到 Python 路径以导入 config
_SELF_DIR = Path(__file__).resolve().parent
_SRC_DIR = _SELF_DIR
_ROOT_DIR = _SRC_DIR.parent
sys.path.insert(0, str(_SRC_DIR))
try:
    from config import RUNTIME_DIR as _RUNTIME_DIR
    # 统一指向项目根目录
    BASE_DIR = Path(_ROOT_DIR)
    # runtime/ 目录存放运行时数据
    RUNTIME_DIR = Path(_RUNTIME_DIR)
except ImportError:
    # 回退：使用脚本所在目录
    BASE_DIR = _SELF_DIR
    RUNTIME_DIR = BASE_DIR / "runtime"

BROWSER_DATA_DIR = str(BASE_DIR / "runtime" / "browser_data")  # Chrome 持久化用户数据
LOG_DIR = BASE_DIR / "runtime" / "logs"
STATE_FILE = RUNTIME_DIR / "data" / "upload_state.json"
PROGRESS_FILE = RUNTIME_DIR / "data" / "auto_upload_progress.json"
UPLOAD_URL = "https://publish.example.com/vendors?tab=upload"

# 模块级 args 占位 — 让 AutoUploader 类方法里 getattr(args, ...) 能拿到
# main() 里会 global args; args = ap.parse_args() 重新赋值
args: "argparse.Namespace | None" = None

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("[ERROR] 请安装 playwright: pip install playwright && python -m playwright install chromium")
    sys.exit(1)

# ==================== 上传字段映射 ====================
# 字段 key → 页面上的 CSS 选择器 / label 文本模式
# 由于无法提前知道页面 DOM 结构，这里使用多策略匹配：
#   1) input[placeholder*="xxx"]
#   2) label:has-text("xxx") + input
#   3) [data-field="xxx"]
#   4) 按 label 文本模糊匹配
FIELD_SELECTORS: dict[str, list[str]] = {
    # ── Task Attributes ──
    "operator_name": [
        "input[placeholder='操作员姓名']",
        "input[placeholder*='操作员姓名']",
        "[data-field='operator_name']",
    ],
    "operator_job": [
        "input[placeholder='操作员从事的标准职业(职业分类)']",
        "[data-field='operator_job']",
    ],
    "operator_consent": [
        "select[data-field='operator_consent']",
    ],
    "task_difficulty": [
        "select[data-field='task_difficulty']",
    ],
    "task_description": [
        "textarea[placeholder='任务描述']",
        "input[placeholder='任务描述']",
        "textarea[data-field='task_description']",
        "input[data-field='task_description']",
    ],
    "environment_description": [
        "input[placeholder='环境（房间 / 光线 / 场景）']",
        "textarea[placeholder='环境（房间 / 光线 / 场景）']",
        "[data-field='environment_description']",
    ],
    # ── Environment & Location ──
    "country": [
        "input[placeholder*='国家']",
        "input[data-field='country']",
    ],
    "state_province": [
        "input[placeholder*='省/州']",
        "input[data-field='state_province']",
    ],
    "city": [
        "input[placeholder*='城市']",
        "input[data-field='city']",
    ],
    "location_address": [
        "input[placeholder='输入地址搜索,选择候选即可锁定 GPS…']",
        "textarea[placeholder*='地址']",
        "input[placeholder*='地址']",
        "[data-field='location_address']",
    ],
    "environment": [
        # shadcn combobox
        "input[placeholder='环境大类']",
        "[data-field='environment']",
    ],
    "facility_venue": [
        # shadcn combobox
        "input[placeholder='设施类型 / 场地']",
        "[data-field='facility_venue']",
    ],
    "scene": [
        # shadcn combobox
        "input[placeholder='场景 / 工位 / 区域']",
        "[data-field='scene']",
    ],
    "business_type": [
        "input[placeholder='细分行业,如 药房、诊所、实验室']",
        "[data-field='business_type']",
    ],
    "business_name": [
        "input[placeholder='注册或对外名称(可匿名)']",
        "[data-field='business_name']",
    ],
    # ── Capture Mode — NOT a form field! It's a button group ──
    "captureMode": [
        "button:has-text('双目')",
        "button:has-text('单摄像头')",
        "button:has-text('三视角')",
    ],
    # ── Operator ──
    "age_range": [
        "label:has-text('年龄段') select",
        "select[data-field='age_range']",
    ],
    "gender": [
        "label:has-text('性别') select",
        "select[data-field='gender']",
    ],
    "handedness": [
        "label:has-text('惯用手') select",
        "select[data-field='handedness']",
    ],
    "gloves": [
        "label:has-text('手套') select",
        "select[data-field='gloves']",
    ],
    "workforce_type": [
        "label:has-text('用工类型') select",
        "select[data-field='workforce_type']",
    ],
    "role_experience": [
        "input[placeholder='从事该岗位的月数或年数']",
        "input[data-field='role_experience']",
    ],
    "task_experience": [
        "input[placeholder='从事该具体任务的月数或年数']",
        "input[data-field='task_experience']",
    ],
    "collection_hours_today": [
        "input[placeholder='当天录制的小时数']",
        "input[data-field='collection_hours_today']",
    ],
    "collection_experience_days": [
        "input[placeholder='此前累计接入天数']",
        "input[data-field='collection_experience_days']",
    ],
    "hand_size_cm": [
        "input[placeholder='手掌/手指跨度测量(cm)']",
        "input[data-field='hand_size_cm']",
    ],
}

# Field key → human-readable label text to search on the page (fallback)
FIELD_LABELS: dict[str, str] = {
    "operator_name": "操作员姓名",
    "operator_job": "操作员从事的标准职业",
    "operator_consent": "操作员同意",
    "task_difficulty": "任务难度",
    "task_description": "任务描述",
    "environment_description": "环境描述",
    "country": "国家",
    "state_province": "省",
    "city": "城市",
    "location_address": "地址",
    "environment": "环境",
    "facility_venue": "设施类型",
    "scene": "场景",
    "business_type": "业务类型",
    "business_name": "业务名称",
    "captureMode": "接入模式",
    "age_range": "年龄范围",
    "gender": "性别",
    "handedness": "惯用手",
    "gloves": "手套",
    "workforce_type": "劳动力类型",
    "role_experience": "岗位经验",
    "task_experience": "任务经验",
    "collection_hours_today": "录制时长",
    "collection_experience_days": "累计天数",
    "hand_size_cm": "手部尺寸",
}

# ── 英文 CSV 值 → 中文页面下拉值映射 ──
VALUE_MAP: dict[str, dict[str, str]] = {
    "operator_consent": {
        "Yes": "是",
        "yes": "是",
        "No": "否",
        "no": "否",
    },
    "task_difficulty": {
        "easy": "简单",
        "medium": "中等",
        "hard": "困难",
    },
    "gender": {
        "Male": "男",
        "male": "男",
        "Female": "女",
        "female": "女",
        "prefer_not_to_say": "不愿透露",
    },
    "handedness": {
        "Right-handed": "右手",
        "right-handed": "右手",
        "right": "右手",
        "Left-handed": "左手",
        "left-handed": "左手",
        "left": "左手",
        "Ambidextrous": "双手皆可",
        "ambidextrous": "双手皆可",
    },
    "gloves": {
        "No — bare hands": "否 —— 徒手",
        "No  bare hands": "否 —— 徒手",
        "No bare hands": "否 —— 徒手",
        "No": "否 —— 徒手",
        "no": "否 —— 徒手",
        "Yes — gloves": "是 —— 戴手套",
        "Yes  gloves": "是 —— 戴手套",
        "Yes gloves": "是 —— 戴手套",
        "Yes": "是 —— 戴手套",
        "yes": "是 —— 戴手套",
    },
    "workforce_type": {
        "Real worker (does this job)": "真实员工(本职工作)",
        "real_worker": "真实员工(本职工作)",
        "Contractor": "承包者(为接入雇佣)",
        "contractor": "承包者(为接入雇佣)",
    },
    "captureMode": {
        "stereo": "双目",
        "Stereo": "双目",
        "single": "单摄像头",
        "single-cam": "单摄像头",
        "Single-cam": "单摄像头",
        "three_views": "三视角",
        "Three-Views": "三视角",
        "single-camera": "单摄像头",
        "single camera": "单摄像头",
    },
    "environment": {
        "Industrial Manufacturing": "工业制造",
        "industrial manufacturing": "工业制造",
        "Retail and Consumer Goods": "零售与消费品",
        "Retail and consumer goods": "零售与消费品",
        "retail": "零售与消费品",
        "Food and Beverage": "餐饮",
        "Food and beverage": "餐饮",
        "food and beverage": "餐饮",
        "Factory": "工业制造",
        "factory": "工业制造",
        "Other": "其他",
        "other": "其他",
    },
    "facility_venue": {
        "Manufacturing Factory": "制造厂",
        "manufacturing factory": "制造厂",
        "Manufacturing factory": "制造厂",
        "Market / Bazaar": "市场",
        "market / bazaar": "市场",
        "Office Building": "办公室",
        "Office building": "办公室",
        "Restaurant": "餐厅",
        "restaurant": "餐厅",
        "Workshop / Studio": "手工作坊",
        "workshop / studio": "手工作坊",
        "Workshop": "手工作坊",
        "workshop": "手工作坊",
        "Office": "办公室",
        "office": "办公室",
        "Other": "其他",
        "other": "其他",
    },
    "scene": {
        "Workshop": "车间",
        "workshop": "车间",
        "Production Line": "生产区",
        "production line": "生产区",
        "Assembly Line": "缝纫车间",
        "assembly line": "缝纫车间",
        "Food Production Area": "加工区",
        "Living Room": "客厅",
        "Office Floor": "办公工作区",
        "Showroom": "展厅",
        "Storage Room": "储藏室",
        "Warehouse Storage": "物流中心",
        "Washing Station": "洗衣房",
        "Workshop Area": "车间区域",
        "Workshop Desk": "工作台",
        "Workshop Table": "工作台",
        "Workshop Yard": "手工作坊",
    },
    "operator_job": {
        "Factory worker": "工厂工人",
        "factory worker": "工厂工人",
        "Packaging operator": "包装工",
        "packaging operator": "包装工",
        "Package handler": "包装工",
        "package handler": "包装工",
        "Product manager": "产品经理",
        "product manager": "产品经理",
        "Production worker": "生产工人",
        "production worker": "生产工人",
        # 中文→中文 兜底（recorders.csv 里有这些变体, 平台 dropdown 只有"包装工"）
        "包装操作员": "包装工",
        "包装处理员": "包装工",
        "包装工人": "包装工",
    },
    "business_type": {
        "Handicraft production": "手工业生产",
        "eyewear industry": "眼镜行业",
        "food production": "食品生产",
        "sanitary ware production": "卫浴用品生产",
    },
    "age_range": {
        # 数字范围格式保持不变
    },
}


# 字段填写顺序（左侧表单自上而下，operator 信息优先）
FILL_ORDER: list[str] = [
    # ── Operator identity (HMD) ──
    "operator_name",
    "operator_job",
    "operator_consent",
    # ── Task ──
    "task_description",
    "task_difficulty",
    "environment_description",
    # ── Capture mode ──
    "captureMode",
    # ── Location (country/state_province/city merged into address input on Chinese page) ──
    "location_address",
    "environment",
    "facility_venue",
    "scene",
    "business_type",
    "business_name",
    # ── Operator demographics ──
    "age_range",
    "gender",
    "handedness",
    "gloves",
    "workforce_type",
    # ── Experience & other ──
    "role_experience",
    "task_experience",
    "collection_hours_today",
    "collection_experience_days",
    "hand_size_cm",
    # ── Source tracking ──
    "source_device",
]


# ==================== 工具函数 ====================

def load_state() -> dict:
    """加载上传状态文件"""
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"uploaded": [], "failed": []}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def log(msg: str, log_path: Path | None = None) -> None:
    """带时间戳的日志输出（同时输出到控制台和文件）"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line, flush=True)
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def load_csv_rows() -> list[dict]:
    """读取 video_manager.csv"""
    csv_path = RUNTIME_DIR / "data" / "video_manager.csv"
    if not csv_path.exists():
        return []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_progress(status: str, current: int = 0, total: int = 0,
                   current_video: str = "", message: str = "",
                   success: int = 0, fail: int = 0):
    """写入上传进度 JSON（供前端轮询）。"""
    try:
        PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "status": status,          # starting / uploading / done / error
            "current": current,
            "total": total,
            "current_video": current_video,
            "message": message,
            "success": success,
            "fail": fail,
            "timestamp": datetime.now().isoformat(),
        }
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass  # 进度写入失败不应影响上传


def mark_uploaded(csv_index: int) -> bool:
    """在 CSV + PG 中标记某行为已上传，写 .uploaded 标记文件

    数据源：
    - CSV: runtime/data/video_manager.csv（始终写入）
    - PG: 配置了 VIDEO_MANAGER_DB_DSN 时同步更新 videos.uploaded='Yes'
    """
    rows = load_csv_rows()
    if csv_index < 0 or csv_index >= len(rows):
        return False
    rows[csv_index]["uploaded"] = "Yes"
    video_path = rows[csv_index].get("path", "")
    # 1) 写入 CSV
    fieldnames = list(rows[0].keys()) if rows else []
    csv_path = RUNTIME_DIR / "data" / "video_manager.csv"
    tmp = str(csv_path) + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, str(csv_path))
    # 2) 写入 .uploaded 标记文件
    if video_path:
        try:
            with open(video_path + ".uploaded", "w") as f:
                f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        except Exception:
            pass
    # 3) 同步更新 PostgreSQL
    try:
        from dotenv import load_dotenv
        load_dotenv(str(BASE_DIR / ".env"))
        DSN = os.environ.get("VIDEO_MANAGER_DB_DSN", "")
        if DSN and video_path:
            from sqlalchemy import create_engine, text
            from sqlalchemy.pool import NullPool
            engine = create_engine(DSN, poolclass=NullPool, future=True)
            with engine.begin() as conn:
                # 用 path 精确匹配 + 模糊匹配（路径可能斜杠格式不同）
                result = conn.execute(
                    text("UPDATE videos SET uploaded = 'Yes' WHERE path = :p OR path LIKE :p2"),
                    {"p": video_path, "p2": f"%{os.path.basename(video_path)}%"}
                )
                if result.rowcount > 0:
                    print(f"  [PG] updated uploaded='Yes' for {video_path} (rowcount={result.rowcount})")
                else:
                    # 如果没找到，再尝试按 path 的 basename 匹配
                    base = os.path.basename(video_path.rstrip("\\/"))
                    result2 = conn.execute(
                        text("UPDATE videos SET uploaded = 'Yes' WHERE path LIKE :p"),
                        {"p": f"%{base}%"}
                    )
                    print(f"  [PG] updated uploaded='Yes' for basename={base} (rowcount={result2.rowcount})")
    except Exception as e:
        print(f"  [PG] 同步失败: {e}")
    return True


def delete_local_files(session_path: str, log_path: Path | None = None, keep_thumbs: bool = False) -> None:
    """上传成功后删除本地文件以释放空间。

    删除范围：
    1. HMD 分片文件（session目录下的 *.hmd 文件）
    2. 处理后的预览视频（hmd_cache 下的 left.mp4, right.mp4）
    3. 缩略图文件（thumbnails 目录）（除非 keep_thumbs=True）
    4. 预览帧文件（frames 目录）

    Args:
        session_path: HMD session 的原始路径
        log_path: 日志文件路径
        keep_thumbs: 为 True 时保留缩略图
    """
    import shutil as _sh

    def _log(msg: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] [CLEANUP] {msg}"
        print(line, flush=True)
        if log_path:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")

    deleted_total = 0
    date_key = _extract_date_from_path(session_path)
    session_name = os.path.basename(session_path.rstrip("\\/"))

    # 1) 删除 HMD 分片文件
    if os.path.isdir(session_path):
        try:
            hmd_files = [f for f in os.listdir(session_path) if f.lower().endswith(".hmd")]
            for f in hmd_files:
                fp = os.path.join(session_path, f)
                size = os.path.getsize(fp)
                os.remove(fp)
                deleted_total += size
                _log(f"  删除 HMD: {f} ({size / 1024 / 1024:.1f} MB)")
            # 删除 metadata.json
            meta_file = os.path.join(session_path, "metadata.json")
            if os.path.exists(meta_file):
                size = os.path.getsize(meta_file)
                os.remove(meta_file)
                deleted_total += size
                _log(f"  删除 metadata.json ({size / 1024:.1f} KB)")
            # 如果目录空了，尝试删除空目录
            try:
                remaining = os.listdir(session_path)
                if not remaining:
                    os.rmdir(session_path)
                    _log(f"  删除空目录: {session_name}")
            except Exception:
                pass
        except Exception as e:
            _log(f"  清理 HMD 分片失败: {e}")

    # 2) 删除 hmd_cache 下的预览视频（新旧命名兼容）
    cache_dir = RUNTIME_DIR / "hmd_cache" / date_key / session_name
    if cache_dir.is_dir():
        sn = session_name
        _all_video = (f"{sn}.mp4", f"{sn}_right.mp4", f"{sn}.h265", f"{sn}_right.h265",
                       "left.mp4", "right.mp4", "left.h265", "right.h265")
        for video_file in _all_video:
            vp = cache_dir / video_file
            if vp.is_file():
                try:
                    size = vp.stat().st_size
                    os.remove(vp)
                    deleted_total += size
                    _log(f"  删除预览视频: {video_file} ({size / 1024 / 1024:.1f} MB)")
                except Exception as e:
                    _log(f"  删除 {video_file} 失败: {e}")

    # 3) 删除缩略图（除非 keep_thumbs=True）
    if not keep_thumbs:
        thumb_dir = RUNTIME_DIR / "thumbnails"
        if thumb_dir.is_dir():
            thumb_patterns = [
                f"{session_name}_*.jpg",
                f"{session_name}_*.png",
            ]
            for pattern in thumb_patterns:
                for thumb in thumb_dir.glob(pattern):
                    try:
                        size = thumb.stat().st_size
                        os.remove(thumb)
                        deleted_total += size
                        _log(f"  删除缩略图: {thumb.name}")
                    except Exception as e:
                        _log(f"  删除缩略图 {thumb.name} 失败: {e}")

    # 4) 删除帧文件（hmd_cache 下可能的 frames 目录）
    frames_dir = cache_dir / "frames"
    if frames_dir.is_dir():
        try:
            frame_count = 0
            for f in frames_dir.glob("*.jpg"):
                size = f.stat().st_size
                os.remove(f)
                deleted_total += size
                frame_count += 1
            if frame_count > 0:
                _log(f"  删除预览帧: {frame_count} 个文件")
        except Exception as e:
            _log(f"  删除预览帧失败: {e}")

    _log(f"总计释放空间: {deleted_total / 1024 / 1024:.1f} MB")


# ==================== 核心上传类 ====================

class AutoUploader:
    """FrameForge 自动上传器（表单填写模式）"""

    def __init__(self, log_path: Path | None = None):
        self.page = None
        self.context = None
        self.playwright = None
        self.log_path = log_path

    def _log(self, msg: str) -> None:
        log(msg, self.log_path)

    async def _with_page(self, page, coro):
        """Context manager: temporarily set self.page for the duration of coro."""
        old_page = self.page
        self.page = page
        try:
            return await coro
        finally:
            self.page = old_page

    # ── 浏览器启动 & 登录检测 ──

    async def start(self) -> bool:
        """启动浏览器并导航到上传页面，检测登录状态。
        如果掉线 → 自动停止，等待用户手动重新登录。
        Returns: True 表示已登录，False 表示需要登录（用户取消）。
        """
        self._log("启动 Chrome 浏览器...")
        self.playwright = await async_playwright().start()

        os.makedirs(BROWSER_DATA_DIR, exist_ok=True)
        self.context = await self.playwright.chromium.launch_persistent_context(
            BROWSER_DATA_DIR,
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
            viewport={"width": 1280, "height": 900},
        )
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()

        # 导航到上传页面
        self._log(f"导航到: {UPLOAD_URL}")
        try:
            await self.page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            self._log(f"导航超时/失败: {e}")
            # 尝试继续

        current_url = self.page.url
        self._log(f"当前页面: {current_url}")

        # 登录检测
        if await self._check_login_required():
            return await self._wait_for_login()

        # 等待上传页面加载完成
        await self._wait_for_upload_form(timeout=30)

        # 切换到中文界面
        await self._switch_to_chinese()

        return True

    async def _check_login_required(self) -> bool:
        """判断当前是否需要登录"""
        url = self.page.url.lower()
        if any(kw in url for kw in ("sign-up", "sign-in", "login", "signin", "signup")):
            return True

        # 额外检查：页面内容是否包含登录提示
        try:
            page_text = await self.page.locator("body").inner_text(timeout=3000)
            if any(kw in page_text.lower() for kw in ("sign in to continue", "log in to your account")):
                return True
        except Exception:
            pass

        return False

    async def _wait_for_login(self) -> bool:
        """阻塞等待用户手动登录，或者用户取消。
        每 3 秒检查一次 URL，直到不再需要登录。
        超时 10 分钟后放弃。
        """
        self._log("=" * 60)
        self._log("⚠ 检测到掉线/未登录状态！")
        self._log("请在浏览器窗口中手动登录 FrameForge")
        self._log("登录后导航到 Vendors > Upload 标签页")
        self._log("程序将自动检测登录状态并继续...")
        self._log("=" * 60)
        print("\n请在浏览器窗口中完成登录...")

        deadline = time.time() + 600  # 10 分钟超时
        while time.time() < deadline:
            await asyncio.sleep(3)
            try:
                current_url = self.page.url
                if not await self._check_login_required():
                    self._log(f"✓ 检测到已登录，当前页面: {current_url}")
                    await self._wait_for_upload_form(timeout=30)
                    return True
            except Exception:
                pass
            # 如果页面关闭了
            if self.context.pages:
                self.page = self.context.pages[-1]
            else:
                self._log("⚠ 浏览器窗口已关闭")
                return False

        self._log("✗ 登录等待超时（10分钟），放弃。")
        return False

    async def _wait_for_upload_form(self, timeout: int = 30) -> None:
        """等待上传页面的表单元素加载"""
        self._log("等待上传页面就绪...")
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                # 尝试多种可能的页面元素检测
                # 新表单可能包含 file input 或者 field labels
                has_form = await self.page.locator(
                    "input, select, textarea, [role='form']"
                ).first.count()
                if has_form > 0:
                    self._log("上传表单已加载")
                    await asyncio.sleep(1)  # 额外等待 React 渲染完成
                    return
            except Exception:
                pass
            await asyncio.sleep(1)

        # 截图供调试
        try:
            await self.page.screenshot(path=str(BASE_DIR / "upload_page_debug.png"))
            self._log("上传页面截图保存为 upload_page_debug.png")
        except Exception:
            pass
        self._log("⚠ 未检测到上传表单元素，继续尝试...")

    async def _switch_to_chinese(self) -> None:
        """点击中文按钮，切换页面语言为中文"""
        for selector in [
            "button:has-text('中文')",
            "[aria-label*='中文']",
            "text=中文",
        ]:
            try:
                cnt = await self.page.locator(selector).count()
                if cnt > 0:
                    await self.page.locator(selector).first.click()
                    self._log("已切换为中文界面")
                    await asyncio.sleep(1.5)
                    return
            except Exception:
                pass
        self._log("⚠ 未找到中文切换按钮")

    # ── 字段填写 ──

    async def _try_fill_element(self, el, key: str, value: str) -> tuple[bool, str]:
        """尝试填一个已定位的元素。返回 (成功, 方法描述)。"""
        # 先滚动到可视区域
        try:
            await el.scroll_into_view_if_needed(timeout=2000)
            await asyncio.sleep(0.15)
        except Exception:
            pass
        tag = await el.evaluate("el => el.tagName.toLowerCase()")
        class_name = await el.evaluate("el => el.className || ''")

        # ── 检测是否为 shadcn/ui combobox (input with ring-offset-background → popover) ──
        is_combobox = (tag == "input" and "ring-offset-background" in class_name)

        if tag == "select":
            # 原生 select
            for attempt in [
                ("value", lambda: el.select_option(value, timeout=3000)),
                ("label", lambda: el.select_option(label=value, timeout=3000)),
            ]:
                try:
                    await attempt[1]()
                    return True, f"select by {attempt[0]}"
                except Exception:
                    pass
            # 按 option 文本模糊匹配
            try:
                option = el.locator(f"option:has-text('{value}')")
                if await option.count() > 0:
                    opt_val = await option.first.get_attribute("value")
                    if opt_val:
                        await el.select_option(value=opt_val, timeout=3000)
                        return True, "select by text match"
            except Exception:
                pass

        elif is_combobox:
            # ── 保存当前 URL，用于后续页面稳定性检测 ──
            original_url = self.page.url
            async def _page_stable() -> bool:
                """检查页面 URL 没有意外跳转"""
                try:
                    return self.page.url == original_url
                except Exception:
                    return False

            # ── 关掉可能已打开的 popover ──
            try:
                await self.page.keyboard.press("Escape")
                await asyncio.sleep(0.15)
            except Exception:
                pass

            v = str(value)
            # 规范化：下划线/连字符 → 空格（popover 选项显示的是空格版本）
            v_norm = re.sub(r'[_-]+', ' ', v).strip()
            first_word = v_norm.split()[0] if v_norm else ""
            self._log(f"    [{key}] combobox: raw='{v}' norm='{v_norm}' first='{first_word}'")

            # ── 辅助：关闭 popover + 点击空白区域 ──
            async def _close_popover():
                try:
                    await self.page.keyboard.press("Escape")
                except Exception:
                    pass
                try:
                    await self.page.mouse.click(10, 300)
                except Exception:
                    pass
                await asyncio.sleep(0.2)

            # ── 辅助：验证选项是否被选中（通过 popover 是否关闭来判断） ──
            async def _verify_selection() -> bool:
                """点击选项后，检查 popover 是否关闭了（表示选中成功）。
                对 shadcn/ui 而言，点击 cmdk-item 后 popover 自动消失。"""
                await asyncio.sleep(0.3)
                # 检查是否还有可见的 popover/cmdk 选项（必须可见，DOM 残留不算）
                for pop_sel in ["[cmdk-item]", "[role='option']", "[class*='CommandItem']"]:
                    try:
                        loc = self.page.locator(f"{pop_sel}:visible").first
                        if await loc.count() > 0:
                            return False
                    except Exception:
                        continue
                # 也检查是否有可见的 popover 容器
                try:
                    popover = self.page.locator("[class*='popover']:visible, [role='listbox']:visible").first
                    if await popover.count() > 0:
                        return False
                except Exception:
                    pass
                # popover 全关了 = 选中成功
                return True

            # 构建搜索词列表（按优先级：完整值 → 原始值 → 首词 → 前缀）
            search_terms: list[str] = []
            seen = set()
            for candidate in [v_norm, v, first_word]:
                if candidate and candidate not in seen and len(candidate) >= 2:
                    search_terms.append(candidate)
                    seen.add(candidate)
            # 额外前缀（基于规范化值，逐级缩短）
            for n in range(len(v_norm) - 1, 1, -1):
                prefix = v_norm[:n].rstrip()
                if prefix and prefix not in seen and len(prefix) >= 2:
                    search_terms.append(prefix)
                    seen.add(prefix)

            # ═══════════════════════════════════════════════════════════
            # 策略 A：不输入文字 → 直接点击打开全量下拉 → has-text 匹配选项
            # ═══════════════════════════════════════════════════════════
            try:
                await el.click(timeout=2000)
                await asyncio.sleep(0.5)
            except Exception as e:
                self._log(f"    [{key}] 策略A: 点击失败 {e}")

            for term in search_terms:
                option_sels = [
                    f"[cmdk-item]:has-text('{term}')",
                    f"[role='option']:has-text('{term}')",
                    f"[class*='CommandItem']:has-text('{term}')",
                    f"div[role='option']:has-text('{term}')",
                    f"[data-value]:has-text('{term}')",
                    f"li:has-text('{term}')",
                    f"[role='menuitem']:has-text('{term}')",
                    f"text='{term}'",
                ]
                for opt_sel in option_sels:
                    try:
                        option = self.page.locator(opt_sel).first
                        if await option.count() > 0:
                            await option.click(timeout=3000)
                            await asyncio.sleep(0.2)
                            self._log(f"    [{key}] 策略A ✓ ({term})")
                            return True, "combobox click-select"
                    except Exception:
                        continue

            if not await _page_stable():
                self._log(f"  ⚠ 页面 URL 已变化！停止填写 combobox")
                await _close_popover()
                return False, "page changed"

            # ═══════════════════════════════════════════════════════════
            # 策略 B：输入首词 → 过滤下拉 → has-text 匹配选项
            # ═══════════════════════════════════════════════════════════
            await _close_popover()
            if first_word and len(first_word) >= 2 and await _page_stable():
                self._log(f"    [{key}] 策略B: 输入'{first_word}'→过滤→点击...")
                try:
                    await el.fill("", timeout=800)
                except Exception:
                    pass
                try:
                    await el.click(timeout=1000)
                except Exception:
                    pass
                await asyncio.sleep(0.1)
                try:
                    await el.fill(first_word, timeout=2000)
                except Exception:
                    pass
                await asyncio.sleep(0.5)

                for term in search_terms:
                    option_sels = [
                        f"[cmdk-item]:has-text('{term}')",
                        f"[role='option']:has-text('{term}')",
                        f"div[role='option']:has-text('{term}')",
                        f"text='{term}'",
                    ]
                    for opt_sel in option_sels:
                        try:
                            option = self.page.locator(opt_sel).first
                            if await option.count() > 0:
                                await option.click(timeout=3000)
                                await asyncio.sleep(0.2)
                                self._log(f"    [{key}] 策略B ✓ ({term})")
                                return True, "combobox type+click"
                        except Exception:
                            continue

            # ═══════════════════════════════════════════════════════════
            # 策略 C：fill 完整值 → blur 让 combobox 接受值
            # ═══════════════════════════════════════════════════════════
            await _close_popover()
            if await _page_stable():
                self._log(f"    [{key}] 策略C: fill→blur 接受值...")
                try:
                    await el.fill("", timeout=500)
                    await el.fill(v, timeout=2000)
                    await asyncio.sleep(0.3)
                    await self.page.mouse.click(10, 300)
                    await asyncio.sleep(0.2)
                    self._log(f"    [{key}] 策略C ✓ (fill+blur)")
                    return True, "combobox fill+blur"
                except Exception:
                    pass

            # ── 最终清理 ──
            self._log(f"    [{key}] 所有策略失败，清理 popover")
            await _close_popover()

        elif tag in ("textarea", "input"):
            # Plain text input/textarea
            await el.click(timeout=2000)
            await asyncio.sleep(0.1)
            try:
                await el.fill("", timeout=2000)
            except Exception:
                pass
            await el.fill(str(value), timeout=5000)
            return True, "fill"

        elif tag in ("div", "span", "button"):
            # 自定义下拉/选择组件（React/AntD/MUI）
            await el.click(timeout=2000)
            await asyncio.sleep(0.6)

            option_selectors = [
                f"[role='option']:has-text('{value}')",
                f"[role='menuitem']:has-text('{value}')",
                f".ant-select-item:has-text('{value}')",
                f".ant-select-dropdown :has-text('{value}')",
                f"[class*='select-dropdown'] :has-text('{value}')",
                f"[class*='dropdown'] :has-text('{value}')",
                f"li:has-text('{value}')",
            ]
            for opt_sel in option_selectors:
                try:
                    option = self.page.locator(opt_sel)
                    cnt = await option.count()
                    if cnt > 0:
                        await option.first.click(timeout=3000)
                        return True, "custom select"
                except Exception:
                    continue
            try:
                await self.page.keyboard.press("Escape")
            except Exception:
                pass

        return False, "no match"

    async def _find_element_by_label(self, key: str) -> list:
        """通过 label 文本在页面上查找对应的表单控件。
        返回找到的所有 locator 列表（Playwright locator）。
        """
        label_text = FIELD_LABELS.get(key, key.replace("_", " ").lower())
        found = []

        # Generate text variants to try (handle dash, slash, asterisk variants)
        # e.g. "facility / venue" → also try "facility", "facility/venue", etc.
        variants = [label_text]
        # Lowercase variant (already lowercase in FIELD_LABELS, but belt-and-suspenders)
        variants.append(label_text.lower())
        # Strip trailing " *" or "*" 
        stripped = label_text.rstrip(" *")
        if stripped != label_text:
            variants.append(stripped)
        # Replace " / " with "/" and vice versa
        if " / " in label_text:
            variants.append(label_text.replace(" / ", "/"))
            variants.append(label_text.replace(" / ", "-"))
        if "-" in label_text:
            variants.append(label_text.replace("-", " "))
            variants.append(label_text.replace("-", "_"))
        if "_" in label_text:
            variants.append(label_text.replace("_", " "))
            variants.append(label_text.replace("_", "-"))
        # Deduplicate
        variants = list(dict.fromkeys(variants))

        # ── 策略 A：标准 <label> 元素，尝试每个 variant ──
        for vt in variants:
            if found:
                break
            label_patterns = [
                f"label:has-text('{vt}')",
                f"[aria-label*='{vt}']",
                f"[placeholder*='{vt}']",
            ]
            for pat in label_patterns:
                try:
                    loc = self.page.locator(pat)
                    if await loc.count() > 0:
                        el = loc.first
                        tag = await el.evaluate("el => el.tagName.toLowerCase()")
                        if tag == "label":
                            ctrl_id = await el.get_attribute("for")
                            if ctrl_id:
                                ctrl = self.page.locator(f"#{ctrl_id}")
                                if await ctrl.count() > 0:
                                    found.append(ctrl.first)
                                    break
                            # Try children: input/select/textarea inside label
                            for child_sel in [" input", ">> input", ">> select", ">> textarea",
                                               "+ input", "+ select", "+ textarea",
                                               " select", " textarea"]:
                                try:
                                    sibling = self.page.locator(f"{pat} {child_sel}")
                                    if await sibling.count() > 0:
                                        found.append(sibling.first)
                                        break
                                except Exception:
                                    pass
                        else:
                            found.append(el.first)
                            break
                except Exception:
                    continue

        # ── 策略 B：通过 JS 查找 label 文本对应的 form control ──
        if not found:
            try:
                result = await self.page.evaluate(f"""() => {{
                    const variants = {json.dumps(variants)};
                    const controls = [];
                    const iter = document.createNodeIterator(document.body, NodeFilter.SHOW_TEXT);
                    let node;
                    while (node = iter.nextNode()) {{
                        const txt = node.textContent.trim();
                        // Check if any variant matches the start of this text node
                        let matched = false;
                        for (const vt of variants) {{
                            if (txt === vt || txt.startsWith(vt) ||
                                // Also match "country *" when looking for "country"
                                txt.replace(/\\s*\\*\\s*$/, '') === vt) {{
                                matched = true;
                                break;
                            }}
                        }}
                        if (!matched) continue;
                        let parent = node.parentElement;
                        for (let i = 0; i < 8 && parent; i++) {{
                            const inputs = parent.querySelectorAll('input, select, textarea');
                            if (inputs.length > 0) {{
                                for (const inp of inputs) {{
                                    const r = inp.getBoundingClientRect();
                                    if (r.width > 0 && r.height > 0) {{
                                        controls.push({{
                                            tag: inp.tagName.toLowerCase(),
                                            placeholder: inp.placeholder || '',
                                            index: Array.from(document.querySelectorAll(inp.tagName)).indexOf(inp),
                                        }});
                                    }}
                                }}
                                break;
                            }}
                            parent = parent.parentElement;
                        }}
                    }}
                    return controls;
                }}""")
                for ctrl_info in result:
                    tag = ctrl_info.get("tag", "input")
                    idx = ctrl_info.get("index", 0)
                    loc = self.page.locator(tag).nth(idx)
                    if await loc.count() > 0:
                        found.append(loc)
            except Exception:
                pass

        # ── 策略 C：包含 label_text 的 class 容器 ──
        if not found:
            for vt in variants:
                if found:
                    break
                container_patterns = [
                    f"[class*='field']:has-text('{vt}')",
                    f"[class*='form-item']:has-text('{vt}')",
                    f"[class*='formField']:has-text('{vt}')",
                    f"div:has-text('{vt}'):not(:has(div:has-text('{vt}')))",
                ]
                for pat in container_patterns:
                    try:
                        container = self.page.locator(pat)
                        cnt = await container.count()
                        if cnt > 0:
                            for tag_sel in ["input", "select", "textarea"]:
                                inner = container.first.locator(tag_sel)
                                if await inner.count() > 0 and await inner.first.is_visible():
                                    found.append(inner.first)
                                    break
                            if found:
                                break
                    except Exception:
                        continue

        # ── 策略 D：antd / MUI 组件 ──
        if not found:
            for vt in variants:
                if found:
                    break
                antd_patterns = [
                    f".ant-form-item:has-text('{vt}') .ant-select",
                    f".ant-form-item:has-text('{vt}') .ant-input",
                    f".ant-form-item:has-text('{vt}') textarea",
                    f"[class*='MuiFormControl']:has-text('{vt}') [role='combobox']",
                    f"[class*='MuiFormControl']:has-text('{vt}') input",
                ]
                for pat in antd_patterns:
                    try:
                        loc = self.page.locator(pat)
                        if await loc.count() > 0:
                            found.append(loc.first)
                            break
                    except Exception:
                        continue

        return found

    async def _set_capture_mode(self, value: str) -> bool:
        """Set the capture mode by clicking the correct button in the button group.
        The capture mode section is a row of <button> elements (not a form field):
          Single-cam | Three-Views | Stereo
        """
        value_lower = value.lower().strip()
        # Map common value formats to button text
        button_map = {
            "stereo": "Stereo",
            "single": "Single-cam",
            "mono": "Single-cam",
            "single-cam": "Single-cam",
            "single_cam": "Single-cam",
            "single cam": "Single-cam",
            "three-views": "Three-Views",
            "three_views": "Three-Views",
            "three views": "Three-Views",
            "threeviews": "Three-Views",
        }
        target_text = button_map.get(value_lower, value)
        self._log(f"  captureMode → button group, clicking '{target_text}'")

        try:
            # Find the button with the matching text (case-insensitive)
            btn = self.page.locator(f"button:has-text('{target_text}')")
            cnt = await btn.count()
            if cnt == 0:
                # Try more relaxed match
                btn = self.page.locator(f"button:has-text('{target_text}')").first
                cnt = await btn.count() if btn else 0
            if cnt > 0:
                # Click the first matching button
                await btn.first.click(timeout=3000)
                await asyncio.sleep(0.3)
                # Verify it became active (bg-emerald-600 indicates selected)
                is_active = await btn.first.evaluate(
                    "el => el.classList.contains('bg-emerald-600')"
                )
                if is_active:
                    return True
                # If not visually active, try clicking again
                await btn.first.click(timeout=3000)
                await asyncio.sleep(0.2)
                return True
        except Exception as e:
            self._log(f"  captureMode button click failed: {e}")

        # Fallback: search by "Capture mode" section
        try:
            section = self.page.locator("text='Capture mode'")
            if await section.count() > 0:
                # Find sibling buttons
                parent = section.locator("..")  # go up one level
                btn = parent.locator(f"button:has-text('{target_text}')")
                if await btn.count() > 0:
                    await btn.first.click(timeout=3000)
                    await asyncio.sleep(0.3)
                    return True
        except Exception:
            pass

        return False

    async def fill_field(self, key: str, value: str) -> bool:
        """尝试用多种策略定位并填写一个字段。
        Returns: True 表示成功填写。
        """
        if not value or not str(value).strip():
            return False  # 跳过空值

        # ── 跳过 GPS 自动填充的字段 ──
        # 中文页面选定地址候选后，页面会根据 GPS 经纬度自动回填 country/state_province/city
        # 如果我们手动填入中文"中国"，页面的英文国家列表会把它转成 "China"
        # 所以这些字段直接跳过，让页面自己根据 GPS 坐标回填
        if key in ("country", "state_province", "city"):
            self._log(f"  ⏭ {key} 跳过（GPS 自动回填）")
            return True  # 视为成功（不需要手动填）

        # Special: captureMode is a button group, not a form field
        if key == "captureMode":
            ok = await self._set_capture_mode(str(value))
            if ok:
                self._log(f"  ✓ {key} = {value} (button group click)")
            else:
                self._log(f"  ✗ {key} = {value} (button group — 未找到匹配按钮)")
            return ok

        # Special: environment 字段的下拉选项是纯 div+span（不是 cmdk-item），
        # 通用 combobox 逻辑找不到，需要用文本匹配单独处理
        if key == "environment":
            ok = await self._fill_environment_combob(value)
            if ok:
                self._log(f"  ✓ {key} = {value} (environment combobox)")
            return ok

        # Special: location_address 是 GPS autocomplete，需要输入后等待候选再选第一个
        # ⚠ 必须 return，否则会落入 Phase 1 再次 fill input，把已锁定的 GPS 经纬度覆盖掉
        if key == "location_address":
            ok = await self._fill_address_autocomplete(value)
            if ok:
                self._log(f"  ✓ {key} = {value} (address autocomplete)")
            else:
                self._log(f"  ✗ {key} = {value} (address autocomplete — GPS 候选未匹配)")
            return ok

        # Phase 1: 尝试预定义的 CSS selectors
        selectors = FIELD_SELECTORS.get(key, [])
        if not selectors:
            selectors = [
                f"[data-field='{key}']",
                f"[name='{key}']",
                f"[id='{key}']",
            ]

        for selector in selectors:
            try:
                loc = self.page.locator(selector)
                cnt = await loc.count()
                if cnt == 0:
                    continue
                el = loc.first
                if not await el.is_visible(timeout=2000):
                    continue
                ok, method = await self._try_fill_element(el, key, str(value))
                if ok:
                    self._log(f"  ✓ {key} = {value} ({method})")
                    return True
            except Exception:
                continue

        # Phase 2: 通过 label 文本搜索
        # ── 安全栅：检查页面是否还在上传页面 ──
        page_url_ok = True
        try:
            if "upload" not in self.page.url.lower() and "vendor" not in self.page.url.lower():
                self._log(f"  ⚠ 页面已跳离上传页面，停止填写 {key}")
                page_url_ok = False
        except Exception:
            pass

        if page_url_ok:
            elements = await self._find_element_by_label(key)
            for el in elements:
                try:
                    if not await el.is_visible(timeout=2000):
                        continue
                    ok, method = await self._try_fill_element(el, key, str(value))
                    if ok:
                        self._log(f"  ✓ {key} = {value} ({method}, via label)")
                        return True
                except Exception:
                    continue

        # Phase 3: 暴力搜索 - 页面上所有可见的 input/select/textarea/combobox
        # 根据 label 文本在附近查找
        if not page_url_ok:
            return False
        label_text = FIELD_LABELS.get(key, key.replace("_", " ").title())
        try:
            # 尝试点击包含 label_text 的任意元素（可能是自定义组件的 trigger）
            triggers = self.page.locator(f"[class*='trigger']:has-text('{label_text}'), "
                                         f"[class*='selector']:has-text('{label_text}')")
            if await triggers.count() > 0:
                await triggers.first.click(timeout=2000)
                await asyncio.sleep(0.5)
                # 再尝试找选项
                for opt_sel in [
                    f"[role='option']:has-text('{value}')",
                    f".ant-select-item:has-text('{value}')",
                    f"li:has-text('{value}')",
                ]:
                    try:
                        opt = self.page.locator(opt_sel)
                        if await opt.count() > 0:
                            await opt.first.click(timeout=3000)
                            self._log(f"  ✓ {key} = {value} (brute-force select)")
                            return True
                    except Exception:
                        continue
                try:
                    await self.page.keyboard.press("Escape")
                except Exception:
                    pass
        except Exception:
            pass

        return False

    async def _fill_field_by_position(self, key: str, value: str) -> bool:
        """终极回退：JS 级别暴力搜索 label 文本 → 最近的 input/select/textarea。
        用于那些 placeholder 为空、CSS 选择器全部失败、label 结构特殊的字段。"""
        try:
            result = await self.page.evaluate(f"""() => {{
                const labelTexts = {json.dumps(FIELD_LABELS.get(key, key).split('/'))};
                const variants = [];
                for (const t of labelTexts) {{
                    const trimmed = t.trim();
                    variants.push(trimmed, trimmed + ' *', trimmed + '*');
                    if (trimmed.includes(' / ')) variants.push(trimmed.replace(' / ', '/'));
                    if (trimmed.includes('-')) {{
                        variants.push(trimmed.replace(/-/g, ' '));
                        variants.push(trimmed.replace(/-/g, '_'));
                    }}
                    if (trimmed.includes('_')) {{
                        variants.push(trimmed.replace(/_/g, ' '));
                        variants.push(trimmed.replace(/_/g, '-'));
                    }}
                }}

                // Walk all text nodes, find closest match
                const iter = document.createNodeIterator(document.body, NodeFilter.SHOW_TEXT);
                const candidates = [];
                let node;
                while (node = iter.nextNode()) {{
                    const raw = node.textContent || '';
                    const txt = raw.replace(/\\\\s+/g, ' ').trim();
                    let bestScore = 0;
                    for (const v of variants) {{
                        const vLower = v.toLowerCase();
                        const tLower = txt.toLowerCase();
                        if (tLower === vLower) {{ bestScore = Math.max(bestScore, 3); break; }}
                        if (tLower.startsWith(vLower)) {{ bestScore = Math.max(bestScore, 2); }}
                        if (tLower.includes(vLower)) {{ bestScore = Math.max(bestScore, 1); }}
                    }}
                    if (bestScore === 0) continue;

                    // Find nearest input/select/textarea in ancestors or siblings
                    let parent = node.parentElement;
                    for (let i = 0; i < 10 && parent; i++) {{
                        const ctrls = parent.querySelectorAll('input:not([type="hidden"]):not([type="file"]), select, textarea');
                        for (const c of ctrls) {{
                            const r = c.getBoundingClientRect();
                            if (r.width > 0 && r.height > 0 && !c.disabled && !c.readOnly) {{
                                candidates.push({{
                                    score: bestScore,
                                    tag: c.tagName.toLowerCase(),
                                    placeholder: c.placeholder || '',
                                    index: Array.from(document.querySelectorAll(c.tagName.toLowerCase() + ':not([type="hidden"]):not([type="file"])')).indexOf(c),
                                    y: Math.round(r.y),
                                }});
                                break;
                            }}
                        }}
                        if (candidates.length > 0 && candidates[candidates.length-1].y > 0) break;
                        parent = parent.parentElement;
                    }}
                }}
                candidates.sort((a, b) => b.score - a.score || a.y - b.y);
                return candidates.length > 0 ? candidates[0] : null;
            }}""")
            if result:
                tag = result["tag"]
                idx = result["index"]
                loc = self.page.locator(tag).nth(idx)
                if await loc.count() > 0 and await loc.is_visible(timeout=2000):
                    ok, method = await self._try_fill_element(loc, key, value)
                    if ok:
                        self._log(f"  ✓ {key} = {value} ({method}, position-scan)")
                        return True
        except Exception:
            pass
        return False

    def _map_value(self, key: str, value: str) -> str:
        """将英文 CSV 值映射为中文页面对应值"""
        field_map = VALUE_MAP.get(key, {})
        return field_map.get(value, value)

    async def _get_field_value(self, key: str) -> str:
        """从页面读取指定字段当前的真实值（input value / select option text）。

        两路查找:
          1) FIELD_SELECTORS / data-field / name / id
          2) _find_element_by_label (label 文本模糊匹配, 与 fill_field 同一机制)
        """
        if key == "captureMode":
            return ""  # captureMode 是按钮组, 不在 input/select 里
        candidates = list(FIELD_SELECTORS.get(key, []))
        candidates += [
            f"[data-field='{key}']",
            f"[name='{key}']",
            f"[id='{key}']",
        ]

        async def _read(el) -> str:
            return await el.evaluate(
                """el => {
                    if (!el) return '';
                    const tag = el.tagName.toLowerCase();
                    if (tag === 'select') {
                        const o = el.options[el.selectedIndex];
                        return o ? o.text : '';
                    }
                    if (tag === 'input' || tag === 'textarea') {
                        return el.value || '';
                    }
                    // shadcn combobox / div-based input
                    return el.value || el.innerText || el.textContent || '';
                }"""
            )

        # 1) CSS selector 路径
        for sel in candidates:
            try:
                loc = self.page.locator(sel).first
                if await loc.count() > 0 and await loc.is_visible(timeout=800):
                    val = await _read(loc)
                    if val and str(val).strip():
                        return str(val).strip()
            except Exception:
                continue

        # 2) label 路径 (跟 fill_field 一样的 _find_element_by_label)
        try:
            elements = await self._find_element_by_label(key)
            for el in elements:
                try:
                    if not await el.is_visible(timeout=500):
                        continue
                    val = await _read(el)
                    if val and str(val).strip():
                        return str(val).strip()
                except Exception:
                    continue
        except Exception:
            pass

        return ""

    async def verify_all_filled(self, template: dict) -> dict[str, dict]:
        """
        上传前校验: 检查 template 中每个待填字段, 在页面上都能查到非空值.

        Returns:
          {key: {"expected": str, "actual": str, "ok": bool}}

        跳过:
          - country / state_province / city (GPS 自动回填)
          - source_device (这是 CSV-only 字段, 表单里没有)
          - captureMode (button group, 不是 input)
          - 没有匹配 FIELD_SELECTORS 的 key
        """
        skip_keys = {"country", "state_province", "city", "source_device", "captureMode"}
        result: dict[str, dict] = {}

        for key, expected in template.items():
            if not expected or not str(expected).strip():
                continue
            if key in skip_keys:
                continue
            if key not in FIELD_SELECTORS:
                continue

            actual = await self._get_field_value(key)
            result[key] = {
                "expected": str(expected).strip(),
                "actual": actual,
                "ok": bool(actual and actual != "未找到对应输入框"),
            }
        return result

    async def _retry_unfilled(self, template: dict, keys: list[str]) -> list[str]:
        """
        重试一组未成功填上的字段:
          1) PositionScan (位置暴力搜索)
          2) 标准 fill_field
          3) 重新 evaluate 状态

        Returns: list of still-unfilled keys.
        """
        still_empty: list[str] = []
        for key in keys:
            value = template.get(key, "")
            if not value or not str(value).strip():
                still_empty.append(key)
                continue
            mapped = self._map_value(key, str(value))

            ok = False
            # 1) PositionScan 优先 (能解决"label 没匹配但 page 有同位置 input"的情况)
            if await self._fill_field_by_position(key, mapped):
                ok = True
            # 2) 标准 fill_field 再来
            elif await self.fill_field(key, mapped):
                ok = True

            if ok:
                # 真实验证
                actual = await self._get_field_value(key)
                if actual and actual.strip():
                    self._log(f"    ✓ {key} 重试后填上 (值={actual[:30]!r})")
                    continue
                self._log(f"    ⚠ {key} 重试表面 ok 但页面查不到值, 再试 fill_field+blur")
                # fill_field+blur 通常是 fill 完把 combobox 关闭, 重新 fill 一次
                try:
                    loc = self.page.locator(FIELD_SELECTORS[key][0]).first
                    if await loc.count() > 0:
                        await loc.fill("", timeout=2000)
                        await loc.fill(mapped, timeout=3000)
                        await asyncio.sleep(0.3)
                        # dismiss popover if appears
                        await self.page.keyboard.press("Escape")
                        await asyncio.sleep(0.2)
                except Exception:
                    pass

            actual = await self._get_field_value(key)
            if actual and actual.strip():
                self._log(f"    ✓ {key} 重试后填上 (值={actual[:30]!r})")
            else:
                self._log(f"    ✗ {key} 重试后仍空: 期望={str(value)[:30]!r}")
                still_empty.append(key)
        return still_empty

    async def fill_all_fields(self, template: dict) -> tuple[int, int]:
        """填写所有有值的字段（按 FILL_ORDER 排序）。返回 (已填, 总数)。"""
        total = 0
        filled = 0
        # 按 FILL_ORDER 排序，不在列表中的字段排最后
        order_index = {k: i for i, k in enumerate(FILL_ORDER)}
        sorted_keys = sorted(
            [k for k, v in template.items() if v and str(v).strip()],
            key=lambda k: order_index.get(k, 999),
        )
        unfilled = []
        for key in sorted_keys:
            value = template[key]
            mapped_value = self._map_value(key, str(value))
            total += 1
            if await self.fill_field(key, mapped_value):
                filled += 1
            else:
                self._log(f"  ✗ {key} = {mapped_value} (未找到对应输入框)")
                unfilled.append((key, mapped_value))
        # ── 终极回退：对仍未填写的字段，用 JS 级别暴力搜索 ──
        if unfilled:
            self._log(f"\n  尝试位置暴力搜索 {len(unfilled)} 个剩余字段...")
            still_unfilled = []
            for key, value in unfilled:
                if await self._fill_field_by_position(key, value):
                    filled += 1
                else:
                    still_unfilled.append((key, value))
            if still_unfilled:
                self._log(f"  ⚠ 暴力搜索后仍有 {len(still_unfilled)} 个字段未填写")
        return filled, total

    # ── 表单元素诊断 ──

    async def _clear_form(self) -> None:
        """清空上传表单所有字段（不清空页面，不丢失inflight状态）。"""
        self._log("  清空表单字段...")
        try:
            await self.page.evaluate("""() => {
                // Clear all inputs (not file inputs)
                document.querySelectorAll('input:not([type="file"]):not([type="hidden"])').forEach(el => {
                    el.value = '';
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                });
                // Reset selects to first option
                document.querySelectorAll('select').forEach(el => {
                    if (el.options.length > 0) el.selectedIndex = 0;
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                });
                // Clear textareas
                document.querySelectorAll('textarea').forEach(el => {
                    el.value = '';
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                });
                // Try clicking body to dismiss any open combobox popovers
                document.body.click();
                document.body.focus();
            }""")
            await asyncio.sleep(0.5)
            # Dismiss any popovers with Escape
            try:
                await self.page.keyboard.press("Escape")
                await asyncio.sleep(0.2)
            except Exception:
                pass
            self._log("  表单已清空")
        except Exception as e:
            self._log(f"  清空表单失败: {e}")

    async def _fill_address_autocomplete(self, value: str) -> bool:
        """GPS autocomplete 字段：输入地址→等待候选加载→点击第一个候选→验证锁定。

        复用 fill_frameforge_form_v7.py 成功的方案：
        - 候选选择器（多策略并联）：
            .bg-popover.absolute div[class*='cursor-pointer'],
            ul[class*='absolute'][class*='z-'] li button,
            [role='listbox'] [role='option']
        - exact_pick=False：地址候选不需要严格包含输入文本
        - 等待 14s（28 × 500ms），比之前 10s 更宽裕
        - 跳过 aria-disabled=true / 不可见的候选
        - 点击第一个可见候选
        """
        v = str(value).strip()
        if not v:
            return False

        inp = None
        for sel in [
            "input[placeholder*='输入地址搜索']",
            "input[placeholder*='地址']",
        ]:
            try:
                cnt = await self.page.locator(sel).count()
                if cnt > 0 and await self.page.locator(sel).first.is_visible(timeout=2000):
                    inp = self.page.locator(sel).first
                    break
            except Exception:
                pass
        if not inp:
            self._log(f"  location_address: 找不到输入框")
            return False

        try:
            await inp.scroll_into_view_if_needed(timeout=2000)
            await inp.click(timeout=2000)
            await asyncio.sleep(0.2)
        except Exception as e:
            self._log(f"  location_address: 点击失败 {e}")
            return False

        # fill value 触发地址搜索
        try:
            await inp.fill("", timeout=2000)
            await asyncio.sleep(0.2)
            await inp.fill(v, timeout=3000)
            self._log(f"  已输入地址: {v}")
        except Exception as e:
            self._log(f"  location_address: 输入失败 {e}")
            return False

        # 给候选列表初次渲染留时间（frameforge 通常 1-2s 出结果）
        await asyncio.sleep(1.5)

        # 多策略候选选择器（来自 v7/v8 成功方案）
        candidate_selectors = (
            ".bg-popover.absolute div[class*='cursor-pointer'], "
            "ul[class*='absolute'][class*='z-'] li button, "
            "[role='listbox'] [role='option']"
        )

        max_wait_iters = 28  # 28 × 500ms = 14 秒
        for i in range(max_wait_iters):
            try:
                candidates = self.page.locator(candidate_selectors)
                cnt = await candidates.count()
                if cnt > 0:
                    self._log(f"  location_address: 检测到 {cnt} 个候选（第 {i + 1} 轮）")
                    for idx in range(cnt):
                        c = candidates.nth(idx)
                        try:
                            dis = (await c.get_attribute("aria-disabled")) or ""
                            if dis.lower() == "true":
                                continue
                            if not await c.is_visible(timeout=500):
                                continue
                            txt = (await c.inner_text()).strip()
                            if not txt:
                                continue
                            # exact_pick=False：地址候选不需要严格匹配 input value
                            await c.scroll_into_view_if_needed(timeout=1000)
                            await c.click(timeout=3000, force=True)
                            self._log(f"  location_address: ✓ 点击候选 = {txt[:60]!r}")
                            # 验证 input value 是否被更新
                            await asyncio.sleep(1.5)
                            input_val = await inp.input_value()
                            self._log(f"  location_address: 点击后 input value = {input_val!r}")
                            if any(kw in input_val for kw in ["南安", "辉煌", "仑苍", "示例市"]):
                                self._log(f"  location_address: ✓ GPS 锁定成功")
                                return True
                            # 即使 input 没显示完整地址（GPS 只锁定坐标，地址显示在别处）也认为成功
                            # 因为很多情况下地址 input value 不一定含完整地址字符串
                            self._log(f"  location_address: ✓ 候选已点击（GPS 已锁定）")
                            return True
                        except Exception as e:
                            self._log(f"  location_address: 候选 {idx} 处理异常: {str(e)[:40]}")
                            continue
            except Exception as e:
                self._log(f"  location_address: 候选查询异常: {str(e)[:40]}")

            await asyncio.sleep(0.5)

        self._log(f"  location_address: 14秒内未选中候选")
        # 关掉残留的下拉
        try:
            await self.page.keyboard.press("Escape")
            await asyncio.sleep(0.3)
        except Exception:
            pass
        return False

    async def _fill_environment_combob(self, value: str) -> bool:
        """environment 字段专用：下拉选项是纯 div+span，需要文本匹配点击。"""
        v = str(value).strip()
        if not v:
            return False

        selectors = [
            "input[placeholder='环境大类']",
            "input[placeholder*='环境大类']",
            "[data-field='environment']",
        ]
        env_input = None
        for sel in selectors:
            cnt = await self.page.locator(sel).count()
            if cnt > 0:
                el = self.page.locator(sel).first
                if await el.is_visible(timeout=2000):
                    env_input = el
                    break

        if not env_input:
            self._log(f"  ✗ environment: 找不到 input")
            return False

        try:
            await env_input.scroll_into_view_if_needed(timeout=2000)
        except Exception as e:
            self._log(f"  ✗ environment: {e}")
            return False

        try:
            await env_input.click(timeout=2000)
            await asyncio.sleep(0.5)
        except Exception as e:
            self._log(f"  ✗ environment: 点击失败 {e}")
            return False

        try:
            await self.page.wait_for_selector(".bg-popover.absolute", state="visible", timeout=3000)
            await asyncio.sleep(0.3)
        except Exception:
            self._log(f"  ✗ environment: popover 未出现")
            return False

        option_sel = f".bg-popover.absolute .cursor-pointer:not([aria-disabled='true']):has(span:text-is('{v}'))"
        option_sel_alt = f".bg-popover.absolute span:text-is('{v}')"

        for sel in [option_sel, option_sel_alt]:
            try:
                cnt = await self.page.locator(sel).count()
                if cnt > 0:
                    opt = self.page.locator(sel).first
                    if await opt.is_visible(timeout=2000):
                        await opt.scroll_into_view_if_needed(timeout=2000)
                        await opt.click(timeout=3000)
                        await asyncio.sleep(0.4)
                        popover_visible = await self.page.locator(".bg-popover.absolute:visible").count()
                        if popover_visible == 0:
                            self._log(f"  ✓ environment = {value} (div span click)")
                            return True
                        await self.page.keyboard.press("Escape")
                        popover_visible = await self.page.locator(".bg-popover.absolute:visible").count()
                        if popover_visible == 0:
                            self._log(f"  ✓ environment = {value} (div span click+escape)")
                            return True
            except Exception:
                continue

        try:
            await env_input.click(timeout=2000)
            await asyncio.sleep(0.3)
            await env_input.fill(v, timeout=2000)
            await asyncio.sleep(0.3)
            await env_input.press("ArrowDown")
            await asyncio.sleep(0.2)
            await env_input.press("Enter")
            await asyncio.sleep(0.4)
            popover_visible = await self.page.locator(".bg-popover.absolute:visible").count()
            if popover_visible == 0:
                self._log(f"  ✓ environment = {value} (fill+ArrowDown+Enter)")
                return True
            await self.page.keyboard.press("Escape")
        except Exception:
            pass

        self._log(f"  ✗ environment = {value}: 未找到选项")
        try:
            await self.page.keyboard.press("Escape")
        except Exception:
            pass
        return False

    async def dump_form_elements(self) -> Path:
        """抓取页面上所有交互元素 + label 关联信息，保存到 JSON 文件。"""
        self._log("抓取页面表单元素（含 label 关联）...")
        await asyncio.sleep(1)

        form_info = await self.page.evaluate("""() => {
            const elements = [];

            // ── Scan visible text/"label" nodes in the form area ──
            // Walk the DOM to find label→control pairs
            function findLabelForControl(ctrl) {
                // Try <label for="id">
                if (ctrl.id) {
                    const lbl = document.querySelector('label[for="' + ctrl.id + '"]');
                    if (lbl) return lbl.textContent.trim();
                }
                // Look for parent <label>
                let p = ctrl.parentElement;
                for (let i = 0; i < 4 && p; i++) {
                    if (p.tagName === 'LABEL') return p.textContent.replace(ctrl.textContent||'', '').trim();
                    // Check previous sibling text
                    const prev = p.previousElementSibling;
                    if (prev && prev.textContent && prev.textContent.trim().length < 60) {
                        const txt = prev.textContent.trim();
                        if (!txt.startsWith('<') && txt.length < 60) return txt;
                    }
                    p = p.parentElement;
                }
                return '';
            }

            // All form controls
            const tags = ['input', 'select', 'textarea'];
            for (const tag of tags) {
                document.querySelectorAll(tag).forEach(el => {
                    const rect = el.getBoundingClientRect();
                    const label = findLabelForControl(el);
                    const hasCombobox = (el.className || '').includes('ring-offset-background');
                    elements.push({
                        tag: tag,
                        type: (hasCombobox && tag === 'input') ? 'combobox' : (el.type || ''),
                        id: el.id || '',
                        name: el.name || '',
                        placeholder: el.placeholder || '',
                        label: label.substring(0, 80),
                        dataField: el.getAttribute('data-field') || '',
                        ariaLabel: el.getAttribute('aria-label') || '',
                        className: (el.className || '').substring(0, 120),
                        value: (el.value || '').substring(0, 60),
                        options: (tag === 'select') ? Array.from(el.options).map(o => o.text).join('|').substring(0, 200) : '',
                        visible: rect.width > 0 && rect.height > 0,
                        bbox: {x: Math.round(rect.x), y: Math.round(rect.y),
                               w: Math.round(rect.width), h: Math.round(rect.height)},
                    });
                });
            }

            // Custom widgets
            document.querySelectorAll('[role="combobox"], [role="listbox"]').forEach(el => {
                const rect = el.getBoundingClientRect();
                elements.push({
                    tag: el.tagName.toLowerCase(),
                    type: 'custom-' + (el.getAttribute('role') || 'widget'),
                    id: el.id || '',
                    dataField: el.getAttribute('data-field') || '',
                    ariaLabel: el.getAttribute('aria-label') || '',
                    className: (el.className || '').substring(0, 120),
                    text: (el.textContent || '').trim().substring(0, 80),
                    visible: rect.width > 0 && rect.height > 0,
                });
            });

            return elements;
        }""")

        out_path = BASE_DIR / "diagnose_form.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(form_info, f, indent=2, ensure_ascii=False)

        # ── 打印摘要，按 y 排序 ──
        visible = [e for e in form_info if e.get("visible")]
        visible.sort(key=lambda e: (e.get("bbox", {}).get("y", 0), e.get("bbox", {}).get("x", 0)))
        self._log(f"共 {len(form_info)} 个元素（{len(visible)} 个可见），已保存到 diagnose_form.json")
        self._log(f"\\n{'─'*70}")
        self._log(f"{'y':>5} {'x':>4} {'tag+type':<22} label/ph/options")
        self._log(f"{'─'*70}")
        for el in visible:
            bb = el.get("bbox", {})
            y, x = bb.get("y", 0), bb.get("x", 0)
            tag_type = f"{el['tag']}[{el.get('type','')}]"
            # Build description
            desc_parts = []
            if el.get("label"): desc_parts.append(f"label='{el['label']}'")
            if el.get("placeholder"): desc_parts.append(f"ph='{el['placeholder']}'")
            if el.get("options"): desc_parts.append(f"opts={el['options']}")
            desc = " | ".join(desc_parts) if desc_parts else "(no info)"
            self._log(f"{y:>5} {x:>4} {tag_type:<22} {desc[:120]}")
        self._log(f"{'─'*70}")

        return out_path

    # ── 文件上传 ──

    async def _upload_hmd_folder_to_preview(self, folder_path: str) -> bool:
        """上传 HMD session 文件夹到页面 Preview 区域。

        页面的 Preview 区有隐藏的 webkitdirectory input，
        需要注入整个文件夹（.hmd 分片 + metadata.json），
        页面会自动在 OPFS 中流式转换为 MCAP。

        注入前需要确保接入模式 = 双目、来源 = HMD 分段，否则 webkitdirectory input
        对应的 upload 区可能不接受文件夹。
        """
        if not os.path.isdir(folder_path):
            self._log(f"✗ HMD 文件夹不存在: {folder_path}")
            return False

        # 收集文件夹内所有文件（含子目录）
        all_files: list[str] = []
        for root, dirs, files in os.walk(folder_path):
            for f in files:
                all_files.append(os.path.join(root, f))

        # 快速检查
        has_meta = any(os.path.basename(f) == "metadata.json" for f in all_files)
        hmd_files = [f for f in all_files if f.lower().endswith(".hmd")]
        if not has_meta:
            self._log(f"✗ 缺少 metadata.json")
            return False
        if not hmd_files:
            self._log(f"✗ 没有 .hmd 分片文件")
            return False

        # 计算总大小
        total_mb = sum(os.path.getsize(f) for f in all_files) / (1024 * 1024)
        self._log(f"HMD 文件夹: {len(hmd_files)} 个 .hmd 分片 + metadata.json ({total_mb:.0f} MB 共 {len(all_files)} 个文件)")

        # 步骤 1: 确保接入模式 = 双目（如果 captureMode 已在前面 fill 完，这里跳过）
        try:
            for sel in [
                "button:has-text('双目')",
                "button:has-text('Stereo')",
            ]:
                btn = self.page.locator(sel).first
                if await btn.count() > 0:
                    try:
                        is_active = await btn.evaluate(
                            "el => el.className.includes('bg-emerald') || el.className.includes('bg-emerald-600')"
                        )
                        if not is_active:
                            await btn.click(timeout=2000)
                            self._log(f"  ✓ 点击接入模式: {sel}")
                            await asyncio.sleep(0.8)
                        break
                    except Exception:
                        continue
        except Exception:
            pass

        # 步骤 2: 确保来源 = HMD 分段（页面有 4 个来源按钮）
        try:
            hmd_src_btn = self.page.locator("button:has-text('HMD 分段')").first
            if await hmd_src_btn.count() > 0:
                # 检查是否已激活
                is_active = await hmd_src_btn.evaluate(
                    "el => el.className.includes('bg-emerald') || el.className.includes('bg-emerald-600') || el.className.includes('active')"
                )
                if not is_active:
                    await hmd_src_btn.click(timeout=2000)
                    self._log(f"  ✓ 点击来源: HMD 分段")
                    await asyncio.sleep(0.8)
        except Exception as e:
            self._log(f"  ⚠ 点击 HMD 分段来源: {e}")

        # 步骤 3: 找到隐藏的 webkitdirectory input（页面有 2 个，都在 class="hidden" 里）
        webkit_input = self.page.locator("input[webkitdirectory]")
        cnt = await webkit_input.count()
        if cnt == 0:
            self._log("✗ 找不到 webkitdirectory input")
            return False

        # Playwright 的 set_input_files 不要求 input 可见。
        # 对 webkitdirectory input，必须传入目录路径（字符串），
        # Playwright 会自动扫描目录并构建 webkitRelativePath。
        try:
            await webkit_input.first.set_input_files(folder_path, timeout=60000)
            self._log(f"  ✓ 已注入 {len(all_files)} 个文件到 Preview（右侧选择区）")
        except Exception as e:
            self._log(f"  ✗ webkitdirectory set_input_files 失败: {e}")
            return False

        # 文件注入后，Preview 区会出现 "Pick Stereo for preview" / "选择 双目 来预览" 按钮，
        # 用于选择预览的捕获模式。点击可能触发原生文件选择对话框。
        await asyncio.sleep(1)
        try:
            preview_btn_selectors = [
                "button:has-text('Pick Stereo for preview')",
                "button:has-text('选择 双目 来预览')",
                "button:has-text('选择 单摄像头 来预览')",
            ]
            preview_stereo_btn = None
            for sel in preview_btn_selectors:
                btn = self.page.locator(sel).first
                if await btn.count() > 0:
                    preview_stereo_btn = btn
                    self._log(f"  找到 Preview 按钮: {sel}")
                    break
            if preview_stereo_btn is not None:
                # 预先设置文件选择器拦截（按钮点击可能弹出原生文件对话框）
                try:
                    async with self.page.expect_file_chooser(timeout=5000) as fc_info:
                        await preview_stereo_btn.click(timeout=5000)
                    chooser = await fc_info.value
                    # 传入 HMD 文件夹路径，让页面确定 stereo 轨道
                    await chooser.set_files(folder_path)
                    self._log("  ✓ 已点击 Preview 按钮并选择了 HMD 文件夹")
                except Exception:
                    # 没有弹出文件选择器：click 已执行，无需额外操作
                    self._log("  ✓ 已点击 Preview 按钮（无需文件选择）")
        except Exception as e:
            self._log(f"  ⚠ Preview 按钮处理异常: {e}")

        # 等待 "Upload to server" 按钮变为可用（MCAP 转换完成）
        self._log("  等待 MCAP 转换完成（本地预览 + 上传按钮就绪）...")
        upload_ready = False
        MAX_MCAP_WAIT = int(os.environ.get("MAX_MCAP_WAIT", "600"))
        for retry in range(MAX_MCAP_WAIT):
            try:
                # 多信号检测：
                # 1) 上传按钮 enabled
                # 2) 本地预览出现（hmd-player 元素 + "已在你的浏览器里解码" 文本）
                upload_btn_enabled = False
                upload_btn_text = None
                for btn_sel in [
                    "button:has-text('上传到服务器')",
                    "button:has-text('Upload to server')",
                ]:
                    btn = self.page.locator(btn_sel).first
                    if await btn.count() == 0:
                        continue
                    text = (await btn.inner_text()).strip()
                    if await btn.is_enabled():
                        upload_btn_enabled = True
                        upload_btn_text = text
                        break

                # 检查本地预览（hmd-player 元素）
                local_preview_state = await self.page.evaluate("""() => {
                    const player = document.querySelector('.hmd-player');
                    const decodedSpan = Array.from(document.querySelectorAll('span')).find(s =>
                        (s.innerText || '').includes('已在你的浏览器里解码')
                    );
                    const sessionInPreview = document.querySelector('.hmd-player-cameras');
                    return {
                        hasPlayer: !!player,
                        hasDecodedText: !!decodedSpan,
                        hasCameras: !!sessionInPreview,
                        decodedSession: decodedSpan ? decodedSpan.innerText.trim() : null,
                    };
                }""")

                if upload_btn_enabled:
                    upload_ready = True
                    self._log(f"  ✓ 上传按钮已就绪 (text={upload_btn_text!r}, 耗时约 {retry + 1}s)")
                    break

                # 调试日志：每 5 秒打印一次状态
                if retry % 5 == 0:
                    state_desc = []
                    if local_preview_state["hasPlayer"]:
                        state_desc.append("本地预览播放器已出现")
                    if local_preview_state["hasDecodedText"]:
                        state_desc.append(f"解码完成 ({local_preview_state['decodedSession']!r})")
                    if not state_desc:
                        state_desc.append("本地预览未出现")
                    self._log(f"  ...状态 ({retry + 1}s): {' | '.join(state_desc)}")
            except Exception as e:
                if retry % 30 == 0:
                    self._log(f"  等待异常: {e}")
            if retry % 15 == 14:
                self._log(f"  仍在等待 MCAP... ({retry + 1}s)")
            await asyncio.sleep(1)

        if not upload_ready:
            self._log(f"  ⚠ 超时：上传按钮未在 {MAX_MCAP_WAIT}s 内就绪")
            try:
                debug = await self.page.evaluate("""() => {
                    const btns = Array.from(document.querySelectorAll('button')).filter(b => {
                        const t = (b.innerText || '');
                        return t.includes('上传到服务器') || t.includes('Upload to server');
                    }).map(b => ({
                        text: b.innerText.trim().substring(0, 60),
                        disabled: b.disabled,
                        title: b.title || '',
                    }));
                    const player = document.querySelector('.hmd-player');
                    return { btns, hasPlayer: !!player };
                }""")
                self._log(f"  调试：{debug}")
            except Exception:
                pass

        return True

    async def upload_video_file(self, video_path: str) -> bool:
        """上传单个视频文件到页面上的文件选择区域。
        仅用于非-HMD 会话（普通 mp4 文件）。
        """
        if not os.path.isfile(video_path):
            self._log(f"✗ 文件不存在: {video_path}")
            return False

        self._log(f"选择文件: {os.path.basename(video_path)}")

        # 策略 1：直接 file input（排除 webkitdirectory，那是注入文件夹用的）
        try:
            file_input = self.page.locator(
                "input[type='file']:not([webkitdirectory])"
            )
            count = await file_input.count()
            if count > 0:
                await file_input.first.set_input_files(video_path, timeout=10000)
                self._log(f"  ✓ 文件已选择")
                return True
        except Exception as e:
            self._log(f"  file input 方式失败: {e}")

        # 策略 2：通过 file chooser（点击上传按钮触发）
        try:
            async with self.page.expect_file_chooser(timeout=10000) as fc_info:
                # 尝试点击上传触发按钮
                upload_trigger = self.page.locator(
                    "[data-testid='upload-trigger'], "
                    "button:has-text('Upload'), "
                    "[role='button']:has-text('Upload'), "
                    ".upload-btn, "
                    "#upload-btn"
                )
                if await upload_trigger.count() > 0:
                    await upload_trigger.first.click(timeout=5000)
                else:
                    # 尝试点击拖放区
                    dropzone = self.page.locator(
                        ".vtb-dropzone, "
                        "[class*='dropzone'], "
                        "[class*='drop-zone'], "
                        "[class*='upload-area']"
                    )
                    if await dropzone.count() > 0:
                        await dropzone.first.click(timeout=5000)
                    else:
                        raise Exception("找不到上传触发区域")

            file_chooser = await fc_info.value
            await file_chooser.set_files(video_path, timeout=10000)
            self._log(f"  ✓ 文件已选择 (via file chooser)")
            return True

        except Exception as e:
            self._log(f"  file chooser 方式失败: {e}")
            return False

    # ── 上传提交 & 等待完成 ──

    async def submit_and_wait(self, timeout: int = 3600) -> bool:
        """点击 'Upload to server' 按钮并等待上传完成。"""
        # 优先查找 "Upload to server" 按钮（MCAP 转换完成后出现）
        submit_selectors = [
            "button:has-text('Upload to server')",
                "button:has-text('上传到服务器')",
            "button:has-text('Upload')",
            "button:has-text('Submit')",
            "button[type='submit']",
            "[data-testid='submit-upload']",
            "#submit-upload",
        ]
        clicked = False
        for sel in submit_selectors:
            try:
                btn = self.page.locator(sel)
                if await btn.count() > 0 and await btn.first.is_enabled(timeout=2000):
                    await btn.first.click(timeout=5000)
                    self._log(f"✓ 已点击 'Upload to server' ({sel})")
                    clicked = True
                    break
            except Exception:
                continue

        if not clicked:
            self._log("⚠ 未找到提交按钮，可能已自动开始上传")
            try:
                await self.page.screenshot(path=str(BASE_DIR / "no_submit_btn.png"))
            except Exception:
                pass

        # 等待上传完成
        return await self._wait_for_completion(timeout)

    async def _handle_unauthorized_restart(self) -> bool:
        """检测到 Unauthorized 后，刷新页面 + 等待用户重新登录。

        返回 True 表示重新登录成功，False 表示超时失败。
        不重试当前任务（已经失败的 session 让它失败），后续任务重新走 start 流程。
        """
        self._log("  ⚠ Unauthorized 重启流程：刷新上传页面 → 检测登录态...")
        for retry in range(3):  # 最多重试 3 次
            try:
                await self.page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2)
            except Exception as e:
                self._log(f"  刷新失败: {e}")
                continue

            if not await self._check_login_required():
                self._log(f"  ✓ 重新登录成功（第 {retry + 1} 次尝试）")
                await self._wait_for_upload_form(timeout=30)
                return True

            self._log(f"  仍未登录，等待用户登录...（第 {retry + 1}/3 次）")

        self._log("  ✗ Unauthorized 重启失败：连续 3 次未登录成功")
        return False

    async def _wait_for_completion(self, timeout: int = 3600) -> bool:
        """轮询等待上传完成。

        检测策略（按优先级）：
        A. "In flight" / "上传中" 区块从 DOM 消失 → 视频出现在 Recent uploads 列表顶部
        B. 页面文本关键词匹配（兜底）
        C. 进度条消失 + inflight 消失（兜底）

        关键观察：上传完成后页面不会出现 "uploaded successfully" 等文字，
        而是 "In flight" 区块（含绿色脉冲圆点 + 进度条）被移除，
        视频条目出现在 "Recent uploads" 列表顶部。
        """
        self._log("等待上传完成（检测 inflight/上传中 区块消失）...")
        deadline = time.time() + timeout
        session_name = getattr(self, "current_session", "")
        inflight_gone = False

        # 等待至少 5 秒再开始检测（给上传请求一点时间）
        await asyncio.sleep(5)

        while time.time() < deadline:
            await asyncio.sleep(3)

            # ── 失败检测（优先，每轮都检查） ──
            try:
                page_text = await self.page.locator("body").inner_text(timeout=5000)
            except Exception:
                continue

            # ── Unauthorized 检测（登录过期）→ 自动重新登录 ──
            if "Unauthorized" in page_text or "未授权" in page_text or "登录已过期" in page_text:
                self._log("⚠ 检测到 Unauthorized 错误，尝试刷新页面重新登录...")
                # 标记当前 session 失败，跳过
                self._log(f"  ✗ {session_name} 因 Unauthorized 失败，跳过")
                # 重新登录（保留 inflight 状态无法恢复，跳过当前任务即可）
                await self._handle_unauthorized_restart()
                return False

            # ── 已上传过检测（重复文件）→ 自动标记 uploaded='Yes' 当作成功 ──
            if "已上传过" in page_text or "Already uploaded" in page_text:
                self._log(f"  ✓ {session_name} 已上传过（服务器端识别为重复）→ 自动标记为已上传")
                # 让调用方走 mark_uploaded 路径
                return True

            fail_keywords = [
                "upload failed", "error uploading", "something went wrong",
                "upload error", "failed to upload",
                "上传失败", "上传出错",
            ]
            if any(kw in page_text.lower() for kw in fail_keywords):
                self._log("✗ 上传失败（检测到错误信息）")
                try:
                    await self.page.screenshot(path=str(BASE_DIR / "upload_error.png"))
                except Exception:
                    pass
                return False

            # ── 策略 A：inflight 区块消失 → 检查 Recent uploads ──
            if not inflight_gone:
                # 检查 "In flight" / "上传中" 区块是否还在 DOM 中
                # 特征：含脉冲动画圆点 + "In flight" / "上传中" 文字
                inflight_present = False
                for anchor in ["In flight", "上传中"]:
                    ind = self.page.locator(f"text={anchor}").first
                    if await ind.count() > 0:
                        inflight_present = True
                        break
                if not inflight_present:
                    inflight_gone = True
                    self._log("  ✓ inflight/上传中 区块已消失，上传流程结束")
                    # 给 Recent uploads 列表一点渲染时间
                    await asyncio.sleep(2)

            if inflight_gone and session_name:
                # 确认 session 是否出现在 Recent uploads 列表中
                # Recent uploads 的 li 元素有 title 属性存放 session 名
                recent_session = self.page.locator(
                    f"[title='{session_name}']"
                ).first
                if await recent_session.count() > 0:
                    self._log(f"✓ 上传成功！（{session_name} 已进入 Recent uploads）")
                    return True
                # inflight 消失但 session 还没渲染出来 → 可能 React 还在更新列表
                self._log(f"  等待 {session_name} 出现在 Recent uploads...")
                continue

            if inflight_gone and not session_name:
                # session_name 未设置，直接用 inflight 消失作为成功标记
                self._log("✓ 上传成功！（inflight 区块消失）")
                return True

            # ── 策略 B：页面文本关键词匹配（兜底） ──
            success_keywords = [
                "uploaded successfully", "upload complete",
                "processing", "analysis queued",
                "scene analysis", "✓ uploaded",
                "上传成功", "上传完成",
            ]
            if any(kw in page_text.lower() for kw in success_keywords):
                self._log("✓ 上传成功！（文本关键词匹配）")
                return True

            # ── 策略 C：进度条消失 + inflight 消失（双重确认） ──
            if inflight_gone:
                progress = self.page.locator("[role='progressbar']")
                if await progress.count() == 0:
                    self._log("✓ 上传成功！（进度条 + inflight 均已消失）")
                    return True

            # ── 空页面检测 ──
            if not page_text.strip():
                self._log("  页面内容为空，可能正在处理中...")
                continue

        self._log("⚠ 上传等待超时")
        return False

    # ── 流水线批量上传：inflight 检测 & 并行编排 ──

    async def _get_inflight_sessions(self) -> list[str]:
        """获取当前页面上 inflight 区块中的 session 名称列表。

        中英文界面兼容：
        - 英文: "In flight" 区块
        - 中文: "上传中" 区块（带绿色脉冲圆点 + 进度条）
        """
        try:
            # 同时尝试英文 "In flight" 和中文 "上传中"
            sessions: list[str] = []
            for anchor_text in ["In flight", "上传中"]:
                # 找到含此文本的区块，再向上找父级包含 ul li [title]
                try:
                    container = self.page.locator(f"text={anchor_text}").first
                    if await container.count() == 0:
                        continue
                    # 向上找含 ul 的父级
                    parent = container.locator("xpath=ancestor::div[.//ul][1]")
                    if await parent.count() == 0:
                        continue
                    items = parent.locator("ul li [title]")
                    cnt = await items.count()
                    for i in range(cnt):
                        title = await items.nth(i).get_attribute("title")
                        if title and title.strip():
                            sessions.append(title.strip())
                except Exception:
                    continue
            # 去重，保持顺序
            return list(dict.fromkeys(sessions))
        except Exception:
            return []

    async def _get_inflight_count(self) -> int:
        """获取当前 inflight 上传数量。"""
        sessions = await self._get_inflight_sessions()
        if not sessions:
            # 备用：检查 "In flight" / "上传中" 文字是否存在
            try:
                for anchor in ["In flight", "上传中"]:
                    indicator = self.page.locator(f"text={anchor}").first
                    if await indicator.count() > 0:
                        return 1  # 有指示器但没拿到具体 session，保守返回 1
            except Exception:
                return 0
        return len(sessions)

    async def _confirm_inflight_entry(self, session_name: str, timeout: int = 30) -> bool:
        """等待指定 session 出现在 inflight 区块中（提交后确认）。

        点击 "Upload to server" 后，页面会短暂处理（~1-3s），
        然后 session 会出现在 inflight 区块。
        """
        self._log(f"  等待 {session_name} 进入 inflight...")
        deadline = time.time() + timeout
        while time.time() < deadline:
            inflight_sessions = await self._get_inflight_sessions()
            if session_name in inflight_sessions:
                self._log(f"  ✓ {session_name} 已进入 inflight")
                return True
            # 也检查是否已经完成了（极快的小文件）
            if await self._is_session_in_recent(session_name):
                self._log(f"  ✓ {session_name} 已完成（小文件，直接出现在 Recent uploads）")
                return True
            # 失败检测
            try:
                page_text = await self.page.locator("body").inner_text(timeout=3000)
                fail_keywords = ["upload failed", "error uploading", "something went wrong"]
                if any(kw in page_text.lower() for kw in fail_keywords):
                    self._log(f"  ✗ 检测到上传失败信息")
                    return False
            except Exception:
                pass
            await asyncio.sleep(2)
        self._log(f"  ⚠ 超时：{session_name} 未在 {timeout}s 内进入 inflight")
        return False

    async def _is_session_in_recent(self, session_name: str) -> bool:
        """检查 session 是否已出现在 Recent uploads 列表中。"""
        try:
            recent_session = self.page.locator(
                f"[title='{session_name}']"
            ).first
            return await recent_session.count() > 0
        except Exception:
            return False

    async def _submit_and_confirm_inflight(self, session_name: str, max_retries: int = 3) -> bool:
        """点击 'Upload to server' 并确认进入 inflight（不等待完成）。最多重试 max_retries 次。"""
        submit_selectors = [
            "button:has-text('Upload to server')",
                "button:has-text('上传到服务器')",
            "button:has-text('Upload')",
            "button:has-text('Submit')",
            "button[type='submit']",
            "[data-testid='submit-upload']",
            "#submit-upload",
        ]

        for attempt in range(1, max_retries + 1):
            if attempt > 1:
                self._log(f"  重试 {attempt}/{max_retries}，等待 3 秒...")
                await asyncio.sleep(3)

            clicked = False
            for sel in submit_selectors:
                try:
                    btn = self.page.locator(sel)
                    if await btn.count() > 0 and await btn.first.is_enabled(timeout=2000):
                        await btn.first.click(timeout=5000)
                        self._log(f"✓ 已点击 'Upload to server' ({sel})")
                        clicked = True
                        break
                except Exception:
                    continue

            if not clicked:
                self._log(f"⚠ 未找到提交按钮（尝试 {attempt}/{max_retries}），可能已自动开始上传")
                try:
                    await self.page.screenshot(path=str(BASE_DIR / f"no_submit_btn_{attempt}.png"))
                except Exception:
                    pass
                if attempt < max_retries:
                    continue
                return False

            # 等待进入 inflight（大 HMD 文件 OPFS 转换可能需较长时间）
            await asyncio.sleep(2)
            # inflight 超时也加长（默认 600s），通过环境变量可调
            inflight_timeout = int(os.environ.get("MAX_INFLIGHT_WAIT", "600"))
            confirmed = await self._confirm_inflight_entry(session_name, timeout=inflight_timeout)
            if confirmed:
                return True

            # 没确认进入inflight，重试
            self._log(f"⚠ 未确认进入 inflight（尝试 {attempt}/{max_retries}）")
            if attempt < max_retries:
                # 刷新页面状态，清除可能的错误状态
                try:
                    await self.page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=20000)
                    await asyncio.sleep(2)
                    await self._wait_for_upload_form(timeout=30)
                except Exception:
                    pass

        self._log(f"✗ 提交 {session_name} 失败，已重试 {max_retries} 次")
        return False

    async def _wait_for_batch_sessions(self, session_names: list[str],
                                        timeout: int = 7200) -> dict[str, bool]:
        """轮询等待一批 session 全部完成（inflight 消失 → Recent uploads 出现）。

        Returns: {session_name: True/False}  成功/失败映射。
        """
        pending = set(session_names)
        results: dict[str, bool] = {}
        deadline = time.time() + timeout
        self._log(f"\n等待 {len(pending)} 个 inflight session 完成: {pending}")
        last_pending_count = len(pending)
        absent_count: dict[str, int] = {n: 0 for n in pending}  # 记录每个session不在recent的次数
        inflight_since: dict[str, float] = {}  # 记录每个session首次出现在inflight的时间
        MAX_INFLIGHT_SEC = 600  # 单视频在 inflight 最大等待 10 分钟

        while pending and time.time() < deadline:
            # 不刷新页面，直接用 JS 获取最新状态（避免丢失 inflight）
            await asyncio.sleep(3)

            # 页面崩溃检测
            try:
                await self.page.locator("body").inner_text(timeout=3000)
            except Exception:
                self._log("  ⚠ 页面连接中断，尝试恢复...")
                await asyncio.sleep(2)
                try:
                    await self.page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=20000)
                    await asyncio.sleep(2)
                    self._log("  页面已恢复")
                except Exception:
                    self._log("  页面恢复失败，继续等待...")
                    await asyncio.sleep(5)
                continue

            # 失败检测
            try:
                page_text = await self.page.locator("body").inner_text(timeout=5000)
                fail_keywords = [
                    "upload failed", "error uploading", "something went wrong",
                    "upload error", "failed to upload",
                ]
                if any(kw in page_text.lower() for kw in fail_keywords):
                    self._log("⚠ 检测到上传失败信息，标记剩余 pending 为失败")
                    for name in list(pending):
                        results[name] = False
                    pending.clear()
                    break
                # ── Unauthorized 检测（登录过期）→ 自动重新登录 + 标记失败当前 pending ──
                if "Unauthorized" in page_text or "未授权" in page_text or "登录已过期" in page_text:
                    self._log("⚠ 检测到 Unauthorized → 自动重新登录")
                    for name in list(pending):
                        results[name] = False
                        self._log(f"  ✗ {name} 因 Unauthorized 失败")
                    pending.clear()
                    await self._handle_unauthorized_restart()
                    break
                # ── 已上传过检测（重复文件）→ 当作成功标记 ──
                if "已上传过" in page_text or "Already uploaded" in page_text:
                    self._log("  ✓ 检测到'已上传过'，当作成功处理")
                    for name in list(pending):
                        results[name] = True
                        self._log(f"  ✓ {name} 已上传过（标记成功）")
                    pending.clear()
                    break
            except Exception:
                pass

            # 获取当前 inflight session 列表
            try:
                inflight_sessions = await self._get_inflight_sessions()
                inflight_set = set(inflight_sessions)
            except Exception:
                inflight_set = set()

            # 检查每个 pending session
            for name in list(pending):
                if name in inflight_set:
                    # 还在 inflight 中 → 记录首次出现时间，检查超时
                    if name not in inflight_since:
                        inflight_since[name] = time.time()
                    elif time.time() - inflight_since[name] > MAX_INFLIGHT_SEC:
                        self._log(f"  ⚠ {name} 在 inflight 中超过 {MAX_INFLIGHT_SEC}s，强制标记失败")
                        results[name] = False
                        pending.discard(name)
                        continue
                else:
                    # session 已不在 inflight → 清除 inflight_since，检查是否在 Recent uploads
                    inflight_since.pop(name, None)
                    try:
                        if await self._is_session_in_recent(name):
                            self._log(f"  ✓ {name} 已完成（进入 Recent uploads）")
                            results[name] = True
                            pending.discard(name)
                            continue
                    except Exception:
                        pass
                    # 不在 inflight 也不在 recent → 累计次数
                    absent_count[name] = absent_count.get(name, 0) + 1
                    if absent_count[name] >= 4:
                        # 连续4轮（12秒）不在 recent 才判定失败（给大文件足够时间）
                        self._log(f"  ⚠ {name} 连续{absent_count[name]}轮未出现，标记为失败")
                        results[name] = False
                        pending.discard(name)

            if pending:
                # 显示当前 inflight 状态
                try:
                    inflight_now = await self._get_inflight_sessions()
                    current_inflight = [s for s in inflight_now if s in pending]
                    if len(pending) != last_pending_count:
                        self._log(f"  剩余 {len(pending)} 个 inflight: {current_inflight}")
                        last_pending_count = len(pending)
                except Exception:
                    pass
                await asyncio.sleep(5)

        # 超时处理
        if pending:
            self._log(f"⚠ 以下 session 等待超时: {pending}")
            # 最后再检查一次 Recent uploads
            for name in list(pending):
                if await self._is_session_in_recent(name):
                    results[name] = True
                    pending.discard(name)
                else:
                    results[name] = False
                    pending.discard(name)
                    self._log(f"  ✗ {name} 超时未完成")

        return results

    async def upload_batch_pipelined(self, video_tasks: list,
                                      max_concurrent: int = 1,
                                      delete_local: bool = False,
                                      keep_thumbs: bool = False) -> tuple[int, int, dict]:
        """流水线批量上传：当一个视频进入 inflight 后立即开始下一个。

        video_tasks: [(idx, video_path, template, hmd_folder, row), ...]
        max_concurrent: 最大并行 inflight 数（FrameForge服务端仅支持1个）

        Returns: (success_count, fail_count, session_results)
        """
        total = len(video_tasks)
        if total == 0:
            return 0, 0, {}

        self._log(f"\n{'=' * 50}")
        self._log(f"流水线批量上传: {total} 个视频，最大并行 {max_concurrent}")
        self._log(f"{'=' * 50}")

        pending = list(video_tasks)  # 待提交队列（浅拷贝）
        active: list[dict] = []  # 已提交但未完成的 [{session, idx, video_path, hmd_folder, row}]
        session_results: dict[str, bool] = {}  # session → success
        success_count = 0
        fail_count = 0
        state = load_state()
        next_task_num = 1

        while pending or active:
            # 预准备任务（跨循环保持）
            prep_task_data: tuple | None = None
            prep_task_obj: asyncio.Task | None = None

            # ── 阶段 1：提交下一个视频 ──
            fast_path_taken = False  # 仅本轮循环内使用，不重新赋值prep_task_data
            self._log(f"  [提交阶段] pending={len(pending)} active={len(active)} max={max_concurrent}")
            while pending and len(active) < max_concurrent:
                # 检查是否有已经预准备好的视频（表单+HMD已就绪，MCAP已完成）
                # 如果有，直接提交而不再填表/注HMD/等MCAP
                if (prep_task_data is not None
                        and prep_task_data[1].done()
                        and prep_task_data[1].result()):
                    task, _ = prep_task_data
                    idx, video_path, template, hmd_folder, row = task
                    check_session = os.path.basename(hmd_folder.rstrip("\\/")) if hmd_folder else os.path.basename(video_path)
                    if any(a["session"] == check_session for a in active):
                        self._log(f"  ⚠ {check_session} 已在inflight，跳过（fast path）")
                        pending.pop(0)
                        self._log(f"  [POP] 快速通道跳过重复后 pop后 pending={len(pending)}")
                        prep_task_data = None
                        continue
                    pending.pop(0)  # 从pending移除
                    self._log(f"  [POP] 快速通道 pop后 pending={len(pending)}")
                    is_first = (next_task_num == 1)
                    self._log(f"\n{'─' * 40}")
                    self._log(f"[流水线 {next_task_num}/{total}] 提交(预准备快速通道): {os.path.basename(video_path)}")
                    next_task_num += 1
                    session_name = await self._submit_prepared_video(video_path, template, hmd_folder, is_first)
                    fast_path_taken = True
                    prep_task_data = None  # 清空，避免下个循环误用
                else:
                    # 没有预准备或MCAP未就绪，走标准完整流程
                    task = pending[0]
                    idx, video_path, template, hmd_folder, row = task
                    check_session = os.path.basename(hmd_folder.rstrip("\\/")) if hmd_folder else os.path.basename(video_path)
                    if any(a["session"] == check_session for a in active):
                        self._log(f"  ⚠ {check_session} 已在inflight，跳过")
                        pending.pop(0)
                        self._log(f"  [POP] 跳过重复后 pop后 pending={len(pending)}")
                        continue
                    task = pending.pop(0)
                    self._log(f"  [POP] 标准流程 pop后 pending={len(pending)}")

                    is_first = (next_task_num == 1)
                    self._log(f"\n{'─' * 40}")
                    self._log(f"[流水线 {next_task_num}/{total}] 提交: {os.path.basename(video_path)}")
                    next_task_num += 1

                    session_name = await self._upload_one_pipeline_submit(
                        video_path, template, hmd_folder, first_submit=is_first,
                        no_submit=getattr(args, "no_submit", False),
                    )

                if session_name:
                    if any(a["session"] == session_name for a in active):
                        self._log(f"  ⚠ {session_name} 已存在于active，跳过重复添加")
                    else:
                        active.append({
                            "session": session_name,
                            "idx": idx,
                            "video_path": video_path,
                            "hmd_folder": hmd_folder,
                            "row": row,
                            "flight_start": time.time(),
                        })
                    self._log(f"  → {session_name} 已进入 inflight（当前活跃: {len(active)}）")
                else:
                    self._log(f"  ✗ 提交失败: {os.path.basename(video_path)}")
                    fail_count += 1
                    if idx >= 0:
                        state.setdefault("failed", []).append(video_path.replace("\\", "/"))
                        save_state(state)

            # ── 阶段 2：等待活跃 session 完成，期间准备下一个视频 ──
            if not active:
                break  # 所有任务都已处理完

            # 预先在后台准备下一个视频的表单和HMD（不阻塞）
            # 这样当inflight腾出空位时，下一个视频的MCAP可能已经就绪
            # 注意：不重新赋值 prep_task_data，保持跨迭代持久化
            # 严格控制：只有 active < max_concurrent 时才启动后台预准备
            if pending and prep_task_data is None and len(active) < max_concurrent:
                task = pending[0]
                idx, vp, tmpl, hmd_f, row = task
                self._log(f"\n  [后台预准备] {os.path.basename(vp)} 的表单和HMD...")
                # 在后台运行整个准备+等待MCAP流程
                prep_task_obj = asyncio.create_task(
                    self._prepare_video_no_submit(vp, tmpl, hmd_f)
                )
                prep_task_data = (task, prep_task_obj)

            # 等待循环
            wait_iterations = 0
            absent_count: dict[str, int] = {}  # session → 连续不在recent的次数

            while active:
                # 1. 检查页面是否存活
                try:
                    await self.page.locator("body").inner_text(timeout=2000)
                except Exception:
                    self._log("  ⚠ 页面连接中断，尝试恢复...")
                    try:
                        await asyncio.sleep(2)
                        await self.page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=20000)
                        await asyncio.sleep(2)
                        self._log("  页面已恢复")
                    except Exception:
                        self._log("  页面恢复失败，继续等待...")
                        await asyncio.sleep(5)
                        continue

                # 2. 获取当前 inflight 状态
                inflight_ok = True
                try:
                    inflight_sessions = await self._get_inflight_sessions()
                    inflight_set = set(inflight_sessions)
                except Exception:
                    inflight_set = set()
                    inflight_ok = False

                # 3. 检查每个 active session 的完成情况（仅在 inflight 查询成功时才判定）
                MAX_INFLIGHT_SEC = 600  # 单个视频在 inflight 的最大等待时间（10分钟）
                if inflight_ok:
                    for a in list(active):
                        name = a["session"]
                        # 超时检测：在 inflight 中停留过久 → 强制标记失败
                        flight_elapsed = time.time() - a.get("flight_start", time.time())
                        if name in inflight_set and flight_elapsed > MAX_INFLIGHT_SEC:
                            self._log(f"  ⚠ {name} 在 inflight 中超过 {MAX_INFLIGHT_SEC}s（{flight_elapsed:.0f}s），强制标记失败")
                            session_results[name] = False
                            fail_count += 1
                            state.setdefault("failed", []).append(a["video_path"].replace("\\", "/"))
                            save_state(state)
                            active.remove(a)
                            absent_count.pop(name, None)
                            continue
                        if name not in inflight_set:
                            # session 已离开 inflight
                            try:
                                if await self._is_session_in_recent(name):
                                    self._log(f"  ✓ {name} 上传成功！（进入 Recent uploads）")
                                    session_results[name] = True
                                    success_count += 1
                                    if a["idx"] >= 0:
                                        mark_uploaded(a["idx"])
                                    if delete_local:
                                        delete_local_files(a["hmd_folder"] if a["hmd_folder"] else a["video_path"], self.log_path, keep_thumbs)
                                    state.setdefault("uploaded", []).append(a["video_path"].replace("\\", "/"))
                                    save_state(state)
                                    active.remove(a)
                                    absent_count.pop(name, None)
                                    continue
                            except Exception:
                                pass
                            # 不在 inflight 也不在 recent → 累计
                            absent_count[name] = absent_count.get(name, 0) + 1
                            if absent_count[name] >= 3:
                                self._log(f"  ⚠ {name} 连续{absent_count[name]}轮未出现在Recent，标记失败")
                                session_results[name] = False
                                fail_count += 1
                                state.setdefault("failed", []).append(a["video_path"].replace("\\", "/"))
                                save_state(state)
                                active.remove(a)
                                absent_count.pop(name, None)
                            else:
                                self._log(f"  ⚠ {name} 已离开inflight但未在Recent（{absent_count[name]}/3）")

                if not active:
                    break

                # 4. 如果还有 slot 空出（active 减少到 < max_concurrent）且有待提交流，
                #    退出等待回到阶段1，让快速通道被检测到
                if pending and len(active) < max_concurrent:
                    break

                # 4b. 如果后台预准备已完成且 MCAP 就绪，退出等待（立即提交prepared视频）
                if prep_task_obj and prep_task_obj.done():
                    mcap_ok = prep_task_obj.result()
                    if mcap_ok:
                        self._log(f"  [后台预准备] MCAP已就绪，退出等待准备提交")
                        break  # 退出wait loop → 进入快速通道提交
                    else:
                        self._log(f"  [后台预准备] MCAP失败，清除并继续等待")
                        prep_task_data = None
                        prep_task_obj = None

                # 5. 显示当前状态（每30秒）
                if wait_iterations % 6 == 0:
                    current_names = []
                    for a in active:
                        elapsed = time.time() - a.get("flight_start", time.time())
                        current_names.append(f"{a['session']}({elapsed:.0f}s)")
                    self._log(f"  当前 inflight: {current_names}，待提交: {len(pending)}")

                wait_iterations += 1
                if prep_task_obj and prep_task_obj.done() and prep_task_obj.result():
                    continue  # 立即回到循环开头检测 if not active
                await asyncio.sleep(5)

            # ── 等待结束后（active 已空），立即检查快速通道 ──
            # 此时 active 必定为空（只有此时才 break），可直接提交 prepared 视频
            if (prep_task_data is not None
                    and prep_task_data[1].done()
                    and prep_task_data[1].result()):
                task, _ = prep_task_data
                idx, vp, tmpl, hmd_f, row = task
                check_session = os.path.basename(hmd_f.rstrip("\\/")) if hmd_f else os.path.basename(vp)
                if any(a["session"] == check_session for a in active):
                    self._log(f"  ⚠ {check_session} 已在inflight，等待结束后跳过（快速通道）")
                    pending.pop(0)
                    self._log(f"  [POP] 等待后快速通道跳过重复 pop后 pending={len(pending)}")
                    prep_task_data = None
                else:
                    pending.pop(0)
                    self._log(f"  [POP] 等待后快速通道 pop后 pending={len(pending)}")
                    is_first = (next_task_num == 1)
                    self._log(f"\n{'─' * 40}")
                    self._log(f"[流水线 {next_task_num}/{total}] 提交(快速通道): {os.path.basename(vp)}")
                    next_task_num += 1
                    session_name = await self._submit_prepared_video(vp, tmpl, hmd_f, is_first)
                    if session_name:
                        if any(a["session"] == session_name for a in active):
                            self._log(f"  ⚠ {session_name} 已存在active，跳过")
                        else:
                            active.append({
                                "session": session_name,
                                "idx": idx,
                                "video_path": vp,
                                "hmd_folder": hmd_f,
                                "row": row,
                                "flight_start": time.time(),
                            })
                        self._log(f"  → {session_name} 已进入 inflight（当前活跃: {len(active)}）")
                        # 清除 prep_task_data，开始为下下一个视频预准备
                        prep_task_data = None
                        prep_task_obj = None
                        # 注意：不等 wait，直接回到外层循环 → 阶段2 → 开始下一个后台预准备
                        continue  # 回到外层 while pending or active
                    else:
                        # 提交失败，清除并走标准流程
                        self._log(f"  ⚠ 快速通道提交失败")
                        prep_task_data = None
                        prep_task_obj = None

            # 阶段3：没有待提交流了，等待所有剩余 active 完成
            if not pending and active:
                self._log(f"  等待最后 {len(active)} 个 session 完成...")
                remaining_names = [a["session"] for a in active]
                remaining_results = await self._wait_for_batch_sessions(remaining_names)
                for name, ok in remaining_results.items():
                    session_results[name] = ok
                    for a in list(active):
                        if a["session"] == name:
                            if ok:
                                success_count += 1
                                if a["idx"] >= 0:
                                    mark_uploaded(a["idx"])
                                if delete_local:
                                    delete_local_files(a["hmd_folder"] if a["hmd_folder"] else a["video_path"], self.log_path, keep_thumbs)
                                state.setdefault("uploaded", []).append(a["video_path"].replace("\\", "/"))
                            else:
                                fail_count += 1
                                state.setdefault("failed", []).append(a["video_path"].replace("\\", "/"))
                            save_state(state)
                            active.remove(a)
                            break
                active.clear()

        return success_count, fail_count, session_results

    async def _upload_batch_on_page(self, page, video_tasks: list,
                                     page_name: str = "Page",
                                     delete_local: bool = False,
                                     keep_thumbs: bool = False) -> tuple[int, int, dict]:
        """在指定页面上顺序上传视频（安静等待，不预准备下一个）。

        video_tasks: [(idx, video_path, template, hmd_folder, row), ...]
        每次只上传一个，等待其进入infight后，再等待其完成，然后提交下一个。
        Returns: (success_count, fail_count, session_results)
        """
        total = len(video_tasks)
        if total == 0:
            return 0, 0, {}

        self._log(f"\n{'=' * 50}")
        self._log(f"[{page_name}] 开始上传: {total} 个视频")
        self._log(f"{'=' * 50}")

        success_count = 0
        fail_count = 0
        session_results: dict[str, bool] = {}
        state = load_state()

        for task_num, (idx, video_path, template, hmd_folder, row) in enumerate(video_tasks, 1):
            is_first = (task_num == 1)
            self._log(f"\n{'─' * 40}")
            self._log(f"[{page_name}] [{task_num}/{total}] {os.path.basename(video_path)}")

            async def _submit():
                return await self._with_page(page, self._upload_one_pipeline_submit(
                    video_path, template, hmd_folder, first_submit=is_first,
                    no_submit=getattr(args, "no_submit", False),
                ))

            session_name = await _submit()

            if session_name:
                self._log(f"  → {session_name} 已进入 inflight")

                # 等待这个 session 完成（安静等待，不做任何其他事）
                done = False
                absent_count = 0
                while not done:
                    await asyncio.sleep(5)
                    try:
                        inflight_sessions = await self._with_page(page, self._get_inflight_sessions())
                        if session_name not in inflight_sessions:
                            absent_count += 1
                            # 检查是否在 Recent uploads
                            if await self._with_page(page, self._is_session_in_recent(session_name)):
                                self._log(f"  ✓ {session_name} 上传成功")
                                session_results[session_name] = True
                                success_count += 1
                                if idx >= 0:
                                    mark_uploaded(idx)
                                if delete_local:
                                    delete_local_files(hmd_folder if hmd_folder else video_path, self.log_path, keep_thumbs)
                                state.setdefault("uploaded", []).append(video_path.replace("\\", "/"))
                                save_state(state)
                                done = True
                            elif absent_count >= 3:
                                self._log(f"  ⚠ {session_name} 连续{absent_count}轮不在Recent，标记失败")
                                session_results[session_name] = False
                                fail_count += 1
                                state.setdefault("failed", []).append(video_path.replace("\\", "/"))
                                save_state(state)
                                done = True
                            else:
                                self._log(f"  ⚠ {session_name} 已离开inflight但未在Recent（{absent_count}/3）")
                        else:
                            absent_count = 0
                    except Exception as e:
                        self._log(f"  ⚠ 检查状态异常: {e}")
                        await asyncio.sleep(5)
            else:
                self._log(f"  ✗ {os.path.basename(video_path)} 提交失败")
                fail_count += 1
                state.setdefault("failed", []).append(video_path.replace("\\", "/"))
                save_state(state)

        self._log(f"\n[{page_name}] 完成: {success_count} 成功, {fail_count} 失败")
        return success_count, fail_count, session_results

    async def _upload_one_pipeline_submit(self, video_path: str, template: dict,
                                           hmd_folder: str | None = None,
                                           first_submit: bool = False,
                                           no_submit: bool = False) -> str | None:
        """upload_one 的流水线变种：填表 + 上传文件 + 点击提交，确认 inflight 后立即返回 session 名。

        first_submit=True 时会刷新页面建立初始状态，之后不再刷新页面以保留 inflight 状态。
        no_submit=True 时只填表+注入文件，不点击提交，浏览器保持打开供检查。
        Returns: session_name 成功提交，None 提交失败。
        """
        video_name = os.path.basename(video_path)
        if hmd_folder:
            session_name = os.path.basename(hmd_folder.rstrip("\\/"))
        else:
            session_name = video_name
        self.current_session = session_name

        self._log(f"  提交: {video_name}  (session: {session_name})")

        if first_submit:
            # 仅首次提交刷新页面，建立初始状态
            self._log("  刷新上传页面...")
            try:
                await self.page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=30000)
            except Exception:
                pass
            await asyncio.sleep(2)
            await self._wait_for_upload_form(timeout=30)

            if await self._check_login_required():
                self._log("  ⚠ 掉线，等待重新登录...")
                logged_in = await self._wait_for_login()
                if not logged_in:
                    return None
                await self.page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2)
                await self._wait_for_upload_form(timeout=30)
        else:
            # 非首次提交：不清空页面，清空表单字段，保留 inflight 状态
            await self._clear_form()

        # 1) 填写表单
        filled, total = await self.fill_all_fields(template)
        self._log(f"  已填: {filled}/{total} 个字段")

        # 1.5) 验证: 从 DOM 实际查询每个字段有没有值, 不只是 fill_field() 返回 True
        verify_report = await self.verify_all_filled(template)
        unfilled_keys = [k for k, v in verify_report.items() if not v["ok"]]
        if unfilled_keys:
            self._log(f"  ⚠ 校验发现 {len(unfilled_keys)} 个字段实际未填: {unfilled_keys}")
            for k in unfilled_keys:
                v = verify_report[k]
                self._log(f"      - {k}: 期望={v['expected'][:40]!r} 实际={v['actual'][:40]!r}")
            # 1.6) 重试一轮
            self._log(f"  🔄 重试 {len(unfilled_keys)} 个字段...")
            still_empty = await self._retry_unfilled(template, unfilled_keys)
            if still_empty:
                self._log(f"  ✗ 重试后仍 {len(still_empty)} 个字段未填: {still_empty}")
                self._log(f"  ⚠ 继续上传, 但下面这些字段可能不完整")
            else:
                self._log(f"  ✓ 重试后全部填好 ✓")

        # 2) 上传文件
        if hmd_folder:
            if not await self._upload_hmd_folder_to_preview(hmd_folder):
                self._log("  ✗ HMD 文件夹注入失败")
                return None
        else:
            if not await self.upload_video_file(video_path):
                self._log("  ✗ 文件选择失败")
                return None

        # 2.5) 注入文件后再校验一次 (页面有 file 状态变化, 一些 invalid 字段会被触发)
        post_inject_report = await self.verify_all_filled(template)
        post_unfilled = [k for k, v in post_inject_report.items() if not v["ok"]]
        if post_unfilled:
            # 有可能在注入文件后几个字段被清掉, 但 MCAP 转换需要时间, 暂记一下不阻断
            self._log(f"  (注: 注入文件后 {len(post_unfilled)} 个字段空: {post_unfilled}, 可能 MCAP 期间会被 page 重置)")

        # 3) 如果有未填字段，短暂等待
        if filled < total:
            self._log(f"  ⚠ 仍有 {total - filled} 个字段未填写，等待 5 秒...")
            await asyncio.sleep(5)

        # 3.5) no_submit 模式：只填表+注入文件，不点击提交，浏览器保持打开
        if no_submit:
            self._log("\n" + "=" * 50)
            self._log(f"⏸  no-submit 模式：表单已填写，文件已注入 Preview（session={session_name}）")
            self._log("   浏览器保持打开，请检查页面后手动关闭窗口")
            self._log("=" * 50)
            try:
                while self.context.pages:
                    await asyncio.sleep(2)
            except Exception:
                pass
            return None  # 不算提交成功

        # 4) 提交并确认 inflight
        if not await self._submit_and_confirm_inflight(session_name):
            self._log(f"  ✗ 提交确认失败")
            return None

        return session_name

    async def _prepare_video_no_submit(self, video_path: str, template: dict,
                                        hmd_folder: str | None = None) -> bool:
        """准备视频（填表+注入HMD），等待MCAP就绪，但不点击提交。

        用于流水线中：在当前视频inflight期间，准备好下一个视频的表单和HMD。
        Returns: True 表示MCAP转换完成（Upload to server按钮可点击），False 失败。
        """
        video_name = os.path.basename(video_path)

        # 清空表单
        await self._clear_form()

        # 填写表单
        filled, total = await self.fill_all_fields(template)
        self._log(f"  准备: 已填 {filled}/{total} 个字段")

        # 验证 + 重试
        verify = await self.verify_all_filled(template)
        unfilled = [k for k, v in verify.items() if not v["ok"]]
        if unfilled:
            self._log(f"  ⚠ 校验发现 {len(unfilled)} 个字段实际未填: {unfilled}")
            await self._retry_unfilled(template, unfilled)

        # 注入文件
        if hmd_folder:
            if not await self._upload_hmd_folder_to_preview(hmd_folder):
                self._log(f"  ✗ HMD 文件夹注入失败")
                return False
        else:
            if not await self.upload_video_file(video_path):
                self._log(f"  ✗ 文件选择失败")
                return False

        # 等待 Upload to server 按钮就绪
        self._log(f"  等待 MCAP 转换完成...")
        upload_btn_ready = False
        upload_btn_sels = [
            "button:has-text('Upload to server')",
                "button:has-text('上传到服务器')",
            "button:has-text('Upload')",
        ]
        deadline = time.time() + 300  # 最多等5分钟MCAP
        while time.time() < deadline:
            for sel in upload_btn_sels:
                try:
                    btn = self.page.locator(sel)
                    if await btn.count() > 0:
                        if await btn.first.is_enabled(timeout=2000):
                            self._log(f"  ✓ MCAP转换完成，Upload to server 按钮已就绪")
                            upload_btn_ready = True
                            break
                except Exception:
                    pass
            if upload_btn_ready:
                break
            await asyncio.sleep(2)

        if not upload_btn_ready:
            self._log(f"  ⚠ MCAP转换等待超时，继续尝试提交")
        return True

    async def _submit_prepared_video(self, video_path: str, template: dict,
                                      hmd_folder: str | None = None,
                                      first_submit: bool = False) -> str | None:
        """提交已预准备好的视频（表单+HMD已注入，MCAP已完成）。

        仅点击 Upload to server 按钮，确认 inflight 后返回 session 名。
        用于流水线优化：避免重复填表/注HMD/等MCAP。
        """
        video_name = os.path.basename(video_path)
        if hmd_folder:
            session_name = os.path.basename(hmd_folder.rstrip("\\/"))
        else:
            session_name = video_name
        self.current_session = session_name

        self._log(f"  快速提交: {video_name}  (session: {session_name})")

        if first_submit:
            self._log("  刷新上传页面...")
            try:
                await self.page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=30000)
            except Exception:
                pass
            await asyncio.sleep(2)
            await self._wait_for_upload_form(timeout=30)
            if await self._check_login_required():
                self._log("  ⚠ 掉线，等待重新登录...")
                logged_in = await self._wait_for_login()
                if not logged_in:
                    return None
                await self.page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2)
                await self._wait_for_upload_form(timeout=30)

        # 确认 Upload to server 按钮就绪
        upload_btn_sels = [
            "button:has-text('Upload to server')",
                "button:has-text('上传到服务器')",
            "button:has-text('Upload')",
        ]
        btn_ready = False
        for sel in upload_btn_sels:
            try:
                btn = self.page.locator(sel)
                if await btn.count() > 0 and await btn.first.is_enabled(timeout=3000):
                    btn_ready = True
                    break
            except Exception:
                pass

        if not btn_ready:
            self._log(f"  ✗ Upload to server 按钮不可点击")
            return None

        # 提交并确认 inflight
        if not await self._submit_and_confirm_inflight(session_name):
            self._log(f"  ✗ 提交确认失败")
            return None

        return session_name



    async def upload_one(self, video_path: str, template: dict,
                         dump_form: bool = False, no_submit: bool = False,
                         hmd_folder: str | None = None) -> bool:
        """上传单个视频的完整流程。
        dump_form: 抓取表单元素到 diagnose_form.json
        no_submit: 只填写不提交，完成后保持浏览器打开
        hmd_folder: HMD 原始会话文件夹路径（含 .hmd 分片 + metadata.json），
                    用于注入到页面 Preview 区
        Returns: True 表示成功。
        """
        video_name = os.path.basename(video_path)
        # 记录 session 名用于上传完成检测
        # HMD: 从原始文件夹名提取（如 "4aa45c_session_00000"）
        # 普通视频: 使用文件名
        if hmd_folder:
            self.current_session = os.path.basename(hmd_folder.rstrip("\\/"))
        else:
            self.current_session = video_name
        self._log(f"\n{'=' * 50}")
        self._log(f"开始上传: {video_name}")
        self._log(f"  session: {self.current_session}")
        self._log(f"{'=' * 50}")

        # 0) 刷新页面，确保干净状态
        self._log("刷新上传页面...")
        try:
            await self.page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=30000)
        except Exception:
            pass
        await asyncio.sleep(2)  # let React/Next.js hydrate
        await self._wait_for_upload_form(timeout=30)

        # 再次检查登录状态
        if await self._check_login_required():
            self._log("⚠ 在上传过程中掉线！需要重新登录。")
            logged_in = await self._wait_for_login()
            if not logged_in:
                self._log("✗ 登录失败，放弃当前视频")
                return False
            await self.page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)
            await self._wait_for_upload_form(timeout=30)

        # 打印模板数据（按 FILL_ORDER 排序）
        self._log("\n上传模板数据:")
        order_index = {k: i for i, k in enumerate(FILL_ORDER)}
        sorted_items = sorted(
            [(k, v) for k, v in template.items() if v],
            key=lambda kv: order_index.get(kv[0], 999),
        )
        for k, v in sorted_items:
            self._log(f"  {k}: {str(v)[:100]}")

        # dump: 抓取页面元素结构
        if dump_form:
            await self.dump_form_elements()

        # 1) 填写表单字段
        self._log("\n填写上传表单...")
        filled, total = await self.fill_all_fields(template)
        self._log(f"  已填: {filled}/{total} 个字段")

        # 验证 + 重试
        verify = await self.verify_all_filled(template)
        unfilled = [k for k, v in verify.items() if not v["ok"]]
        if unfilled:
            self._log(f"  ⚠ 校验发现 {len(unfilled)} 个字段实际未填: {unfilled}")
            await self._retry_unfilled(template, unfilled)

        # no_submit mode: upload files (folder for HMD, single file otherwise), then stop
        if no_submit:
            self._log("\n" + "-" * 40)
            self._log("no-submit 模式：上传文件到 Preview...")

            # HMD session → 注入文件夹到 Preview 的 webkitdirectory input
            # 普通视频 → 使用 upload_video_file 单文件上传
            file_ok = False
            if hmd_folder:
                file_ok = await self._upload_hmd_folder_to_preview(hmd_folder)
            else:
                file_ok = await self.upload_video_file(video_path)

            if not file_ok:
                self._log("✗ 文件选择失败")
                return False

            # 等待 "Upload to server" 按钮变为可点击
            # HMD 文件夹注入后页面需要时间做 OPFS 转换（左侧"本地预览"区显示进度）
            self._log("等待 'Upload to server' 按钮变为可点击（左侧本地预览做 MCAP 转换）...")
            upload_btn_ready = False
            upload_btn_sels = [
                "button:has-text('Upload to server')",
                "button:has-text('上传到服务器')",
                "button:has-text('Upload')",
                "[data-testid='upload-server-btn']",
                "[class*='upload-server']",
                "button[type='submit']",
            ]
            MAX_NO_SUBMIT_WAIT = int(os.environ.get("MAX_NO_SUBMIT_WAIT", "600"))
            for _ in range(MAX_NO_SUBMIT_WAIT):  # HMD 转换可能较慢，最多等 600 秒
                for sel in upload_btn_sels:
                    try:
                        btn = self.page.locator(sel)
                        if await btn.count() > 0:
                            if await btn.first.is_enabled(timeout=1000):
                                self._log(f"  ✓ 'Upload to server' 已可点击 ({sel})")
                                upload_btn_ready = True
                                break
                    except Exception:
                        continue
                if upload_btn_ready:
                    break
                await asyncio.sleep(1)

            self._log("\n" + "=" * 50)
            self._log("⏸  no-submit 模式：表单已填写，文件已注入 Preview")
            if upload_btn_ready:
                self._log("   'Upload to server' 按钮已就绪（MCAP 转换已完成）")
            else:
                self._log("   ⚠ 未检测到 'Upload to server' 按钮变为可点击")
                self._log("   （可能仍在转换中，或需手动检查页面）")
            self._log("   右侧预览区是文件选择器（看起来空白是正常的）")
            self._log("   左侧本地预览区显示 MCAP 转换进度")
            self._log("   浏览器保持打开，请检查页面")
            self._log("   检查完成后手动关闭浏览器窗口即可")
            self._log("=" * 50)
            # block until user closes browser
            try:
                while self.context.pages:
                    await asyncio.sleep(2)
            except Exception:
                pass
            return False  # not a "success" since we didn't submit

        # 正常提交: 2) 选择并上传文件
        if hmd_folder:
            if not await self._upload_hmd_folder_to_preview(hmd_folder):
                self._log("✗ HMD 文件夹注入失败")
                return False
        else:
            if not await self.upload_video_file(video_path):
                self._log("✗ 文件选择失败")
                return False

        # 3) 如果还缺字段，pause 让用户手动补
        if filled < total:
            self._log(f"\n⚠ 仍有 {total - filled} 个字段未填写，等待 10 秒供手动补填...")
            await asyncio.sleep(10)

        # 4) 提交并等待完成
        if not await self.submit_and_wait():
            return False

        return True

    # ── 清理 ──

    async def cleanup(self) -> None:
        """清理浏览器资源"""
        try:
            if self.context:
                await self.context.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception:
            pass


# ==================== 命令行入口 ====================

async def main_async(args: argparse.Namespace) -> int:
    """异步主函数"""
    # 设置日志路径
    log_path = LOG_DIR / f"auto_upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    uploader = AutoUploader(log_path=log_path)

    try:
        # 1) 启动浏览器
        if not await uploader.start():
            uploader._log("✗ 启动失败（登录未完成）")
            await uploader.cleanup()
            return 1

        # 2) 确定要上传的视频列表
        if args.row_index is not None:
            # 支持多个 --row-index（批量上传）
            row_indices = args.row_index if isinstance(args.row_index, list) else [args.row_index]
            rows = load_csv_rows()

            # 预检查所有索引
            video_tasks = []
            missing_files: list[tuple[int, str]] = []  # (idx, path) 缺失的视频
            for idx in row_indices:
                if idx < 0 or idx >= len(rows):
                    print(f"[ERROR] 行索引 {idx} 超出范围（共 {len(rows)} 行）")
                    continue  # 跳过越界索引，继续处理其他行

                row = rows[idx]
                video_path = row.get("path", "").strip()
                is_hmd = _is_hmd_session(video_path)
                hmd_folder: str | None = None

                if is_hmd:
                    hmd_folder = video_path
                    resolved = _resolve_hmd_video(video_path)
                    if not resolved:
                        print(f"[WARN] HMD 会话无已处理视频文件（不影响上传）: {video_path}")
                    else:
                        print(f"[INFO] HMD 会话，已处理视频: {resolved}")
                    video_path = resolved if resolved else video_path
                elif not video_path or not os.path.isfile(video_path):
                    # 文件不存在：跳过但不退出
                    print(f"[SKIP] 视频文件不存在: {video_path}")
                    missing_files.append((idx, video_path))
                    continue

                if row.get("uploaded", "").strip() == "Yes":
                    print(f"[SKIP] 已标记上传完成: {os.path.basename(video_path)}")
                    continue

                template = _build_template_from_row(row, idx)
                video_tasks.append((idx, video_path, template, hmd_folder, row))

            if missing_files:
                print(f"\n[WARN] 共 {len(missing_files)} 个视频文件不存在，已跳过:")
                for idx, p in missing_files:
                    print(f"  [{idx}] {p}")

            if not video_tasks:
                print("[INFO] 所有视频均已上传完成，无需处理")
                await uploader.cleanup()
                return 0

            print(f"\n[批量上传] 共 {len(video_tasks)} 个视频待上传:")
            video_names = []
            for idx, vp, _, hmd, _ in video_tasks:
                name = os.path.basename(vp)
                video_names.append(name)
                print(f"  [{idx}] {name}")
            write_progress("starting", 0, len(video_tasks),
                          current_video="", message=f"准备上传 {len(video_tasks)} 个视频",
                          success=0, fail=0)

        elif args.video and args.data:
            video_path = args.video
            template = json.loads(args.data)
            idx = -1  # 不更新 CSV
            hmd_folder: str | None = None
            video_tasks = [(idx, video_path, template, hmd_folder, {})]

        elif args.extra_desc is not None:
            # 自动扫描：额外描述=指定值 且 recorder_id 和 task_id 都已填好 且 已上传=空
            rows = load_csv_rows()
            target_extra = str(args.extra_desc).strip()
            video_tasks = []
            for idx, row in enumerate(rows):
                extra_desc = (row.get("extra_description") or "").strip()
                uploaded = (row.get("uploaded") or "").strip()
                recorder_id = (row.get("recorder_id") or "").strip()
                task_id = (row.get("task_id") or "").strip()
                if extra_desc == target_extra and uploaded.lower() != 'yes' and recorder_id and task_id:
                    video_path = row.get("path", "").strip()
                    if not video_path:
                        print(f"[SKIP] 行 {idx} 路径为空，跳过")
                        continue
                    is_hmd = _is_hmd_session(video_path)
                    hmd_folder: str | None = None
                    if is_hmd:
                        hmd_folder = video_path
                        resolved = _resolve_hmd_video(video_path)
                        if resolved:
                            print(f"[INFO] HMD 会话，已处理视频: {os.path.basename(resolved)}")
                            video_path = resolved
                    env_desc = ""
                    env_desc_en = ""
                    if task_id:
                        task_info = _load_task_info(task_id)
                        if task_info:
                            env_desc = (task_info.get("environment_description") or "").strip()
                            env_desc_en = (task_info.get("environment_description_en") or "").strip()
                    if not env_desc and not env_desc_en:
                        print(f"[SKIP] 行 {idx} 的 task_id={task_id} 缺少 environment_description，请先在 tasks.csv 中补充")
                        continue
                    template = _build_template_from_row(row, idx)
                    video_tasks.append((idx, video_path, template, hmd_folder, row))
            if not video_tasks:
                print(f"[INFO] 没有找到 extra_description='{target_extra}' 且未上传的视频")
                await uploader.cleanup()
                return 0
            # 按文件大小升序排列（小文件先上传）
            video_tasks.sort(key=lambda t: _get_hmd_folder_size(t[3], t[1]))
            print(f"\n[自动扫描] 找到 {len(video_tasks)} 个待上传视频 (extra_description='{target_extra}'，按大小排序):")
            for idx, vp, _, hmd, _ in video_tasks:
                size_mb = _get_hmd_folder_size(hmd, vp) / (1024 * 1024)
                print(f"  [{idx}] {os.path.basename(vp)} ({size_mb:.0f} MB)")
            write_progress("starting", 0, len(video_tasks),
                          current_video="", message=f"自动扫描到 {len(video_tasks)} 个待上传视频",
                          success=0, fail=0)
        else:
            print("[ERROR] 需要 --row-index 或 (--video + --data) 或 --extra-desc")
            await uploader.cleanup()
            return 1

        if getattr(args, "limit", None):
            video_tasks = video_tasks[:args.limit]

        # 3) 批量执行上传
        use_dual = getattr(args, "dual", False) and len(video_tasks) > 1
        use_pipeline = not use_dual and getattr(args, "pipeline", False) and len(video_tasks) > 1

        if use_dual:
            # 双页面并行模式：两个页面同时上传，互不干扰
            n = len(video_tasks)
            half = n // 2
            tasks_a = video_tasks[:half]
            tasks_b = video_tasks[half:]

            uploader._log(f"\n{'=' * 50}")
            uploader._log(f"启用双页面模式: {n} 个视频 ({len(tasks_a)} + {len(tasks_b)})")
            uploader._log(f"{'=' * 50}")

            # 创建第二个页面（共享同一context的cookie，自动保持登录）
            page1 = uploader.page
            page2 = await uploader.context.new_page()
            uploader._log(f"[Page-1] 使用页面 {page1.url[:50]}")
            uploader._log(f"[Page-2] 导航到上传页面...")
            try:
                await page2.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2)
                uploader._log(f"[Page-2] 使用页面 {page2.url[:50]}")
            except Exception as e:
                uploader._log(f"[Page-2] 导航失败: {e}，尝试继续")

            async def run_page_a():
                return await uploader._upload_batch_on_page(
                    page1, tasks_a, "Page-1",
                    delete_local=getattr(args, "delete_local", False),
                    keep_thumbs=getattr(args, "keep_thumbs", False),
                )

            async def run_page_b():
                return await uploader._upload_batch_on_page(
                    page2, tasks_b, "Page-2",
                    delete_local=getattr(args, "delete_local", False),
                    keep_thumbs=getattr(args, "keep_thumbs", False),
                )

            results = await asyncio.gather(run_page_a(), run_page_b())
            total_success = sum(r[0] for r in results)
            total_fail = sum(r[1] for r in results)
            combined_results: dict[str, bool] = {}
            for r in results:
                combined_results.update(r[2])

            uploader._log(f"\n{'=' * 50}")
            uploader._log(f"双页面上传完成: {total_success} 成功, {total_fail} 失败, 共 {n} 个")
            uploader._log("浏览器保持打开，请检查页面后手动关闭窗口")
            uploader._log(f"{'=' * 50}")
            write_progress("done", n, n,
                          current_video="", message=f"完成: {total_success} 成功, {total_fail} 失败",
                          success=total_success, fail=total_fail)
            success_count = total_success
            fail_count = total_fail
            session_results = combined_results

        elif use_pipeline:
            # 流水线模式：当视频进入inflight后立即提交下一个
            uploader._log(f"\n{'=' * 50}")
            uploader._log(f"启用流水线模式: {len(video_tasks)} 个视频")
            uploader._log(f"{'=' * 50}")
            write_progress("starting", 0, len(video_tasks),
                          current_video="", message=f"流水线上传 {len(video_tasks)} 个视频",
                          success=0, fail=0)

            success_count, fail_count, session_results = await uploader.upload_batch_pipelined(
                video_tasks,
                max_concurrent=1,  # 严格顺序：等一个完成再提交下一个
                delete_local=getattr(args, "delete_local", False),
                keep_thumbs=getattr(args, "keep_thumbs", False),
            )

            uploader._log(f"\n{'=' * 50}")
            uploader._log(f"流水线上传完成: {success_count} 成功, {fail_count} 失败, 共 {len(video_tasks)} 个")
            uploader._log("浏览器保持打开，请检查页面后手动关闭窗口")
            uploader._log(f"{'=' * 50}")
            write_progress("done", len(video_tasks), len(video_tasks),
                          current_video="", message=f"完成: {success_count} 成功, {fail_count} 失败",
                          success=success_count, fail=fail_count)
        else:
            # 提交模式：每个视频只等进入inflight就继续下一个，限制inflight<=3，实时清理已完成文件
            MAX_INFLIGHT = 1
            uploader._log(f"\n{'=' * 50}")
            uploader._log(f"批量上传（提交模式，inflight限制≤{MAX_INFLIGHT}）: {len(video_tasks)} 个视频")
            uploader._log(f"{'=' * 50}")
            write_progress("starting", 0, len(video_tasks),
                          current_video="", message=f"开始提交 {len(video_tasks)} 个视频",
                          success=0, fail=0)

            active_sessions = []  # [{session, idx, video_path, hmd_folder}]
            completed_sessions = []  # [{session, idx, video_path, hmd_folder, result}]
            success_count = 0
            fail_count = 0
            state = load_state()
            next_task_num = 1
            submitted_count = 0  # 已提交的任务数
            task_idx = 0

            async def wait_for_some_completions(min_slots_needed: int = 1):
                """等待直到有至少 min_slots_needed 个 slot 空出来。"""
                nonlocal active_sessions, success_count, fail_count
                if not active_sessions:
                    return

                pending = {a["session"]: a for a in active_sessions}
                deadline = time.time() + 7200
                # 离开 inflight 但 recent 尚未确认的 session，需要重试
                left_inflight: dict[str, dict] = {}  # name -> {session_data, first_seen_ts}
                last_progress_ts = time.time()

                def _write_wait_progress():
                    """更新进度文件，告知前端正在等待中。"""
                    nonlocal last_progress_ts
                    now = time.time()
                    if now - last_progress_ts < 5:
                        return
                    last_progress_ts = now
                    wait_names = ", ".join(list(pending.keys())[:3])
                    write_progress("uploading", task_idx, len(video_tasks),
                                  current_video=list(pending.values())[0].get("video_path", "").split("\\")[-1] if pending else "",
                                  message=f"等待上传完成... 等待中({len(pending)}): {wait_names}",
                                  success=success_count, fail=fail_count)

                while pending and time.time() < deadline:
                    # 等待一段时间
                    await asyncio.sleep(5)
                    _write_wait_progress()

                    # 检查页面状态
                    try:
                        await uploader.page.locator("body").inner_text(timeout=3000)
                    except Exception:
                        uploader._log("  ⚠ 页面连接中断，尝试恢复...")
                        _write_wait_progress()
                        try:
                            await uploader.page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=20000)
                            await asyncio.sleep(2)
                            uploader._log("  页面已恢复")
                        except Exception:
                            uploader._log("  页面恢复失败，继续等待...")
                            continue

                    # 获取当前 inflight 列表
                    inflight_ok = True
                    inflight_set = set()
                    try:
                        inflight_sessions = await uploader._get_inflight_sessions()
                        inflight_set = set(inflight_sessions)
                    except Exception:
                        uploader._log("  ⚠ 获取 inflight 列表失败，跳过本轮检查")
                        inflight_ok = False

                    if not inflight_ok:
                        # inflight 查询失败：不判定任何结果，只更新进度
                        _write_wait_progress()
                        continue

                    # ── Unauthorized 检测（登录过期）→ 自动重新登录 ──
                    try:
                        page_text_unauth = await uploader.page.locator("body").inner_text(timeout=3000)
                        if "Unauthorized" in page_text_unauth or "未授权" in page_text_unauth or "登录已过期" in page_text_unauth:
                            uploader._log("⚠ 检测到 Unauthorized → 自动重新登录")
                            for name in list(pending.keys()):
                                uploader._log(f"  ✗ {name} 因 Unauthorized 失败")
                                active_sessions[:] = [a for a in active_sessions if a["session"] != name]
                            pending.clear()
                            await uploader._handle_unauthorized_restart()
                            _write_wait_progress()
                            break
                        # ── 已上传过检测（重复文件）→ 当作成功标记 + mark_uploaded ──
                        if "已上传过" in page_text_unauth or "Already uploaded" in page_text_unauth:
                            uploader._log("  ✓ 检测到'已上传过'，自动标记为已上传")
                            for name in list(pending.keys()):
                                # 找到对应的 session_data 并标记
                                matching = [a for a in active_sessions if a["session"] == name]
                                if matching:
                                    sd = matching[0]
                                    uploader._log(f"  ✓ {name} 已上传过 → mark_uploaded")
                                    if sd.get("idx", -1) >= 0:
                                        mark_uploaded(sd["idx"])
                                    success_count += 1
                                    completed_sessions.append({**sd, "result": True})
                                    state.setdefault("uploaded", []).append(sd["video_path"].replace("\\", "/"))
                                active_sessions[:] = [a for a in active_sessions if a["session"] != name]
                            pending.clear()
                            save_state(state)
                            _write_wait_progress()
                            break
                    except Exception:
                        pass

                    # 检查每个 pending session
                    for name in list(pending.keys()):
                        if name in inflight_set:
                            continue  # 还在 inflight，继续等待

                        # session 已不在 inflight，可能是已完成
                        session_data = pending[name]
                        determined: bool | None = None  # None=待定, True/False=终局
                        try:
                            if await uploader._is_session_in_recent(name):
                                uploader._log(f"  ✓ {name} 已完成")
                                determined = True
                            else:
                                # 不在 recent 也不在 inflight — 可能是过渡期，记录并重试
                                if name not in left_inflight:
                                    left_inflight[name] = {
                                        "session_data": session_data,
                                        "first_seen_ts": time.time(),
                                    }
                                    uploader._log(f"  ⏳ {name} 离开 inflight，等待进入 recent（最多等 120s）...")
                                    _write_wait_progress()
                                    # 暂不判定，下次循环再检查
                                elif time.time() - left_inflight[name]["first_seen_ts"] < 120:
                                    # 还在等待期，输出等待时间
                                    elapsed = int(time.time() - left_inflight[name]["first_seen_ts"])
                                    uploader._log(f"  ⏳ {name} 已等待 {elapsed}s...")
                                    _write_wait_progress()
                                else:
                                    uploader._log(f"  ⚠ {name} 等待 120s 后仍未进入 recent，标记为失败")
                                    determined = False
                        except Exception:
                            uploader._log(f"  ⚠ {name} 检查 recent 失败，标记为失败")
                            determined = False

                        if determined is not None:
                            session_data = pending.pop(name)
                            if name in left_inflight:
                                del left_inflight[name]
                            active_sessions[:] = [a for a in active_sessions if a["session"] != name]
                            completed_sessions.append({**session_data, "result": determined})

                            if determined:
                                success_count += 1
                                if session_data["idx"] >= 0:
                                    mark_uploaded(session_data["idx"])
                                if getattr(args, "delete_local", False):
                                    session_to_delete = session_data["hmd_folder"] if session_data["hmd_folder"] else session_data["video_path"]
                                    uploader._log(f"  开始清理 {session_data['session']} 本地文件...")
                                    delete_local_files(session_to_delete, uploader.log_path, getattr(args, "keep_thumbs", False))
                                state.setdefault("uploaded", []).append(session_data["video_path"].replace("\\", "/"))
                                uploader._log(f"  ✓ {name} 上传成功，已清理本地文件")
                            else:
                                fail_count += 1
                                state.setdefault("failed", []).append(session_data["video_path"].replace("\\", "/"))
                                uploader._log(f"  ✗ {name} 上传失败")
                            save_state(state)
                            _write_wait_progress()

                    # 检查是否有足够的空位
                    current_active = len(active_sessions)
                    completed_active = len([a for a in active_sessions if a["session"] not in pending])
                    actual_active = current_active - completed_active

                    if actual_active < MAX_INFLIGHT and (MAX_INFLIGHT - actual_active) >= min_slots_needed:
                        # 有足够的空位
                        uploader._log(f"  当前活跃 {actual_active}，有 {MAX_INFLIGHT - actual_active} 个空位")
                        return

                    if not pending:
                        return

            while task_idx < len(video_tasks) or active_sessions:
                # 如果有任务要提交且 active < MAX_INFLIGHT
                if task_idx < len(video_tasks) and len(active_sessions) < MAX_INFLIGHT:
                    idx, video_path, template, hmd_folder, row = video_tasks[task_idx]
                    vname = os.path.basename(video_path)
                    is_first = (task_idx == 0 and submitted_count == 0)
                    uploader._log(f"\n[提交 {next_task_num}/{len(video_tasks)}] {vname}")
                    next_task_num += 1
                    task_idx += 1

                    session_name = await uploader._upload_one_pipeline_submit(
                        video_path, template, hmd_folder, first_submit=is_first,
                        no_submit=getattr(args, "no_submit", False),
                    )

                    if session_name:
                        active_sessions.append({
                            "session": session_name,
                            "idx": idx,
                            "video_path": video_path,
                            "hmd_folder": hmd_folder,
                        })
                        submitted_count += 1
                        uploader._log(f"  → {session_name} 已进入inflight（当前活跃: {len(active_sessions)}）")
                        write_progress("uploading", task_idx, len(video_tasks),
                                      current_video=vname,
                                      message=f"已提交 {submitted_count} 个，活跃 {len(active_sessions)} 个，剩余 {len(video_tasks) - task_idx} 个",
                                      success=success_count, fail=fail_count)
                    else:
                        uploader._log(f"  ✗ 提交失败: {vname}")
                        fail_count += 1
                        video_key = video_path.replace("\\", "/")
                        state.setdefault("failed", []).append(video_key)
                        write_progress("uploading", task_idx, len(video_tasks),
                                      current_video=vname,
                                      message=f"提交失败: {vname}，请检查页面",
                                      success=success_count, fail=fail_count)
                        save_state(state)
                else:
                    # Active 已满或没有任务了，等待一些完成
                    if active_sessions:
                        uploader._log(f"\n  活跃已达 {len(active_sessions)}，等待腾出空位...")
                        await wait_for_some_completions(min_slots_needed=1)
                    else:
                        break

                # 如果所有任务都提交完了，等待剩余的完成
                if task_idx >= len(video_tasks) and active_sessions:
                    uploader._log(f"\n  所有任务已提交，等待剩余 {len(active_sessions)} 个完成...")
                    await wait_for_some_completions(min_slots_needed=1)

            # 清理剩余的 active sessions
            for a in active_sessions:
                name = a["session"]
                if not any(c["session"] == name for c in completed_sessions):
                    uploader._log(f"  ⚠ {name} 还在等待最终检查")

            # 处理还没有记录的 completed_sessions（从 wait_for_some 返回后可能还有没处理的）
            # 实际上 wait_for_some 应该已经处理了所有 active_sessions
            active_sessions.clear()

            # 批量上传总结
            uploader._log(f"\n{'=' * 50}")
            uploader._log(f"批量上传完成: {success_count} 成功, {fail_count} 失败, 共 {len(video_tasks)} 个")
            uploader._log("浏览器保持打开，请检查页面后手动关闭窗口")
            uploader._log(f"{'=' * 50}")
            write_progress("done", len(video_tasks), len(video_tasks),
                          current_video="", message=f"完成: {success_count} 成功, {fail_count} 失败",
                          success=success_count, fail=fail_count)

        # 等待用户手动关闭浏览器
        try:
            while uploader.context and uploader.context.pages:
                await asyncio.sleep(2)
        except Exception:
            pass

        await uploader.cleanup()
        return 0 if fail_count == 0 else 1

    except KeyboardInterrupt:
        uploader._log("⏹ 用户取消上传")
        write_progress("error", 0, 1, current_video="", message="用户取消上传")
        await uploader.cleanup()
        return 130
    except Exception as e:
        uploader._log(f"✗ 异常: {type(e).__name__}: {e}")
        write_progress("error", 0, 1, current_video="", message=f"异常: {type(e).__name__}: {e}")
        await uploader.cleanup()
        return 1


def _get_hmd_folder_size(hmd_folder: str | None, video_path: str) -> int:
    """返回 HMD 文件夹或视频文件的总大小（字节），用于排序。"""
    if hmd_folder and os.path.isdir(hmd_folder):
        try:
            return sum(os.path.getsize(os.path.join(hmd_folder, f))
                       for f in os.listdir(hmd_folder)
                       if os.path.isfile(os.path.join(hmd_folder, f)))
        except Exception:
            pass
    if video_path and os.path.isfile(video_path):
        try:
            return os.path.getsize(video_path)
        except Exception:
            pass
    return 0


def _build_template_from_row(row: dict, idx: int) -> dict:
    """从 CSV 行 + 维表构建上传模板。

    优先级（从低到高）：内置默认 → config.json 用户默认 → recorders.csv → sd_cards.csv → tasks.csv → CSV 行数据
    """
    template = {}

    # 1) 内置必需字段默认值（最低优先级，全部使用中文页面对应值）
    template.setdefault("operator_consent", "yes")
    template.setdefault("operator_job", "生产工人")
    template.setdefault("location_address", "南安市辉煌工业园区")
    template.setdefault("environment", "工业制造")
    template.setdefault("facility_venue", "工厂")

    # 2) config.json 用户自定义默认值
    template.update(_load_template_defaults())

    # 3) Recorder info — from recorders.csv, keyed by recorder_id
    recorder_id = (row.get("recorder_id") or "").strip()
    if recorder_id:
        cinfo = _load_recorder_info(recorder_id)
        if cinfo:
            # operator_name = recorders.id
            template["operator_name"] = cinfo.get("id", "")
            if cinfo.get("operator_job"):
                template["operator_job"] = cinfo["operator_job"]
            if cinfo.get("operator_consent"):
                template["operator_consent"] = cinfo["operator_consent"]
            if cinfo.get("age_range"):
                template["age_range"] = cinfo["age_range"]
            if cinfo.get("gender"):
                template["gender"] = cinfo["gender"]
            if cinfo.get("handedness"):
                template["handedness"] = cinfo["handedness"]
            if cinfo.get("gloves"):
                template["gloves"] = cinfo["gloves"]
            if cinfo.get("workforce_type"):
                template["workforce_type"] = cinfo["workforce_type"]
            if cinfo.get("role_experience"):
                template["role_experience"] = cinfo["role_experience"]
            if cinfo.get("task_experience"):
                template["task_experience"] = cinfo["task_experience"]
            if cinfo.get("collection_hours_today"):
                template["collection_hours_today"] = cinfo["collection_hours_today"]
            if cinfo.get("collection_experience_days"):
                template["collection_experience_days"] = cinfo["collection_experience_days"]
            if cinfo.get("hand_size_cm"):
                template["hand_size_cm"] = cinfo["hand_size_cm"]

    # 4) SD card info — from sd_cards.csv, keyed by device_id
    device_id = (row.get("device_id") or "").strip()
    if device_id:
        sinfo = _load_sd_card_info(device_id)
        if sinfo:
            if sinfo.get("capture_mode"):
                template["captureMode"] = sinfo["capture_mode"]
    # 5) Task info — from tasks.csv, keyed by task_id (覆盖上面的默认值)
    task_id = (row.get("task_id") or "").strip()
    if task_id:
        task_info = _load_task_info(task_id)
        if task_info:
            if task_info.get("difficulty"):
                template["task_difficulty"] = task_info["difficulty"]
            # 中文优先：上传页是中文页面，只填中文 task_description / environment_description
            process_val = (task_info.get("process") or "").strip()
            if not process_val:
                process_val = (task_info.get("process_en") or "").strip()
            if process_val:
                template["task_description"] = process_val
            if task_info.get("business_type"):
                template["business_type"] = task_info["business_type"]
            if task_info.get("business_name"):
                template["business_name"] = task_info["business_name"]

    # 5b) Environment info — from environments.csv, keyed by env_id
    env_id = (row.get("env_id") or "").strip()
    if env_id:
        env_info = _load_env_info(env_id)
        if env_info:
            # 中文优先：上传页是中文页面，只填中文 environment_description
            env_desc_val = (env_info.get("environment_description") or "").strip()
            if not env_desc_val:
                env_desc_val = (env_info.get("environment_description_en") or "").strip()
            if env_desc_val:
                template["environment_description"] = env_desc_val
            if env_info.get("scene"):
                template["scene"] = env_info["scene"]
            if env_info.get("location_address"):
                template["location_address"] = env_info["location_address"]
            if env_info.get("environment"):
                template["environment"] = env_info["environment"]
            if env_info.get("facility_venue"):
                template["facility_venue"] = env_info["facility_venue"]

    # 6) Source device（来源设备）
    source_device = (row.get("source_device") or "").strip()
    if source_device:
        template["source_device"] = source_device

    return template


def _load_recorder_info(recorder_id: str) -> dict | None:
    """复用 upload_service 的加载函数（支持 CSV + PG，自动选 BOM 处理正确的源）"""
    try:
        from services.upload_service import _load_recorder_info as _us_load
        return _us_load(recorder_id)
    except Exception:
        pass
    return None


def _load_sd_card_info(device_id: str) -> dict | None:
    """复用 upload_service 的加载函数"""
    try:
        from services.upload_service import _load_sd_card_info as _us_load
        return _us_load(device_id)
    except Exception:
        pass
    return None


def _load_task_info(task_id: str) -> dict | None:
    """复用 upload_service 的加载函数"""
    try:
        from services.upload_service import _load_task_info as _us_load
        return _us_load(task_id)
    except Exception:
        pass
    return None


def _load_env_info(env_id: str) -> dict | None:
    """复用 upload_service 的加载函数"""
    try:
        from services.upload_service import _load_env_info as _us_load
        return _us_load(env_id)
    except Exception:
        pass
    return None


def _load_template_defaults() -> dict:
    """从 config.json 加载上传模板默认值"""
    config_path = RUNTIME_DIR / "data" / "config.json"
    if not config_path.exists():
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg.get("uploadTemplate", {})
    except Exception:
        return {}


def _extract_date_from_path(path: str) -> str:
    """从源路径中提取日期目录名 (MMDD 格式)，返回 'YYYY-MM-DD' 或 'unknown'。"""
    parts = os.path.normpath(path).split(os.sep)
    for part in reversed(parts):
        if len(part) == 4 and part.isdigit():
            month = part[:2]
            day = part[2:]
            year = datetime.now().year
            return f"{year}-{month}-{day}"
    return "unknown"


def _resolve_hmd_video(session_dir: str) -> str | None:
    """Resolve the actual video file to upload for a HMD session directory.
    
    Priority: session-named mp4 → left.mp4 → session-named h265 → left.h265 → first .hmd part
    Returns the full path to the video file, or None if nothing found.
    """
    date_key = _extract_date_from_path(session_dir)
    base = os.path.basename(session_dir.rstrip("\\/"))
    hmd_cache = RUNTIME_DIR / "hmd_cache" / date_key / base

    # 1) Fully processed MP4 (best for upload) — 新旧命名兼容
    for mp4 in (f"{base}.mp4", f"{base}_right.mp4", "left.mp4", "right.mp4"):
        p = hmd_cache / mp4
        if p.is_file():
            return str(p)

    # 2) Raw h265 stream — 新旧命名兼容
    for h265 in (f"{base}.h265", f"{base}_right.h265", "left.h265", "right.h265"):
        p = hmd_cache / h265
        if p.is_file():
            return str(p)

    # 3) First .hmd part from session directory
    if os.path.isdir(session_dir):
        try:
            hmd_files = sorted(
                f for f in os.listdir(session_dir) if f.lower().endswith(".hmd")
            )
            if hmd_files:
                return os.path.join(session_dir, hmd_files[0])
        except Exception:
            pass

    return None


def _is_hmd_session(path: str) -> bool:
    """Check if path is a HMD session (directory containing .hmd files or metadata)."""
    if path.lower().endswith(".hmd"):
        return True
    if os.path.isdir(path):
        if os.path.isfile(os.path.join(path, "metadata.json")):
            return True
        try:
            if any(f.endswith(".hmd") for f in os.listdir(path)):
                return True
        except Exception:
            pass
        # Check hmd_cache (date-based structure)
        date_key = _extract_date_from_path(path)
        base = os.path.basename(path.rstrip("\\/"))
        cache_dir = RUNTIME_DIR / "hmd_cache" / date_key / base
        if cache_dir.is_dir():
            try:
                if any(f.endswith((".mp4", ".h265")) for f in os.listdir(str(cache_dir))):
                    return True
            except Exception:
                pass
    return False


def main():
    global args  # 让 AutoUploader 类方法里 getattr(args,...) 能拿到
    ap = argparse.ArgumentParser(description="FrameForge 自动上传工具")
    ap.add_argument("--row-index", type=int, nargs="+", default=None,
                    help="CSV 中的行索引（从 0 开始），支持多个（批量上传）")
    ap.add_argument("--video", type=str, default=None,
                    help="视频文件路径")
    ap.add_argument("--data", type=str, default=None,
                    help="JSON 格式的上传模板数据")
    ap.add_argument("--dump-form", action="store_true", default=False,
                    help="抓取页面表单元素结构到 diagnose_form.json")
    ap.add_argument("--no-submit", action="store_true", default=False,
                    help="只填写表单不提交，保持浏览器打开供检查")
    ap.add_argument("--delete-local", action="store_true", default=False,
                    help="上传成功后删除本地文件（HMD分片、预览视频、封面图、预览帧）")
    ap.add_argument("--keep-thumbs", action="store_true", default=False,
                    help="删除本地文件时保留缩略图（需要配合 --delete-local 使用）")
    ap.add_argument("--pipeline", action="store_true", default=False,
                    help="启用流水线模式：当视频进入inflight后立即提交下一个，所有inflight完成后不关闭浏览器")
    ap.add_argument("--dual", action="store_true", default=False,
                    help="双浏览器页面并行模式：同时打开两个页面，各自从队列取视频上传，互不干扰")
    ap.add_argument("--extra-desc", type=str, default=None,
                    help="自动筛选：额外描述等于指定值的视频（例如 --extra-desc=1）")
    ap.add_argument("--limit", type=int, default=None,
                    help="限制上传视频数量（用于测试）")
    args = ap.parse_args()

    if args.row_index is None and (not args.video or not args.data) and not args.extra_desc:
        ap.print_help()
        return 1

    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
