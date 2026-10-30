# Structure — video-sort-package

> 项目目录与模块映射。改文件结构时同步更新本文件。

---

## 顶层目录

```
video-sort-package/
├── app.py                       # Flask 后端（全部 REST + CSV 读写）
├── config.json                  # 列定义 / 扫描目录 / 列宽 / 排序
├── video_manager.csv            # 主数据（20 列）
├── wcs-manifest.yaml            # WCS 中央索引（v2.0）
├── README.md                    # 项目入口 + 快速上手
├── prompt.txt                   # 用户原始需求
├── requirements.txt             # Python 依赖
├── run.py                       # 启动封装
├── launcher.py                  # launcher 入口
├── 启动视频管理.bat              # 一键启动（Windows）
├── 打包备份.bat                  # 项目 zip 打包
├── pack.ps1                     # PowerShell 打包脚本
│
├── templates/                   # Flask 模板
│   ├── index.html               # 主单页前端（表格 + 预览 + HMD 面板）
│   └── hmd_preview.html         # 独立 HMD 预览页（带 splitStereo）
│
├── static/                      # 静态资源
│   └── hmd/                     # HMD 浏览器端模块
│       ├── hmd-decode.esm.js    # 解析器 ESM 版
│       └── hmd-player-core.js   # WebCodecs 播放封装
│
├── docs/                        # WCS 基线文档
│   ├── project_status.md        # 当前快照
│   ├── structure.md             # 本文件
│   ├── dev_plan.md              # 路线图
│   ├── dev_log.md               # 实现记录
│   ├── error_book.md            # 缺陷手册
│   ├── features.md              # 能力索引
│   ├── CODING_STANDARDS.md      # 规范
│   ├── workflow.md              # 流程
│   ├── EXPORT.md                # 导出 TXT 旧文档
│   ├── README.md                # 旧 docs README
│   ├── UPLOAD_DEVPLAN.md        # 上传器开发计划（旧）
│   └── minimax接入参考.txt      # 接入参考
│
├── vendor-upload-pkg/           # 上传脚本 vendor（git 不追踪，由打包脚本下载）
│
├── csv_backups/                 # CSV 自动备份（保留最近 10）
│
├── archive/                     # 合并后的历史 CSV
│
├── logs/                        # 上传日志
│
├── device_monitor.py            # USB/SD 卡监听 + 复制
├── copy_progress_window.py      # 复制进度 Tkinter 窗口
├── rotate_video.py              # 视频旋转 CLI
├── split_video.py               # 视频分割 CLI（30s 边界 + 3GB 均匀）
├── _upload_now.py               # 上传脚本生成（运行时）
├── _upload_now.cmd              # 上传启动（生成）
│
└── docs/_archive/               # 旧测试数据（不追踪）
```

---

## 模块职责映射

### 后端：app.py

| 模块（按行） | 职责 |
|---|---|
| 常量 + 路径（1-100） | `BASE_DIR` / `CSV_PATH` / `DEFAULT_FIELDNAMES` / `SESSION_MARKER` |
| 工具函数（100-200） | `load_config` / `get_fieldnames` / `_get_video_duration` / `_fmt_duration` / `read_csv` / `write_csv` |
| 路由：`/api/config` / `/api/data` | 配置读写 + 表格数据 |
| 路由：`/api/scan` | MP4 + HMD 双模扫描，支持 `scope=current/all` |
| 路由：`/api/video` | 视频流（Range 头） |
| 路由：`/api/pick-directory` | 目录选择对话框（tkinter 子进程） |
| 路由：`/api/hmd/*` | HMD scan / info / raw / file / duration / register |
| 路由：`/hmd-preview` | 独立 HMD 预览页 |
| 路由：`/api/upload-*` | 上传器（旧，待 frameforge 规范） |
| 路由：`/api/fix-*` | 一次性数据迁移 |

### 前端：templates/index.html

| 模块（按行近似） | 职责 |
|---|---|
| CSS（1-300） | 表格 + 预览区 + 上传 dialog + HMD 内嵌面板 |
| HTML 结构（300-380） | toolbar / previewArea / hmdPanel / tableWrap / dialogs |
| JS：列定义（380-420） | `getDefaultColumns()` |
| JS：排序 + 列显隐（420-620） | 多列排序栈 + 列 chip + 列宽 + 列顺序拖拽 |
| JS：表格渲染 + 编辑（620-1100） | `renderTable` / 单元格编辑 / 自动保存 / 撤销 |
| JS：MP4 预览（1100-1280） | `preview(index)` + `navPreview` + `closePlayer` |
| JS：上传 + 导出（1280-1700） | `openUploadDialog` / `openExportDialog` / SSE 进度 |
| JS：HMD 预览（1700+） | `openHmdPreviewInline` / 双 canvas / splitStereo / 1×5×10×16× 速度 |

### 离线工具

| 文件 | 入口 | 用途 |
|---|---|---|
| `device_monitor.py` | `start_monitor()` | USB/SD 卡循环扫描；复制 → CSV |
| `rotate_video.py` | CLI | 单视频旋转 |
| `split_video.py` | CLI | 单视频分割（30s + 3GB 阈值） |
| `static/hmd/hmd-decode.esm.js` | ESM | 浏览器端 HMD 解析 |
| `static/hmd/hmd-player-core.js` | ESM | WebCodecs 播放封装 |

---

## 维护导航

- **改后端逻辑** → `app.py` + 对应 docs/error_book.md
- **改前端 UI** → `templates/index.html` + docs/features.md
- **改 HMD 解析** → `static/hmd/*` + `hmd_preview.html`
- **改上传器** → `app.py` 的 `/api/upload-*` + `vendor-upload-pkg/`
- **改设备监控** → `device_monitor.py` + `copy_progress_window.py`

---

## 关键约定

- **原子写**：`write_csv()` 自动备份 10 份 + `os.replace` 原子替换
- **路径**：Windows 风格 `F:\sys\...`；前端需 `encodeURIComponent`
- **编码**：所有 CSV / JSON 用 UTF-8 with BOM（`utf-8-sig`）
- **配置文件**：JSON；改列定义后前端自动合并 DEFAULT_FIELDNAMES
- **HEVC 帧率**：HMD 假设 30 fps 恒定（容器不携带）
- **dimension tables**：未来加（PR 2）