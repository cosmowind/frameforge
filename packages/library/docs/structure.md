# Structure — video-sort-package

> 模块职责映射 + 维护导航。完整目录树见 `docs/ARCHITECTURE.md`。
> 2026-06-24 更新：项目已从扁平结构重构为 `src/` 模块化架构。

---

## 源码模块职责（`src/`）

### 入口层

| 文件 | 职责 |
|---|---|
| `src/run.py` | Flask 应用启动入口 + 设备监控线程 |
| `src/launcher.py` | PyInstaller EXE 打包入口 |
| `src/app.py` | Flask 创建 + 蓝图注册 + auto-fill 路由（544 行） |
| `src/config.py` | 全局常量 & 路径配置（RUNTIME_DIR、CSV_PATH 等） |
| `src/device_monitor/` | 设备监控包（2026-07-02 拆分）：`scanner.py`（驱动器发现 319 行） + `copier.py`（文件复制 613 行） + `monitor.py`（主类 1282 行） |

### 路由层 (`src/routes/`)

> 9 个蓝图已注册并活跃使用（`app.py` 通过 `register_blueprint` 注册）。
> 2026-07-02 拆分：原 data_routes/upload_routes 拆出 3 个新蓝图（cleanup、upload_config、auto_upload）。

| 文件 | 职责 |
|---|---|
| `misc_routes.py` | 首页、favicon、统计、磁盘空间、目录选择、设备监控恢复 |
| `data_routes.py` | 数据 CRUD、扫描、配置、合并历史、删除记录（650 行） |
| `dim_routes.py` | 维表 CRUD、任务排序、翻译处理 |
| `video_routes.py` | 视频流、缩略图、帧提取、预热 |
| `hmd_routes.py` | HMD 处理、扫描、预览、队列管理 |
| `upload_routes.py` | 上传执行（generate/run/batch/status/cancel，387 行） |
| `cleanup_routes.py` | 缓存清理 + 预处理概览（`/api/clean-orphan-cache`、`/api/clean-uploaded-cache`、`/api/preprocess-overview`） |
| `upload_config_routes.py` | 上传模板配置 + 自动补录（`/api/upload-config`、`/api/upload-template*`、`/api/auto-fill*`） |
| `auto_upload_routes.py` | 自动上传 start/status/progress |
| `data_helpers.py` | data_routes 私有辅助函数（_extract_date_from_path、_auto_upsert_*） |

### 服务层 (`src/services/`)

| 文件 | 职责 |
|---|---|
| `lazy_loader.py` | 惰性导入 + 预处理共享状态（避免循环依赖） |
| `video.py` | 缩略图生成、视频帧提取、HMD 抽帧 |
| `preprocess_service.py` | HMD 预处理服务 |
| `scan_service.py` | 目录扫描、session 发现 |
| `upload_service.py` | SSE 批量上传、上传状态管理 |
| `data_service.py` | CSV 数据 CRUD |
| `dim_service.py` | 维表 CRUD、聚合查询 |
| `upload_options.py` | 上传表单选项加载 |
| `upload_config_service.py` | 上传配置 + 模板默认值 |
| `upload_execution_service.py` | 上传执行逻辑（run、cmd） |
| `scan_maintenance.py` | 历史合并 + 删除 + 缓存清理（从 scan_service 拆出） |

### 数据层 (`src/models/`)

| 文件 | 职责 |
|---|---|
| `csv_store.py` | CSV 读写 + 原子备份（10 份轮转） |
| `dim_registry.py` | 维表注册表 + CRUD 辅助函数 |

### 工具层 (`src/utils/`)

| 文件 | 职责 |
|---|---|
| `path_utils.py` | 路径安全处理、日期提取、缓存目录 |
| `format_utils.py` | 格式化（时长 mm:ss、文件日期） |
| `video_frames_helper.py` | MP4 视频帧提取辅助 |

### 离线工具 (`src/scripts/`)

> 独立运维脚本，从项目根目录执行（如 `python src/scripts/xxx.py`）。
> 2026-06-25 整理：根目录 4 个 Python 脚本 + 1 个 ps1 移入此处。

