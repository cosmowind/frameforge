# TODO

> 创建时间: 2026-06-24 | 最后更新: 2026-07-05
> 已完成部分归档至 `docs/done/app重构done.md`

---

## 🔥 frameforge 补录参数助手 ✅ 已完成 (2026-06-27)

> 详见 `docs/chrome_cdp_guide.md`

通过 Chrome CDP + Playwright 自动化 publish.example.com 上传历史页面，扫描全部视频并批量补录参数。

### 已完成
- ✅ `start_helper.bat` — Chrome 启动器（9222 端口 + CDP + 禁用安全策略）
- ✅ `src/scripts/setup_filters.py` — 筛选条件设置（Stereo + 3 个 Excludes 标签）
- ✅ `src/scripts/scan_all_videos.py` — 全量扫描 6 页（262 条），获取 session_id / date / duration / missing
- ✅ `src/scripts/csv_editor.py` — Web 编辑器（http://localhost:5001），链接 recorders/tasks/environments 维表
- ✅ `src/scripts/auto_fill_helper.py` — Ctrl+B 快捷键自动填写 20+ 字段
- ✅ 分页修复：JS native value setter + JS click Go 按钮
- ✅ 滚动修复：`scrollIntoView` + 等待 tiles 渲染
- ✅ 自动保存：单行 JSON 发送（避免 413 超限）

### 待完成
- ⬜ 批量处理脚本：读 CSV 中 missing>0 的行，逐一打开视频 → Edit metadata → 自动填完
- ⬜ 填写完后验证：确认所有 184 个 missing=17 的视频参数已补齐

---

## 🔥 场景任务多样性重构 ✅ 已完成 (2026-06-26)

> 业务依据: `docs/业务要求文档/场景任务多样性.md`
> 详细计划: `docs/dev_重构场景任务多样性规划.md`

所有 5 个 Phase 已完成：
- ✅ P1: tasks 表单清理（移除环境字段、配额系统）
- ✅ P2: 视频管理页字段清理（删除 work_content/category/upload_feasibility/task_name；添加 env_id）
- ✅ P3: 上传模板参数来源验证（task/env 字段来源已正确区分）
- ✅ P4: 删除录入员 phone 字段
- ✅ P5: 统计页前端实现（环境/任务/任务×环境/操作员×任务×环境 四个维度）

### 🔧 数据迁移修复 (2026-06-26)
- ✅ `_migrate_tasks_env_to_environments()`: 首次打开"环境"页时自动从 tasks.csv 提取环境数据写入 environments.csv，并回填 video_manager.csv 的 env_id 列，同时清理旧废弃列（work_content_cn/en, category, upload_feasibility, task_name）

---

## 🔥 上传页中文化 ✅ 已完成 (2026-07-05)

> 详见 `docs/dev_log.md` 2026-07-05 段 + `docs/error_book.md` E15 / E16

适配 publish.example.com 上传页中文用户：

- ✅ `src/config.py` — `UPLOAD_TEMPLATE_DEFAULTS` 中文化（CN/示例省/示例/工业制造/制造厂/生产工人/是 等）
- ✅ `src/services/upload_service.py` — 4 个 `_load_*_info` stub 接入 dim 真实查询
- ✅ `src/auto_upload.py` — `VALUE_MAP` 翻译表补漏并修订中译（"制造厂"非"工厂"、"办公室"非"办公楼"、"缝纫车间"非"装配线"、"手工作坊"非"车间/工作室"）
- ✅ `src/static/js/dim-table-crud.js` — `operator_job` 235 项英文→中文、`operator_consent` 中文化
- ✅ `src/static/js/gallery-editor.js` — 双语字段只显示中文（单复制按钮）
- ✅ 清理 79 个调试脚本（fill_frameforge_form_v1..v8 / inspect_* / dump_* / migrate_* 等）+ 截图 + 临时 txt
- ✅ `.gitignore` 加 `_debug_*.py` 模式防止未来调试产物堆积

### 过程教训（→ E16）
- 调试脚本禁用 `v1`/`v2` 后缀复制，用单一文件 + `--stage` 参数
- 临时调试文件放 `scripts/_debug_<日期>/`，完结时 `git clean`
- 开发完成收尾流程必含「调试产物清理」步骤

---

## 核心目标（原有）

将 `app.py` 从 5500+ 行单体拆分为模块化结构：config / utils / models / services / routes，每层职责清晰。

**当前进度**: Services 层已完成，Routes 层尚未拆分（app.py 仍为单体 5509 行）。

---

## 待完成（原有）

### 1. Routes 层拆分

`src/routes/` 目录已建但为空，需从 app.py 中抽出以下蓝图：

- `config_routes.py` / `data_routes.py` / `upload_routes.py` / `hmd_routes.py` / `dim_routes.py` / `video_routes.py`

完成后将 `app.py` 精简为 `create_app()` + 蓝图注册（<80 行）。

### 2. 前端单视频上传功能

- 模板面板加"🚀 自动上传"按钮
- 调 `/api/auto-upload-start`，重复检测弹窗
- 2s 轮询 `/api/auto-upload-status`
- 成功/失败 toast + inflight 面板刷新

涉及 API：`auto-upload-start`(增强)、`auto-upload-status`(增强)、`auto-upload-log`(新增)、`upload-history`(新增)、`auto-upload-cancel`(新增)。

### 3. 测试视频1上传（手动）

```bat
cd /d ./vendor
python auto_upload.py --row-index 0
```

视频 `4aa45c_session_00000` 需重新上传验证。
