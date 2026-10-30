# STRUCTURE — codec-hmd

> 文件与模块的目录映射。结构变化时同步本文件（见 wcs-manifest.yaml update_trigger）。

## 当前目录（重构前）

```
codec-hmd/
├── wcs-manifest.yaml           # WCS 中央索引（v2.0 必填）
├── README.md                   # 入口（待写）
├── prompt.txt                  # 用户原始需求
├── docs/                       # WCS 基线文档
│   ├── dev_plan.md
│   ├── dev_log.md
│   ├── project_status.md
│   ├── structure.md            # 本文件
│   ├── error_book.md
│   ├── features.md
│   ├── CODING_STANDARDS.md
│   └── workflow.md
├── .claude/
│   └── settings.local.json     # 本地权限
├── hmd-decode.js               # HMD 容器解析（CommonJS，Node + 浏览器共用）
├── hmd-decode.esm.js           # ES module 版本（hmd-preview.html 用）
├── hmd2mp4.js                  # CLI: HMD → MP4（ffmpeg remux）
├── hmd-preview.html            # 单目浏览器播放（WebCodecs）
├── hmd-player.html             # 旧版播放器（保留）
├── hmd-player-all-in-one.html  # 打包版播放器（保留）
├── side-by-side.html           # 双视频对比（保留）
├── serve.ps1                   # PowerShell 本地 HTTP 服务器
├── mp4-muxer.mjs               # mp4-muxer 库（CDN 拉取后保留）
└── session_00000/              # 样本 HMD 数据
    ├── part_000.hmd            # 主文件
    ├── part_001.hmd            # 续段
    ├── metadata.json           # 录制参数
    ├── extracted.h265          # 已转码的原始 HEVC
    ├── extracted.mp4           # 已转码的 MP4
    └── ...
```

## 模块依赖

```
hmd-preview.html ──import──> hmd-decode.esm.js
                                │
                                └──exports──> { parse, findPackets, ... }

hmd2mp4.js ──require──> hmd-decode.js
                         (CommonJS)

serve.ps1 ──(外部)──> ffmpeg
                       (HTTP 流给浏览器)
```

## 数据流

```
[SD 卡 .hmd]
  │
  ├─→ [hmd-decode.js] ─→ 解析 → { video: HEVC, imu: samples }
  │                              │
  │                              ├─→ [hmd-preview.html] 浏览器内 WebCodecs 播放
  │                              └─→ [hmd2mp4.js] ffmpeg remux → MP4
  │
  └─→ [视频-sort-package 集成后]
        ├─→ [SQLite video_manager 表] 入库
        └─→ [Web 端] 列表/筛选/编辑
```

## 重构后（并入 video-sort-package）

```
video-sort-package/
├── app.py                      # Flask 后端（含 /api/hmd/*）
├── db.py                       # SQLite 连接 + schema
├── templates/
│   ├── index.html              # 视频列表（HMD 视频 + MP4 视频 共用）
│   ├── hmd_preview.html        # HMD 浏览器播放（含双目）
│   └── static/
│       └── hmd/
│           ├── hmd-decode.esm.js   # 从 codec-hmd 搬来
│           ├── side-by-side.html   # 从 codec-hmd 搬来
│           └── ...
├── tools/
│   └── hmd2mp4.py              # 从 hmd2mp4.js 改写为 Python
├── video_sort.db               # SQLite（取代 video_manager.csv 为主）
├── video_manager.csv           # 导入/导出兼容
├── recorders.csv               # 新增
├── devices.csv                 # 新增
├── sd_cards.csv                # 新增
├── task_keywords.csv           # 新增
├── recordable_tasks.csv        # 新增
├── verify_*.py / verify_*.js   # 回归脚本
└── ...
```

## SQLite Schema（规划）

```sql
-- 主表：原 video_manager.csv 升级版
CREATE TABLE video_manager (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,              -- 文件或目录路径
    location_status TEXT,                    -- local / history / sd_pending
    scan_date TEXT,
    original_history_date TEXT,
    work_content_cn TEXT,
    work_content_en TEXT,
    category TEXT,
    recorder_id INTEGER,                     -- → recorders.id
    upload_feasibility TEXT,
    uploaded TEXT,
    extra_description TEXT,
    score REAL,
    duration TEXT,                          -- HH:MM:SS
    -- 新字段
    device_id INTEGER,                       -- → devices.id
    sd_id INTEGER,                          -- → sd_cards.id
    task_code TEXT,                          -- → recordable_tasks.task_code
    hmd_layout TEXT,                         -- mono / stereo-sbs / stereo-interleaved
    hmd_metadata_path TEXT,                 -- 指向 metadata.json
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (recorder_id) REFERENCES recorders(id),
    FOREIGN KEY (device_id) REFERENCES devices(id),
    FOREIGN KEY (sd_id) REFERENCES sd_cards(id),
    FOREIGN KEY (task_code) REFERENCES recordable_tasks(task_code)
);

CREATE TABLE recorders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recorder_id TEXT UNIQUE NOT NULL,        -- 业务编号，如 LX01
    name TEXT NOT NULL,                      -- 中文姓名
    alias TEXT,                              -- 拼音/英文
    phone TEXT,
    note TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT UNIQUE NOT NULL,          -- 业务编号，如 D02
    model TEXT,                              -- 设备型号
    sn TEXT,                                 -- 序列号
    location TEXT,                           -- 存放位置
    note TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE sd_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    volume_serial TEXT UNIQUE,               -- 来自 wmic/fsutil
    volume_label TEXT,                       -- SD 卡卷标
    device_id INTEGER,                       -- → devices.id
    note TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (device_id) REFERENCES devices(id)
);

CREATE TABLE task_keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scene TEXT,                              -- 场景：车间/户外/实验室
    product TEXT,                            -- 产品：A/B/C
    task TEXT,                               -- 任务：装配/检测/搬运
    tool TEXT,                               -- 工具：机械臂/AGV/相机
    process TEXT,                            -- 工序：上料/焊接/喷涂
    name_en TEXT NOT NULL,                   -- 简称：P2G1
    name_cn TEXT,                            -- 中文名
    UNIQUE (scene, product, task, tool, process)
);

CREATE TABLE recordable_tasks (
    task_code TEXT PRIMARY KEY,               -- P2G1-2-INS-RG-WL
    keyword_id INTEGER NOT NULL,
    seq INTEGER NOT NULL,                    -- 同 keyword 下的序号
    difficulty TEXT NOT NULL,                -- simple / medium / hard
    planned_duration_s INTEGER NOT NULL,      -- 3600 / 7200 / 36000
    actual_duration_s INTEGER DEFAULT 0,
    last_recorded_at TEXT,
    note TEXT,
    FOREIGN KEY (keyword_id) REFERENCES task_keywords(id)
);

CREATE INDEX idx_vm_path ON video_manager(path);
CREATE INDEX idx_vm_task ON video_manager(task_code);
CREATE INDEX idx_sd_serial ON sd_cards(volume_serial);
```