| 文件 | 用途 |
|---|---|
| `batch_preprocess.py` | 批量预处理符合条件的 HMD session（筛选：HMD+未上传+extra≠1） |
| `reprocess_incomplete.py` | 重处理所有缓存不完整的 HMD session |
| `rename_all.py` | 全量文件名迁移（6 步：源→缓存→文件→CSV→缩略图→状态） |
| `fix_duplicate_prefix.py` | 修复被重复添加设备ID前缀的文件夹名 |
| `preprocess_manager.py` | 预处理管理器（查看/重试/清理状态） |
| `rotate_video.py` | 视频旋转 CLI（ffmpeg） |
| `split_video.py` | 视频分割 CLI（30s 边界 + 3GB 阈值） |
| `diagnose_form.py` | 上传表单诊断 |
| `fix_video_durations.py` | 修复视频时长字段 |
| `check_hmd_cache.py` | HMD 缓存完整性检查 |
| `cleanup_duplicate_sessions.py` | 清理重复 session |
| `merge_hmd_directories.py` | 合并 HMD 目录 |
| `check_all_cache_integrity.py` | 全量缓存完整性检查 |
| `check_source_integrity.py` | 源文件完整性检查 |
| `check_routes.py` | 路由 & 函数清单检查 |
| `verify_pages.py` | 38 个端到端集成测试 |
| `test_flask_routes.py` / `test_flask_routes2.py` | Flask 集成测试 |
| `verify_auto_complete.js` | 自动补全 e2e 测试（Node.js） |
| `verify_sort.js` | 排序 e2e 测试（Node.js） |
| `reprocess_hmd.ps1` | 通过 Flask API 批量重处理 HMD（PowerShell） |
| 其余脚本 | `fix_data_sessions.py`、`fix_hmd_sessions.py`、`retry_failed_hmd.py`、`reprocess_hmd_to_h264.py`、`test_scan.py`、`test_upload.py`、`verify_scan_date_protection.py`、`_check_template.py` |

### 外部工具 (`src/tools/`)

> 2026-07-02 拆分：`hmd_fast_preprocess.py` → 包；`extract_scenario_taxonomy.py` → 数据分离。

| 文件 | 用途 |
|---|---|
| `hmd_preprocess.py` | HMD → MP4 完整预处理（splitStereo + ffmpeg，369 行） |
| `hmd_preprocess_ops.py` | HMD 预处理底层操作（路径、解码、转码，352 行） |
| `hmd_fast/` | HMD → h265 快速预处理包（`path_utils.py` + `media_ops.py` + `preprocess.py`） |
| `extract_scenario_taxonomy.py` | 场景分类解析（253 行） |
| `taxonomy_translations.py` | 场景翻译数据（559 + 72 + 337 + 6 条目，纯数据） |

### 调试脚本 (`scripts/debug/`)

> Playwright 自动补录功能的调试脚本。详见 `scripts/debug/README.md`。
> 2026-07-01 整理：从 `scripts/temp/` 迁移至此，补充分类文档。
> 2026-07-05 清理：上传页中文化调试产生的 79 个 `??` 未提交脚本（`fill_frameforge_form_v1..v8` / `inspect_*` / `dump_*` / `migrate_*` 等）全部清掉，仅保留历史已入库的 `temp_*.py`。

| 类别 | 脚本 | 调试目标 |
|------|------|---------|
| 流程调试 | `temp_autofill_flow.py` / `temp_autofill_test.py` / `temp_fill_test.py` | 补录流程、JS 注入、字段填充 |
| Ctrl+B 调试 | `temp_ctrlb_test.py` / `temp_ctrlb_test2.py` / `temp_test2.py` | 键盘快捷键触发补录 |
| 线上调试 | `temp_live_test.py` / `temp_live_test2.py` | 真实 publish.example.com 页面验证 |
| 点击调试 | `temp_click_test.py` | 视频 tile 展开交互 |

### 前端 (`src/templates/` + `src/static/`)

> 2026-07-02 模块化：index.html 7417→2293（CSS + 15 个 JS 模块分离）；新增 `src/static/css/` 和 `src/static/js/`。

