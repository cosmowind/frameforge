# Project Status — video-sort-package

> 2026-06-30 当前状态。AI 接手时第一眼读本文件。

---

## 🚦 总状态

**PostgreSQL 云数据库全面上线 + 来源设备追踪 + 服务端缓存层**。Flask 单进程 + 单页前端 + PostgreSQL 云存储；2026-06-30 完成从 CSV 到 PG 的全面迁移（维表 + 主表所有读写走 PG），新增 `source_device` 字段追踪视频来源设备，修复维表路由 GET/POST handler 和 pg_dim 映射 bug；新增服务端内存缓存层（`models/cache.py`），视频列表 30s TTL、维表 60s TTL，写操作自动失效，路径校验 O(1)。

| 维度 | 当前 | 备注 |
|---|---|---|
| 入口 | `python src/run.py` → http://localhost:5000 | 也可双击 `启动视频管理.bat` |
| 架构 | `src/` 模块化（services/models/utils/routes 蓝图） | routes 蓝图注册并正常工作 |
| 视频格式 | MP4（FFprobe） + HMD（WebCodecs HEVC） | 单目流；真双目=两独立设备的两个 session |
| 数据存储 | **PostgreSQL 云数据库** + 内存缓存层 | .env 配置连接串，cache.py 30s/60s TTL |
| 数据备份 | 本地 CSV 保留（`runtime/data/video_manager.csv`） | CSV 作为离线备份，正常流程不再读写 |
| 元数据 | 录制人 / 设备编号 / 任务 ID / 时长 / **来源设备** | 21 列（新增 source_device） |
| 上传器 | Playwright 自动上传（auto_upload.py） | 支持批量 + delete-local + 进度追踪 + source_device |
| WebCodecs | 必需 Edge 88+ / Chrome 94+ | Linux 无系统 HEVC 解码器 |

---

## ✅ 已实现能力（2026-06-20 快照）

### 后端（app.py）

| 能力 | 端点 | 状态 |
|---|---|---|
| 单页 + 配置读写（`/` no-cache） | `GET /`, `GET/POST /api/config` | ✅ |
| 表格数据 + 保存 | `GET /api/data`, `POST /api/save` | ✅ |
| 扫描 mp4/HMD（scope=current） | `POST /api/scan` | ✅ |
| 视频流（Range） | `GET /api/video` | ✅ |
| 目录选择对话框 | `POST /api/pick-directory` | ✅ |
| HMD session 扫描 | `POST /api/hmd/scan` | ✅ |
| HMD session 元数据 | `GET /api/hmd/info` | ✅ |
| HMD 部分文件流 | `GET /api/hmd/raw` | ✅ |
| HMD 单文件流（API 兼容） | `GET /api/hmd/file` | ✅ |
| HMD duration 回填 | `POST /api/hmd/duration` | ✅ |
| HMD 注册为 CSV 行 | `POST /api/hmd/register` | ✅ |
| 独立 HMD 预览页 | `GET /hmd-preview` | ✅ |
| 维表 CRUD 通用端点 | `GET/POST/DELETE /api/dim/<name>` | ✅ |
| 任务时长配额聚合 | `GET /api/dim/tasks/with-usage` | ✅ |
| 缩略图（MP4 + HMD + smart-seek + luma） | `GET /api/thumbnail` | ✅ |
| 缩略图批量预热 | `POST /api/thumbnail/warm` | ✅ |
| 上传脚本生成 + 执行 | `/api/upload-*` | ✅ SSE 批量上传 |
| 自动上传（Playwright） | `/api/auto-upload-start`, `/api/auto-upload-status` | ✅ 批量 + delete-local |
| **上传模板按路径查找** | `/api/upload-template-by-path` | ✅ 新增（2026-06-24） |
| **自动上传进度轮询** | `/api/auto-upload-progress` | ✅ 新增（2026-06-24） |
| 数据迁移一次性 | `/api/fix-dates`, `/api/fix-empty-scan-dates` | ✅ |
| **MP4 原始日期修正**（ffprobe creation_time） | `_get_file_date` | ✅ |
| **HMD 原始日期修正**（metadata+目录名） | `_get_hmd_date` | ✅ |

### 前端（templates/index.html，~2400 行）

| 能力 | 状态 |
|---|---|
| 列控制（chip / 拖宽 / 拖序） | ✅ |
| 多列排序栈 | ✅ |
| 行预览（MP4 单视频） | ✅ |
| 行预览（HMD 双 canvas 内嵌） | ✅ |
| 1× / 5× / 10× / 16× 速度按钮 | ✅ |
| IDR-aware seek | ✅ |
| WebCodecs HEVC 解码 | ✅ |
| splitStereo 双目 | ✅ |
| 中英自动补全 | ✅ |
| 批量上传 + 进度终端 | ✅ |
| 导出 TXT | ✅ |
| 撤销 Ctrl+Z | ✅ |
| 5 tab 页面框架（视频/录入员/SD卡/任务/设置） | ✅ |
| 维表 CRUD UI（3 个页面） | ✅ |
| `select-dimension:` 列类型（recorder_id/device_id/task_id 已升级） | ✅ |
| 任务时长配额进度条（5 档色） | ✅ |
| recorder 自动收录（首次 GET recorders） | ✅ |
| **维表主键连续改名保留 original_key** | ✅ |
| **画廊视图（缩略图 + 全屏 + 多选 + 筛选）** | ✅ |
| **画廊播放视频（状态感知）** | ✅ |
| **「同上」按钮（表格+画廊）** | ✅ |
| **「↩ 撤回同上」** | ✅ |
| **Build 标记戳（console 首行）** | ✅ |

