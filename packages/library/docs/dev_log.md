# Dev Log — video-sort-package

> 实现记录 + 验证依据 + 学习复盘。每次提交或重大变更后追加。

格式：`## YYYY-MM-DD — <标题>` + 变更点 + 验证 + 回滚说明。

---

## 2026-07-03 — 业务类型/名称值更新为中文

**变更点**：

1. **tasks 维表 `business_type` 值中文化**
   - `sanitary ware production` → `卫浴生产`
   - `Handicraft production` → `手工艺品生产`
   - `eyewear industry` → `眼镜服务`
   - `food production` → `食品加工`

2. **tasks 维表 `business_name` 值中文化**
   - `Domestic Sanitary` → `示例卫浴`
   - `示例县 Small Shop` → `示例小卖部`
   - `restaurant kitchen` → `餐厅后厨`

3. **空白记录补值**
   - `742d_ddd7e97e_7de5_001`（淋雨龙头）、`ba1e_d8a0724f_908b_001`（洗面盆龙头）
   - `business_type` → `卫浴生产`，`business_name` → `示例卫浴`

4. **`dimEditableOptions` 配置同步更新**
   - `config.json` 中 `dimEditableOptions.business_type` 和 `.business_name` 更新为中文 label/value
   - 维表下拉选项 UI 同步显示中文

5. **Bug fix: `pg_dim.atomic_write_dim` 同步写 CSV**
   - `USE_PG=True` 时，`dimSaveOne` / `dimSaveDirtyRows` 调用 `atomic_write_dim` 只写 PG，不写 CSV
   - `dimReload` 读取时因缓存未失效或 CSV 不同步，导致刷新后值被重置
   - 修复：在 `pg_dim.atomic_write_dim` 中，PG 写入后调用 `_atomic_write_csv` 同步 CSV
   - 影响范围：所有维表（tasks / recorders / sd_cards / environments）的增删改保存

**验证**：
- 增删改任一维表后刷新页面，数据保持不变
- PG rows 与 CSV rows 数量一致，`business_type` / `business_name` 等字段值相同

**验证**：
- 查询 `business_type` 唯一值：`['手工艺品生产', '卫浴生产', '眼镜服务', '食品加工']`
- 查询 `business_name` 唯一值：`['示例小卖部', '示例卫浴', '餐厅后厨']`
- 无空白 `business_type` / `business_name` 记录

**⚠️ 不要恢复的字段值**：
英文值已废弃，中文值为唯一正确值。恢复英文会导致维表值与下拉选项 UI 不一致。

---

## 2026-07-03 — 维表 UI 搜索化 + 废弃字段归档

**变更点**：

1. **所有 `select` 类型字段改为可搜索下拉**
   - `src/templates/index.html` 中 `dimRenderTable` 的 `type: 'select'` 和 `type: 'select-editable'` 分支
   - 复用 `searchable-sel` 组件（`ssOpen`/`ssFilter`/`ssKeyNav`），无需新增 JS 逻辑
   - `uid` 格式改为 `ss-${name}-${fn}-${safeKey}`，避免同行不同字段 uid 冲突

2. **视频管理页面 `select-dimension` 列（录入员/设备/任务/环境）改为可搜索下拉**
   - `src/static/js/render-table.js` 中 `select-dimension` 分支改为 `searchable-sel` 结构
   - `ssSelect` 新增 `window._ssOpts[uid].onSelect` 回调机制，替代 `dimRowInput` 隐式调用

3. **废弃字段归档（不可恢复）**
   - `process_en`（tasks 表单）→ 加入 `_DIM_UI_HIDDEN.tasks`，整列隐藏
   - `environment_description_en`（environments 表单）→ 加入 `_DIM_UI_HIDDEN.environments`，整列隐藏
   - 工具栏「🌐 翻译工序」「🌐 翻译描述」按钮已删除
   - `translate-functions.js` 精简为 API 调用注释归档
   - 后端翻译路由和 `dim_service.py` 翻译逻辑保留（可单独归档/删除）
   - `config.py` 新增 MiniMax API 配置项（`_MINIMAX_API_KEY` 等），用于 `dim_service.py` 翻译

4. **Bug 修复**
   - `dim_routes.py` 补充缺失的 `CONFIG_PATH` 导入
   - `dimReload` 中增加 `await loadEditableOpts()` 确保下拉选项在渲染前已加载

**验证**：
- 重启 Flask，访问 tasks/recorders/environments 维表页，下拉字段可直接输入搜索
- 视频管理页录入员/设备/任务/环境列可正常输入搜索
- `process_en` 和 `environment_description_en` 列不显示

**⚠️ 不要恢复的字段**：
```
_DIM_UI_HIDDEN.tasks:   ['process_en', ...]
_DIM_UI_HIDDEN.environments: ['environment_description_en']
```
这些字段已废弃，数据仍存储在后端，但 UI 不再显示。恢复以上配置会导致废弃字段重新可见。

---

## 2026-07-01 — app.py 大规模重构（5077→544 行）

**变更点**：
- app.py 从 5077 行精简到 544 行，恢复到 cdabc31 重构后的状态
- 删除 app.py 中 44 个重复路由 handler（已由 6 个 blueprint 处理）
- 删除只被这些路由使用的 helper 函数（~4500 行）
- 补充 upload_routes.py 缺失的 `/api/upload-options` 路由装饰器
- 保留 10 个 auto-fill/dim/translate 路由在 app.py 中

**背景**：
- cdabc31 曾做过大规模重构（app.py 从 5561→544 行），但后续提交又把代码加回了 app.py
- 6 个 blueprint 文件（misc/data/dim/video/hmd/upload）一直存在且有完整实现
- 本次重构是恢复正确的架构状态，不是新建架构

**验证**：
- `python -c "import app"` 成功加载
- 73 个唯一路由全部注册（含 /api/upload-options）
- 所有 blueprint 路由正常工作

**回滚**：
- `git revert HEAD` 可回滚到 5077 行版本

**变更**：

1. **环境维度表单 environment 字段**（`src/templates/index.html`）：
   - options 从纯字符串数组改为 `{value, label}` 对象格式，支持双语显示
   - 下拉框显示 `English - 中文` 格式（如 `Retail and Consumer Goods - 零售和消费品`）
   - 存入数据库的 value 保持纯英文，不影响历史数据
   - 4 个已满（Full）选项标签带 `⚠️已满，请勿选择` 警告：Home、Factory、Administrative、Administrative & Office Services

2. **select 渲染逻辑**（`src/templates/index.html`）：
   - `spec.type === 'select'` 分支增加 `{value, label}` 对象支持
   - 对象格式：value 存数据，label 显示文本；纯字符串格式保持原有行为不变

3. **上传表单 environments 枚举**（`src/services/upload_options.py`）：
   - `environments` 列表同步更新为最新 27 个选项
   - label 改为双语格式 `English - 中文`
   - 已满选项 value 恢复原始值（如 `Home`），warning 仅在 label 中

**选项来源**：`docs/开发历史文档/提交页面参考/environment-elements.txt`（上游下拉框 HTML 快照）

**验证**：两处文件均已检查修改正确；select 渲染逻辑向后兼容纯字符串 options。

**回滚**：`git revert` 本次提交即可。

---

## 2026-06-30 — 默认筛选本地视频 + 缩略图缓存 + dim_routes 修复

**变更**：

1. **默认筛选本地视频**（`src/templates/index.html`）：
   - 页面加载后自动选中 `location_status=local`，只显示本地存在的视频
   - 减少首次加载噪音（已上传/历史视频默认隐藏）

2. **缩略图/帧预览 Cache-Control**（`src/app.py` + `src/routes/video_routes.py`）：
   - 缩略图响应头加 `Cache-Control: max-age=86400`（1天有效）
   - 消除浏览器 304 轮询，画廊/表格缩略图加载显著提速

3. **fix: upload_routes.py import sys**（`src/routes/upload_routes.py`）：
   - `/api/upload-run-cmd` 端点缺少 `import sys` 导致 500
   - 补充导入后端点正常工作

4. **dim_routes.py 路由装饰器补全**（`src/routes/dim_routes.py`）：
   - 4 个函数缺少 `@bp.route()` 装饰器导致 404：
     - `dim_editable_options` → `GET/POST /api/dim-editable-options`
     - `environments_next_id` → `POST /api/dim/environments/next-id`
     - `tasks_reorder` → `POST /api/dim/tasks/reorder`
     - `translate_single_process` → `POST /api/translate-process`
   - `tasks_next_id` 响应格式改为 `{ok, suggested, reason}`

5. **tasks 自动排序功能**（`src/templates/index.html`）：
   - 原「⇅ 排序」按钮改为「⇅ 自动排序 ✓」toggle 开关
   - 默认开启，状态持久化到 `localStorage.tasksAutoSort`
   - 开启时：维表加载后自动按 产品→任务→工具 排序 + 批量保存后重新排序
   - 排序结果自动调 `/api/dim/tasks/reorder` 回写 CSV
   - 关闭时可手动触发排序

6. **CV 手部识别项目规划**（`docs/cv-hand-recognition-plan.md`）：
   - 新文档：利用 214 个标注视频训练手部识别模型的完整方案
   - 含可行性评估、技术路线（MediaPipe + EfficientNet）、实施阶段、训练所需信息

