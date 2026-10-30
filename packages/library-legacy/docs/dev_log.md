# Dev Log — video-sort-package

> 实现记录 + 验证依据 + 学习复盘。每次提交或重大变更后追加。

格式：`## YYYY-MM-DD — <标题>` + 变更点 + 验证 + 回滚说明。

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