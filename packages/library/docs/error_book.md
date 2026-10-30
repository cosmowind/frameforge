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

---

## E11. ✅ FIXED — docstring 中 Windows 路径 `\u` 导致 `unicodeescape` SyntaxError

| 字段 | 内容 |
|---|---|
| 发现 | 2026-06-20 |
| 修复 | 2026-06-20 |
| 现象 | `python device_monitor.py` 启动报 `SyntaxError: (unicode error) 'unicodeescape' codec can't decode bytes in position 357-358: truncated \uXXXX escape` |
| 期望 | 正常启动 |
| 根因 | docstring 中写了 `/media\0615`，`\视` 的字节序列恰好以 `\u` 开头，Python 解析器把 `\uXXXX` 当成 Unicode 转义尝试解码，结果 `\视频` 不是有效的 `\uXXXX` 四位十六进制，触发 truncated 错误 |
| 修复 | 将 docstring 中的 Windows 路径反斜杠 `\` 改为正斜杠 `/`：`/media/0615/hmd/...`。注释中的 `/media`（双反斜杠）不受影响 |
| 验证 | `python -c "import py_compile; py_compile.compile('device_monitor.py', doraise=True)"` → OK；启动 `启动视频管理.bat` 成功 |
| 预防 | **docstring / f-string 中避免裸反斜杠 Windows 路径**：用正斜杠 `/`、raw string `r"D:\..."`、或双反斜杠 `/media`。变量赋值用 `r"..."` raw string；注释用正斜杠或双反斜杠 |
| 关联 | dev_log.md 2026-06-20 unicodeescape |

---

## E12. ✅ FIXED — HMD 预处理在另一台设备失败（缺少 .cjs 文件）

| 字段 | 内容 |
|---|---|
| 发现 | 2026-06-20 |
| 修复 | 2026-06-20 |
| 现象 | `hmd_preprocess.py` 的 CJS 分支报错，Node.js `require()` 无法加载 `.esm.js` 文件 |
| 期望 | CJS 和 ESM 都能正常调用 HMD 解析器 |
| 根因 | 项目只提供了 `hmd-decode.esm.js`（ESM 格式），`require()` 无法直接导入 ESM。`hmd_preprocess.py` 的 CJS 分支需要 `.cjs` 格式入口 |
| 修复 | 新建 `hmd-decode.cjs`（`static/hmd/` + `templates/static/hmd/`）：用 `import()` 动态加载 `.esm.js`，导出 `{ parse, splitStereo, dedupParamSets }` 异步接口。`hmd_preprocess.py` CJS 分支增加 `typeof === 'function'` 运行时检测 |
| 验证 | 预处理在新设备成功运行 |
| 预防 | Node.js CJS 和 ESM 互操作：`require()` 不能直接加载 `.esm.js`；必须用 CJS wrapper + `import()` 桥接 |
| 关联 | dev_log.md 2026-06-20 CJS/ESM bridge |

---

## E13. ✅ FIXED — 批量上传启动失败：`auto_upload.py` 路径错误导致 404

| 字段 | 内容 |
|---|---|
| 发现 | 2026-06-24 |
| 修复 | 2026-06-24 |
| 现象 | 前端点击"批量上传"后 `fetch('/api/auto-upload-start')` 返回 HTML（404 页面），`res.json()` 报 `Unexpected token '<'` |
| 期望 | 启动子进程 `auto_upload.py`，返回 `{ok: true, pid, count}` |
| 根因 | **双层路由**：项目既有 `src/routes/upload_routes.py`（blueprint，但未注册到 app.py），实际生效的是 `src/app.py` 中用 `@app.route()` 直接定义的路由。`app.py` 中的 `auto_upload_py` 路径写的是 `BASE_DIR/auto_upload.py`，但文件已移到 `src/auto_upload.py`，同时缺少新接口（`/api/upload-template-by-path`、`/api/auto-upload-progress`） |
| 修复 | 在 `app.py` 中新增 3 个缺失路由（`by-path`、`progress`）；修正 `auto_upload_py` 路径为 `src/auto_upload.py`；同步更新 `upload_routes.py` |
| 验证 | 前端无报错；批量上传 3 个视频正常启动 |
| 预防 | 移动文件后全局搜索旧路径引用；blueprint 注册状态用 `check_routes.py` 检查；路由改动同时在 `app.py` 和蓝图文件两处生效（蓝图注册前） |

---

## E14. ✅ FIXED — `/api/auto-upload-start` 返回 500 + HTML（`_is_hmd_session` NameError）

| 字段 | 内容 |
|---|---|
| 发现 | 2026-07-01 |
| 修复 | 2026-07-01 |
| 现象 | 前端 `fetch('/api/auto-upload-start')` 返回 HTML（Flask 默认 500 页面），`res.json()` 报 `Unexpected token '<', "<!doctype "... is not valid JSON` |
| 期望 | 返回 `{ok: true, pid, count}` JSON |
| 根因 | **服务器未重启**：代码中 `upload_routes.py` 第 32 行已导入 `_is_hmd_session`，但 Flask 服务自 2026-06-30 23:08 后未重启，运行的是旧版代码（缺少该导入）。日志确认 `NameError: name '_is_hmd_session' is not defined` 持续发生（6 次，最新 2026-07-01 11:02） |
| 失败尝试 | 1) 检查导入语句 → 存在且正确；2) 检查函数定义 → 存在于 `upload_service.py:101` |
| 修复 | 1) **重启 Flask 服务器**（加载最新代码）；2) 加固 `_is_hmd_session()`：`os.listdir()` 加 `try/except (PermissionError, OSError)` 保护，防止目录不可访问时二次崩溃；3) 清理 `upload_service.py` 中残留的死代码函数（`auto_upload_start`/`auto_upload_status`/`auto_upload_progress`，缺少 `request` 导入，从未被调用） |
| 验证 | 语法检查通过；导入链验证正确（`_is_hmd_session` 在 `upload_service.py:101` 定义，`upload_routes.py:32` 导入） |
| 预防 | 代码改动后必须重启 Flask 服务；`os.listdir()` 必须加异常保护；定期清理死代码 |
| 关联 | E13（同为 auto-upload 500 问题，上次是路径错误，本次是 NameError） |

---

## E15. ✅ FIXED — 单引号字符串跨行导致 `switchPage is not defined`（整块脚本失效）

| 字段 | 内容 |
|---|---|
| 发现 | 2026-07-05 |
| 修复 | 2026-07-05 |
| 现象 | 浏览器报 `Uncaught SyntaxError: Invalid or unexpected token`，随后点任意导航标签报 `Uncaught ReferenceError: switchPage is not defined`，页面卡在视频管理页无法切换 |
| 期望 | 导航标签正常切换页面 |
| 根因 | `index.html` 字段配置里 `environment_description` 的 `title:` 用单引号字符串写了两行（第 1 行 `'照明…分布。` 未闭合，换行后第 2 行才 `…职能。'`）。JS 单引号/双引号字符串不能跨物理行 → parse 期即报 `Invalid or unexpected token`，导致 `switchPage`（同一 `<script>` 块，1703–2793 行）所在的**整块脚本被丢弃**，块内所有函数都未定义 |
| 失败尝试 | 无（浏览器报错行号是渲染后偏移 887，指向另一有效块的 DEBUG 日志，误导定位）|
| 修复 | 把跨行字符串合并为一行，行内换行用转义 `\n`：`title: '照明 (Lighting): …分布。\n场景 (Scene/Setting): …职能。'` |
| 验证 | `sed -n '1704,2791p' index.html \| node --check` → `BLOCK OK`；硬刷新后无 SyntaxError、导航标签可切换 |
| 预防 | 多行提示文案一律用反引号模板字符串或 `\n`，禁止单/双引号跨行；改动前端脚本块后必跑 `node --check`；症状为「某函数 `xxx is not defined`」时先查同一 `<script>` 块内是否有 SyntaxError（一处语法错误会废掉整块） |
| 关联 | E6（同类：孤立代码致浏览器 SyntaxError）；dev_log.md 2026-07-02（`<script>` 块嵌套致 `_xxx is not defined`）|

---

## E16. ✅ FIXED — 调试脚本版本爆炸（v1→v8）+ 调试产物污染工作区

| 字段 | 内容 |
|---|---|
| 发现 | 2026-07-05（开发完成清理时） |
| 修复 | 2026-07-05 |
| 现象 | 工作区堆积 79 个调试脚本（`fill_frameforge_form.py` → `v8`、`migrate_pg_to_chinese.py` → `v3`、`match_options.py` → `v2`），外加 `after_inject.png` 截图、`runtime/data/env_check.txt`；每次 `git status` 噪音巨大，无法看清真实改动 |
| 期望 | 工作区干净，调试脚本与生产代码分离，git diff 只显示有意义的变更 |
| 根因 | **流程层**问题，非代码 bug：(1) 调试遇到问题时复制旧脚本加 `v2`/`v3` 后缀而不是加参数分支；(2) 调试产物（截图/临时 txt/中间脚本）无清理约定，开发完成时仍堆积在 `scripts/` 和工作区根 |
| 失败尝试 | 无（是清理时发现的） |
| 修复 | (1) 一次性 `rm -f` 清掉全部 79 个 `??` 未提交调试脚本 + 截图 + txt；(2) 保留 51 个 `scripts/` 下已纳入版本控制的运维脚本（`pg_backup.py`/`sync_*.py` 等是历史有意 commit）；(3) 写入 dev_log + E16 立规矩 |
| 验证 | `git status` 干净：仅 5 个 `M` 源文件 + 1 个归档目录 txt；79 个未提交脚本全部消失（从未入版本，无需 `git revert`） |
| 预防 | (1) 调试脚本用**单一文件 + `--stage` 参数**或日志分支，禁用 `v1`/`v2` 后缀复制；(2) 临时调试文件放 `scripts/_debug_<日期>/` 目录（已加进 .gitignore），完结时 `git clean -fd scripts/_debug_*`；(3) 开发完成收尾流程（wcs-cn "开发完" 阶段）必须包含「调试产物清理」步骤 |
| 关联 | dev_log.md 2026-07-05（上传页中文化 4 阶段调试过程）；E15（同次调试中触发的代码层 bug） |
---

## E17. ✅ FIXED — auto_upload 链路 9 个 bug 叠加（environments 双重 BOM + GPS 覆盖 + 中英文不兼容 等）

| 字段 | 内容 |
|---|---|
| 发现 | 2026-07-05（中文化 commit 31a4d6a 后跑端到端测试时） |
| 修复 | 2026-07-05 |
| 现象 | 表单填写看似正确但上传按钮永远等不到、地址 GPS 锁定后又被覆盖、country 字段被自动转成 "China"、批量上传 1 个文件缺失就退出整批、CSV 标 uploaded='Yes' 但 PG 还是 'No' |
| 期望 | 单条视频一键填对→点击上传→自动完成→CSV+PG 同步标记 |
| 根因 | **9 个独立 bug 叠加**：每个单独看都不复杂，但叠加效应让上传链路完全断裂 |
| 失败尝试 | (1) 反复改 `auto_upload.py` 的 selector，没意识到页面有中英文两套文本；(2) 调 GPS 候选选择，没借鉴 v7.py 已验证方案；(3) 手动 type "中国" 试图修 country 字段，没意识到 GPS 自动回填 |
| 修复 | 9 个修复详见 `docs/开发历史文档/retrospectives/2026-07-05_frameforge_auto_upload.md`：双重 BOM / 中文优先 / return 守卫 / 多选择器并联 / 跳过 country / 中英文 selector / 双信号检测 / CSV+PG 双写 / 批处理容错 |
| 验证 | 单条：表单一键填对 + GPS 锁定 + MCAP 转换检测（53s 内识别）+ Upload to server 可点击 + inflight 检测（中英文）+ Recent uploads 检测 → uploaded='Yes' 双写。批量：66 个视频 PID 26508 后台运行 |
| 预防 | (1) **selector 兼容中英文**是硬规矩（"Upload to server" + "上传到服务器"、"In flight" + "上传中"）；(2) **多信号检测异步操作**：MCAP 转换和按钮 enabled 是异步的，单一信号不可靠；(3) **批处理容错**：单条失败必须 `continue` 不能 `return`；(4) **双写 data integrity**：CSV 和 PG 任何写入操作都要同步；(5) **借鉴已验证方案**：调通的问题优先参考历史成功脚本（`v7.py`） |
| 关联 | dev_log.md 2026-07-05（auto_upload 端到端）；retrospectives/2026-07-05_frameforge_auto_upload.md（完整复盘） |

---

## E18. ⚠️ FIXED — CSV+PG 大量重复记录 + path 格式不一致

| 字段 | 内容 |
|---|---|
| 发现 | 2026-07-06（用户报告 0625-0629 数据丢失后调查发现） |
| 修复 | 2026-07-06 |
| 现象 | 同一 session 在 CSV+PG 中有 4-5 条不同 path 格式的重复记录：<br>- `/media/0625/hmd/...`（反斜杠）<br>- `/media/videos\0625\hmd\...`（混用）<br>- `/media/videos/0625/hmd/...`（正斜杠）<br>用户在前端看到"空数据"行就以为数据丢失，实际数据在另一条 path 的副本里 |
| 期望 | 同一 session 在 CSV+PG 中只有 1 条记录，path 格式统一 |
| 根因 | **path 格式不一致**累积导致：(1) `scan_dir` 用 `os.path.normpath` 规范化 → 正斜杠；(2) `mark_uploaded` 写 PG 时用 raw `path` 字段（可能保留反斜杠）；(3) PG `UNIQUE INDEX (path)` 把不同 slash 当作不同记录 → 重复行通过；(4) `auto_upload.py` 跑批时 `os.path.isfile(path)` 走 raw path，找不到正斜杠记录，又插入新副本 |
| 失败尝试 | (1) 第一版 dedup 按 `(device_id, basename)` 合并 → 合并 339 行，但太激进，可能影响其他电脑的历史记录 → 用户叫停；(2) 改用按 path 严格匹配 dedup，保留完整 + uploaded=Yes 的副本，删除空副本 |
| 修复 | (1) **execute_focused_dedup.py** + **execute_0701_0705_dedup.py**：按 path 严格匹配 + 字段合并（不直接覆盖，从空副本取 `source_device` 等附加字段补到保留行）；(2) **CSV+PG 同步删除 + 字段合并**；(3) **删除前先备份**到 `*.before_*.csv` 和 PG `videos_backup_*` 表 |
| 验证 | CSV: 606 → 373 行；0701-0705: 114 → 57 (全部 thisPC_local)；0625-0629 完整 + uploaded=Yes: 112 行保留；uploaded=Yes 总数: 294；thisPC_local: 131 |
| 预防 | (1) **写库前必须规范化 path**：`os.path.normpath(p).replace('\', '/')` 统一为正斜杠；(2) **mark_uploaded 必须按规范化 path 查询 + 写入**（auto_upload.py 已加）；(3) **dedup 之前先 verify**（verify_dedup_safe.py）：确认每个待删除行是被保留行的空副本，**不丢数据**；(4) **自动重命名同 path 重复行**：写入前用 SELECT 检查，存在则 UPDATE 而不是 INSERT；(5) **路径约定**：`/media/videos/MMDD/hmd/...` 是本机，`/media/inbox/hmd/...` 是 otherPC（其他电脑历史） |
| 关联 | dev_log.md 2026-07-05（auto_upload 端到端）；E15（字符串跨行）；E16（脚本版本爆炸）；E17（9 个 bug 叠加）|

### 反思：数据管理模式

**问题1：单一可信源（Single Source of Truth）缺位**
- CSV 和 PG 是**两份独立存储**，没有强一致的同步机制
- 每次 `mark_uploaded` 都要双写，但写路径可能用不同 path 格式
- 写 PG 时如果 path 已被另一条记录占用，INSERT 失败但不报错（因为 path 不完全相同）

**问题2：数据模型没考虑幂等性**
- 同一逻辑操作（标记 uploaded='Yes'）在 PG 中可能产生多条记录
- 没有 UPSERT 语义，每次 INSERT 都可能产生新副本
- 应该用 `(device_id, basename)` 作为业务主键，而不是 path

**问题3：写入路径缺少验证**
- `mark_uploaded` 写完不校验 CSV 重新读是否正确
- 没有"写入后立即读出比对"的自检机制
- 应该加 atomic write + post-write verify

**正确的模式应该是**：
1. **path 规范化函数**作为唯一入口（`utils.path_utils.normalize_path`）
2. **业务主键 = (device_id, basename)** 而非 path
3. **写库前 SELECT 检查**，存在则 UPDATE，否则 INSERT
4. **CSV 和 PG 用同一个写入函数**，避免两套逻辑
5. **定期 reconcile job** 扫描两边差异，自动同步

---

## E19. ✅ FIXED — 任务维表 "+ 新增" 后填的字段识别不到（搜索框非空时）

| 字段 | 内容 |
|---|---|
| 发现 | 2026-07-07（用户报告） |
| 修复 | 2026-07-07 |
| 现象 | 任务维表（tasks）页面点 "+ 新增" 后依次填 产品/任务/工具/工序，右边"校验"列一直显示 `⚠ 还差 4/4 字段`，点保存 toast `缺 4 元组字段` |
| 期望 | 4 元组填满后校验列实时递减 → ✓ 4/4 → 保存成功 |
| 根因 | **2 个独立 bug 叠加**：<br>**Bug A — 新行被过滤掉**：`dimRenderTable` (`src/templates/index.html:2499-2507`) 的过滤判断 `if (search && !hay.includes(search)) return` 对所有行一视同仁，新行 4 元组空字符串不含搜索词被 return 跳过，根本没渲染进 `#dimBodyTasks`<br>**Bug B — `dimAddRow` 后续 querySelector 错位**：`dim-write-ops.js:4-29`（或 `task-validation.js:168`，同名函数后加载覆盖）在 `dimRenderTable` 之后调 `bodyEl.querySelector('tr')`，本意拿新行，但新行不在 DOM 里，返回的是**第一个匹配过滤的旧行**；然后 `firstTr.dataset.key = '__new_xxx__'` 把这个旧行的 dataset.key **篡改成新行临时键**，焦点跳到旧行的 product 输入框<br>**Bug C — difficulty 中英校验不一致**：`_taskValidateRow` (`task-validation.js:13`) 校验 `['easy','medium','hard']` 但下拉框选项是 `['','简单','中等','困难']`；后端 `config.py:130 validators` 同样只认英文。用户选"简单"后 `_taskValidateRow` 返回 `{ok:false}`，但 `_taskRefreshRowHint` 的 else 分支只数 4 元组缺几个不显示真实原因 → 文字停在 `⚠ 还差 0/4`（0 missing 但其实卡 difficulty） |
| 失败尝试 | 排查中曾怀疑 `process_en` 渲染问题、`dim-table-crud.js` vs index.html 双源分歧 → 都不是。Playwright 实测确认过滤态下 `tr[data-key^="__new_"]` 计数是 1 但 `#dimBodyTasks tr` 总数不变 → 才锁定根因 |
| 修复 | (1) **`index.html:2500-2513` 内联 `dimRenderTable`**：把 `isNew` 判断前移到过滤之前，过滤判断加 `&& !isNew` 豁免新行，新行无论搜索词为何都进 DOM；`dimAddRow` 后续 `querySelector('tr')` 自然拿到正确的新行<br>(2) **`task-validation.js:7-17` `_taskValidateRow`**：删除 difficulty 英文校验<br>(3) **`task-wizard.js:30-36` `_validateBatchRow`**：同样删除 difficulty 校验<br>(4) **`config.py:130`**：删除 `"difficulty": {"easy","medium","hard"}` 后端校验规则 |
| 验证 | 过滤态点 "+ 新增"：新行冒出在顶部（旧行不再被涂黄伪装）；依次填 4 字段，hint `⚠ 4/4 → 3/4 → 2/4 → 1/4 → ✓ 4/4`；保存后 server 生成 `task_id = slug(prod)_slug(task+tool)_slug(process)_NNN`；后端 CSV + PG 双写成功 |
| 预防 | (1) **`dimAddRow` 类函数不能依赖 `bodyEl.querySelector('tr')` 拿新行**——新行可能因过滤不可见；要么过滤豁免新行，要么渲染时给新行加 `tr.dim-new` class 让 querySelector 用 `.dim-new` 选择器；<br>(2) **校验提示必须显示真实失败原因**——`_taskRefreshRowHint` 不该只看 missing count，应读 `v.reason`；<br>(3) **前后端校验字段值集合要保持一致**——如果后端 / quota / 统计都按 `easy/medium/hard` 走，前端下拉也该用这套值（或用 `{value, label}` 对象形式 label=中文、value=英文）；现在 difficulty 直接放过不校验是妥协方案，副作用是 quota 查表 `DIFFICULTY_LIMITS_HOURS = {"easy":10,...}` 不会命中中文 difficulty → quota 走兜底值<br>(4) **dim-table-crud.js 是死代码**（index.html 未引入），重复维护两份反而埋坑，建议删除或合并到 index.html |
| 关联 | dev_log.md 2026-07-07 |
