# Features — video-sort-package

> 已实现能力索引（按模块/领域）。新增能力时同步更新。

---

## 📂 视频扫描

| 能力 | 入口 | 状态 | 备注 |
|---|---|---|---|
| MP4 扫描 | `/api/scan` mode=mp4 | ✅ | 递归 + 自动 ffprobe 时长 |
| HMD session 扫描 | `/api/scan` mode=hmd | ✅ | 1 session = 1 CSV 行 |
| 自动检测（推荐） | `/api/scan` mode=auto | ✅ | metadata.json → hmd |
| scope=current（默认） | `/api/scan` `scope` | ✅ | 仅显示/保留当前目录的行 |
| scope=all（历史） | `/api/scan` `scope=all` | ✅ | 旧行为，保留所有历史 |
| CSV 自动备份 10 份 | `write_csv` | ✅ | 写前复制到 `csv_backups/` |
| 原子写（os.replace） | `write_csv` | ✅ | 崩溃安全 |
| scan_date 锁定 | `/api/save` | ✅ | 被清空时回填旧值 |

## 🎬 MP4 预览

| 能力 | 入口 | 状态 |
|---|---|---|
| 单视频内嵌预览 | 表格"预览"按钮 | ✅ |
| Range 请求（seek） | `/api/video` | ✅ |
| 上一/下一个导航 | 方向键 / 按钮 | ✅ |
| 同步右侧表单 | `previewForm` | ✅ |
| 字段实时编辑 | 表单 input/select | ✅ |
| **单帧提取** | `/api/video/frame` | ✅ | 按时间戳提取单帧 |
| **多帧提取** | `/api/video/frames` | ✅ | 批量提取多帧 |
| **帧预热** | `/api/frames/warm` | ✅ | 预生成帧缓存 |

## 👁 HMD 双目预览

| 能力 | 入口 | 状态 |
|---|---|---|
| 单流 + 双 canvas 内嵌 | 表格预览按钮（file_type=hmd） | ✅ |
| splitStereo（NAL 奇偶分左右） | `templates/index.html` `openHmdPreviewInline` | ✅ |
| 1× / 5× / 10× / 16× 速度 | 控件条按钮 | ✅ |
| IDR-aware seek（避免 DataError） | `seek.onchange` | ✅ |
| 单调时间戳（避免 timestamp 冲突） | `feedHmdFrame` | ✅ |
| WebCodecs HEVC 解码 | `static/hmd/hmd-player-core.js` | ✅ |
| Range 流式 .hmd part | `/api/hmd/raw` + `/api/hmd/file` | ✅ |
| 路径遍历保护 | `/api/hmd/raw` | ✅ |
| 独立预览页（带 4 阶段进度 UI） | `/hmd-preview` | ✅ |
| Duration 客户端回填 | `/api/hmd/duration` | ✅ |

## 📊 表格编辑

| 能力 | 状态 |
|---|---|
| 13→20 列（向后兼容） | ✅ |
| 列 chip 显隐 | ✅ |
| 列宽拖动 | ✅ |
| 列顺序拖拽 | ✅ |
| 多列排序栈 | ✅ |
| 单字段 Ctrl+Z 撤销 | ✅ |
| 自动保存（800ms debounce） | ✅ |
| 中→英自动补全（同中文→复用英文） | ✅ |
| "应用到全部"对话框 | ✅ |
| 批量删除 + 自动备份 | ✅ |
| 一次性数据迁移（fix-dates / fix-empty-scan-dates） | ✅ |
| **「同上」按钮**（复制上一条的录制员/Task/Env） | ✅ |
| **「↩ 撤回同上」**（恢复同上操作前的值） | ✅ |
| **tasks 自动排序**（产品→任务→工具，toggle + localStorage 持久化） | ✅ |

## 🤖 frameforge 补录参数助手

> 通过 Chrome CDP 连接用户已登录的 Chrome，自动扫描 publish.example.com 上传历史页面并批量补录参数。

