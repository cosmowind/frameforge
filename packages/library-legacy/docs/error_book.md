# Error Book — video-sort-package

> 缺陷根因 + 失败尝试 + 最终修复 + 预防要点。
> 新 bug 按 E{n} 编号追加，修复后加 ✅ FIXED 标记。

---

## E1. ✅ FIXED — WebCodecs "key frame required after configure/flush"

| 字段 | 内容 |
|---|---|
| 发现 | 2026-06-17（HMD 集成首版） |
| 修复 | 2026-06-17 |
| 现象 | 浏览器抛 `Uncaught DataError: Failed to execute 'decode' on 'VideoDecoder': A key frame is required after configure() or flush()` |
| 期望 | 拖动 seek 后正常重置解码位置 |
| 根因 | WebCodecs 规则：`configure()` / `flush()` 之后的第一帧必须是 key frame（NAL type 19/20）。原代码 seek 时 `setupDecoders()` → `primeDecoders()` 从 `state.leftIdx = 0` 喂，frame 0 不一定是 IDR |
| 失败尝试 | 1) 加 try/catch 吞错 → 静默丢帧；2) 用 `timestamp: 0` 硬编码 → 触发"duplicate timestamp" |
| 修复 | `frameToChunks()` 返回 `{nals, firstIdr}`；`primeDecoders()` 前设 `state.leftIdx = state.leftFirstIdr`；seek handler 找最近 IDR 后从 0 喂到 IDR；`feedFrame` 时间戳改为 `frameIdx * dur` 单调递增 |
| 验证 | Node `node --input-type=module --check` 通过；session_00000 leftFirstIdr=86、rightFirstIdr=172 字节偏移；浏览器拖动 seek 不报错 |
| 预防 | 任何 `setupDecoders()` 后第一帧前必须 `state.leftIdx = state.leftFirstIdr`；时间戳永不复用 0 |
| 关联 | dev_log.md 2026-06-17 IDR fix |

---

## E2. ✅ FIXED — HMD "双目" 实测是单流

| 字段 | 内容 |
|---|---|
| 发现 | 2026-06-17 |
| 修复 | 2026-06-17 |
| 现象 | 用户期待"双目预览两个视频"，实测每个 .hmd 文件只含一路 HEVC（1920x1080），没有 SBS/TB/帧交替 |
| 期望 | 双目 = 单文件双路流 |
| 根因 | metadata.json 的 `cameras[0/1]` 是 RV1106 配置占位（实际 I2C/CSI-2 lane 未连）。"left"/"right" 是两个独立设备的两段 .hmd |
| 决策 | A. 单流播放 + 提供"并排加载第二 session"按钮（用户选）；B. 单流 + cam0/cam1 切换；C. 用两段 session 替代。**采用 A** |
| 预防 | 任何文档/PR 描述 HMD 时明确"单流，真双目=两独立设备的两段 session" |
| 关联 | `codec-hmd/docs/error_book.md` E4（本项目独立验证） |

---

## E3. ✅ FIXED — `/api/scan` 把无关历史行带进当前扫描结果

| 字段 | 内容 |
|---|---|
| 发现 | 2026-06-17 |
| 修复 | 2026-06-17 |
| 现象 | 用户扫描 `F:\...\codec-hmd` 后表格里出现 17 行 `图片/*` 路径下的 mp4 |
| 期望 | 扫描指定目录 = 只显示/保留该目录的行 |
| 根因 | `scan_directory()` 用 `existing_map` 累积所有 CSV 旧行，从未根据扫描目录过滤 |
| 失败尝试 | 1) 只过滤返回结果（write_csv 仍写全量）→ 下次 scan 又复活；2) 按 file_type 区分 → 不能解决路径杂混 |
| 修复 | 加 `scope` 参数（默认 `current`）：仅保留路径在 `directory` 下或 `scan_date == today` 的行；`write_csv(result)` 也用过滤后的（即同步落盘） |
| 验证 | curl 测试 codec-hmd 扫 → 10 行；扫 video-sort-package 目录 → CSV 清空到 0 行 |
| 预防 | 任何"扫描"类操作默认 `scope=current`；`scope=all` 明确语义为"看全部历史" |
| 关联 | dev_log.md 2026-06-17 scope=current |

---

## E4. ✅ FIXED — HMD 播放速度无法控（视觉上 16×+）

| 字段 | 内容 |
|---|---|
| 发现 | 2026-06-17 |
| 修复 | 2026-06-17 |
| 现象 | HMD 双目播放时画面一闪而过，无法正常观看 |
| 期望 | 默认 1×（30 fps），可切 5× / 10× / 16× |
| 根因 | `primeDecoders()` 一次性灌 60 帧，decoder 全力消化 → 视觉上是 full-speed |
| 修复 | 用 `hmdFrameDebtL/R` 累积欠帧数；每 RAF tick 按 `30 * rate / 60 = rate/2` 喂入；带 `maxBurst` cap 防失控 |
| 验证 | 1× 时帧率 ~30 fps；切 16× 时明显加速但不丢帧 |
| 预防 | 任何 rate-control 用 frame-debt 模式（fractional accumulator），不要直接按 wall-clock 触发 |
| 关联 | dev_log.md 2026-06-17 速度按钮 |