### 离线工具

| 能力 | 文件 | 状态 |
|---|---|---|
| HMD 解析器（ESM） | `src/static/hmd/hmd-decode.esm.js` | ✅ |
| HMD 解析器（CJS 桥接） | `src/static/hmd/hmd-decode.cjs` | ✅ |
| WebCodecs 播放核心 | `src/static/hmd/hmd-player-core.js` | ✅ |
| HMD → MP4 命令行 | `src/vendor-upload-pkg/hmd_to_mcap.js` | ✅ |
| USB 监听 + 自动复制 | `src/device_monitor.py` | ✅ **MP4 + HMD + Data 三模** |
| 视频旋转 + 分割 | `src/scripts/rotate_video.py` / `src/scripts/split_video.py` | ✅ |
| HMD 预处理（splitStereo + ffmpeg） | `src/tools/hmd_preprocess.py` | ✅ |
| 批量预处理 | `src/scripts/batch_preprocess.py` | ✅ |
| 文件名迁移 | `src/scripts/rename_all.py` | ✅ |
| 重复前缀修复 | `src/scripts/fix_duplicate_prefix.py` | ✅ |

---

## 🚧 待办（按优先级）

详见 `docs/dev_plan.md`。摘要：
- 画廊批量操作（多选已实现，批量标记/删除未接）
- 视频自动重命名（mmdd-DevID-RecID-TaskCode）
- 深度上传器（适配 frameforge 后台端口）
- ~~SD 卡卷标 → 设备编号自动识别~~（✅ 已完成）
- ~~HMD 端到端：扫描 → 注册 → 字段填写~~（✅ device_monitor 已支持）

---

## 🔗 上游依赖

| 依赖 | 版本 | 用途 | 备注 |
|---|---|---|---|
| Python | 3.11+ | 后端 | 已验证 |
| Flask | latest | Web 框架 | pip install flask |
| FFmpeg / FFprobe | latest | mp4 旋转/分割/时长 | 系统 PATH |
| 浏览器 | Edge 88+ / Chrome 94+ | WebCodecs HEVC | HMD 必需 |
| Node.js | 18+ | `verify_hmd_packets.js` | 离线测试用 |

---

## 📁 核心文件清单

| 文件 | 用途 | 状态 |
|---|---|---|
| `src/app.py` | Flask 主应用（蓝图注册） | ✅ 瘦身完成 |
| `src/config.py` | 全局常量 & 路径配置 | ✅ |
| `src/models/` | 数据模型层（csv_store + dim_registry） | ✅ |
| `src/services/` | 业务逻辑层（8 个服务） | ✅ |
| `src/routes/` | ~~Flask 蓝图路由层~~（已删除，死代码） | 🗑 |
| `src/utils/` | 工具函数层 | ✅ |
| `src/templates/index.html` | 单页前端（~6000 行） | ✅ |
| `src/templates/hmd_preview.html` | 独立 HMD 预览页 | ✅ |
| `src/static/hmd/hmd-decode.esm.js` | HMD ESM 解析 | ✅ |
| `src/static/hmd/hmd-player-core.js` | WebCodecs 封装 | ✅ |
| `src/scripts/device_monitor.py` | USB 监听 | ✅ MP4 + HMD 双模 + 去重 |
| `src/auto_upload.py` | FrameForge 自动上传（~3000 行） | ✅ 批量 + 进度 + delete-local |
| `src/vendor-upload-pkg/` | 上传脚本（vendor） | ✅ |
| `runtime/data/video_manager.csv` | 主数据（20 列） | ✅ |
| `runtime/data/config.json` | 列定义 + 扫描目录 | ✅ |
| `runtime/csv_backups/` | 自动备份（10 份） | ✅ |

---

## 🛡 兼容性矩阵

| 旧行为 | 新位置 | 兼容 |
|---|---|---|
| 双击 hmd-preview.html | `/hmd-preview?path=...` | ✅ 仍可用 |
| `node hmd2mp4.js` | 不变 | ✅ |
| `python hmd_decompile.py` | 已移除 | ⚠️ |
| 13 列 CSV | 20 列（向后兼容） | ✅ |
| 旧扫描（保留历史） | `scope=all` 参数 | ✅ |
| 客户端 video.seek 抓帧 | 服务端 `/api/thumbnail` | ✅（更稳定） |