| 能力 | 文件 | 状态 | 备注 |
|---|---|---|---|
| Chrome 启动器（9222 CDP） | `start_helper.bat` | ✅ | `--remote-allow-origins` + `--disable-web-security` |
| 筛选条件初始化 | `src/scripts/setup_filters.py` | ✅ | Capture=Stereo + Excludes 3 标签 |
| 全量扫描 6 页 | `src/scripts/scan_all_videos.py` | ✅ | 262 条，scrollIntoView + 分页 JS click |
| missing 状态检测 | `scan_all_videos.py` | ✅ | 从 modal 文本提取 `(\d+)\s*missing` |
| Edit metadata 字段读取 | `scan_all_videos.py` | ✅ | operator_name / task_description / environment_description |
| CSV Web 编辑器 | `src/scripts/csv_editor.py` | ✅ | http://localhost:5001，自动保存 |
| 维表下拉选择器 | `csv_editor.py` | ✅ | 链接 recorders/tasks/environments.csv |
| 下拉选中文 → 自动填英文 | `csv_editor.py` | ✅ | 选 task_id → 填 process_en；选 env_id → 填 environment_description_en |
| Ctrl+B 快捷键自动填写 | `src/scripts/auto_fill_helper.py` | ✅ | 注入 JS，填 20+ 字段 |
| 单行 JSON 自动保存 | `csv_editor.py` `/save_row` | ✅ | 避免 413 超限 |

**工作流：**
1. 双击 `start_helper.bat` 启动 Chrome（9222 端口）
2. 运行 `scan_all_videos.py` 扫描全部视频 → `video_batch_config.csv`
3. 打开 http://localhost:5001 编辑 CSV（选 recorder_id / task_id / env_id）
4. 运行批量处理脚本（待开发）逐一补录 missing>0 的视频

## 📤 上传器

| 能力 | 状态 | 备注 |
|---|---|---|
| 生成 _upload_now.py + .cmd | ✅ | `_generate_upload_runner` |
| SSE 流式进度 | ✅ | `/api/upload-run` |
| 跳过已上传（marker + CSV 双重判重） | ✅ | `*.uploaded` 标记文件 |
| 启动可见 cmd 窗口 | ✅ | `cmd /c start` |
| **Playwright 自动上传** | ✅ | `auto_upload.py` ~3000 行 |
| **批量上传 + 进度追踪** | ✅ | paths 参数、JSON 轮询、前端进度条 |
| **上传模板按路径查找** | ✅ | `/api/upload-template-by-path?path=xxx` |
| **上传后自动清理（delete-local）** | ✅ | `--delete-local` 释放空间 |
| 适配 frameforge 后台端口 | ✅ | 已通过 Playwright 自动化适配 |
| **自动上传状态轮询** | ✅ | `/api/auto-upload-start` + `/api/auto-upload-status` + `/api/auto-upload-progress` |

## 💾 导出 TXT

| 能力 | 状态 |
|---|---|
| 选列 + 选行 + 分隔符 | ✅ |
| 行范围输入（xx-xx） | ✅ |
| 浏览器下载 | ✅ |
| 详见 docs/EXPORT.md | ✅ |

## 🖥 设备监听