---

## E5. ✅ FIXED — Flask debug reloader 子进程残留

| 字段 | 内容 |
|---|---|
| 发现 | 2026-06-17 |
| 修复 | 2026-06-17 |
| 现象 | `netstat -ano \| findstr :5000` 显示 3+ 个 LISTEN 进程；改 app.py 后代码变更未生效 |
| 根因 | Flask `debug=True` 时启动 reloader 父进程 + 子进程；多次重启未清理；旧代码仍在响应 |
| 修复 | `taskkill //F //PID <pid>` 清理；或 `del __pycache__` 强制重编译 |
| 验证 | kill 后单实例响应新代码 |
| 预防 | 改 app.py 后若响应未变，先 `netstat -ano \| findstr :5000` 检查残留进程 |
| 关联 | dev_log.md 2026-06-17 WCS 维护 |

---

## E6. ✅ FIXED — "Unexpected token '}'" 浏览器语法错误

| 字段 | 内容 |
|---|---|
| 发现 | 2026-06-17 |
| 修复 | 2026-06-17 |
| 现象 | 浏览器报 `Uncaught SyntaxError: Unexpected token '}'`；hmd_preview.html 不能解析 |
| 根因 | 重写 `fwdBtn.addEventListener` 时旧 handler 末尾 2 行（`seek.dispatchEvent(...)` + `});`）残留成孤立代码 |
| 修复 | 删除孤立的两行 |
| 验证 | Node `node --input-type=module --check` 通过；浏览器无报错 |
| 预防 | 大段重写时用 `read_entire_block + replace_entire_block` 而非单点 patch；改完跑 `node --check` |
| 关联 | dev_log.md 2026-06-17 IDR fix（同期） |

---

## E7. ✅ FIXED — Gallery 缩略图全是黑帧

| 字段 | 内容 |
|---|---|
| 发现 | 2026-06-19 |
| 修复 | 2026-06-19 |
| 现象 | 切到「画廊」视图后所有卡片封面是纯黑（应该显示 HMD 视频的代表性画面） |
| 期望 | 封面是真实画面，能识别出 session 内容 |
| 根因（三层叠加） | **L1**：`_generate_mp4_thumbnail` 默认 seek 到 1.0s，对 HEVC 启动 GOP / 摄像头盖未摘 / 暗光启动场景拿到的是全黑/暗帧。<br>**L2**：ffmpeg filter 链 `scale=240:135:force_original_aspect_ratio=decrease,pad=240:135:(ow-iw)/2:(oh-ih)/2:black` 在 1920×1080 源 → 240×135 目标时触发 "Padded dimensions cannot be smaller than input dimensions"，静默返回 False，**永远不写 jpg**。<br>**L3**：HMD 行 `kind="hmd"`，旧的 `_ensure_thumbnail` 直接跳过，只支持 mp4 |
| 失败尝试 | 1) 单独 fix 1.0s → 3.0s 单点 seek（用户数据 luma 38 不是 0，是暗不是黑，问题没解决）；2) 加 luma 兜底循环（被 L2 静默失败吞掉，根本没进 luma 步骤） |
| 修复 | **L2** 先修：filter 简化为 `scale=240:135:force_original_aspect_ratio=decrease`（去掉 pad 表达式，aspect-preserving 已经够用）。<br>**L3** 加 `_generate_hmd_thumbnail(session_dir)`：定位 `hmd_cache/<basename>/left.mp4` → 退化 `right.mp4` → 退化 `part_*.hmd`，复用 `_generate_mp4_thumbnail`。<br>**L1** 强化 smart-seek：`THUMB_SEEK_TRY=[3.0, 1.0, 5.0, 10.0]`，每 offset 后跑 `_ffmpeg_avg_luma`（PGM 灰度帧字节均值），`< LUMA_MIN=8.0` 视为全黑，跳到下个 offset。<br>JS 端统一走 `<img data-thumb-idx>` + `/api/thumbnail` 单一路径（删除 `<video>` + canvas 客户端抓帧，因为不同浏览器/编解码器对 h265 拆 mp4 的 seek 行为不一致，canvas drawImage 跨域策略也常静默失败） |
| 验证 | `python -c "_generate_hmd_thumbnail(session_00000, out.jpg)"` → 4812 B（黑帧 jpg 约 1-2 KB）；3 个 session 平均亮度 92 / 124 / 98（> LUMA_MIN 8.0，非黑）；luma_at(0.1s) = 38.7 / luma_at(3.0s) = 90.0 验证 1s 确实是摄像头启动暗帧 |
| 预防 | 任何 ffmpeg filter 链涉及 `pad` + 算术表达式时，**先手工 ffmpeg 跑一遍**确认不会触发 "Padded dimensions smaller"；暗场景检测用 PGM 灰度帧字节均值（轻量、不依赖 ffmpeg signalstats filter）；客户端 video seek 抓帧只作 fallback，主路径走服务端缩略图 |
| 关联 | dev_log.md 2026-06-19 gallery thumbnail；features.md "画廊视图" 章节 |

