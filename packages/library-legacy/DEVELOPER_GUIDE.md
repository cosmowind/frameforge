# DEVELOPER_GUIDE

> 给下一位接手这个项目的人。读完你应该能：1) 5 分钟内把项目跑起来，2) 10 分钟内理解整体架构，3) 30 分钟内定位到任意功能的代码入口，4) 知道坑在哪里。

---

## 0. 30 秒项目总览

| 维度 | 情况 |
|------|------|
| 项目类型 | 单机桌面 Web 工具（Flask + 单文件前端 SPA） |
| 目标 | 运动相机/SD 卡视频素材本地管理 + 元数据编辑 + 批量上传 |
| 代码量 | 后端 ~1300 行单文件 + 前端 ~53KB 单文件 + 3 个独立 GUI 工具 |
| 依赖 | flask, werkzeug, requests + 系统 ffmpeg/ffprobe（Windows-only 设备监听） |
| 数据 | `video_manager.csv`（13 字段，行数 10⁴ 级别） |
| 凭据 | **无 API key**（早期 MiniMax 翻译已替换为基于 CSV 的自动补全）。publish.example.com 上传 cookie 在 `vendor-upload-pkg/cookie.txt`（**用户本地自建，已 .gitignore**）|
| 平台 | 主开发 Windows，macOS 大部分可跑（设备监听除外） |

---

## 1. 5 分钟启动

```bash
# 1. 装依赖
pip install -r requirements.txt

# 2. 改 config.json
#    - scanDirectory: 你本地视频根目录
#    - deviceMonitor.destinationBase: 自动复制目标根

# 3. 启动
python run.py          # Windows / macOS / Linux
# 或 Windows 双击 启动视频管理.bat
```

启动器做的事：开 Web（5000 端口）+ 启动设备监控后台线程。浏览器自动打开。

> ⚠️ Windows 中文路径乱码：`启动视频管理.bat` 已 `chcp 65001`。手工 `python run.py` 时如果路径含中文，先在 PowerShell 跑 `chcp 65001`。

---

## 2. 架构图

```
┌─────────────────────────────────────────────────────────────┐
│ 浏览器 (templates/index.html, 53KB 单文件 SPA)              │
│  - 表格渲染 / 单元格编辑 / 实时同步                          │
│  - 排序 sortStack 状态机                                    │
│  - 自动补全 pickCanonicalEnglish (4 规则)                    │
│  - 列宽拖拽 / 列显示 chip / 预览视频                         │
└──────────────────┬──────────────────────────────────────────┘
                   │ fetch + EventSource
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ Flask (app.py, 单文件 17 路由)                              │
│  - /api/data /api/save /api/scan  (CSV 读写)                │
│  - /api/config              (列配置 / 排序栈)               │
│  - /api/upload-*            (publish.example.com 上传)             │
│  - /api/pick-directory      (tkinter 子进程)                │
│  - /api/fix-dates /api/fix-empty-scan-dates  (数据迁移)     │
└─────────────┬───────────────────────────────┬───────────────┘
              │ 读写                          │ 启动后台线程
              ▼                              ▼
       video_manager.csv           device_monitor.py
       config.json                 ┌──────────────────┐
                                  │ 扫描 USB 设备     │
                                  │ ctypes GetDrives  │
                                  │ 复制 MP4 → 目标   │
                                  │ CSV 登记          │
                                  └──────────────────┘

独立工具 (Tkinter GUI):
  rotate_video.py     split_video.py     copy_progress_window.py
```

### 数据流（核心）

```
scan_directory() → 扫 MP4 → 检查已有 path →
  ├─ 已存在 → 保留编辑数据，只更新 path 元数据
  └─ 新建 → 空行（scan_date=今天, original_history_date=文件创建时间）

前端编辑 → input 事件 → tableData[idx][key] = value → scheduleAutoSave
  → 3s 后 POST /api/save → 写 CSV（**scan_date 保护**：空值回填旧值）

扫描设备 → 复制 MP4 → register_to_csv → 同上
```

---

## 3. 关键代码位置