| 能力 | 状态 | 备注 |
|---|---|---|
| Windows GetLogicalDrives 扫描 | ✅ | 排除 C/D 系统盘 |
| 视频源识别（DCIM / MP_ROOT / PRIVATE） | ✅ | DJI/GoPro 子目录 |
| 自动复制到 /media/inbox | ✅ | mmdd = 当天月日 |
| 复制后清理 mp4 + lrf（保留 jpg） | ✅ | |
| Tkinter 进度窗口 | ✅ | `copy_progress_window.py` |
| 设备断开检测 | ✅ | 复制中途断开时中断 |
| CSV 登记（自动建行） | ✅ | |
| **HMD session 复制 + 设备ID前缀重命名** | ✅ | `copy_hmd_sessions` |
| **≥0623 日期前缀** | ✅ | 6月23日起的视频重命名时额外添加 MMDD 前缀：`0625_f83c30_session_00007` |
| **HMD 复制后自动删除 SD 卡源** | ✅ | `shutil.rmtree` + 清理空目录 |
| **HMD 复制后自动触发预处理** | ✅ | `_start_hmd_preprocess` → `splitStereo` + `ffmpeg left.mp4` |
| **SD 卡自动注册** | ✅ | `_auto_register_mp4_device` — 卷序列号+卷标→`sd_cards.csv` |
| **卷序列号获取（Win32 API）** | ✅ | `_get_drive_volume_info` → `GetVolumeInformationW` |
| **MP4 原始日期修正** | ✅ | `_get_mp4_original_date` — ffprobe creation_time > mtime > ctime |
| **HMD 原始日期修正** | ✅ | `_get_hmd_original_date` — metadata start_time > 目录名MMDD > mtime |
| **MP4 去重（防止重复存储）** | ✅ | `_check_mp4_already_exists` — 同名同大小即视为已存在 |
| **HMD 去重（防止重复存储）** | ✅ | `_check_hmd_already_exists` — 同设备ID+session名+part数 |
| **CJS/ESM 桥接** | ✅ | `hmd-decode.cjs` 用 `import()` 动态加载 `.esm.js` |

## 🎬 HMD 预处理管理

> 核心流程：`hmd_fast_preprocess.py` 异步管线（Stage1: H265解码 → Stage2: 抽帧+封面+MP4封装）

| 能力 | 入口 / 实现 | 状态 | 备注 |
|---|---|---|---|
| 快速预处理（两阶段异步管线） | `/api/hmd/process` → `queue.enqueue` | ✅ | Stage1 解码 + Stage2 抽帧/封面/MP4 |
| 进度状态文件 `preprocess_status.json` | `hmd_fast_preprocess.write_status` | ✅ | 前端轮询 `/api/hmd/status` |
| **预处理完成后自动删除 .h265** | `hmd_fast_preprocess._do_stage2()` & `process_fast()` | ✅ | **设计要点**：mp4 可播放 + 预览帧完整 + 封面存在 → 删除 `left.h265`，每个 session 约省 50% 空间 |
| **完成判定兼容 h265 已清理** | `hmd_fast_preprocess.check_fast_done()` | ✅ | **设计要点**：接受 "mp4 存在但 h265 已清理" 为有效完成状态（之前要求 h265 必须存在） |
| 启动时磁盘空间检查 | `src/run.py._check_disk_space_for_preprocess()` | ✅ | **设计要点**：统计所有未处理 HMD 源文件总大小，预估需 2x 空间（h265+mp4+帧+封面），比较 runtime 目录所在磁盘的 `shutil.disk_usage` |
| 空间不足时用户询问 | `src/run.py.main()` 交互式 `input()` | ✅ | 显示 pending 数、源文件大小、所需空间、可用空间；默认 **N**（不开启） |
| `AUTO_PREPROCESS_ENABLED` 环境变量 | `os.environ` → `app.py` | ✅ | **设计要点**：`run.py` 根据用户选择设置 `"1"`/`"0"`，`app.py` 据此决定是否 `_startup_auto_warm` 和 `_auto_warm_all` |
| 扫描后自动预热受控 | `app.py` `/api/scan` handler | ✅ | `_auto_warm_all()` 仅在 `AUTO_PREPROCESS_ENABLED=1` 时执行 |
| 防重复启动标记文件 | `_startup_warm_flag` | ✅ | 路径：`runtime/.startup_warm_done`，确保 Flask reloader 不重复触发 |
| **HMD 队列状态查询** | `/api/hmd/queue-status` | ✅ | 查看预处理队列排队情况 |
| **HMD 处理中状态** | `/api/hmd/is-processing` | ✅ | 前端判断是否有 HMD 正在处理 |

## 🧹 缓存清理

> 入口：工具栏「🧹 清理缓存 ▼」下拉菜单 → 两项子功能

