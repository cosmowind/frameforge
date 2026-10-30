# 项目架构文档

> 最后更新：2026-06-24
> 基于目录重组（`runtime/` 缓存目录 + `src/` 业务代码目录）

---

## 📁 目录结构总览

```
video-sort-package/
│
├── runtime/                      # 🔒 所有运行时数据 & 缓存（已 gitignore）
│   ├── data/                     #   持久状态：config.json, *.csv, upload_state.json
│   ├── thumbnails/               #   缩略图缓存（*.jpg + *.fp 指纹）
│   ├── hmd_cache/                #   HMD 预处理产物（h265/mp4/jpg）
│   ├── csv_backups/              #   CSV 10 份轮转备份
│   ├── logs/                     #   运行日志（*.log）
│   ├── browser_data/             #   浏览器 session/cookie
│   └── archive/                  #   历史数据归档
│
├── src/                          # 📦 所有业务代码
│   ├── app.py                    #   Flask 主应用（路由 + create_app）
│   ├── config.py                 #   全局常量 & 路径配置
│   ├── run.py                    #   应用启动入口（Flask + 设备监控线程）
│   ├── launcher.py               #   PyInstaller EXE 打包入口
│   ├── auto_upload.py            #   FrameForge 自动上传
│   ├── device_monitor.py         #   存储卡自动导入模块
│   ├── copy_progress_window.py   #   复制进度弹窗（tkinter）
│   │
│   ├── services/                 #   业务逻辑层
│   │   ├── lazy_loader.py        #     惰性导入 + 预处理共享状态
│   │   ├── video.py              #     缩略图/视频帧/HMD 抽帧
│   │   ├── preprocess_service.py #     预处理服务
│   │   ├── scan_service.py       #     目录扫描服务
│   │   ├── upload_service.py     #     SSE 上传服务
│   │   ├── data_service.py       #     数据 CRUD 服务
│   │   ├── dim_service.py        #     维表服务
│   │   └── upload_options.py     #     上传选项加载
│   │
│   ├── models/                   #   数据模型层
│   │   ├── csv_store.py          #     CSV 读写（read/write/atomic backup）
│   │   └── dim_registry.py       #     维表 CRUD
│   │
│   ├── utils/                    #   工具函数层
│   │   ├── path_utils.py         #     路径处理（日期提取、缓存目录）
│   │   ├── format_utils.py       #     格式化（时长、文件日期）
│   │   └── video_frames_helper.py #    MP4 视频帧提取
│   │
│   ├── tools/                    #   外部工具集
│   │   ├── hmd_preprocess.py     #     HMD → MP4 完整预处理
│   │   ├── hmd_fast_preprocess.py #    HMD → h265 快速预处理（含 .h265 自动清理）
│   │   └── hmd_decode_py.py      #     Pure-Python HMD 解码器
│   │
│   ├── scripts/                  #   独立运行脚本（24 个）
│   ├── static/                   #   Flask 静态资源
│   ├── templates/                #   Flask Jinja2 模板
│   └── vendor-upload-pkg/        #   上传页面依赖
│
├── docs/                         # 📚 文档
├── .gitignore                    # Git 忽略规则
├── README.md                     # 项目说明
├── requirements.txt              # Python 依赖
├── pack.ps1                      # 打包脚本（排除 runtime/）
├── 打包备份.bat                   # 一键打包到 zip
├── 启动视频管理.bat               # 用户启动入口
├── 启动视频管理(跳过预处理).bat     # 跳过预处理启动
└── 视频管理.spec                  # PyInstaller 打包配置
```

---

## 🔀 模块依赖关系

```
启动入口:
  启动视频管理.bat → python src/run.py → Flask + device_monitor

PyInstaller:
  视频管理.spec → src/launcher.py → src/run.py

核心导入链:
  src/config.py           (最底层 — 路径常量)
    ↓
  src/models/             (CSV 读写 / 维表 CRUD)
    ↓
  src/services/           (业务逻辑 — video / scan / upload / preprocess)
    ↓
  src/app.py              (Flask 主应用 — 所有路由直接定义在 app.py)
    ↓
  src/run.py              (启动入口 — 磁盘空间检查 + 自动预处理决策)
```

**循环依赖解决**：`services/lazy_loader.py` 作为共享基础层，存放所有惰性导入函数和预处理共享状态（`_PREPROCESS_STATUS`），避免 `app.py` ↔ `services/video.py` 循环依赖。

---

## 🛠 关键设计决策

| 决策 | 说明 |
|------|------|
| **`runtime/` 与 `src/` 分离** | 所有运行时产物（日志、缩略图、HMD 缓存、CSV 备份、浏览器数据）统一放入 `runtime/`，gitignore 可仅针对该目录 |
| **`src/` 集中业务代码** | `models/`, `services/`, `utils/`, `tools/`, `scripts/`, `static/`, `templates/` 均在 `src/` 下，根目录保持极简。`routes/` 已删除（蓝图未注册的死代码），路由直接定义在 `app.py` |
| **无根入口包装** | 因为 `run.py` / `launcher.py` 与 `src/run.py` 同名冲突导致循环导入，改为直接在根层引用 `src/run.py`（bat 文件：`python src/run.py`） |
| **惰性导入** | `tools/` 下的预处理模块通过 `services/lazy_loader.py` 惰性加载，避免重依赖在启动时阻塞 |
| **原子 CSV 写入** | `os.replace()` + 10 文件备份轮转，保证数据安全 |
| **缩略图缓存失效** | SHA1 指纹（path + mtime + size）检测源文件变更，自动刷新缓存 |

---

## 🚀 运行 & 构建

```bash
# 开发环境启动
python src/run.py

# 或双击 batch 文件
启动视频管理.bat

# 打包到 zip（排除 runtime/）
pack.ps1

# PyInstaller 打包为 EXE
pyinstaller 视频管理.spec
```

---

## 📋 目录分类规则

| 目录 | 内容 | 规则 |
|------|------|------|
| `src/` | 所有 Python 业务代码 | 被其他模块 `import` 或有 `if __name__ == "__main__"` |
| `runtime/` | 所有运行时/缓存/用户数据 | .gitignore 统一忽略该目录 |
| `docs/` | 项目文档 | Markdown + 参考文本 |
| `根目录` | 入口脚本 + 构建配置 | `.bat`, `.ps1`, `.spec`, `.md`, `requirements.txt` |

---

## 📊 拆分进度

| 步骤 | 文件 | 状态 |
|------|------|------|
| S1 | `config.py`（路径常量） | ✅ 完成 |
| S2 | `utils/path_utils.py` + `utils/format_utils.py` | ✅ 完成 |
| S3 | `models/dim_registry.py`（维表 CRUD） | ✅ 完成 |
| S4 | `models/csv_store.py`（CSV 主表读写） | ✅ 完成 |
| S5 | `services/lazy_loader.py`（惰性导入 + 共享状态） | ✅ 完成 |
| S6 | `services/scan_service.py`（目录扫描） | ✅ 完成 |
| S7 | `services/upload_service.py`（上传服务） | ✅ 完成 |
| S8 | `services/data_service.py` + `dim_service.py` | ✅ 完成 |
| S9 | `services/video.py`（缩略图/帧提取） | ✅ 完成 |
| S10-S11 | routes/*.py（5 蓝图）+ app.py 瘦身 | ✅ 完成 |
| — | 目录重组（`runtime/` + `src/`） | ✅ 完成 |