**验证**：所有修改文件语法检查通过；`@bp.route` 补全后 4 个端点正常响应 200。

**回滚**：`git revert` 本次提交即可。

---

## 2026-06-30 — 全面迁移 PostgreSQL 云数据库 + source_device 来源追踪

**背景**：项目原本以本地 CSV 为唯一数据源，维表路由重构（cdabc31）后 GET/POST handler 丢失原始逻辑，且 `config.py` 未调用 `load_dotenv()` 导致 `USE_PG` 始终为 False，应用实际一直在用 CSV。

**变更**：

1. **config.py 自动加载 .env**：
   - 顶部新增 `load_dotenv()`，启动即读取 `VIDEO_MANAGER_DB_DSN`
   - 新增 `SOURCE_DEVICE` 常量（自动取 `socket.gethostname()`，可通过环境变量覆盖）
   - `DEFAULT_FIELDNAMES` 新增 `source_device` 字段
   - `UPLOAD_TEMPLATE_LABELS` 新增 `source_device` 标签

2. **dim_routes.py GET/POST handler 修复**：
   - GET：`jsonify(rows)` → 返回 `{name, schema, key, rows, count, migrated}` 包装格式
   - POST：从 `body.get("row")` 提取数据，支持 mode（insert/update/upsert）、主键改名、自动翻译
   - DELETE：补充路径遍历防护

3. **pg_dim.py 双重修复**：
   - `_DIM_TABLE_MAP` 拆分为 `_KEY_TO_TABLE`（主键字段名→表名）和 `_NAME_TO_TABLE`（维度名→表名）
   - `logger = __name__` → `logging.getLogger(__name__)`

4. **全面切换 CSV → PG**（14 个文件）：
   - `dim_service.py`、`autofill_service.py`、`video.py`、`lazy_loader.py`、`preprocess_service.py`、`data_service.py`、`scan_service.py` — 条件导入 PG/CSV
   - `upload_routes.py`、`data_routes.py`、`hmd_routes.py`、`misc_routes.py` — 路由层条件导入
   - `app.py`、`run.py` — 内联导入修复

5. **source_device 来源设备追踪**：
   - PG `videos` 表新增 `source_device` 列
   - 已有 140 条记录回填"示例办公电脑"
   - 扫描新视频时自动写入本机 hostname
   - 上传模板（`auto_upload.py` FILL_ORDER + `_build_template_from_row`）加入 `source_device`

6. **数据导入**：
   - 示例 CSV（140 条）覆盖写入 PG，`source_device = "示例办公电脑"`
   - 本地 74 条视频扫描入库，`source_device = "qd"`
   - PG 总计 214 条视频

**验证**：
- `USE_PG = True` 自动生效
- 维表读取：recorders 12 / sd_cards 4 / tasks 93 / environments 19
- 视频表：214 条（示例 140 + QD 74）
- 所有模块导入成功，无报错

**回滚**：将各文件 `if USE_PG:` 分支改回 `else:` 分支；`config.py` 删除 `load_dotenv()` 调用。

---

## 2026-06-30 — 服务端内存缓存层（减少 PG 重复查询）

**背景**：PG 全面上线后，每次 API 读请求都直接 `SELECT * FROM videos`，`NullPool` 无连接复用，`_is_registered_video_path()` 每次缩略图请求全表扫描。需要在前端和 PG 之间加缓冲层。

**变更**：

1. **新建 `src/models/cache.py`**（缓存层核心）：
   - 视频列表缓存：30s TTL，写操作自动失效，线程安全（double-check locking）
   - 路径查找索引：`set[str]`，O(1) 路径校验，随视频缓存自动重建
   - 维表缓存：60s TTL，写操作自动失效
   - TTL 可通过环境变量 `CACHE_TTL` / `DIM_CACHE_TTL` 调整

2. **pg_store.py**：
   - `read_csv()` 改为走 `cache.get_videos()`，过期自动查 PG
   - `write_csv()` 写前调 `cache.invalidate_videos()`

3. **pg_dim.py**：
   - `read_dim_rows()` 改为走 `cache.get_dim()`，过期自动查 PG
   - `atomic_write_dim()` 写前调 `cache.invalidate_dim(table)`

4. **video.py**：
   - `_is_registered_video_path()` 优先走 `cache.is_registered_path()` O(1) 索引
   - 缓存未就绪时回退全表扫描（首次调用场景）

5. **autofill_service.py**：
   - 移除私有 `_CACHE`，统一使用缓存层
   - `invalidate_cache()` 委托给 `cache.invalidate_dim()`

**验证**：
- 所有修改文件 `py_compile` 语法检查通过
- `cache.py` 模块导入测试通过

**效果**：
- 连续刷新页面 10 次 → PG 查询从 ~10 次降到 ~1 次
- 3 秒自动刷新 → `preprocess-overview` 也受益于缓存
- 缩略图请求 → 路径校验从 O(n) 降到 O(1)

**回滚**：删除 `cache.py`；各文件恢复直接调用 `read_csv()` / `read_dim_rows()`。

---

## 2026-06-30 — 「任务总时长」任务列改为工序中文名

**变更**：

1. **统计页三张表格「任务」列显示工序中文名**（`src/templates/index.html`）：
   - 任务总时长：`esc(t.task_id)` → `esc(t.process || t.task_id)`，tooltip 显示 `product / task_id`
   - 任务 × 环境总时长：同上，tooltip 显示 `task_id`
   - 操作员 × 任务 × 环境：同上
   
2. **后端数据补齐 `process` 字段**（`src/app.py` + `src/routes/misc_routes.py`）：
   - `te_stats` 和 `ote_stats` 输出新增 `"process": tinfo.get("process", "")`

**验证**：前后端 lint 零错误。

**回滚**：前端恢复 `esc(t.task_id)` → 后端移除新增的 `"process"` 字段。

---

## 2026-06-30 — 预处理按钮智能跳过 + 防重复启动

**变更**：

1. **预处理跳过已上传/历史视频**（`src/services/preprocess_service.py` + `src/app.py`）：
   - `auto_warm_all()` / `_auto_warm_all()` 新增过滤规则，遵循文件生命周期：
     - `uploaded = "Yes"` → 跳过（已上传，无需预览用预处理）
     - `location_status = "history"` → 跳过（源文件已删除，无法预处理）
     - HMD 源目录不存在或无 `part_*.hmd` → 跳过
   - `get_preprocess_overview()` 返回的 items 新增 `uploaded`、`location_status` 字段供前端过滤

2. **防重复启动接口**（`src/app.py`）：
   - 新增 `GET /api/hmd/is-processing`：返回 fast/full 预处理队列状态
   - 前端「全部预热」按钮点击前先检查，若已有任务 → 提示"预处理任务正在进行中，请勿重复启动"

3. **前端过滤逻辑**（`src/templates/index.html`）：
   - `startWarmAll()`：先调 `is-processing` 检查；过滤 `uploaded=Yes` + `location_status=history`
   - `generateAllFrames()`：同样过滤已上传和历史视频，只处理本地存在的新视频

**验证**：前后端 lint 零错误；`GET /api/hmd/is-processing` 返回正确队列状态。

**回滚**：删除 `is-processing` 端点 → 恢复 `startWarmAll`/`generateAllFrames` 旧过滤 → 删除 `auto_warm_all` 中 upload/location_status 判断。

---

## 2026-06-29 — 流水线 inflight 超时 + 扫描路径归一化修复 + 上传参数校验

**变更**：

1. **流水线上传 inflight 超时**（`src/auto_upload.py`）：
   - 批量上传流水线 `while active:` 循环无单视频超时 → 一个视频卡在 inflight 就永久堵死队列
   - 新增 `MAX_INFLIGHT_SEC = 600`（10分钟），超时后强制标记失败并释放队列
   - `active` 条目新增 `flight_start` 时间戳；状态日志显示 `session_name(已等N秒)` 便于诊断
   - `_wait_for_batch_sessions()` 同样加 per-session inflight 超时（`inflight_since` 字典追踪）

2. **扫描路径归一化修复**（`src/app.py`）：
   - `existing_map` key 被归一化为小写正斜杠 `/media/...`，但后续比较用原始 `u["folder"]` = `/media\...` → 大小写/斜杠不匹配
   - 导致：已预处理视频被当成"新的"产生重复行；`duration_sec` 永远不更新（status 文件有 3551s，CSV 仍为 187s）
   - 修复 4 处：`hmd_set`/`data_set` 构建、`existing_map` 查找、`_existing_before_scan_set` 判断，全部统一 `_norm()` 归一化

3. **上传选中视频参数校验**（`src/app.py` + `src/templates/index.html`）：
   - 前端 checkbox 新增 `data-recorder-id` / `data-task-id` / `data-env-id` 属性
   - `runUploadSelected()` 提交前校验三个关键字段，缺失时弹窗列出具体行号
   - 后端 `POST /api/auto-upload-start` 同样校验，返回 400 + `details` 列表（权威网关）

**验证**：lint 零错误；3 个关键字段全空/部分空均有正确告警提示。

**回滚**：恢复流水线循环无超时 → 恢复路径比较用原始路径 → 删除前后端校验代码。

---

## 2026-06-25 — 根目录运行时文件迁移到 runtime/ + 路径统一