| 文件 | 职责 |
|---|---|
| `src/templates/index.html` | 主单页前端（表格 + 预览 + HMD 面板 + 上传进度，2293 行） |
| `src/templates/hmd_preview.html` | 独立 HMD 预览页（155 行） |
| `src/static/css/index.css` | 全局样式（840 行） |
| `src/static/js/render-table.js` | 表格渲染 |
| `src/static/js/preview-player.js` | 视频预览播放器 |
| `src/static/js/hmd-progress.js` | HMD 预处理进度面板 |
| `src/static/js/hmd-inline-player.js` | HMD 立体播放器（HEVC 解码 + WebCodecs） |
| `src/static/js/upload-options-cache.js` | 上传选项缓存 + select-search 组件 |
| `src/static/js/dim-table-crud.js` | 维表 CRUD 渲染与交互 |
| `src/static/js/dim-write-ops.js` | 维表写操作（add/save/copy/delete） |
| `src/static/js/task-validation.js` | 任务行校验、自动排序、翻译 |
| `src/static/js/task-wizard.js` | 任务向导 + 批量任务创建 |
| `src/static/js/translate-functions.js` | 翻译处理（工序/环境描述） |
| `src/static/js/statistics-page.js` | 统计页渲染 |
| `src/static/js/settings-page.js` | 设置页逻辑 |
| `src/static/js/shared-filters.js` | 跨页筛选器 |
| `src/static/js/gallery-view.js` | 画廊视图（网格 + 懒加载 + 帧预览） |
| `src/static/js/gallery-editor.js` | 画廊编辑表单 + 上传模板 |
| `src/static/js/auto-upload.js` | 批量自动上传轮询 |
| `src/static/js/export-upload-dialogs.js` | 导出/上传对话框 |
| `src/static/hmd/hmd-decode.esm.js` | 浏览器端 HMD 解析器（ESM） |
| `src/static/hmd/hmd-decode.cjs` | CJS 桥接（Node.js 端 import() → .esm.js） |
| `src/static/hmd/hmd-player-core.js` | WebCodecs 播放封装 |

---

## 运行时数据 (`runtime/`)

> Git ignored。所有运行时产物统一在此。

| 子目录 | 内容 |
|---|---|
| `runtime/data/` | 持久状态：`video_manager.csv`, `config.json`, `upload_state.json` 等 |
| `runtime/thumbnails/` | 缩略图缓存（*.jpg + *.fp 指纹） |
| `runtime/hmd_cache/` | HMD 预处理产物（h265/mp4/jpg） |
| `runtime/csv_backups/` | CSV 10 份轮转备份 |
| `runtime/logs/` | 运行日志 |
| `runtime/browser_data/` | Chrome 持久化用户数据（cookie/session） |
| `runtime/archive/` | 历史数据归档 |

---

## 维护导航

- **改后端逻辑** → `src/app.py` + `src/services/*.py` + `docs/error_book.md`
- **改前端 UI** → `src/templates/index.html` + `docs/features.md`
- **改 HMD 解析** → `src/static/hmd/*` + `src/templates/hmd_preview.html`
- **改上传器** → `src/auto_upload.py` + `src/vendor-upload-pkg/`
- **改设备监控** → `src/device_monitor.py` + `src/copy_progress_window.py`
- **改预处理流程** → `src/tools/hmd_fast_preprocess.py` + `src/run.py`（磁盘检查/启动决策）
- **批量运维** → `src/scripts/batch_preprocess.py` / `reprocess_incomplete.py` / `rename_all.py`
- **诊断修复** → `src/scripts/diagnose_form.py` / `fix_duplicate_prefix.py` / `check_hmd_cache.py`
- **查文件路径/生命周期** → `docs/file-lifecycle.md`
- **完整目录树** → `docs/ARCHITECTURE.md`

---

## 关键约定

- **原子写**：`csv_store.py` 自动备份 10 份 + `os.replace` 原子替换
- **路径**：Windows 风格；前端需 `encodeURIComponent`
- **编码**：所有 CSV / JSON 用 UTF-8 with BOM（`utf-8-sig`）
- **配置分离**：`runtime/data/` 存放用户数据，`src/config.py` 存放代码常量
- **HEVC 帧率**：HMD 假设 30 fps 恒定（容器不携带）
- **循环依赖**：`services/lazy_loader.py` 作为共享基础层解决