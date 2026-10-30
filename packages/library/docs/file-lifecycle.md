# 视频文件完整生命周期

> 从 SD 卡插入 → 预处理 → 预览 → 上传 → 清理，一个视频走过的每个阶段和涉及的所有文件路径。

---

## 📍 路径约定

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `dest_base` | `/media` | 目标盘根目录（config.json `scanDirectory` 可覆盖） |
| `MMDD` | 当天月日（如 `0615`） | `device_monitor.get_destination_dir()` 生成 |
| `RUNTIME_DIR` | `<项目根>/runtime` | 所有运行时产物根目录 |
| `HMD_CACHE_ROOT` | `runtime/hmd_cache` | HMD 预处理缓存根目录（环境变量可覆盖） |
| `thumbnails/` | `runtime/thumbnails` | 缩略图缓存目录 |

---

## 🔄 完整生命周期

```
┌─────────────────────────────────────────────────────────────┐
│  Phase 1: 设备导入 (device_monitor.py)                       │
│  SD 卡插入 → 自动复制 → 删除源 → CSV 注册                     │
├─────────────────────────────────────────────────────────────┤
│  Phase 2: 扫描注册 (app.py /api/scan)                       │
│  遍历目录 → 识别类型 → CSV 行创建/更新 → ffprobe 时长         │
├─────────────────────────────────────────────────────────────┤
│  Phase 3: 预处理 (hmd_fast_preprocess.py) —— 仅 HMD，可选    │
│  HMD 解码 → H265 抽帧 → MP4 封装 → 封面 → 预览帧 → 清 H265   │
│  目的：生成可播放 mp4 用于画廊预览，确认录制员/任务 ID        │
├─────────────────────────────────────────────────────────────┤
│  Phase 4: 画廊/预览 (app.py + video.py)                      │
│  缩略图生成 → 画廊网格 → 6 帧预览 → 视频播放                  │
├─────────────────────────────────────────────────────────────┤
│  Phase 5: 上传 (auto_upload.py)                              │
│  表单填写 → 原始 .hmd 文件注入 → 浏览器 OPFS 转 MCAP → 提交   │
├─────────────────────────────────────────────────────────────┤
│  Phase 6: 导出 (app.py /api/export)                         │
│  选列选行 → TXT 下载                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 1: 设备导入

> **触发**：SD 卡 / USB 设备插入，`device_monitor.py` 后台线程自动检测  
> **入口**：`DeviceMonitor._scan_and_copy()`  
> **影响范围**：磁盘 I/O、CSV 写入、SD 卡源删除

### 1.1 MP4 文件导入

| 步骤 | 操作 | 路径 |
|------|------|------|
| ① 扫描 SD 卡 | 在 `DCIM/`、`MP_ROOT/`、`PRIVATE/` 下查找 `.mp4` | SD 卡原始路径 |
| ② 去重检查 | 同名同大小是否已在 `dest_base` 下存在 | `dest_base/**/同名.mp4` |
| ③ 复制到本地 | `shutil.copy2` | **`<dest_base>/<MMDD>/<原始文件名>.mp4`** |
| ④ 删除 SD 卡源 | `os.remove` | SD 卡上的 `.mp4` + 同名 `.LRF` |
| ⑤ 保留照片 | 不删除 `.jpg` | — |
| ⑥ CSV 注册 | 新增一行（详见下） | `runtime/data/video_manager.csv` |
| ⑦ SD 卡注册 | 卷序列号 → device_id | `runtime/data/sd_cards.csv` |

**CSV 注册字段**：

| 字段 | 写入值 |
|------|--------|
| `path` | 目标文件完整路径 |
| `location_status` | `"local"` |
| `scan_date` | 当天 `YYYY-MM-DD` |
| `original_history_date` | ffprobe `creation_time` → mtime → ctime |
| `uploaded` | `"No"` |
| `file_type` | `"mp4"` （或留空，旧版兼容） |
| 其余字段 | 留空（待用户填写） |

### 1.2 HMD Session 导入

| 步骤 | 操作 | 路径 |
|------|------|------|
| ① 扫描 SD 卡 | 找 `hmd/` 下含 `metadata.json` + `part_*.hmd` 的目录 | SD 卡 `hmd/<session_name>/` |
| ② 去重检查 | 同 device_id + 同 session 名 + 同 part 数 | `dest_base/**/hmd/` |
| ③ 重命名 | 加日期前缀（≥0623）+ 设备 ID 前缀避免冲突 | `<MMDD>_<device_id_short>_<原session名>` |
| ④ 复制到本地 | `shutil.copytree`（整目录） | **`<dest_base>/<MMDD>/hmd/<MMDD>_<device_id>_<session>/`** |
| | 目录内容： | `part_000.hmd`, `part_001.hmd`, ..., `metadata.json` |
| ⑤ 删除 SD 卡源 | `shutil.rmtree` 整个源目录 | SD 卡上被复制的 session 目录 |
| ⑥ CSV 注册 | 新增一行 | `runtime/data/video_manager.csv` |
| ⑦ SD 卡注册 | 获取卷序列号 + 设备 ID | `runtime/data/sd_cards.csv` |
| ⑧ 自动预处理 | **已禁用**（当剩余磁盘空间是新一批视频体积3倍时自动开启），改为由 run.py 启动流程控制 | — |

**CSV 注册字段**：

| 字段 | 写入值 |
|------|--------|
| `path` | 目标 session 目录路径 |
| `location_status` | `"local"` |
| `scan_date` | 当天 `YYYY-MM-DD` |
| `original_history_date` | `metadata.start_time` → 目录名 MMDD → mtime → 当天 |
| `uploaded` | `"No"` |
| `file_type` | `"hmd"` |
| `device_id` | 设备 ID 末 6 位 |
| `extra_description` | `"HMD session · N parts · X MB · part_*.hmd"` |

### 1.3 Data Session 导入

| 步骤 | 操作 | 路径 |
|------|------|------|
| ① 扫描 SD 卡 | `data/` 下含 `session.json` 或 `metadata.json`（无 HMD part） | SD 卡 `data/` |
| ② 复制到本地 | `shutil.copytree` | **`<dest_base>/<MMDD>/data/<MMDD>_<device_id>_<session>/`** |
| ③ 删除 SD 卡源 | `shutil.rmtree` | SD 卡源目录 |
| ④ CSV 注册 | `file_type = "data"` | `runtime/data/video_manager.csv` |

### 1.4 磁盘空间保护

复制前检查：`可用空间 < SD卡内容 × 2` → 暂停扫描（`_check_disk_space`、`_disk_space_ratio=2.0`）

---

## Phase 2: 扫描注册

> **触发**：用户点击"扫描"按钮，或 `POST /api/scan`  
> **入口**：`app.py` → `/api/scan`  
> **影响范围**：CSV 新增/更新行，Directory 自动重命名

### 2.1 扫描过程

| 操作 | 说明 |
|------|------|
| `os.walk` 遍历目录 | 从 `scanDirectory`（config.json）指定的根目录开始 |
| MP4 识别 | `.mp4` 文件 → 排除 `left.mp4`/`right.mp4` 等预处理产物 |
| HMD 识别 | 目录同时含 `part_*.hmd` + `metadata.json`（也支持 `.mcap` + `session.json`） |
| Data 识别 | 目录含 `session.json`/`metadata.json` 但无 HMD 分片 |
| 自动重命名 | HMD session 缺设备前缀时 `os.rename` 自动添加 |

### 2.2 CSV 写入规则

| 场景 | 操作 |
|------|------|
| 新文件（不在 CSV 中） | 新增行 |
| 已有行，但 `location_status = "history"` | 改回 `"local"` |
| 已有行 `location_status = "local"` | 不更新（保留已填写的字段） |
| **不更新** `scan_date` | 首次扫描日期永久锁定 |
| duration_sec 自动填充 | HMD 优先读预处理状态文件；MP4 走 ffprobe |

---

## Phase 3: 预处理（仅 HMD Session，可选 —— 目的是生成预览视频）

> **触发**：`POST /api/hmd/process` 手动触发，或启动自动预热  
> **入口**：`hmd_fast_preprocess.py` → `process_fast()` → 异步管线  
> **核心管线**：Stage 1（H265 解码）→ Stage 2（抽帧/封面/MP4 封装）→ 清理 H265
> 
> ⚠️ **预处理不是上传的前置条件。** 它的唯一目的是生成可播放的 `<session_basename>.mp4 `，让操作员在画廊中预览视频内容，从而填写录制员和任务 ID。如果这些字段已填写完毕，可以直接上传原始 `.hmd` 文件，无需预处理。

### 3.0 自动跳过规则

> 🆕 2026-06-30：`auto_warm_all()` 和前端「全部预热」/「生成预览帧」按钮统一遵循以下跳过规则：

| 条件 | 行为 | 原因 |
|------|------|------|
| `uploaded = "Yes"` | ✅ 跳过 | 已上传完成，预览用 mp4/缩略图已无意义 |
| `location_status = "history"` | ✅ 跳过 | 源文件已删除，无法进行预处理 |
| HMD 源目录不存在 | ✅ 跳过 | 无源文件可解码 |
| 无 `part_*.hmd` 分片 | ✅ 跳过 | 目录为空或不完整 |

> 🔁 **防重复启动**：前端点击「全部预热」前先调 `GET /api/hmd/is-processing`，若后台 fast 或 full 队列已有任务 → 提示用户，不重复启动。

### 3.1 预处理产物目录

```
runtime/hmd_cache/                       ← HMD_CACHE_ROOT
  └── <YYYY-MM-DD>/                      ← 从源路径提取日期
      └── <session_basename>/            ← 如 "0619_4aa45c_session_00000"
          ├── left.h265                  ← Stage 1 输出（❌ Stage 2 完成后自动删除）
          ├── <session_basename>.mp4                   ← Stage 2 输出（✅ 可播放，仅用于预览）
          ├── cover.jpg                  ← Stage 2 输出（封面）
          ├── preprocess_status.json     ← 状态文件（前端轮询）
          └── frames/                    ← Stage 2 输出（6 帧预览）
              ├── frame_00.jpg
              ├── frame_01.jpg
              ├── frame_02.jpg
              ├── frame_03.jpg
              ├── frame_04.jpg
              └── frame_05.jpg