---

## E8. ✅ FIXED — `/api/thumbnail` 对 HMD 目录返回 404

| 字段 | 内容 |
|---|---|
| 发现 | 2026-06-19（紧接 E7） |
| 修复 | 2026-06-19 |
| 现象 | 修了 E7 后 `curl /api/thumbnail?path=...session_00000` 仍返回 404 "File not found" |
| 期望 | HMD 目录路径也能生成缩略图（200 + jpg） |
| 根因 | `/api/thumbnail` 路由里**先**用 `os.path.isfile(path)` 检查再判断 `kind`，但 HMD 行的 `path` 是**目录**（`F:\...\session_00000`）不是文件，`isfile` 返回 False 直接 404，根本走不到 `_generate_hmd_thumbnail` |
| 修复 | 把 `kind` 判断**前移**到 `isfile` 检查之前：`if kind == "mp4" and not os.path.isfile(path): return 404`（HMD 目录不强制要求是 file） |
| 验证 | curl 3 个 session 全部 200 + Content-Length 4812 / 1535 / 2021 |
| 预防 | 任何"path 既可能是文件又可能是目录"的端点，**先按类型分流**再做存在性检查；不要假设 `isfile` 是普适的预检 |
| 关联 | dev_log.md 2026-06-19 gallery thumbnail |

---

## E9. ✅ FIXED — 浏览器缓存导致 console.log 看不到、JS 不生效

| 字段 | 内容 |
|---|---|
| 发现 | 2026-06-19（紧接 E7/E8） |
| 修复 | 2026-06-19 |
| 现象 | 后端已修、文件已改、Flask 已重启，**但用户浏览器 console 一行新加的 `[galleryThumb]` log 都不出现**。硬刷新 + DevTools 勾 "Disable cache" 才生效 |
| 期望 | 改完 JS / templates 后浏览器刷新立刻生效 |
| 根因 | Flask `send_file("templates/index.html")` 默认带 `Cache-Control: public` 之类的弱头，Chrome 把 `templates/index.html` 整页（含内嵌 `<script>`）缓存 5-30 分钟。改 `app.py` Flask 会重启 → 后端 OK；但改 `templates/index.html` 浏览器读缓存的旧 HTML，**旧 HTML 里的旧 `<script>`** 仍是改之前的逻辑 |
| 失败尝试 | 1) 反复 commit + 改 build 标记戳（用户看不到 build 号 → 缓存没刷）；2) 告诉用户"硬刷新"（用户不知道） |
| 修复 | (1) `app.py` `/` 路由显式 `Cache-Control: no-cache, no-store, must-revalidate` + `Pragma: no-cache` + `Expires: 0`；(2) `<script>` 首行加版本戳 `console.log('[VideoSort] page loaded, build=YYYY-MM-DD-HHMM')`，用户打开 console 第一行就能确认加载的是不是最新代码 |
| 验证 | 用户刷新后看到 `[VideoSort] page loaded, build=2026-06-19-2330-gallery-fallback` 即确认 |
| 预防 | SPA 单文件应用必须 `Cache-Control: no-cache`；任何 dev 期间加 build 戳（git short SHA 或日期）；console 第一行始终打印 build 号，排查时第一时间确认代码版本 |
| 关联 | dev_log.md 2026-06-19 build marker |

---

## E10. ✅ FIXED — 维表主键连续改名（lx→l→""→o→op→op02）后保存丢数据

| 字段 | 内容 |
|---|---|
| 发现 | 2026-06-19 |
| 修复 | 2026-06-19 |
| 现象 | 录入员管理页把 `lx` 的 id 改成 `op02`（中间连续改了几次），点保存后服务端 404 "主键 op02 不存在"；刷新页面数据消失 |
| 期望 | 连续改名后保存成功，`op02` 持久到 recorders.csv |
| 根因 | `dimRowInput` 在每次主键改名后把 `tr.dataset.key` 更新为**新值**（`lx → l → "" → o → ... → op02`），但**原始的 `lx` 丢了**。等用户点保存时，`row.id === 'op02' === keyVal`，JS 走 `mode=update` 不带 `?original_key=` 参数，服务器找不到 `op02` → 404 |
| 修复 | `dimRowInput` 第一次主键改名时把**原始 key** 存到 `tr.dataset.originalKey`（不会被后续改名覆盖）；`dimSaveOne` 检测到 `originalKey && originalKey !== row[primary]` 时走 `mode=upsert + ?original_key=<originalKey>`，服务端用 original_key 找原行做 rename |
| 验证 | `verify_pages.py` 38/38 通过（含 `recorders rename via original_key` 新增 case）；独立 Python 测试：insert renametest01 → rename 为 renametest02 → action=renamed count 正确 |
| 预防 | 任何"主键可改"的 UI 必须在 tr 上独立保存 originalKey 锚，不要用 current key 反推；改 key 类操作总走 `upsert` + `original_key` 二元组，不用 `update` 单点 |
| 关联 | dev_log.md 2026-06-19 original_key preservation |