> 一句话定位。**强烈建议收藏这个表**——找代码时打开它。

### 后端 `app.py`

| 行号 | 主题 |
|------|------|
| `:128-146` | `/api/config` GET/POST — 白名单字段含 `sortStack`、`sortColumn`、`sortDirection` |
| `:188` | 扫描时 `scan_date = datetime.now()` |
| `:241-243` | merge_history：两日期都用 hist_date（未动） |
| `:321-352` | `/api/save` 双层保护 scan_date（**核心安全网**）|
| `:1230-1247` | `/api/fix-dates` 一次性迁移（错填的 scan_date → original_history_date）|
| `:1249-1266` | `/api/fix-empty-scan-dates` 一次性迁移（空 scan_date → 今天）|
| `:1267+` | `/api/pick-directory` tkinter 子进程目录选择 |
| `:???-???` | `/api/upload-*`（5 个端点：generate / batch / run SSE / status / cancel）|

### 前端 `templates/index.html`

| 行号 | 主题 |
|------|------|
| `:360-372` | `sortStack` 全局 + `loadConfig` 恢复（旧字段兼容）|
| `:420-477` | `toggleSort` 3 状态循环 + `compareSingle` + `compareRows` |
| `:556-580` | `saveColConfig` 发 sortStack + 兼容字段 |
| `:695-715` | 表头渲染：箭头 + 优先级角标 |
| `:720-730` | scan_date 默认只读 + ✏️ 按钮 |
| `:785-820` | `handleCellEditLive` (input 事件) / `handleCellEditCommit` (change/INPUT blur) |
| `:822-850` | `pickCanonicalEnglish` 4 条规则 |
| `:855-880` | 弹框 + Toast |
| `:1298-1303` | `getSortedMapping` 预览页用 — 跟随 compareRows 自动支持多列 |

### 设备监控 `device_monitor.py`

| 行号 | 主题 |
|------|------|
| `:268-281` | `register_to_csv` 写新行（**scan_date = 今天** + original = 文件创建时间）|
| `:???` | 驱动检测 ctypes（`kernel32.GetLogicalDrives`）|

> 行号会随代码变动漂移。**用 `grep -n` 比记行号更靠谱**。

---

## 4. 测试

### 单元测试

```bash
python test_scan.py
```

只测扫描逻辑（`scan_directory` 是否能正确发现 MP4）。覆盖率低。

### 端到端测试（推荐）

```bash
# 必须先启动 Flask
python run.py

# 另一终端跑
node verify_auto_complete.js          # 自动补全 16/16
python verify_scan_date_protection.py # 录入日期保护 4/4
node verify_sort.js                   # 排序 19/19
```

**总计 39 断言**，全过才算 OK。

### 写新测试的约定

- **不动 Flask**：e2e 测试用 `http://localhost:5000` 跑真实 HTTP
- **不动用户数据**：测试前后要还原（参考 `verify_scan_date_protection.py` 的"测试 4 还原"）
- **Windows GBK 兼容**：脚本开头加 `sys.stdout.reconfigure(encoding="utf-8")`，emoji 改为 ASCII（如 `[OK]`/`[FAIL]`/`[PASS]`）
- **断言风格**：用 `[PASS]`/`[FAIL]` 前缀 + 计数器，结束时打印 `=== 结果: N pass / M fail ===`

### 跑测试前先

1. `rm -rf __pycache__`（防止旧字节码缓存）
2. 备份 `video_manager.csv` 到 `csv_backups/`

---

## 5. 常见坑

### 5.1 `config.json` 出现 API key？

> **不要再加了。** 项目已完全无外部 API 依赖。如果发现 key 类内容泄露（如 `sk-...`），应去对应服务商控制台 **rotate**。

### 5.2 修改 `app.py` 后没生效

Flask 默认不开 debug auto-reload，**改完要手动重启**：

```bash
# 找到当前 run.py 进程
tasklist | findstr python
# 杀掉
taskkill /PID <pid> /F
# 重启
python run.py
```

### 5.3 排序"无"状态怎么恢复

```js
// 浏览器 Console
sortStack = []; renderTable(); saveColConfig();
```

