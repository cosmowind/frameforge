# Video Sort Package

一个面向运动相机/SD 卡视频素材的本地管理工具：自动监听外置设备、归类整理、用网页表格编辑元数据、调用 ffmpeg 旋转/分割、批量上传到 [publish.example.com](https://publish.example.com) 并管理上传状态。

> **目标场景**：每次拍摄后插上 SD 卡 → 工具自动把 `DCIM/DJI_xxx` 下的 MP4 复制到 `/media/inbox` → 在网页里给每条视频填"工作内容" → 一键生成上传脚本 → 在 publish.example.com 上投稿 → 自动清理本地已上传文件。

---

## ✨ 功能总览

### 1. 🎥 视频目录扫描与元数据管理（核心）
- **扫描本地目录**：递归收集所有 `.mp4` 文件
- **CSV 持久化**：以 `video_manager.csv` 存储每条视频的 13 个字段（见下表）
- **历史合并**：将历史 `video_managerMMDD-*.csv` 合并为 `archive/video_manager_history.csv`
- **自动回填**：新发现的视频自动建空行；已存在的保留人工编辑数据
- **删除记录**：勾选行后从 CSV 中删除（自动备份）

### 2. 🌐 Web 端表格编辑器（`templates/index.html`）
- **单页应用**：浏览器内查看/编辑/播放
- **列控制**：列名 chip 点击切换显示；列宽可拖动调整；列顺序可拖动重排
- **行预览**：点击"预览"按钮在同页内播放视频；支持"上一个/下一个"导航
- **实时编辑**：单元格/预览区修改即时同步到内存
- **快捷键**：`Ctrl+S` 保存全部
- **导出 TXT**：勾选要导出的列和行，一键下载 `export.txt`（详见 `docs/EXPORT.md`）

### 3. 🔌 USB 设备自动监听（`device_monitor.py`）
- **驱动检测**：用 `ctypes` 调 Windows `kernel32.GetLogicalDrives / GetDriveType` 识别可移动/外置盘
- **后台扫描**：可配置间隔（默认 60s）扫描所有非系统盘
- **视频源识别**：
  - **单目设备（MP4）**：匹配 `DCIM` / `MP_ROOT` / `PRIVATE` 等关键字、`DJI_001/002`、`100GOPRO`、`GOPRO` 等子目录
  - **双目设备（HMD）**：扫描 `hmd/` 目录下的 session 文件夹（包含 `metadata.json` + `part_*.hmd`）
  - **数据设备（Data）**：扫描 `data/` 目录下的 session 文件夹（包含 `session.json` + 视频文件）
- **自动复制**：
  - **MP4**：复制到 `/media/inbox`（MMDD = 复制当天月日）
  - **HMD**：复制到 `/media/inbox\hmd\<device_id>_session_xxxxx/`（自动添加设备ID前缀）
  - **Data**：复制到 `/media/inbox\data\<device_id>_session_xxxxx/`（自动添加设备ID前缀）
- **设备前缀**：自动从 `metadata.json` 或 `session.json` 读取设备ID，为 session 文件夹添加 `6位设备ID_` 前缀，避免不同设备 session 编号冲突
- **复制后清理**：
  - **MP4**：源目录下所有 `.mp4 / .lrf` 删除，但保留 `.jpg` 照片
  - **HMD/Data**：删除已复制的源 session 目录
- **空目录清理**：递归清理复制后留下的空目录
- **进度窗口**：Tkinter 弹窗显示复制进度（`copy_progress_window.py`）
- **CSV 登记**：复制完成自动在 `video_manager.csv` 增加新行（文件类型分别为 `mp4`、`hmd`、`data`）

### 4. 🔁 中英自动补全（替代原 AI 翻译）
基于 CSV 已有数据的"中文 → 英文"自动补全，**纯前端，无外部 API**：

- **自动补全**：填写或修改某条记录的中文 `work_content_cn` 时，若表中已有相同中文的记录，**自动用那条的英文填入** `work_content_en`
- **同步提示**：编辑英文时，若同中文记录 **≥ 2 条**，弹出"是否同步到全部"对话框
  - **应用到全部**：把这条新英文写到所有同中文记录
  - **仅此条**：只改这一条；未来同中文记录的自动补全英文按下表规则取值
- **"默认英文"选择规则**（用于未来新记录的英文）：
  1. 同中文记录只有 1 条 → 用这条
  2. 共 2 条 → 用"另一条"（非刚编辑的那条）
  3. > 2 条 → 用出现次数最多的英文
  4. 出现次数并列最多 → 随机挑一个 + Toast 提示："建议在中文后加 -1/-2/-3 后缀以区分"

> 说明：早期版本曾调用 MiniMax M2.7 做 AI 翻译；为减少外部依赖与凭据管理，已用此机制替换。
> **重要**：因为不再需要任何外部 API key，**`config.json` 里**没有任何凭据。如发现 key 类内容泄露，应立即去对应服务商控制台 rotate。

### 5. 🔢 排序（3 状态循环 + 多列优先级）
- **3 状态循环**：点击列头在 `无 → 升序 → 降序 → 无` 之间循环
- **多列排序**：每点一个新列就升为**第一优先级**；同列再点切换升/降
- **列头反馈**：
  - 未排序列 → 灰色 `▲`
  - 已排序列 → 蓝色 `▲` / `▼` + 优先级角标 `<sup>1</sup>` `<sup>2</sup>` `<sup>3</sup>`（数字小=优先级高）
  - 鼠标悬停 title：`点击切换：无 → 升序 → 降序`
- **类型感知**：自动检测数字 / 日期（`YYYY-MM-DD...`）/ 字符串三类型分别比较
- **持久化**：排序状态存 `config.json.sortStack`，刷新页面后保留

### 6. 🔄 视频旋转（`src/scripts/rotate_video.py`）
- 独立 GUI 工具：拖放或选择文件/文件夹
- 调 `ffmpeg -vf transpose=...` 实现 90°/180°/270° 无损旋转
- 后台线程执行，实时显示 ffmpeg 日志
- 输出文件名自动加 `(rotated_90)` 后缀

### 7. ✂️ 视频分割（`src/scripts/split_video.py`）
- 独立 GUI 工具：选文件、选输出目录、设段数
- 用 `ffprobe` 提取关键帧时间戳，在最接近等分点的位置切割（避免黑帧/卡顿）
- **30 秒最小段** 规则（项目硬性要求）
- 3GB 以上大文件强制均匀分割

### 8. 📤 批量上传到 publish.example.com（`/api/upload-*`）
- **生成脚本**：勾选行后端生成自包含的 Python runner（包含 `vendor-upload-pkg/upload.py`）
- **本地执行**：另开终端窗口跑 `python _upload_now.py`，避免阻塞 Web
- **SSE 实时进度**：每上传完一条，前端实时显示（`/api/upload-run` + EventSource）
- **状态查询**：`/api/upload-status` / `/api/upload-cancel`
- **去重**：每条视频旁边写 marker 文件，重复跑自动跳过
- **失败重跑**：命令可重入，服务端 dedup
- **字段映射**（CSV → upload 参数）：
  - `path` → `--file`
  - `work_content_en` → `--label`
  - `extra_description` → `--notes`
  - 固定参数（来自 `config.json` / `.env`）：`--country CN --region Shanghai --recorder "lingxu zhou" --category industrial_manufacturing --subcategory mfg_other`

### 9. 🧹 上传后自动清理
- `_upload_now.py` 检测到 `vendor-upload-pkg/upload.py` 上传成功后，自动删除本地分出来的 parts
- （详见 `prompt.txt` 描述）

### 10. 🗓 录入日期保护（双保险）
- **前端**：`scan_date` 单元格默认 `readonly`（灰底），`✏️` 按钮 → 解锁/重锁
- **后端**：`/api/save` 读取旧 CSV，若新数据中某行 `scan_date` 为空而旧 CSV 中有值，则**自动回填**旧值
  - 返回 JSON 多 `"protected": <int>` 字段告诉你保住了几行
- 防止测试或前端 bug 把录入日期意外清空

---

## 📂 数据字段（`config.json.fieldnames`）

| 字段键 | 中文标签 | 类型 | 说明 |
|--------|----------|------|------|
| `path` | 视频路径 | path | 完整文件路径 |
| `location_status` | 状态 | select-location | local / uploaded / … |
| `scan_date` | 录入日期 | input | 扫描加入的日期 |
| `original_history_date` | 原始日期 | input | 历史 CSV 解析出的日期 |
| `work_content_cn` | 工作内容（中文） | input | 中文描述 |
| `work_content_en` | 工作内容（英文） | input | 英文描述（用于上传） |
| `category` | 类别 | input | 自由标签 |
| `recorder` | 录制者 | input | 自由标签 |
| `upload_feasibility` | 上传可行性 | select-feasibility | 高/中/低 |
| `uploaded` | 已上传 | select-yesno | Yes / No |
| `extra_description` | 额外描述 | input | 补充说明（→ notes） |
| `score` | 得分 | input | 自由评分 |
| `duration` | 时长 | duration | 来自 ffprobe |

列显示、宽度、顺序默认在 `config.json` 中配置，前端 chip / 拖拽改动会写回。

---

## 🚀 快速启动

### 方式 1：开发模式

```bash
# 1. 装依赖
pip install -r requirements.txt

# 2. 编辑 config.json
#    - scanDirectory: 你本地视频根目录
#    - deviceMonitor.destinationBase: 复制目标根目录

# 3. 启动（同时拉起 Web + 设备监控线程）
python src/run.py
# 或 Windows 双击 启动视频管理.bat
```

浏览器自动打开 http://localhost:5000

### 方式 2：打包成 EXE

```bash
pip install pyinstaller
pyinstaller 视频管理.spec
# 产物在 dist/视频管理/
```

打包时 `tkinterdnd2` 被显式 exclude（spec 中已配置）。

### 方式 3：单独跑上传

```bash
python _upload_now.py --log-file logs/upload_$(date +%Y%m%d_%H%M%S).log
```

---

## 🌐 API 端点

### 核心数据

| Method | Path | 用途 |
|--------|------|------|
| GET | `/` | 主页 |
| GET | `/api/config` | 取列配置（显示/顺序/宽度/类型/排序） |
| POST | `/api/config` | 部分保存列配置（只更新提供的字段） |
| GET | `/api/data` | 取全部 CSV 数据 |
| POST | `/api/scan` | 扫描 `scanDirectory` 合并到 CSV |
| POST | `/api/merge-history` | 合并历史 CSV |
| POST | `/api/delete` | 按行号删除（自动备份到 `csv_backups/`） |
| POST | `/api/save` | 把内存数据写回 CSV（**保护 scan_date**） |
| GET | `/api/video?path=...` | 流式返回视频（用于预览） |
| POST | `/api/export` | 导出 TXT（按列/行筛选） |

### 设备与文件选择

| Method | Path | 用途 |
|--------|------|------|
| POST | `/api/pick-directory` | 弹原生目录选择对话框（tkinter 子进程） |

### 上传

| Method | Path | 用途 |
|--------|------|------|
| GET | `/api/upload-config` | 取上传固定参数 |
| POST | `/api/upload-generate` | 生成 `_upload_now.py` / `.cmd` |
| POST | `/api/upload-run-cmd` | 启动终端跑上传脚本 |
| POST | `/api/upload-batch` | 准备上传 session，返回 session_id |
| GET | `/api/upload-run` | **SSE** 流式推送上传进度 |
| GET | `/api/upload-status` | 查 session 状态 |
| POST | `/api/upload-cancel` | 取消 session |

### 数据迁移（一次跑完建议删）

| Method | Path | 用途 |
|--------|------|------|
| POST | `/api/fix-dates` | 旧数据迁移：把错填的 scan_date 挪回 original_history_date |
| POST | `/api/fix-empty-scan-dates` | 旧数据迁移：location=local 且 scan_date=空 的行回填今天 |

---

## 📁 目录结构

```
video-sort-package/
├── src/                          # 📦 所有业务代码
│   ├── app.py                    #   Flask 主应用（路由 + create_app）
│   ├── config.py                 #   全局常量 & 路径配置
│   ├── run.py                    #   应用启动入口（Flask + 设备监控线程）
│   ├── launcher.py               #   PyInstaller EXE 打包入口
│   ├── auto_upload.py            #   FrameForge 自动上传（Playwright）
│   ├── device_monitor.py         #   USB/SD 卡监听 + 自动复制（MP4+HMD+Data）
│   ├── copy_progress_window.py   #   Tkinter 复制进度弹窗
│   ├── services/                 #   业务逻辑层（8 个服务）
│   ├── models/                   #   数据模型层（CSV 读写 + 维表 CRUD）
│   ├── utils/                    #   工具函数层（路径/格式化/视频帧）
│   ├── tools/                    #   外部工具集（HMD 预处理/解码/场景提取）
│   ├── scripts/                  #   独立运维脚本（24 个，见下表）
│   ├── templates/                #   Jinja2 模板（index.html + hmd_preview.html）
│   ├── static/hmd/               #   浏览器端 HMD 模块（WebCodecs 解码）
│   └── vendor-upload-pkg/        #   嵌入的上传包（upload.py + cookie 模板）
│
├── runtime/                      # 🔒 运行时数据（Git ignored）
│   ├── data/                     #   CSV + config.json + 维表
│   ├── hmd_cache/                #   HMD 预处理产物（h265/mp4/jpg）
│   ├── thumbnails/               #   缩略图缓存
│   ├── csv_backups/              #   CSV 自动备份（10 份轮转）
│   ├── logs/                     #   运行日志
│   ├── browser_data/             #   Chrome 持久化数据
│   └── archive/                  #   历史数据归档
│
├── docs/                         # 📚 项目文档（18 个 .md + 8 个 .txt）
├── 启动视频管理.bat               # 一键启动（检查依赖 → python src/run.py）
├── 启动视频管理(跳过预处理).bat     # 跳过自动预处理启动
├── 打包备份.bat                   # 调用 pack.ps1 打包到 zip
├── pack.ps1                      # 打包脚本（排除 runtime/）
├── 视频管理.spec                  # PyInstaller 打包配置
├── requirements.txt              # Python 依赖
└── README.md                     # 本文件
```

### 🔧 独立运维脚本（`src/scripts/`，从项目根目录执行）

| 脚本 | 用途 | 运行方式 |
|------|------|----------|
| `batch_preprocess.py` | 批量预处理符合条件的 HMD session | `python src/scripts/batch_preprocess.py --yes` |
| `reprocess_incomplete.py` | 重处理缓存不完整的 HMD session | `python src/scripts/reprocess_incomplete.py` |
| `rename_all.py` | 全量文件名迁移（6 步：源→缓存→文件→CSV→缩略图→状态） | `python src/scripts/rename_all.py --execute` |
| `fix_duplicate_prefix.py` | 修复重复设备ID前缀的文件夹名 | `python src/scripts/fix_duplicate_prefix.py` |
| `preprocess_manager.py` | 预处理管理器（查看/重试/清理状态） | `python src/scripts/preprocess_manager.py` |
| `rotate_video.py` | 视频旋转 CLI（ffmpeg） | `python src/scripts/rotate_video.py` |
| `split_video.py` | 视频分割 CLI（30s 边界 + 3GB 阈值） | `python src/scripts/split_video.py` |
| `check_hmd_cache.py` | HMD 缓存完整性检查 | `python src/scripts/check_hmd_cache.py` |
| `cleanup_duplicate_sessions.py` | 清理重复 session | `python src/scripts/cleanup_duplicate_sessions.py` |
| `merge_hmd_directories.py` | 合并 HMD 目录 | `python src/scripts/merge_hmd_directories.py` |
| `reprocess_hmd.ps1` | 通过 Flask API 批量重处理 HMD（PowerShell） | `.\src\scripts\reprocess_hmd.ps1` |
| `verify_pages.py` | 38 个端到端集成测试 | `python src/scripts/verify_pages.py` |
| `check_routes.py` | 路由 & 函数清单检查 | `python src/scripts/check_routes.py` |
| `diagnose_form.py` | 上传表单诊断 | `python src/scripts/diagnose_form.py` |
| `fix_video_durations.py` | 修复视频时长字段 | `python src/scripts/fix_video_durations.py` |
| `check_all_cache_integrity.py` | 全量缓存完整性检查 | `python src/scripts/check_all_cache_integrity.py` |
| ... 等共 24 个脚本 | — | — |

---

## ⚙️ 配置 `config.json` 关键项

```jsonc
{
  "scanDirectory": "/media\\0530",          // 手动扫描根目录
  "deviceMonitor": {
    "enabled": true,
    "destinationBase": "/media\\0530",      // 自动复制目标根（MMDD 子目录会自动创建）
    "excludeDrives": ["C", "D"],             // 不扫描这些盘符
    "scanInterval": 60,                       // 秒
    "deleteAfterCopy": true,                  // 复制后是否清空源
    "videoPatterns":  ["DCIM", "MP_ROOT", "PRIVATE"],
    "subdirPatterns": ["DJI_001", "DJI_002", "DJI_003",
                         "DJI001", "DJI002", "DJI003",
                         "100GOPRO", "GOPRO", ""],
    "hmdPatterns":   ["hmd"],                  // HMD 双目设备目录名模式
    "dataPatterns":  ["data"]                  // Data 数据设备目录名模式
  },
  "fieldnames": [...],       // 13 个字段键
  "columnLabels": {...},     // 中文标签
  "columnVisibility": {...}, // 默认显示哪些
  "columnTypes":    {...},   // 每列的输入类型
  "columnWidths":   {...},   // 默认列宽（px）
  "columnOrder":    [...],   // 默认顺序
  "sortStack":      [],      // 多列排序栈 [{col, dir}]，数组末尾 = 最高优先级
  "sortColumn":     "scan_date",   // 兼容旧字段：栈末 = 主排序列
  "sortDirection":  "asc"          // 兼容旧字段：栈末方向
}
```

**配置说明**：

- `deviceMonitor.hmdPatterns`：指定 SD 卡上 HMD 双目设备的目录名（默认 `["hmd"]`）
- `deviceMonitor.dataPatterns`：指定 SD 卡上 Data 数据设备的目录名（默认 `["data"]`）
- HMD 和 Data 的 session 会自动添加 **6位设备ID前缀**（如 `4aa45c_session_00000`）
- 设备ID 从 `metadata.json` 或 `session.json` 中读取，如果读取失败则使用 SD 卡卷序列号

> **关于凭据**：`config.json` **不应该**存任何 API key / cookie / 密码。
> 上传 publish.example.com 用的 cookie 在 `vendor-upload-pkg/cookie.txt.template`（占位），
> 用户在本地自行复制为 `cookie.txt`（**`cookie.txt` 已被 .gitignore 排除**）。

---

## 📦 依赖

```
flask
werkzeug
requests
```

外部命令：
- **ffmpeg / ffprobe**（系统 PATH 中）：旋转、分割、时长读取都依赖
- **Windows**：`device_monitor.py` 用 `ctypes` 调 `kernel32`，仅 Windows 可用

---

## 🧪 测试

```bash
# 启动 Flask（必须，否则 e2e 测试连不上）
python src/run.py

# 端到端测试套件（先启动 Flask，在另一终端跑）
node src/scripts/verify_auto_complete.js          # 自动补全 16/16
python src/scripts/verify_scan_date_protection.py # 录入日期保护 4/4
node src/scripts/verify_sort.js                   # 排序 19/19

# 单元测试
python src/scripts/test_scan.py
```

3 套 e2e 测试 = 39 个断言，全过才算 OK。详见 [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) "测试"段。

---

## 📚 文档索引（WCS v2.0）

本项目用 [WCS（Wind Code Standard）v2.0](~/.claude/skills/wcs-cn/SKILL.md) 中央 manifest + 按需加载 docs 的方式管理文档。AI 接手时先读 [`wcs-manifest.yaml`](wcs-manifest.yaml)，再按任务类型加载对应 docs。

| 文档 | 用途 |
|---|---|
| [`wcs-manifest.yaml`](wcs-manifest.yaml) | 中央索引（必读，~2KB） |
| [`docs/project_status.md`](docs/project_status.md) | 技术栈 / 已实现能力 / 运行状态 |
| [`docs/structure.md`](docs/structure.md) | 目录结构 + 模块职责 |
| [`docs/dev_plan.md`](docs/dev_plan.md) | 路线图 + 进行中 + 待办 |
| [`docs/dev_log.md`](docs/dev_log.md) | 实现记录 + 验证依据 |
| [`docs/error_book.md`](docs/error_book.md) | 缺陷根因 + 修复手册 |
| [`docs/features.md`](docs/features.md) | 已实现能力索引 |
| [`docs/CODING_STANDARDS.md`](docs/CODING_STANDARDS.md) | 代码规范纲领 |
| [`docs/workflow.md`](docs/workflow.md) | 执行流程 + 质量门禁 |
| [`docs/prompt.txt`](docs/prompt.txt) | 用户原始需求 |

---

## ❓ 常见问题

**Q: 插了 SD 卡但没自动复制？**
- 检查 `deviceMonitor.enabled` 是否 `true`
- 检查 `excludeDrives` 是否包含该盘符
- 确认 SD 卡目录里有 `DCIM/DJI_001` 之类的子目录
- 看 `device_monitor.log`

**Q: 同中文的英文没自动补全？**
- 先确认中文字段非空且与其它行精确一致（去尾空格后比较）
- 若同中文 ≤ 1 条则不弹同步框
- 若并列最多英文，会弹 toast 提示加 `-1/-2/-3` 后缀

**Q: 上传脚本里找不到 upload.py？**
- `vendor-upload-pkg/upload.py` 必须在；EXE 打包时 spec 已包含

**Q: 中文文件名 / 路径在 Windows 上乱码？**
- `启动视频管理.bat` 已 `chcp 65001`；如手工启动需先 `chcp 65001`

**Q: 上传中断后想继续？**
- 重跑同一条命令即可，服务端 dedup；本地未上传的视频会从断点继续

**Q: 排序状态怎么清？**
- 浏览器 Console 跑 `sortStack = []; renderTable(); saveColConfig();`
- 或编辑 `config.json` 把 `sortStack` 设为 `[]`

**Q: e2e 测试报 `ECONNREFUSED`？**
- Flask 没启动。先在另一终端跑 `python run.py`

**Q: 怎么改默认列宽 / 哪些列默认显示？**
- 改 `config.json` 的 `columnWidths` / `columnVisibility`
- 也可在浏览器里点列头 chip 改显示、拖右边线改宽度，会自动写回 config.json