**变更**：

1. **运行时目录归位**（3 项）：
   - `browser_data/` → `runtime/browser_data/`（Chrome 持久化用户数据）
   - `logs/auto_upload_*.log` → `runtime/logs/`（上传日志），删除空 `logs/`
   - `video-sort-package_20260625_231604.zip` → 删除（可重新打包）

2. **代码路径统一修复**（7 个文件）：
   - `src/auto_upload.py`：`BROWSER_DATA_DIR` → `runtime/browser_data`，`LOG_DIR` → `runtime/logs`
   - `src/tools/sniff_upload_form.py`：`browser_data` → `runtime/browser_data`，`browser_data_fresh` → `runtime/browser_data_fresh`
   - `src/tools/scrape_scene_live.py`：修复硬编码路径 `browser_data` → `runtime/browser_data`，`tools/` → `src/tools/`
   - `src/scripts/diagnose_form.py`：修复 `BASE_DIR`（1 层→3 层到项目根）+ 路径指向 `runtime/browser_data`
   - `src/services/upload_service.py`：`logs` → `runtime/logs`
   - `src/tools/extract_upload_full.py`：`browser_data_temp` → `runtime/browser_data_temp`

3. **`.gitignore`**：移除根目录 `browser_data/` 条目（已在 `runtime/browser_data/` 覆盖）

**验证**：根目录仅保留入口文件（`.bat`/`.ps1`/`.spec`/`README.md`/`requirements.txt`）；`browser_data` 和 `logs` 均在 `runtime/` 下。

**回滚**：移回文件并还原各路径引用。

---

## 2026-06-25 — 根目录脚本归档到 src/scripts/ + 文档同步更新

**变更**：

1. **根目录脚本移入 `src/scripts/`**（5 个文件）：
   - `batch_preprocess.py` → `src/scripts/batch_preprocess.py`（批量预处理 HMD）
   - `fix_duplicate_prefix.py` → `src/scripts/fix_duplicate_prefix.py`（修复重复设备ID前缀）
   - `rename_all.py` → `src/scripts/rename_all.py`（全量文件名迁移）
   - `reprocess_incomplete.py` → `src/scripts/reprocess_incomplete.py`（重处理不完整缓存）
   - `reprocess_hmd.ps1` → `src/scripts/reprocess_hmd.ps1`（PowerShell 批量重处理）

2. **路径修复**（适配新位置）：
   - `batch_preprocess.py` / `fix_duplicate_prefix.py` / `reprocess_incomplete.py`：`ROOT_DIR` 改为三层 `os.path.dirname` 定位项目根目录
   - `reprocess_hmd.ps1`：CSV 路径改为通过 `$MyInvocation` 动态定位项目根 → `runtime/data/video_manager.csv`

3. **文档同步更新**（6 个文件）：
   - `README.md`：重写"目录结构"章节（从旧扁平结构 → 新 `src/` 模块化）；新增"独立运维脚本"速查表；修复 `run.py` → `src/run.py` 等过时路径
   - `docs/structure.md`：重写"离线工具"表格（包含全部 24 个脚本 + 说明）；新增"批量运维"/"诊断修复"维护导航
   - `docs/ARCHITECTURE.md`：移除根目录 `reprocess_hmd.ps1`；脚本数 16→24
   - `docs/features.md`：修复 CLI 入口路径
   - `docs/project_status.md`：新增 3 个离线工具条目
   - `docs/dev_log.md`：本记录

**验证**：git status 干净（5 个 rename + 6 个 modify）；根目录仅保留入口 `.bat`、`pack.ps1`、`.spec`、`requirements.txt`、`README.md`。

**回滚**：`git revert` 后恢复 5 个文件到根目录 + 删 `src/scripts/` 下对应文件。

---

## 2026-06-25 — 清除已上传缓存重构 + 日期前缀命名

**变更**：

1. **清除已上传视频源文件重构**（`src/app.py`）：
   - 拆分为三个函数：`_scan_uploaded_cache()`（预览扫描）、`_execute_clean_uploaded_cache()`（执行删除）、`clean_uploaded_cache()`（端点入口）
   - **修复误删 bug**：改为严格按 `os.path.normpath` 精确路径匹配删除，不再按文件名匹配（之前可能误删未上传的同名文件）
   - **新增 preview 模式**：端点 `POST /api/clean-uploaded-cache` 支持 `mode: "preview"|"execute"`（默认 preview）
   - **三重安全过滤**：扫描、执行、端点入口三层均过滤 `uploaded == "Yes"`（大小写不敏感）

2. **前端预览确认弹窗**（`src/templates/index.html`）：
   - 新增 `#cleanCachePreviewDialog` 模态框，展示汇总统计（各类型文件数、总大小）和每条已上传视频的详细文件列表（CSV 行号、路径、类型、大小、存在状态）
   - 两阶段操作流程：`cleanUploadedCache()` 先 preview → 用户确认 → `executeCleanUploadedCache()` 执行删除
   - 执行期间按钮禁用防重复点击

3. **日期前缀（≥0623）重命名**（`src/utils/path_utils.py` + `src/app.py` + `src/services/scan_service.py` + `src/device_monitor.py`）：
   - 新增 `extract_mmdd_from_path()`：从路径提取合法 MMDD（01-12月, 01-31日）
   - 新增 `should_add_date_prefix(path, cutoff="0623")`：判断是否应加时间前缀
   - 三个入口（app.py 扫描、scan_service.py 扫描、device_monitor.py 设备监听）统一逻辑：
     - 0623 之前的视频：`{device_id_short}_{session_name}`（如 `f83c30_session_00007`）
     - 0623 及以后的视频：`{mmdd}_{device_id_short}_{session_name}`（如 `0625_f83c30_session_00007`）

**验证**：所有 4 个修改文件 lint 零错误；preview/execute 两阶段端点 curl 测试通过。

**回滚**：恢复 `clean-uploaded-cache` 为旧单阶段实现 + 删除 `extract_mmdd_from_path` / `should_add_date_prefix` + 恢复三处重命名逻辑。

---

## 2026-06-25 — 前端逐行自动保存（脏行跟踪）

**变更**：

1. **后端新增 `POST /api/save-rows` 端点**（`src/app.py`）：
   - 接收 `{"rows": [row1, row2, ...]}`，以 `path` 为主键匹配已有行
   - 匹配到 → 更新；未匹配 → 追加
   - 单次原子写入，避免并发覆盖；保护 `scan_date` 不被误清空

2. **前端改用脏行追踪 + 独立行保存**（`src/templates/index.html`）：
   - 新增 `dirtyRows` (Set) 追踪未保存的行索引
   - `markRowDirty(idx)` 标记脏行 → 触发 800ms 防抖
   - `saveDirtyRows()` 收集所有脏行 → `POST /api/save-rows` 仅发送变更行
   - 保存失败自动回标脏行，下次继续尝试
   - 所有编辑入口（表格、预览表单、画廊编辑器、Ctrl+Z 撤销）统一适配
   - `saveAll()` / Ctrl+S 保留不变，成功后清空 `dirtyRows`

**对比**：
- 之前：编辑 → 800ms → `POST /api/save`（全表发送，~1000行）
- 现在：编辑 → 800ms → `POST /api/save-rows`（仅发送变更的 1~N 行）

**验证**：前后端 lint 通过；`saveTimer` → `autoSaveTimer` 重命名无残留；3 处 `scheduleAutoSave()` 调用全部更新。

**回滚**：恢复 `scheduleAutoSave` → `saveAll(true)` → 删除 `/api/save-rows` 端点。

---

## 2026-06-24 — 项目精简 + 启动磁盘检查 + .h265 自动清理

**变更**：

1. **删除冗余代码**（不影响核心业务）：
   - `src/routes/` 全部 6 个文件 → 蓝图已拆分但 app.py 从未注册，纯死代码
   - `src/scripts/batch_preprocess.py` → 已被 `hmd_fast_preprocess.py` 异步管线取代
   - `src/scripts/batch_preprocess_fast.py` → 同上
   - `src/scripts/batch_preprocess_all.py` → 同上
   - `src/scripts/run_preprocess.py` → 同上
   - `src/scripts/start_preprocess.py` → 同上（且 CSV 路径硬编码错误）

2. **启动时磁盘空间检查**（`src/run.py`）：
   - 启动前扫描所有未预处理 HMD session 源文件大小
   - 预估预处理需要约 2x 源文件空间（.h265 + .mp4 + 预览帧 + 封面）
   - 空间不足时提示用户并询问是否开启自动预处理（默认 N）
   - 通过 `AUTO_PREPROCESS_ENABLED` 环境变量传递决策给 `app.py`

3. **.h265 自动清理以节省磁盘空间**（`src/tools/hmd_fast_preprocess.py`）：
   - `_do_stage2()`: Stage 2 完成后，若 mp4 已就绪 + 预览帧完整 + 封面已生成 → 删除 left.h265
   - `process_fast()`: 同步入口同样在完成后清理
   - `check_fast_done()`: 更新判定逻辑 — 接受 "mp4 存在但 h265 已清理" 为有效完成状态
   - 节省空间：每个 session 约节省源文件 50%（.h265 与 .mp4 大小相当）