| 能力 | 入口 / 实现 | 状态 | 备注 |
|---|---|---|---|
| 清理孤儿缓存 | `/api/clean-orphan-cache` → `app.py` | ✅ | **设计要点**：对比 `video_manager.csv` 注册路径与 `runtime/hmd_cache/*` + `runtime/thumbnails/*` 实际文件，删除已从 CSV 删除但残留的预处理文件 |
| 清除已上传视频源文件 | `/api/clean-uploaded-cache` → `app.py` | ✅ | **设计要点**：仅处理 `uploaded=Yes` 的行，严格按**完整路径**删除（非文件名匹配），避免误删未上传的同名文件。支持两阶段操作：preview（扫描展示列表）→ execute（确认后执行） |
| **清除预览弹窗** | `#cleanCachePreviewDialog` 模态框 | ✅ | **设计要点**：preview 后弹出详情弹窗，展示：①汇总统计（视频数、各类型文件数和大小）；②每条已上传视频的详细文件列表（含 CSV 行号、路径、类型、大小、存在状态）。用户确认后执行删除，按钮在执行期间禁用 |
| 前端 dropdown 交互 | `toggleCleanCacheMenu()` / `closeCleanCacheMenu()` | ✅ | **设计要点**：点击按钮 show/hide 菜单，点击页面其他位置自动关闭（`event.stopPropagation` + `document.addEventListener('click', ...)`）|
| 三步安全过滤 | scan / execute / endpoint 入口 | ✅ | **设计要点**：三层均过滤 `uploaded == "Yes"`（大小写不敏感），确保绝不删除未上传视频

## 📈 视频处理 CLI

| 能力 | 入口 | 状态 |
|---|---|---|
| 旋转（ffmpeg） | `python src/scripts/rotate_video.py` | ✅ |
| 分割（30s 边界 + 3GB 阈值） | `python src/scripts/split_video.py` | ✅ |
| HMD → MP4 命令行 | `node hmd2mp4.js` | ✅ |
| HMD 包验证 | `node verify_hmd_packets.js` | ✅ |

## ⚙️ 配置 / 列定义

| 能力 | 状态 |
|---|---|
| `config.json` 列定义（label/type/width/order） | ✅ |
| 运行时合并 DEFAULT_FIELDNAMES | ✅ |
| 列类型：input / select-yesno / select-feasibility / select-location / duration / path | ✅ |
| 列类型：select-dimension（已实现） | ✅ |
| 排序栈持久化（config.sortStack） | ✅ |

## 🔍 维表系统（待 PR 2）

| 能力 | 状态 |
|---|---|
| `recorders.csv`（录入员 id→姓名） | ✅ |
| `sd_cards.csv`（SD 卡→设备编号） | ✅ |
| `tasks.csv`（可录制任务表） | ✅ |
| `/api/dim/<name>` 通用端点 | ✅ |
| 维表管理 dialog | ✅（独立 tab 页面） |
| 任务时长配额（easy=1h/medium=2h/hard=10h） | ✅ |
| 进度条 5 档色（绿/蓝/黄/红/灰） | ✅ |
| `with-usage` 聚合（实时算已用秒数） | ✅ |
| recorder 自动收录（首次 GET recorders 时从 video_manager.csv 收集） | ✅ |
| `select-dimension:<dim_name>` 列类型 | ✅ |
| **任务下一个 ID** | `/api/dim/tasks/next-id` | ✅ | 自动生成下一个任务 ID |
| **翻译空流程** | `/api/dim/tasks/translate-empty-process` | ✅ | 批量翻译未翻译的任务流程描述 |
| **维表条目删除** | `/api/dim/<name>/<key_val>` DELETE | ✅ | 按 key 删除单条维表记录 |

## 🧭 页面导航

| 能力 | 状态 | 备注 |
|---|---|---|
| 5 个 tab：视频管理 / 录入员 / SD卡 / 任务 / 画廊 | ✅ | toolbar 左侧 tab 栏 |
| `switchPage()` + 隐藏/显示 page-panel | ✅ | `localStorage.lastTab` 持久化 |
| 维表 CRUD 通用骨架（subtoolbar + 表格 + 操作列） | ✅ | recorders / sd_cards / tasks |
| `dimCache` 启动时预热所有 `select-dimension:` 引用 | ✅ | 解决单元格渲染顺序问题 |