或编辑 `config.json` 把 `sortStack` 设为 `[]`。

### 5.4 前端编辑单元格时频弹"同步到全部"框

是 `input` 事件（每次按键）触发的。**这版代码已经修过**：
- `handleCellEditLive`（input 事件）→ 实时写回 + 中文自动补全，**不弹框**
- `handleCellEditCommit`（change / INPUT blur 事件）→ 离焦后才问"应用到全部"

如果再次出现这个症状，检查 `bindTableInputSync` 是否还在用 `wrap.addEventListener('input', ...)` 一把抓（应该分 input/change 两套）。

### 5.5 scan_date 被清空 / 显示为空

可能原因：
1. 老数据（`/api/fix-empty-scan-dates` 可修）
2. 误调用 `data[0]["scan_date"] = ""` + `/api/save`（保护逻辑应回填旧值）
3. 前端 `✏️` 按钮解锁后手改了空值（用户主动行为，允许）

`/api/save` 响应 JSON 的 `"protected": N` 字段会告诉你这次保住了几行。

### 5.6 `e2e` 测试报 `ECONNREFUSED`

Flask 没启动，或启动了别的实例占着 5000 端口。

```bash
netstat -ano | findstr :5000
```

### 5.7 Windows 路径含中文乱码

- 启动前 `chcp 65001`
- 或用 `启动视频管理.bat`（已带）

### 5.8 `_upload_now.py` 生成后找不到 `upload.py`

`vendor-upload-pkg/upload.py` 是嵌入的上传包，**不能删**。EXE 打包时 `视频管理.spec` 已 include。

---

## 6. 调试技巧

### 6.1 看前端内存数据

```js
// 浏览器 Console
tableData              // 全部数据
tableData.length       // 行数
tableData[0]           // 第一行
sortStack              // 当前排序栈
```

### 6.2 改前端代码不重启 Flask

直接刷新浏览器即可（前端是纯静态文件）。后端改完要重启 Flask。

### 6.3 测单条 API

```bash
curl -s http://localhost:5000/api/data | python -m json.tool | head
curl -s -X POST http://localhost:5000/api/scan -H "Content-Type: application/json" -d '{"directory":"/media\\test"}'
curl -s -X POST http://localhost:5000/api/pick-directory -H "Content-Type: application/json" -d '{}'
```

### 6.4 用 `ctx_execute_file` 静态分析大文件

```js
// 在 Claude Code 里
const lines = FILE_CONTENT.split('\n').length;
console.log('index.html 行数:', lines);
```

### 6.5 测排序不污染数据

```js
// 浏览器 Console，先备份
const _orig = JSON.parse(JSON.stringify(tableData));
// ... 做实验 ...
// 还原
tableData = _orig;
renderTable();
```

---

## 7. 改了东西别忘

| 改了 | 别忘 |
|------|------|
| `app.py` 加新 API | README "API 端点"表 + DEVELOPER_GUIDE 行号表 |
| `index.html` 加新列 | `config.json` `fieldnames` / `columnLabels` / `columnOrder` |
| 加新测试 | README "测试"段 + DEVELOPER_GUIDE "写新测试的约定" |
| 改 `config.json` 字段 | README "配置" 段同步示例 |
| 改排序逻辑 | 更新 `verify_sort.js` 用例 |
| 修 bug | DEV_PLAN.md 加一段"## 修复记录"（给未来会话参考）|

---

## 8. 相关文档

| 文件 | 用途 |
|------|------|
| `README.md` | 用户/上手文档（先读） |
| `DEVELOPER_GUIDE.md` | **本文件** — 开发者深度指南 |
| `DEV_PLAN.md` | 当前会话的工作日志（**非文档，仅历史**） |
| `OPTIMIZATIONS.md` | 20 项代码优化建议（按 ROI 排序） |
| `docs/EXPORT.md` | 导出 TXT 详细文档 |
| `docs/UPLOAD_DEVPLAN.md` | 上传功能开发计划（含 publish.example.com 流程）|
| `prompt.txt` | 项目原始需求描述 |