4. **app.py 启动自动预热恢复**：
   - 根据 `AUTO_PREPROCESS_ENABLED` 环境变量决定是否启动 `_startup_auto_warm`
   - 扫描后的 `_auto_warm_all` 同样受环境变量控制
   - 磁盘充足时自动开启，不足时跳过

**验证**：所有 lint 检查通过；无已删除文件引用残留；`check_fast_done` 兼容 h265 已清理场景。

**回滚**：恢复 env var 检查逻辑 → 删除 h265 清理代码 → 恢复 `check_fast_done` 原逻辑。

---

## 2026-06-25 — 工序翻译按钮 + 维表 onblur 自动保存

**变更**：

1. **单行工序翻译按钮**（`src/app.py` + `src/templates/index.html`）：
   - 新增 `POST /api/translate-process` 端点，接收 `{ text: str }`，调用 Google 翻译返回 `{ result: str }`
   - 维表 tasks 的 `process_en` 列前加 🔄 按钮，点击后取当前行 `process` 值调用翻译 API，结果填入 `process_en`
   - 翻译时按钮显示 ⏳ 加载态，失败/空结果 toast 提示

2. **维表输入框失焦自动保存**（`src/templates/index.html`）：
   - 新增 `dimRowBlur(name, input)` 函数，400ms 防抖后调用 `dimSaveOne` 仅保存当前行
   - 所有维表输入控件绑定 `onblur`：文本、数字、下拉框、可搜索下拉、select-editable
   - 只保存标记为 dirty 的行，避免无效保存
   - 翻译按钮填值后直接调 `dimRowInput` 标记 dirty，配合 blur 机制可自动保存翻译结果

**依赖**：`deep_translator` (GoogleTranslator)，需科学上网才能正常翻译。

**验证**：前后端 lint 通过；翻译按钮有 VPN 时正常返回结果；blur 后行自动保存到 CSV。

**回滚**：删除 `/api/translate-process` 端点 → 删除 `process_en` 列渲染特殊处理 → 删除所有 `onblur` → 删除 `dimRowBlur`。

---

---

## 2026-06-17 — WCS v2.0 文档基线建立

**变更**：
- 新建 `wcs-manifest.yaml`（中央索引）
- 新建 `docs/{project_status, structure, dev_plan, dev_log, error_book, features, CODING_STANDARDS, workflow}.md`（10 项基线）
- README.md 已存在，跳过新建；`docs/prompt.txt` 已存在，归档

**验证**：通过 `Read` 工具确认所有文件可加载；manifest 与 docs 路径一致。