```

> **路径函数映射**（`hmd_fast_preprocess.py`）：
> - `get_output_dir()` → `<cache_root>/<YYYY-MM-DD>/<basename>/`
> - `get_h265_path()` → `.../<basename>/left.h265`
> - `get_mp4_path()` → `.../<basename>/<session_basename>.mp4 `
> - `get_status_path()` → `.../<basename>/preprocess_status.json`
> - `get_frames_dir()` → `.../<basename>/frames/`
> - **封面**：直接拼 `os.path.join(get_output_dir(), "cover.jpg")`

### 3.2 Stage 1: H265 解码

| 步骤 | 操作 | 输出文件 |
|------|------|----------|
| 读取 `part_*.hmd` 分片 | `hmd_decode_py` Pure-Python 解码器 | — |
| 提取 HEVC NAL 单元 | splitStereo 分离左右目 | 左目原始 H265 流 |
| 写入 H265 文件 | 连续写入 | **`left.h265`**（~源文件大小） |
| 写状态文件 | `preprocess_status.json` → `stage=h265, progress=50` | 前端进度条显示 |

### 3.3 Stage 2: 抽帧 + 封面 + MP4 封装

| 步骤 | 操作 | 输出文件 |
|------|------|----------|
| H265 → MP4 封装 | `ffmpeg -i left.h265 -c copy <session_basename>.mp4 ` | **`<session_basename>.mp4 `**（≈ h265 大小） |
| 封面提取 | ffmpeg 从 mp4 抓第 1 帧 → 缩放 240p | **`cover.jpg`**（~20-40 KB） |
| 6 帧预览 | 等间隔抽 6 帧 → `frames/frame_00.jpg` ~ `frame_05.jpg` | **`frames/*.jpg`**（~30-60 KB/张） |
| 时长计算 | ffprobe `<session_basename>.mp4 ` → `duration_sec` | 写入 `preprocess_status.json` |
| 写完成状态 | `status=done, progress=100` | `preprocess_status.json` |
| **清理 H265** | `os.unlink(left.h265)` ⚡ **自动** | **删除 left.h265**（省 ~50% 空间） |

### 3.4 .h265 自动清理机制

> ⚠️ **设计要点**：Stage 2 完成后，自动删除 `left.h265`。仅保留可播放的 `<session_basename>.mp4 `。

| 触发条件 | 说明 |
|----------|------|
| `<session_basename>.mp4 ` 存在且大小 > 0 | 确保 MP4 已成功封装 |
| `frames/` 下 ≥ 6 张 jpg | 确保预览帧已生成 |
| `cover.jpg` 存在且 > 0 | 确保封面已生成 |

**两个清理点**：
1. `_do_stage2()` 末尾 — 异步 Stage 2 完成时
2. `process_fast()` 末尾 — 同步调用的完成时

### 3.5 完成判定（`check_fast_done`）

> ⚠️ **设计要点**：接受 "有 mp4 但无 h265" 为完成状态。

```
check_fast_done(folder) → True 的条件：
  ├── status = "done"（preprocess_status.json）
  ├── video_ok = mp4_ok OR h265_ok（至少一个可播放源存在）
  ├── cover.jpg 存在
  └── frames/ 下 ≥ 6 张 frame_*.jpg
```

### 3.6 预处理过程中的磁盘增长

| 阶段 | 新增文件 | 约占用空间 |
|------|----------|------------|
| 原始 session | `part_*.hmd` + `metadata.json` | ≈ X GB |
| Stage 1 期间 | + `left.h265` | ≈ +X GB（共 2X） |
| Stage 2 期间 | + `<session_basename>.mp4 ` + `cover.jpg` + `frames/*` | ≈ +X.05 GB（共 3X） |
| Stage 2 完成后 | − `left.h265` | ≈ −X GB（共 2X） |
| **最终留存** | `<session_basename>.mp4 ` + `cover.jpg` + `frames/*` | ≈ **X.05 GB** |

> 这就是启动时磁盘检查用 **2x 预估** 的原因：峰值空间需求约为源文件 × 2（Stage 2 期间 h265 + mp4 同时存在）。

---

## Phase 4: 画廊/预览

> **触发**：用户打开画廊视图、点击预览按钮  
> **入口**：`app.py` `/api/thumbnail`、`/api/video`、`/api/hmd/raw`  
> **影响范围**：缩略图生成（一次性缓存）、浏览器内存（HEVC 解码）

### 4.1 缩略图生成

| 视频类型 | 生成函数 | 输入源（优先级递减） | 输出路径 |
|----------|----------|---------------------|----------|
| **MP4** | `_generate_mp4_thumbnail()` | ffmpeg smart-seek: 3s → 1s → 5s → 10s，跳过黑帧（luma < 8） | **`runtime/thumbnails/<sha1>.jpg`** |
| **HMD** | `_generate_hmd_thumbnail()` | cover.jpg → `<session_basename>.mp4 ` → `right.mp4` → `left.h265` → `right.h265` → `frames/frame_00.jpg` → cache .hmd → 源 .hmd | **同上** |

**缩略图缓存键**：`sha1(path|mtime|size)` → `runtime/thumbnails/<hex>.jpg`

若缩略图生成失败 → 返回占位图 `runtime/thumbnails/_placeholder.jpg`

### 4.2 画廊视图

```
前端 `templates/index.html` 画廊标签页
  ├── CSS grid 自动列（minmax(220px, 1fr)）
  ├── IntersectionObserver 懒加载
  ├── 全屏预览（左右键 + Esc）
  ├── 多选（Shift 区间 / Ctrl 切换）
  ├── 筛选（按 device / recorder / task / uploaded）
  └── 内嵌编辑器（左视频 + 右字段面板）
```

### 4.3 HMD 视频播放

| 播放方式 | 入口 | 技术 |
|----------|------|------|
| **表格内预览** | 表格"预览"按钮 | WebCodecs HEVC + 双 canvas splitStereo |
| **独立预览页** | `/hmd-preview?path=...` | 4 阶段进度 UI + WebCodecs |
| **画廊全屏** | 卡片点击 | 6 帧抽帧替代实时播放（替代原视频播放器） |

**HMD 6 帧预览**（画廊卡片内）：直接读取 `runtime/hmd_cache/<date>/<basename>/frames/frame_*.jpg`，逐帧点击放大。

---

## Phase 5: 上传

> **触发**：用户点击"自动上传"，或命令行 `python auto_upload.py --pipeline --delete-local`  
> **入口**：`auto_upload.py` → `AutoUploader.upload_batch_pipelined()`  
> **影响范围**：CSV `uploaded` 字段、`.uploaded` 标记文件、本地文件删除

### 5.1 上传决策 / 跳过

| 条件 | 行为 |
|------|------|
| CSV 中 `uploaded = "Yes"` | ✅ 跳过 |
| 存在 `path.uploaded` 标记文件 | ✅ 跳过 |
| `extra_description ≠ "1"` | ✅ 跳过（未标记待上传） |
| 以上均不满足 | 进入上传流程 |

### 5.2 上传什么文件

| 视频类型 | 上传文件 | 源路径 |
|----------|----------|--------|
| **HMD** | 原始 `.hmd` 分片 + `metadata.json`（通过 webkitdirectory 注入浏览器） | `<dest_base>/<MMDD>/<session_name>/` |
| **MP4** | 源 MP4 文件 | `<dest_base>/<MMDD>/<文件名>.mp4` |

> **HMD session 上传的是原始 `.hmd` 分片文件**，由浏览器端 OPFS 流式转换为 MCAP 后提交。
> `<session_basename>.mp4 ` 仅用于本地预览（画廊视图、6 帧抽帧），**不参与上传流程**。
>
> 预处理（Phase 3）的目的是生成可播放的 `<session_basename>.mp4 ` 供操作员预览视频内容、确认录制员和任务 ID。
> 如果录制员和任务 ID 已经填写，则不需要预处理，可直接上传。

### 5.3 上传成功后标记

| 标记方式 | 路径 | 内容 |
|----------|------|------|
| **CSV 字段** | `runtime/data/video_manager.csv` | `uploaded` → `"Yes"` |
| **标记文件** | `<视频路径>.uploaded` | 上传时间戳 `YYYY-MM-DD HH:MM:SS` |

> `.uploaded` 标记文件用于双重判重（即使 CSV 被误修改也能跳过）。

### 5.4 --delete-local 清理范围

> `auto_upload.py` `delete_local_files(session_path)` 函数

| 序号 | 清理对象 | 路径 | 方式 |
|------|----------|------|------|
| 1 | **HMD 分片文件** | `<session_dir>/part_*.hmd` + `metadata.json` | `os.remove`，目录空则 `os.rmdir` |
| 2 | **预览视频** | `runtime/hmd_cache/<date>/<name>/<session_basename>.mp4 `、`right.mp4`、`left.h265`、`right.h265` | `os.remove` |
| 3 | **缩略图** | `runtime/thumbnails/<session_name>_*.jpg`、`*.png` | `os.remove` |
| 4 | **预览帧** | `runtime/hmd_cache/<date>/<name>/frames/*.jpg` | `os.remove` |

> 清理完成后在日志中输出释放的总空间量。

### 5.5 上传后残留文件

| 文件/目录 | `--delete-local` 后？ | 说明 |
|-----------|----------------------|------|
| CSV 行 | ✅ 保留 | `uploaded = "Yes"`，作为历史记录 |
| `path.uploaded` 标记 | ✅ 保留 | 上传成功的时间戳 |
| `cover.jpg` | ❌ 不删除 | 小文件，保留 |
| `preprocess_status.json` | ❌ 不删除 | 状态文件，保留 |
| 空的 session 目录 | ✅ 已删除 | `device_monitor` 和 `auto_upload` 都会清理空目录 |
| 空的 hmd_cache 目录 | ❌ 不清理 | 需手动或后续脚本处理 |

---

## Phase 6: 导出

> **触发**：前端导出按钮 `POST /api/export`  
> **影响范围**：生成 TXT 文件，浏览器下载

| 参数 | 说明 |
|------|------|
| `columns` | 选择要导出的列 |
| `rows` | 选择要导出的行（索引） |
| `rowRange` | 行范围 `"xx-xx"` |
| `separator` | 分隔符（默认 `.`） |

---

## 📊 文件路径速查表

### 原始数据（由 device_monitor 写入）

| 文件 | 路径 |
|------|------|
| MP4 源文件 | `<dest_base>/<MMDD>/<文件名>.mp4` |
| HMD session 目录 | `<dest_base>/<MMDD>/hmd/<device_id>_<session_name>/` |
| HMD 分片 | `.../part_000.hmd`, `part_001.hmd`, ... |
| metadata.json | `.../metadata.json` |
| Data session | `<dest_base>/<MMDD>/data/<device_id>_<session_name>/` |

### 预处理产物（由 hmd_fast_preprocess.py 写入）

| 文件 | 路径 |
|------|------|
| 预处理根目录 | `runtime/hmd_cache/<YYYY-MM-DD>/<session_basename>/` |
| H265 原始流 | `.../left.h265` → **❌ Stage 2 后自动删除** |
| MP4 封装视频 | `.../<session_basename>.mp4 ` → ✅ 可播放（仅用于预览） |
| 封面图 | `.../cover.jpg` |
| 状态文件 | `.../preprocess_status.json` |
| 6 帧预览 | `.../frames/frame_00.jpg` ~ `frame_05.jpg` |

### 缩略图及预览（由 app.py + video.py 生成）

| 文件 | 路径 |
|------|------|
| 缩略图 | `runtime/thumbnails/<sha1>.jpg` |
| 占位图 | `runtime/thumbnails/_placeholder.jpg` |

### CSV 及配置（运行时状态）

| 文件 | 路径 |
|------|------|
| 主数据表 | `runtime/data/video_manager.csv` |
| 列定义 | `runtime/data/config.json` |
| 录入员表 | `runtime/data/recorders.csv` |
| SD 卡表 | `runtime/data/sd_cards.csv` |
| 任务表 | `runtime/data/tasks.csv` |
| CSV 备份 | `runtime/csv_backups/`（10 份轮转） |
| 上传进度 | `vendor-upload-pkg/parts/` |

### 上传标记

| 文件 | 路径 |
|------|------|
| .uploaded 标记 | `<视频路径>.uploaded` |

### 日志和浏览器数据

| 文件 | 路径 |
|------|------|
| 运行日志 | `runtime/logs/` |
| Chrome 用户数据 | `runtime/browser_data/` |

---

## 🔁 关键自动清理时机一览

| 时机 | 删除内容 | 触发代码 |
|------|----------|----------|
| SD 卡复制完成后 | SD 卡上的 `.mp4` + 同名 `.LRF` | `device_monitor.py` `_delete_source_files()` |
| SD 卡 HMD 复制完成后 | SD 卡上的整个 session 目录 | `device_monitor.py` `shutil.rmtree()` |
| 预处理 Stage 2 完成后 | `runtime/hmd_cache/.../left.h265` | `hmd_fast_preprocess.py` `_do_stage2()` / `process_fast()` |
| **上传成功后** | `.hmd` 分片 + 预览视频 + 缩略图 + 预览帧 | `auto_upload.py` `delete_local_files()` |
| 上传后空目录清理 | 空的 session 目录 | `delete_local_files()` + `device_monitor` |
| **🆕 手动批量清理** | 所有 `uploaded=Yes` 视频的源文件 + mp4/h265 预览 + 预览帧（保留 cover.jpg） | `GET /api/clean-uploaded-cache` → 前端「🧹 清理缓存 ▼」→「清除已上传视频源文件」 |

---

## 📈 空间占用典型示例

以一个 4 GB 的 HMD session 为例：

| 阶段 | 存储占用 | 文件 |
|------|----------|------|
| 原始 session（本地盘） | 4.0 GB | `part_*.hmd` + `metadata.json` |
| Stage 1 期间（峰值 1） | 8.0 GB | + `left.h265` (4.0 GB) |
| Stage 2 期间（峰值 2） | 12.1 GB | + `<session_basename>.mp4 ` (4.0 GB) + `cover.jpg` + 6 帧 |
| **预处理完成后** | 8.1 GB | `<session_basename>.mp4 ` + `cover.jpg` + 6 帧 + 原始 .hmd |
| **上传完成后** (`--delete-local`) | 0.1 GB | 仅 CSV 行 + `.uploaded` 标记 + `preprocess_status.json` |
