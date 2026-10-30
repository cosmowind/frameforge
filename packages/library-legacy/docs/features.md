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

## 📤 上传器（待适配）

| 能力 | 状态 | 备注 |
|---|---|---|
| 生成 _upload_now.py + .cmd | ✅ | `_generate_upload_runner` |
| SSE 流式进度 | ✅ | `/api/upload-run` |
| 跳过已上传（marker + CSV 双重判重） | ✅ | `*.uploaded` 标记文件 |
| 启动可见 cmd 窗口 | ✅ | `cmd /c start` |
| 适配 frameforge 后台端口 | ❌ | 待用户规范 |

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
| .hmd 文件支持 | ❌ | 待 PR 3 |

## 📈 视频处理 CLI

| 能力 | 入口 | 状态 |
|---|---|---|
| 旋转（ffmpeg） | `python rotate_video.py` | ✅ |
| 分割（30s 边界 + 3GB 阈值） | `python split_video.py` | ✅ |
| HMD → MP4 命令行 | `node hmd2mp4.js` | ✅ |
| HMD 包验证 | `node verify_hmd_packets.js` | ✅ |

## ⚙️ 配置 / 列定义

| 能力 | 状态 |
|---|---|
| `config.json` 列定义（label/type/width/order） | ✅ |
| 运行时合并 DEFAULT_FIELDNAMES | ✅ |
| 列类型：input / select-yesno / select-feasibility / select-location / duration / path | ✅ |
| 列类型：select-dimension（待实现） | ❌ |
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
| Build 标记戳 | ✅ | console 首行 `[VideoSort] page loaded, build=...` |
| `/` 路由 no-cache | ✅ | `Cache-Control: no-cache, no-store, must-revalidate` |
| 缩略图缓存目录 | ✅ | `thumbnails/<sha1(path\|mtime)>.jpg`（git ignored） |

## 🧰 开发者工具

| 能力 | 状态 | 备注 |
|---|---|---|
| `打包备份.bat` / `pack.ps1` 一键打包 | ✅ | 输出 `video-sort-package_<ts>.zip` |
| 打包递归排除 `hmd_cache` / `node_modules` / `thumbnails` | ✅ | 1.4GB → 340KB |
| `verify_pages.py` 集成测试 | ✅ | 38 个端到端 case（启 Flask + curl 全套端点） |
| Build 标记戳（防浏览器缓存） | ✅ | console 首行输出 build 号 |
| `/` 路由 `Cache-Control: no-cache` | ✅ | dev 期间改 templates 立即生效 |