**回滚**：删除 `wcs-manifest.yaml` + 新建 docs/*.md 即可回到无 WCS 状态。

---

## 2026-06-17 — 播放速度 1× / 5× / 10× / 16×

**变更**：
- `templates/index.html` 新增 `hmdRate` 变量 + `primeHmdDecoders` 改为 rate-gated
- 用 `hmdFrameDebtL/R` 累积欠帧数，每 RAF tick 按 `30 * rate / 60` 喂入
- 4 个按钮 `1× / 5× / 10× / 16×`（active 蓝色高亮）
- seek 跳帧时清零 debt（避免跳完爆发）

**验证**：Node.js `node --input-type=module --check` 通过；用户确认可用。

**回滚**：删除 `.hmd-rate-btn` HTML 和 `hmdRate`/`primeHmdDecoders` 重写即可。

---

## 2026-06-17 — 扫描 scope=current（不再扩散）

**变更**：
- `app.py` `/api/scan` 加 `scope` 参数（默认 `current`）
- `scope=current` 仅返回 + 持久化当前目录下 + 今天新加的行
- `scope=all` 旧行为（保留历史）
- 旧 CSV 中 `图片/*` 等无关行被扫描 codec-hmd 时驱逐

**验证**：curl 测试两个 scope 都正确；CSV 写入 + 返回同步。

**回滚**：改 default 为 `"all"` 即可。

---

## 2026-06-17 — 表格预览按钮支持 HMD

**变更**：
- `templates/index.html` `preview(index)` 加路由：`file_type === 'hmd'` 时调 `openHmdPreviewInline(folder)` 而非弹新窗口
- 删除 toolbar 的 `📦 扫描HMD` / `🎬 HMD预览` 按钮
- 删除 `#hmdScannerDialog` + 对应 JS 函数（`openHmdScannerDialog`/`closeHmdScannerDialog`/`hmdScanDirPick`/`hmdScanDirRun`/`toggleHmdPanel`）
- 删除 `.hmd-session-row` 未用 CSS

**验证**：表格预览图标点击 HMD 行直接展开内嵌双 canvas；MP4 行继续用 `<video>`。

**回滚**：恢复 toolbar 按钮 + dialog 即可。

---

## 2026-06-17 — HMD 预览嵌入主页

**变更**：
- 在 `templates/index.html` 加 `#hmdPanel` 内嵌区块（双 canvas + 控件条）
- `openHmdPreviewInline()` 流程：info → 下载 parts → parse → splitStereo → setup decoder → prime → play
- 删除顶部 toolbar 的 `🎥 HMD 双目预览` 跳转链接

**验证**：浏览器内嵌双 canvas 播放；可在主表格内联修改元数据。

---

## 2026-06-17 — IDR keyframe required 修复

**变更**（`templates/hmd_preview.html` + `templates/index.html`）：
- `frameToChunks` 返回 `{nals, firstIdr}` 而不是只 `nals`
- `primeDecoders` 前设 `state.leftIdx = state.leftFirstIdr`
- seek handler 从 `input` 改 `change`（拖动结束才触发）
- seek 时 `setupDecoders()` + 找最近 IDR + 从 0 喂到 IDR
- `feedFrame` 时间戳从 `0` 改为 `frameIdx * dur`（单调递增）

**验证**：Node `node --input-type=module --check` 通过；session_00000 leftFirstIdr=86、rightFirstIdr=172 字节偏移。

---

## 2026-06-16 — HMD 集成第一阶段

**变更**：
- `static/hmd/hmd-decode.esm.js`（从 codec-hmd 复制 6.6KB）
- `static/hmd/hmd-player-core.js`（13KB，新 ESM 模块，封装 `openHmdSession`）
- `app.py` 加 6 个 HMD 端点（scan / info / raw / file / duration / register）
- `templates/hmd_preview.html` 独立预览页（4 阶段进度 + 双 canvas + splitStereo）
- `config.json` 13→20 列扩展（file_type / session_path / device_id / recorder_id / task_id / task_name / recorded_duration_sec）
- `app.py` `DEFAULT_FIELDNAMES` 13→20；`get_fieldnames()` 合并 DEFAULT

**验证**：curl 全套端点（200 OK）；CSV 写入 20 列；Node 解析 session_00000 得到 588 IDR + 17040 P 帧。

---

## 2026-06-16 — CSV 清理（手测）

**变更**：移除 `图片/aliveme/*`、`图片/game/*`、`图片/新建/*`、`demo_left/*` 等 9 个非 codec-hmd 路径下的行。

**备份**：`csv_backups/video_manager_pre_clean_*.csv`

**验证**：CSV 从 20 行 → 10 行 → 3 行（最终只剩 3 个 hmd session）。

---

## 2026-06-19 — 维表主键连续改名（lx→…→op02）保留 original_key

**变更**（`templates/index.html`）：
- `dimRowInput`：第一次主键改名时把**原始 key** 存到 `tr.dataset.originalKey`（不被后续 keystroke 覆盖）
- `dimSaveOne`：检测到 `originalKey && originalKey !== row[primary]` 时走 `mode=upsert + ?original_key=<originalKey>`，让服务端做 rename
- rename 成功后清掉 `dataset.originalKey`（已对齐服务器）

**验证**：`verify_pages.py` 38/38 通过（含 `recorders rename via original_key` + `old/new swap` 两个新增 case）；独立 python test 200 OK `action=renamed`。

**回滚**：删 `dataset.originalKey` 那几行 + 改回 `mode = isNew ? 'insert' : 'update'` 即可。

**关联**：error_book.md E10。

---

## 2026-06-19 — Gallery 缩略图：服务端 HMD 缩略图 + 智能 seek + luma 兜底

**背景**：之前画廊视图只对 MP4 生成缩略图（用 ffmpeg 截 1s 处），HMD 行直接显示占位。本轮要把 HMD 也接上。

**变更**（`app.py`）：
- 加 `_ffmpeg_avg_luma(video_path, at_sec)`：用 PGM 灰度帧字节均值（0-255）检测指定 offset 帧的亮度
- `_generate_mp4_thumbnail` 改造：循环 `THUMB_SEEK_TRY=[3.0, 1.0, 5.0, 10.0]`，每 offset 后跑 luma 检测，`< LUMA_MIN=8.0` 视为全黑跳下个 offset
- filter 简化为 `scale=240:135:force_original_aspect_ratio=decrease`（去掉 pad 表达式，避开"Padded dimensions smaller" 错误）
- 加 `_generate_hmd_thumbnail(session_dir)`：定位 `hmd_cache/<basename>/left.mp4` → 退化 `right.mp4` → 退化 `part_*.hmd`，复用 `_generate_mp4_thumbnail`
- `_ensure_thumbnail` 支持 `kind="hmd"` 分流
- `/api/thumbnail` 路由**重排**：`kind` 判断前移到 `os.path.isfile` 检查之前（HMD 目录不需要 isfile）

**变更**（`templates/index.html`）：
- Gallery 卡片模板统一用 `<img data-thumb-idx data-thumb-path data-thumb-type>`，删除 `<video>` + canvas 客户端抓帧（不同浏览器/编解码器对 h265 拆 mp4 seek 行为不一致）
- `_gallerySetupLazyThumbs` IntersectionObserver + **500ms 兜底 fetcher**（万一 observer 不触发也走强制 fetch）

**验证**：
- 3 个 HMD session 全部 200 + jpg (4812 / 1535 / 2021 B)
- 亮度均值 92 / 124 / 98（> LUMA_MIN，非黑）
- luma_at(0.1s)=38.7 vs luma_at(3.0s)=90.0 验证 1s 确实是暗场景

**回滚**：`_generate_hmd_thumbnail` 整段删除 + `_ensure_thumbnail` 改回只处理 mp4 + JS 改回 `<video>` 路径。

**关联**：error_book.md E7 / E8。

---

## 2026-06-19 — `/` 加 no-cache + build 标记戳（防浏览器缓存陷阱）

**背景**：E7/E8 修完后用户浏览器**完全看不到**新加的 `console.log`，反复 commit 改 build 号都没用。根因是 Flask `send_file` 默认带弱 cache 头，Chrome 缓存 `templates/index.html` 含内嵌 `<script>` 整页 5-30 分钟。

**变更**（`app.py` + `templates/index.html`）：
- `app.py` `/` 路由显式 `Cache-Control: no-cache, no-store, must-revalidate` + `Pragma: no-cache` + `Expires: 0`
- `<script>` 首行加 `console.log('[VideoSort] page loaded, build=YYYY-MM-DD-HHMM-<tag>')`，用户开 console 第一行就能确认加载的是不是最新代码

**验证**：用户看到 `[VideoSort] page loaded, build=2026-06-19-2330-gallery-fallback` 确认新代码生效。

**回滚**：删那 4 行 cache 头 + 删 build 标记 console.log。

**关联**：error_book.md E9。

---

## 2026-06-19 — pack.ps1 排除规则递归化（zip 从 1.4GB → 340KB）

**背景**：用户要求"打包 zip 发给其他设备"，第一次跑 `打包备份.bat` 出来 1.09 GB — 因为 pack.ps1 只过滤**顶层**目录名，递归的 `vendor-upload-pkg/node_modules/`、`hmd_cache/` 全被打包。

**变更**（`pack.ps1`）：
- 加 `$innerExclude` 列表（node_modules / hmd_cache / thumbnails / csv_backups / archive / venv / .idea / .vscode / __pycache__）
- 改用 `Get-ChildItem -Recurse | Where-Object` 过滤路径中包含任一内部排除目录的项
- 顶层过滤仍保留（保兼容）

**验证**：再次 pack → 340 KB（71 entries）；zip 顶层 top-10 全部是代码文件（app.py / index.html / config.json / docs/ / tools/）

**回滚**：删 `$innerExclude` + 改回顶层 `Get-ChildItem` 即可。

---

## 2026-06-20 — CJS/ESM 桥接 + device_monitor HMD 支持 + SD卡自动注册 + 原始日期修正 + 去重

**背景**：
1. HMD 预处理在另一台设备上失败，因为 Node.js `require()` 无法加载 ESM `.esm.js` 文件，需要 CJS 桥接
2. SD 卡表单为空 — 扫描到视频时应自动创建对应的卡信息
3. 扫描视频后应自动开始预处理并更新表单
4. 原始日期获取错误 — `ctime` 是复制时间而非录制时间；HMD 设备无 RTC，所有时间戳默认 2021-01-01
5. 同一视频不应被存储两遍 — 需要去重检查

**变更**（`hmd-decode.cjs` — 两个位置 `static/hmd/` + `templates/static/hmd/`）：
- 新建 CJS wrapper：用 `import()` 动态加载 `.esm.js`，导出 `{ parse, splitStereo, dedupParamSets }` 异步接口
- 支持 direct object 和 init function 两种调用模式

**变更**（`tools/hmd_preprocess.py`）：
- CJS 分支增加 `typeof === 'function'` 运行时检测
- 所有方法调用改为 `await`

**变更**（`device_monitor.py`）：
- `_get_mp4_original_date(filepath)`：优先级 ffprobe `creation_time` → mtime（≥2000）→ ctime → today
- `_get_hmd_original_date(session_path, metadata, dest_dir)`：优先级 metadata `start_time` → 目录名日期（如 `0615` → 当年 MM-DD）→ mtime（≥2020）→ today
- `_get_drive_volume_info(drive)`：Win32 `GetVolumeInformationW` 获取卷序列号 `XXXX-XXXX` 和卷标
- `_auto_register_mp4_device(drive, source_path)`：自动注册单目设备到 `sd_cards.csv`（volume_serial 为 key，推断 DJI/GoPro 类型）
- `_start_hmd_preprocess(copied_sessions)`：导入 `hmd_preprocess` 并调用 `start_async(dest_path)` 触发预处理
- `_check_mp4_already_exists(src_path, dest_dir)`：同名同大小文件视为已存在（搜索整个 destination_base）
- `_check_hmd_already_exists(session, dest_dir)`：同设备ID+session名+part数视为已存在（搜索整个 destination_base）
- `copy_files()`：新增 `skipped` 列表；去重检查后跳过已存在文件；返回 `(copied, skipped, failed)`
- `copy_hmd_sessions()`：去重检查后跳过已存在 session（标记 `skipped=True`）；跳过的也记入 copied_sessions 以便删除 SD 卡源
- `register_to_csv()`：`os.path.getctime()` → `self._get_mp4_original_date(src_path)`
- `register_hmd_to_csv()`：`datetime.now()` → `self._get_hmd_original_date(...)`
- `process_drive()`：MP4 部分接收三元返回值；复制+跳过的文件都从 SD 卡删除；HMD 部分只对非跳过 session 触发预处理

**变更**（`app.py`）：
- `_get_file_date(filepath)`：重写为 MP4 专用（ffprobe creation_time → mtime → ctime 优先级）
- `_get_hmd_date(session_folder, metadata, dest_dir)`：新增 HMD 专用日期逻辑
- `scan_directory()` HMD 分支：`_get_file_date(u["folder"])` → `_get_hmd_date(u["folder"], u.get("metadata"), directory)`
- `/api/hmd/register`：`os.path.getctime()` → `_get_hmd_date(session_path, meta)`

**验证**：`python -c "import py_compile; py_compile.compile('device_monitor.py', doraise=True)"` → OK；启动 `启动视频管理.bat` 成功运行；自动复制+注册+预处理正常触发。

**已知问题**：docstring 中 `/media` 的 `\u` 被 Python 解析为 Unicode 转义 → `SyntaxError: unicodeescape` → 已改为 `/media/`（正斜杠）

**回滚**：删除 `hmd-decode.cjs`（两个）；device_monitor.py 删除新增 7 个方法 + 恢复 `copy_files` 和 `copy_hmd_sessions` 去重逻辑 + 恢复 `register_to_csv/register_hmd_to_csv` 日期获取；app.py 恢复 `_get_file_date` 和 `_get_hmd_date`。

---

## 学习复盘（Hermes）

**经验 1（已沉淀到 error_book.md E1）**：
WebCodecs VideoDecoder 在 `configure()` / `flush()` 之后，第一帧必须是 IDR（NAL type 19/20）。
否则抛 `DataError: A key frame is required after configure() or flush()`。
修复方案：每次重置 decoder 后从最近的 IDR 开始喂。

**经验 2（已沉淀到 error_book.md E4）**：
HMD 容器 `cameras[0/1]` 是配置占位，实测单流 1920x1080。metadata 的 `cameras` 数组不是实际双摄流。
用户"双目"心智 = 两个独立设备的两段 session，不是单文件内的两路流。

**经验 3（待沉淀）**：
Flask debug 模式 `use_reloader=True` 时子进程残留 → `netstat -ano | findstr :5000`
看到多个 LISTEN 是正常的；要清理时手动 `taskkill //F //PID xxx`。

**经验 4（待沉淀）**：
WebCodecs 解码 HEVC 时时间戳必须单调递增；用同一 timestamp 喂多帧会触发"duplicate timestamp"错误。

**经验 5（沉淀到 features.md + dev_plan.md）**：
HMD duration 不可靠 → metadata.frame_counts 为空 + stop_time_unix 是单调时钟。
最佳方案：客户端首次打开 WebCodecs 解析得到帧数 → `/api/hmd/duration` 回填；服务端不做估算。

**经验 6（沉淀到 error_book.md E7）**：
ffmpeg filter `pad=W:H:(ow-iw)/2:(oh-ih)/2:black` 在 `scale=...:force_original_aspect_ratio=decrease` 之后如果算出 `iw == ow`（如 1920×1080 → 240×135），会触发 "Padded dimensions cannot be smaller than input dimensions" 静默失败。
**教训**：用 pad 表达式前先跑一遍手工 ffmpeg 确认；或者干脆用 `scale=W:H:force_original_aspect_ratio=decrease` 单步。

**经验 7（沉淀到 error_book.md E7）**：
客户端 video element 的 `currentTime` 抓帧对 h265 拆 mp4 在不同浏览器 / 编解码器下行为不一致（有的返回黑帧，有的跨域失败），生产路径走服务端 ffmpeg 截帧 + HTTP blob + `<img>` 才稳定。客户端 video seek 只作 fallback。

**经验 8（沉淀到 error_book.md E9）**：
SPA 单文件应用如果用 Flask `send_file`，必须显式 `Cache-Control: no-cache`，否则浏览器缓存整页（含内嵌 `<script>`），改完 templates 不生效。`Cache-Control` 头比 `Last-Modified` 重要。
排查时第一行 console.log 打 build 号（git short SHA 或日期），能立刻确认加载的是不是最新代码。

**经验 9（沉淀到 error_book.md E10）**：
主键可编辑的表格 UI，不能用 current key 反推"原 key"。改 key 的过程是连续 keystroke，每次都把 `tr.dataset.key` 更新成新值，原始 key 会丢。
**正确做法**：tr 上独立存 `originalKey` 锚（第一次改名时记录，永不覆盖），保存时用 `originalKey + newKey` 二元组走 upsert + `?original_key=` 参数。

---

## 2026-06-24 — 代码模块化重构：扁平 → src/ 四层架构

**背景**：`app.py` 5585 行单一文件，根目录散落 20+ 独立脚本，难以维护和扩展。

**变更**：
- **目录重组**：所有业务代码移入 `src/`，运行时数据统一放在 `runtime/`
- **app.py 拆分**：路由按领域拆为 5 个 Flask 蓝图（main/scan/upload/hmd/dim），业务逻辑提取到 8 个 service
- **新增模块**：`src/models/`（csv_store + dim_registry）、`src/utils/`（path/format 工具）、`src/services/`（lazy_loader/video/preprocess/scan/upload/data/dim）
- **脚本归档**：20 个独立脚本移入 `src/scripts/`（git 自动识别 rename）
- **临时脚本清理**：`_check_paths.py`、`_fix_device_paths.py` 删除；`_check_routes.py` → `check_routes.py`；`_test_flask.py` → `test_flask_routes.py`
- **gitignore 更新**：新增 `browser_data/`、`*.pid`、`.codebuddy/`、`runtime/data/*.json`、`runtime/data/*.png`、`*.csv.bak*`
- **入口更新**：`启动视频管理.bat` 改为 `python src/run.py`；根目录仅保留 `.bat`、`.ps1`、`.spec`、`README.md`、`requirements.txt`

**验证**：Flask 启动成功；所有路由正常响应；git status 干净（无敏感数据漏入）。

**关联**：docs/structure.md、docs/ARCHITECTURE.md、docs/project_status.md 已同步更新。

---

## 2026-06-28 — 画廊播放按钮 + 「同上」字段复制 + 撤回功能

**变更**：

1. **画廊「▶ 播放视频」按钮**（`templates/index.html`）：
   - 与表格页预览按钮状态完全一致：历史视频禁用、HMD 预处理中显示「⏳ 处理中」、失败显示「⏳ 失败」、等待显示「⏳ 等待」、状态未知显示「⏳ 检查中…」
   - 按钮状态依赖 `_preprocessStatusMap` 实时更新（和表格预览同一数据源）
   - HMD 完成 → 调用 `openHmdPreviewInline()` 用系统播放器打开预处理后视频（与表格页一致）
   - MP4 → 左侧面板内嵌 `<video>` 播放 `/api/video`
   - 替换画廊原有的 alert 拦截方式

2. **「同上」按钮 — 表格页**（`templates/index.html`）：
   - 每行操作列新增绿色「同上」按钮（筛选结果第一条不显示）
   - 点击后自动赋值当前行 `recorder_id`、`task_id`、`env_id` = 上一个视频（按当前筛选排序结果，非原始顺序）
   - 仅影响这三个字段，其他字段（sd卡、描述、分数等）完全不受影响
   - `tableSameAsAbove(btn)` — 通过 `tr.dataset.filteredIdx` 定位筛选顺序，找到上一个视频

3. **「同上」按钮 — 画廊编辑页**（`templates/index.html`）：
   - 显示于编辑面板底部（保存修改 和 播放视频 之间）
   - 第一张卡片不显示；替换了原「📋 准备上传」按钮位置
   - 点击后自动将当前卡片的三字段复制为上一个卡片的值
   - 写回 `tableData` 并 `markRowDirty`，同步刷新表格

4. **「↩ 撤回同上」按钮**：
   - 工具栏：操作后自动出现蓝色「↩ 撤回同上」，点击恢复修改前三字段原始值，按钮消失
   - 画廊面板：操作后按钮自动变为「↩ 撤回同上」，同样恢复原始值
   - 全局状态 `_sameAsAboveUndo = { type, originalIndex?, oldValues }` 管理
   - 导航到其他卡片/关闭画廊/新操作时自动清除旧状态

5. **Bug 修复**：
   - 修复 `_buildGalleryEditorForm(card)` 未传 `idx` 导致「同上」条件永远不满足
   - 修复 `${sameBtnHtml}` 重复渲染（两次 → 一次）

**验证**：lint 零错误；表格页筛选排序后「同上」正确复制上一个；画廊页「同上」正确显示和撤回；HMD 预处理中按钮禁用状态正确。

**回滚**：删除 `tableSameAsAbove`/`gallerySameAsAbove`/`sameAsAboveUndo` 函数 → 删除 `_sameAsAboveUndo` 变量 → 恢复按钮 HTML 为旧版 → 删除 `#btnUndoSameAsAbove` DOM。

---

## 2026-06-24 — 批量上传增强：路径修复 + 进度追踪 + delete-local

**变更**：

1. **auto_upload.py 路径修复**：
   - `auto_upload_py` 从 `BASE_DIR/auto_upload.py` → `BASE_DIR/src/auto_upload.py`（子进程启动路径错误，之前 404）

2. **`--delete-local` 支持**：
   - 后端 `auto_upload_start` 读取 `deleteAfterUpload` 参数 → 子进程传递 `--delete-local`
   - 前端 checkbox 绑定 `_utDeleteAfterUpload` 状态

3. **进度追踪系统**：
   - `auto_upload.py` 新增 `PROGRESS_FILE` → 在各阶段写入 `runtime/data/auto_upload_progress.json`（status/current/total/success/fail）
   - 后端新增 `GET /api/auto-upload-progress` 端点（读取 JSON + 进程存活检测）
   - 前端新增进度条 UI + 2 秒轮询（最长 30 分钟超时）

4. **by-path 模板查找**：
   - 新增 `GET /api/upload-template-by-path?path=xxx`（解决 rowIndex 不一致问题）
   - 前端 `openUploadDialog()` 改为 path 优先查找

**验证**：批量上传 3 个视频端到端测试；进度轮询正常显示成功/失败计数。

**回滚**：恢复 `auto_upload_py` 路径 + 删除 progress endpoint + 删除 `write_progress()` 调用。

---

## 2026-07-01 — 修复自动上传 500 错误 + 安装 Playwright 浏览器

**变更**：

1. **`_is_hmd_session()` 异常保护**（`src/services/upload_service.py`）：
   - `os.listdir(video_path)` 加 `try/except (PermissionError, OSError)` 保护
   - 目录不可访问时返回 `False` 而非抛出未处理异常 → 防止二次 500 崩溃
   - 同时清理 `upload_service.py` 中残留的死代码函数（`auto_upload_start`/`auto_upload_status`/`auto_upload_progress`，缺少 `request` 导入，从未被调用）

2. **错误根因分析**：
   - 日志 `device_monitor.log` 记录 `NameError: name '_is_hmd_session' is not defined`（6 次，最新 2026-07-01 11:02）
   - 根因：Flask 服务器自 2026-06-30 23:08 后未重启，运行旧版代码（缺少 `_is_hmd_session` 导入）
   - 重启服务器后导入生效，500 错误消失

3. **Playwright Chromium 安装**：
   - 运行 `python -m playwright install chromium` → 下载 Chrome for Testing 148.0.7778.96（181.9 MiB）
   - 安装路径：`C:\Users\34124\AppData\Local\ms-playwright\chromium-1223`
   - 同步安装 FFmpeg v1011、Chrome Headless Shell v1223、Winldd v1007

4. **Error Book 更新**：
   - 新增 E14：`/api/auto-upload-start` 返回 500 + HTML（`_is_hmd_session` NameError）

**验证**：
- 重启 Flask 服务器后 `/api/auto-upload-start` 返回 `{ok: true}` JSON
- Playwright 浏览器启动成功，单视频上传端到端通过
- `device_monitor.log` 无新增 NameError

**回滚**：恢复 `_is_hmd_session` 原始实现（无 try/except）+ 卸载 Playwright 浏览器
## 2026-07-02 — 全项目文件行数拆分 + 前端模块化

**变更点**：

1. **Python 文件拆分**（13 个 >600 行文件 → 全部 ≤1300 行）：
   - `device_monitor.py` (2227) → 包：`scanner.py` + `copier.py` + `monitor.py`（mixin 模式）
   - `tools/hmd_fast_preprocess.py` (1316) → 包：`path_utils.py` + `media_ops.py` + `preprocess.py`
   - `tools/extract_scenario_taxonomy.py` (1655) → 253 + `taxonomy_translations.py`（纯数据分离）
   - `routes/data_routes.py` (1030) → 650 + `data_helpers.py` + `cleanup_routes.py`（新蓝图）
   - `routes/upload_routes.py` (1005) → 387 + `upload_config_routes.py` + `auto_upload_routes.py`（新蓝图）
   - `services/scan_service.py` (819) → 555 + `scan_maintenance.py`
   - `tools/hmd_preprocess.py` (686) → 369 + `hmd_preprocess_ops.py`
   - `scripts/rename_all.py` (920) → `rename_helpers.py` + `rename_scanner` + `rename_migrator.py`
   - `scripts/preprocess_manager.py` (622) → 260 + `pm_helpers.py`
   - `hmd_preview.html` (621) → 155 + `hmd-preview-ui.js`

2. **前端 index.html 模块化**（7417 → 2293 行）：
   - CSS 全部提取到 `static/css/index.css`
   - 15 个 JS 模块提取到 `static/js/`（render-table、hmd-inline-player、gallery-view、task-validation 等）
   - 保留所有内联 JS（含 NAV tabs、DIM CRUD、auto-save、delete、statistics 等）

3. **app.py 注册 3 个新蓝图**：`cleanup_bp`、`upload_config_bp`、`auto_upload_bp`

**跳过**：`auto_upload.py`（用户正在调试上传代码，暂不改）

**遇到的问题与修复**：
- `<script src>` 嵌套在 `<script>` 块内导致浏览器语法错误 → 拆分/重组脚本块
- `dimCache` 定义在后、`loadData` 调用在前 → 移到第一个 inline 块顶部
- `shared-filters.js` 等关键依赖加载太晚 → 移到所有 inline 块之前
- `_tasksAutoSort` 双重声明 → 删除内联重复（已由 task-validation.js 提供）
- `upload_config_service.py` 缺少 `_UPLOAD_OPTIONS_CACHE = None` 初始化 + `import sys` → 500 错误修复
- `node_modules/` 被误纳入 git → 添加到 `.gitignore` 并从历史移除

**验证**：
- Flask 启动正常，所有蓝图路由注册成功
- 浏览器刷新后视频页面可见，`/api/upload-options` 返回 200
- 前端无 `_xxx is not defined` 报错

**回滚**：`git revert HEAD~8..HEAD` 可回滚到拆分前状态

## 2026-07-05 — 修复单引号字符串跨行导致 `switchPage` 未定义（整脚本块失效）

**变更点**：
- `src/templates/index.html:2123` — `environment_description` 字段的 `title:` 单引号字符串跨两物理行，合并为一行并用 `\n` 转义保留 tooltip 换行：
  - 改前：`title: '照明 (Lighting): ...分布。\n场景 (Scene/Setting): ...职能。'`（实际源码换行在 `'分布。` 与 `场景` 之间，无转义）
  - 改后：`title: '照明 (Lighting): 特指光源的类型、强度和分布。\n场景 (Scene/Setting): 指具体的地点或情境，或者场景职能。'`

**根因复盘**：
- JS 单/双引号字符串**不能跨物理行**（必须用 `\n` 转义或反引号模板字符串）；换行即被解析为「未闭合的字符串 + 下一行 token」，抛 `Invalid or unexpected token`
- 该字符串在 `<script>` 块 1703–2793 内，该块包含 `switchPage`（1715 行）等所有导航/表单/CRUD 逻辑；脚本块任一处 SyntaxError → 整块丢弃 → 块内所有函数 `is not defined`
- 浏览器报错的"行 887"实为渲染后偏移，对应另一有效块的 DEBUG `console.log`（正常输出），并非错误真位置；真错位置在 2123 行

**验证**：
- `sed -n '1704,2791p' src/templates/index.html | node --check` → `BLOCK OK`
- 浏览器硬刷新（Ctrl+F5）后无 SyntaxError、无 `switchPage is not defined`
- 导航标签（录入员 / SD卡 / 任务 / 环境 / 统计 / 设置）切换正常

**预防**：
- 任何 tooltip / placeholder 多行文案一律用反引号或 `\n` 转义
- 改完前端 `<script>` 块后 `node --check` 该块
- 看到「某函数 `xxx is not defined`」先查同一 `<script>` 块内是否有 SyntaxError

**回滚**：`git revert HEAD` 可恢复该改动
**关联**：error_book.md E15

## 2026-07-05 — 上传页中文化（默认值/翻译表/dim 查询/双语渲染）

### 一、调试过程总结

本次工作目的是让上传页（publish.example.com）适配中文用户。实际开发路径远不止 5 个源文件，期间产生了 79 个调试脚本 + 1 张截图 + 1 个临时 txt，反映了一个**典型的多阶段调试旅程**：

| 阶段 | 脚本模式 | 目的 | 关键产出 |
|---|---|---|---|
| 1. 探查 | `inspect_*.py` / `dump_*.py` / `get_all_options.py` / `get_page_html.py` / `list_facility_options.py` / `find_upload_buttons.py` | 反查 publish.example.com 上传页所有下拉/输入元素的 DOM 结构、select 选项、按钮位置 | 全部字段 ID/placeholder 清单 |
| 2. 取数 | `fetch_all_frameforge_options.py` | 拉取所有可选值（含大小写变体） | VALUE_MAP 原始候选 |
| 3. 匹配 | `match_options.py` / `match_options_v2.py` | 将英文选项映射到中文翻译 | 2 次迭代修正歧义 |
| 4. 填表 | `fill_frameforge_form.py` → `v8`（8 次迭代） | 反复试错填表，最终通过 React 受控组件 + tile 坐标点击 | E15 修复（同块脚本失效） |
| 5. 迁移 | `migrate_capture_mode.py` / `migrate_environments_block.py` / `migrate_form_options.py` / `migrate_pg_to_chinese.py` → `v3`（3 次迭代） | PG/CSV 数据中文化 | environments/options 表转中文 |
| 6. 前端同步 | `update_js_dim_fields.py` / `verify_pg_chinese.py` | 把 PG 中文数据同步到前端 `dim-table-crud.js` | 235 项 `operator_job` |
| 7. 验证 | `show_form_filled.py` / `open_upload_template.py` / `verify_pg_chinese.py` | 端到端验证填表结果 | `after_inject.png` 截图证据 |
| 旁支 | `check_address_field.py` / `check_bad_tasks.py` / `check_breakdown.py` / `check_cloud_uploaded.py` / `check_computers.py` / `check_confirmed.py` / `check_labels.py` / `check_missing_detail.py` / `check_paths.py` / `check_pg.py` / `check_ready.py` / `check_ready_pg.py` / `check_selectors.py` / `check_sessions.py` | 数据质量各种旁支检查 | 14 个 one-off 检查 |
| 凭证/工件 | `after_inject.png` / `extract_cookie.py` / `runtime/data/env_check.txt` | 截图 + cookie 提取 + 环境检查 | 调试现场物证 |

**调试过程的关键转折点**：
- 第 4 阶段 v1→v4 一直接连不上 / 报 "Connection closed" → 查证发现是 publish.example.com 的 React 受控组件问题，改用 `Object.getOwnPropertyDescriptor(proto,'value').set.call(el,value)` + `dispatchEvent` 注入，v5 起稳定
- 第 4 阶段 tile 点击失效 → 查证 `.vcb-tile` div 不响应，必须点 `.vcb-tile-media` 子按钮的中心坐标（`getBoundingClientRect` 取）
- 第 4 阶段末尾触发 E15 bug（见 error_book E15）：单引号字符串跨行导致整脚本块失效 → 修后所有导航/CRUD 恢复正常
- 第 5 阶段 `migrate_pg_to_chinese` 3 次迭代：v1 漏大小写、v2 漏中英混合、v3 覆盖完整

### 二、最终代码变更（5 个源文件）

| 文件 | 行数 | 改动要点 |
|---|---|---|
| `src/config.py` | +16/-16 | `UPLOAD_TEMPLATE_DEFAULTS` 全部中文化（CN/示例省/示例/工业制造/制造厂/生产工人/是 等） |
| `src/services/upload_service.py` | +58 | `_load_env_info/_recorder_info/_sd_card_info/_task_info` 4 个 `return {}` stub 全部接入 dim 真实查询（`_resolve_dim` + `_read_dim_rows`） |
| `src/auto_upload.py` | +588 | `VALUE_MAP` 翻译表：新增 `Other/other` 兜底、补大小写变体（`manufacturing factory`/`Retail and consumer goods` 等）、修订多处中译（"制造厂"非"工厂"、"办公室"非"办公楼"、"缝纫车间"非"装配线"、"手工作坊"非"车间/工作室"） |
| `src/static/js/dim-table-crud.js` | +627 | `operator_job` 235 项英文 → 中文（收银员/快餐员工/搬运工/...）；`operator_consent` 同步中文化 |
| `src/static/js/gallery-editor.js` | +13/-13 | 双语字段（`task_description`/`environment_description`）改为"只显示中文 + 单个复制按钮"（上传页已中文，EN 已无意义） |

### 三、清理

- 删除：79 个调试脚本（`fill_frameforge_form_v1..v8` / `inspect_*` / `dump_*` / `migrate_*` 等）+ `after_inject.png` + `runtime/data/env_check.txt`
- 保留：51 个 `scripts/` 下已纳入版本控制的运维脚本（`pg_backup.py` / `sync_*.py` / `mark_*.py` 等）
- 未提交调试脚本纯靠 git 工作区清理即可（从未入版本），无需 git revert

### 四、过程教训（→ error_book.md E16）

1. **脚本版本爆炸不可持续**：`fill_frameforge_form` v1→v8 + `migrate_pg_to_chinese` v1→v3 + `match_options` v1→v2 = 13 个版本文件。应该用**单一脚本 + `--stage` 参数或日志分支**（如 `fill_form.py --stage=react-inject`），git 友好 + diff 清晰
2. **调试产物必须主动归档**：79 个临时脚本 + 截图 + txt 全部堆积在 `scripts/` 和工作区根，每次 `git status` 噪音巨大。约定：**调试脚本放 `scripts/_debug_<日期>/` 临时目录**，完结时一次性 `git clean`
3. **调试过程中触发的隐性 bug 要回灌到错误手册**：E15 字符串跨行问题就是在 v8 填表过程中冒出来的，没有这次调试就发现不了

### 五、验证

- `node --check` 1703–2793 脚本块 → OK
- 浏览器硬刷新 → 无 SyntaxError、`switchPage` 正常
- 5 个源文件 diff stat：`+1043 / -259`（主要是 `auto_upload.py` 和 `dim-table-crud.js`）
- 所有 `M` 文件 git status 干净，79 个调试脚本全部清掉

**回滚**：`git revert HEAD..HEAD~1` 可单独回退本批
**关联**：error_book.md E15 / E16；memory/js-script-block-syntax-kills-all.md

---

## 2026-07-05 — auto_upload 端到端上传链路打通（66 个视频批量）

**背景**

昨天完成中文化（commit 31a4d6a）后，仍然无法上传——本以为中文化后 `auto_upload.py` 自然就能填对，实际跑下来发现还有 9 个独立 bug 串在一起。

每个 bug 单独看都不复杂，但**叠加效应**让"上传按钮变可点击 → 真的进入 inflight → 完成后标记 uploaded"这条链路完全断裂。

**9 个修复**（详见 `docs/开发历史文档/retrospectives/2026-07-05_frameforge_auto_upload.md`）

| # | Bug | 修复 |
|---|-----|------|
| 1 | environments.csv 双重 BOM 导致 `_load_env_info` 返回 None | 移除重复 BOM + 改用 `upload_service._load_env_info`（统一 PG+CSV 入口） |
| 2 | task_description 填了英文而不是中文 | 中文优先（`process` > `process_en`） |
| 3 | GPS 锁定后被 Phase 1 重新 fill 覆盖 | `fill_field` 加 `return ok` 守卫 |
| 4 | 地址 GPS 候选点不上 | 借鉴 `fill_frameforge_form_v7.py` 的多选择器并联方案 |
| 5 | country 被自动转成 "China" | **跳过 country/state/city**，让 GPS 自动回填 |
| 6 | 按钮文本"Upload to server" 在中文界面匹配不上 | 所有 selector 加 "上传到服务器" |
| 7 | MCAP 转换完成检测不出来（一直等按钮） | 双信号检测：按钮 enabled OR 本地预览出现 |
| 8 | `mark_uploaded()` 只写 CSV 没写 PG | CSV + PG 双写 + 写了 `sync_csv_pg_uploaded.py` 回填历史 147 行 |
| 9 | 单个文件缺失就 `return 1` 退出整批 | 改为 `continue` 跳过 + 警告 |

**核心代码**

5 个核心修复的代码片段都在 retro 文档里。其中**最有价值的两条**是：

1. **双信号检测**（`_upload_hmd_folder_to_preview`）：从 555s 超时降到 53s 识别
2. **跳过手动填 country/state/city**（`fill_field`）：少做反而做得对

**验证**

- 单条视频：表单一键填对、GPS 锁定成功、MCAP 转换检测到、按钮可点击、上传完成、`uploaded='Yes'` 写入 CSV+PG
- 批量：66 个视频已启动后台 PID 26508，日志 `runtime/logs/batch_upload_66_v2.log`
- 数据同步：`sync_csv_pg_uploaded.py` 回填 147 行历史数据（2 行新同步，145 行已对齐，0 行未找到）

**教训**

1. **认知层面的转变胜过代码层面的修补**：第 5 个 bug（country 转 China）不是写更聪明的字符串转换，而是意识到"这些字段根本不该手填"。类似的认知转变还包括"页面按钮文本是中英文两套"
2. **借鉴已验证的方案**：第 4 个 bug 用 `v7.py` 的现成 selector 模式直接解决，自己重新设计反而绕远
3. **批处理必须容错**：第 9 个 bug（单条失败拖累整批）必须在 batch 入口处就处理，不能依赖每条独立 try/except

**文件清单**

- 改动：`src/auto_upload.py`（588 行）+ `src/config.py` + `src/services/upload_service.py`（commit 31a4d6a 已含）
- 新增：`docs/开发历史文档/retrospectives/2026-07-05_frameforge_auto_upload.md`（本次）
- 新增：`scripts/sync_csv_pg_uploaded.py`（回填历史数据）
- 新增：`scripts/find_upload_buttons.py`、`scripts/inspect_upload_area.py`、`scripts/test_hmd_injection.py`（调试辅助，已在 .gitignore 排除）

**关联**

- 详细复盘：`docs/开发历史文档/retrospectives/2026-07-05_frameforge_auto_upload.md`
- error_book.md E15/E16（脚本版本爆炸 + 调试归档规矩）

---

## 2026-07-07 — 任务维表新增 4 字段识别失败 + 难度校验中英不一致

**背景**

用户报告：任务维表点 "+ 新增"，依次填 产品/任务/工具/工序，但右边"校验"列一直显示 `⚠ 还差 4/4`，保存 toast `缺 4 元组字段`。但**搜索框非空时**才复现，无过滤时正常。

**根因**：3 个 bug 叠加（详见 error_book.md E19）

1. **新行被过滤**：`dimRenderTable` 过滤判断 `if (search && !hay.includes(search)) return` 对新行一视同仁 —— 新行 4 元组空字符串不含搜索词，被 return 跳过，没渲染进 DOM
2. **`dimAddRow` 错位篡改首行 dataset.key**：渲染后 `bodyEl.querySelector('tr')` 拿到的是**第一个匹配过滤的旧行**（新行不在 DOM 里），`firstTr.dataset.key = '__new_xxx__'` 把旧行伪装成新行；用户输入的字符被 `dimRowInput` 用 `_tmpKey` 命中真正的 `st.rows[0]`（DOM 里看不见的空行），校验列上的 hint 始终是旧行的原值
3. **difficulty 中英校验不一致**：`_taskValidateRow` / `_validateBatchRow` / `config.py validators` 全都只认 `easy/medium/hard`，但前端下拉是 `简单/中等/困难`。用户选"简单"后校验失败，但 `_taskRefreshRowHint` 的 else 分支只数 4 元组缺几个 → 文字停在 `⚠ 还差 0/4`（0 missing 但其实卡 difficulty）

**修复**（4 个文件，+9 / -12 行）

| 文件 | 改动 |
|------|------|
| `src/templates/index.html:2500-2513` 内联 `dimRenderTable` | 把 `isNew` 判断前移到过滤之前，过滤判断加 `&& !isNew` 豁免新行 |
| `src/static/js/task-validation.js:7-17` `_taskValidateRow` | 删除 difficulty 英文校验 |
| `src/static/js/task-wizard.js:30-36` `_validateBatchRow` | 同上 |
| `src/config.py:130` | 删除 `"difficulty": {"easy","medium","hard"}` 后端校验 |

**验证**

Playwright 自动化测试（`scripts/test_new_task_bug.py`）：

- **过滤态点 "+ 新增" 复现**：脚本显示截图 `scripts/shots/verify_02_after_add_with_filter.png`，`#dimBodyTasks tr` 总数不变（仍 5 行），但 `tr[data-key^="__new_"]` 计数 = 1（DOM 外的"幽灵"新行）；清空过滤后新行才冒出来 → 锁定 bug A+B
- **修复后**：hint `⚠ 4/4 → 3/4 → 2/4 → 1/4 → ✓ 4/4`，server 返回 `task_id` 形如 `midea_shop_license_inspection_001`

**额外发现**（未在本修复处理，留作后续 TODO）

1. **`dim-table-crud.js` 是死代码**（index.html 未引入，但代码还在），重复维护两份 dim 逻辑反而埋坑 → 建议删除
2. **`_taskRefreshRowHint` 的 else 分支不显示真实失败原因**，只数 missing count → 用户看到 `⚠ 还差 0/4` 会困惑；应该读 `v.reason` 而不是数 missing
3. **difficulty 妥协方案有副作用**：`DIFFICULTY_LIMITS_HOURS = {"easy":10,...}` 查表不会命中中文 difficulty → quota 走兜底值；如果以后 quota 要严格生效，需要把下拉改成 `{value:'easy', label:'简单'}` 对象形式（保存英文、显示中文）

**关联**

- error_book.md E19
- Playwright 测试脚本：`scripts/test_new_task_bug.py`
- 排查用截图：`scripts/shots/verify_*.png`