---

## ⚠️ 已知限制

1. HMD duration 仅靠客户端首次打开时回填，依赖浏览器
2. WebCodecs 在 Linux 上不可用（无系统 HEVC 解码器）
3. 并排第二 session 暂未实现（E2 真双目场景）
4. 没有单元测试，靠 `verify_pages.py` 集成脚本验证
5. Flask debug 模式 reloader 子进程残留（手动 kill PID 解决）
6. 浏览器缓存陷阱：单文件 SPA 必须 `Cache-Control: no-cache`
7. 缩略图首次生成走 ffmpeg 约 0.5-2s，未做 lazy warm 预热
8. HMD 设备无 RTC，原始日期最多只能推断到「天」精度
9. MP4 去重基于同名同大小，无法区分内容不同但碰巧同名同大的极罕见情况
10. 自动上传需桌面环境（Playwright 浏览器），无法在纯服务端运行

## 🆕 2026-06-30 最新变更（未推送）

| 变更 | 说明 |
|---|---|
| **默认筛选本地视频** | 页面加载时自动选中 `location_status=local`，只显示本地存在的视频 |
| **缩略图/帧预览 Cache-Control** | `max-age=86400`（1天），消除 304 轮询，大幅提升画廊/表格加载速度 |
| **fix: upload_routes.py import sys** | 修复 `/api/upload-run-cmd` 500 错误 |
| **dim_routes.py 路由装饰器补全** | 4 个路由函数缺少 `@bp.route` 导致 404：`dim_editable_options`、`environments_next_id`、`tasks_reorder`、`translate_single_process` |
| **tasks 自动排序** | 新增 ⇅ 自动排序 toggle 按钮，默认开启，状态持久化到 localStorage；开启后加载/保存时自动按 产品→任务→工具 排序并回写 CSV |
| **tasks_next_id 响应格式** | 返回 `{ok, suggested, reason}` 替代旧格式，前端兼容更友好 |
| **CV 手部识别项目规划** | 新增 `docs/cv-hand-recognition-plan.md`，利用标注视频数据训练手部识别模型的完整方案 |

## 🆕 2026-06-28 变更

| 变更 | 说明 |
|---|---|
| **画廊播放视频按钮** | 与表格预览状态一致（处理中/失败/等待/检查中…），HMD 走系统播放器 |
| **「同上」按钮（表格+画廊）** | 一键复制上一个视频的录制员、Task、Env（按筛选排序顺序） |
| **「↩ 撤回同上」** | 工具栏+画廊面板撤回按钮，恢复同上操作前的原始值 |
| **Bug 修复** | 修复画廊 `_buildGalleryEditorForm` 缺 `idx` 参数；修复按钮 HTML 重复渲染 |

| 变更 | 说明 |
|---|---|
| **frameforge 补录参数助手** | Chrome CDP + Playwright 自动化 publish.example.com 上传历史页面 |
| **全量扫描** | `scan_all_videos.py` 扫描 6 页 262 条视频，获取 session_id / date / duration / missing |
| **滚动修复** | `scrollIntoView` 确保下方 tile 坐标正确 |
| **分页修复** | JS native value setter + JS click Go 按钮（Playwright 认为 disabled） |
| **CSV Web 编辑器** | `csv_editor.py` (localhost:5001)，链接 recorders/tasks/environments 维表 |
| **维表下拉选择** | 下拉选中文 → 自动填 ID + 英文字段（process_en / environment_description_en） |
| **自动保存** | 单行 JSON 发送 `/save_row`，避免 413 超限 |

## 🆕 2026-06-24 变更

| 变更 | 说明 |
|---|---|
| 模块化重构 | 扁平结构 → `src/` 四层架构（routes/services/models/utils），app.py 从 5585 行瘦身 |
| 批量上传增强 | paths 参数支持、进度追踪（JSON 轮询）、前端进度条 UI、`--delete-local` 标志 |
| 路径修复 | `auto_upload.py` 子进程路径、`/api/upload-template-by-path` by-path 查找 |
| 根目录清理 | 临时脚本归档到 `src/scripts/` 或删除，gitignore 更新 |
| **死代码清理** | 删除 `src/routes/`（蓝图未注册）+ 5 个过时 batch_preprocess 脚本，共 2721 行 |
| **启动磁盘空间检查** | `run.py` 启动前扫描未处理 HMD 总大小，预估 2x 空间需求，不足时询问用户 |
| **自动预处理开关** | `AUTO_PREPROCESS_ENABLED` 环境变量控制 `_startup_auto_warm` + `_auto_warm_all` |
| **h265 自动清理** | Stage2 完成后，mp4 可播放 + 预览帧完整 → 删除 `left.h265`，每 session 省 ~50% 空间 |
| **完成判定兼容** | `check_fast_done` 接受 "mp4 存在但 h265 已清理" 为有效完成状态 |