## 🖼 画廊视图

| 能力 | 状态 | 备注 |
|---|---|---|
| 缩略图网格（4-6 列自适应） | ✅ | CSS grid `auto-fill, minmax(220px, 1fr)` |
| 缩略图懒加载（IntersectionObserver） | ✅ | 500ms 兜底直接 fetch（防 observer 不触发） |
| **服务端 HMD 缩略图** | ✅ | `_generate_hmd_thumbnail` → `hmd_cache/<basename>/left.mp4` |
| **服务端 MP4 缩略图** | ✅ | `_generate_mp4_thumbnail` + smart-seek `[3,1,5,10]` + luma 兜底 |
| **暗场景检测** | ✅ | `_ffmpeg_avg_luma` (PGM 灰度帧字节均值，< LUMA_MIN=8 视为全黑) |
| `/api/thumbnail?path=...`（白名单） | ✅ | 必须 video_manager.csv 已登记 |
| 全屏预览 + 左右键 + Esc | ✅ | `galleryOverlayOpen` / `galleryOverlayNav` / `galleryOverlayClose` |
| 多选（Shift 区间 / Ctrl 切换） | ✅ | `galleryState.selectedKeys` |
| 筛选（按 device/recorder/task/uploaded） | ✅ | 共享筛选 `_populateSharedFilters` |
| 全屏内嵌编辑器 | ✅ | 左视频 + 右字段面板（`galleryEditorSave`） |
| **画廊播放视频** | ✅ | 状态与表格预览一致（处理中/失败/等待/检查中…），HMD 用系统播放器 |
| **画廊「同上」按钮** | ✅ | 复制上一个卡片的录制员/Task/Env（筛选后顺序） |
| **画廊「↩ 撤回同上」** | ✅ | 恢复同上操作前的值 |
| Build 标记戳 | ✅ | console 首行 `[VideoSort] page loaded, build=...` |
| `/` 路由 no-cache | ✅ | `Cache-Control: no-cache, no-store, must-revalidate` |
| 缩略图缓存目录 | ✅ | `thumbnails/<sha1(path\|mtime)>.jpg`（git ignored） |

## 🧰 开发者工具

| 能力 | 状态 | 备注 |
|---|---|---|
| `打包备份.bat` / `pack.ps1` 一键打包 | ✅ | 输出 `video-sort-package_<ts>.zip` |
| 打包递归排除 `hmd_cache` / `node_modules` / `thumbnails` | ✅ | 1.4GB → 340KB |
| `src/scripts/verify_pages.py` 集成测试 | ✅ | 38 个端到端 case（启 Flask + curl 全套端点） |
| `src/scripts/test_flask_routes.py` 路由测试 | ✅ | 14+15 个 route 冒烟测试 |
| `src/scripts/check_routes.py` 路由清单 | ✅ | 列出所有路由和函数 |
| Build 标记戳（防浏览器缓存） | ✅ | console 首行输出 build 号 |
| `/` 路由 `Cache-Control: no-cache` | ✅ | dev 期间改 templates 立即生效 |
| **`src/` 模块化架构** | ✅ | 四层分离，app.py 瘦身 |

## 🖥 系统工具

| 能力 | 入口 | 状态 | 备注 |
|---|---|---|---|
| 统计数据 | `/api/statistics` | ✅ | 视频数量、时长等汇总统计 |
| 预估 | `/api/estimate` | ✅ | GET 获取预估信息 / POST 重新计算 |
| 磁盘空间状态 | `/api/disk-space-status` | ✅ | 实时磁盘使用情况 |
| 目录选择器 | `/api/pick-directory` | ✅ | 服务端目录浏览 |
| 恢复设备监控 | `/api/resume-monitor` | ✅ | 设备断开后重新启动监控 |
| 翻译处理 | `/api/translate-process` | ✅ | 批量翻译任务流程描述 |