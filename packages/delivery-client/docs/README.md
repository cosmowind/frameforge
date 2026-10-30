# vendor-upload-pkg

CLI 工具,把供应商接入的视频上传到 `publish.example.com/vendors` 的 task-box 体系下。

- **每个 box 是一个任务桶**(5 元组:`scenario` × `taskDescription` × `environmentDescription` × `operatorName` × `captureMode`),总时长上限 10 小时
- **自动复用**:同一 5 元组下已有 `approved` box 时,跳过创建,直接追加;否则创建新 box
- **(.hmd) Stereo view 自动转换**:本地 `hmd-decode.esm.js`(预览用)解析 → Node 脚本 `hmd_to_mcap.js` 按 [MCAP 交付规范(供应商版)](../MCAP%20交付规范（供应商版）.md) 产出 `.mcap` + `metadata.json`,Python CLI 上传到 frameforge 的 stereo 端点
- **Clerk session 自动轮转**(`__session` 5 分钟过期自动续)
- **S3 分片上传 + 失败 part 重传**(复用 `upload.py` 的 `put_part` / `upload_parts`)

---

## 业务边界(很重要)

**预览和上传走完全独立的两条管线,互不依赖。**

| 组件 | 作用 | 在哪跑 |
|---|---|---|
| `static/hmd/hmd-decode.esm.js` | **本地预览**用,把 `.hmd` 解出 HEVC + IMU 给浏览器看 | 浏览器内 |
| `hmd_to_mcap.js`(本仓库新建) | **提交侧**转换:自己内联解 `.hmd` Galaxea wire format,按 frameforge 上游 `lib/mcap/proto.ts` + 供应商 MCAP 交付规范,产出可上传的 `.mcap` + `metadata.json` | 本地 Node 子进程 |
| `upload_pkg.py`(本仓库新建) | 把上一步的产物上传到 frameforge stereo 端点 | 本地 Python CLI |
| `upload.py`(已存在) | 老的 free-form `.mp4`/`.mov` 上传器,**不再用于 stereo** | 本地 Python CLI |

**不要**把 `hmd-decode.esm.js` 的输出(裸 HEVC + IMU byte slice)直接当上传物 — 那不是 frameforge 要的格式。**必须**走 `hmd_to_mcap.js` 包成 MCAP,且 `hmd_to_mcap.js` 不 import `hmd-decode.esm.js` — 它自己解 `.hmd`,保持预览与上传两条管线互不耦合。

---

## 1. 一次性设置

### 1.1 Python 依赖

```bash
pip install -r requirements.txt
# requests + mcap (Foxglove 官方 Python MCAP reader,用于 --mcap-dir 模式读 videoStats 和 inspect_mcap.py)
```

### 1.2 Node 依赖(用于 .hmd → .mcap 转换)

```bash
cd vendor-upload-pkg
npm install
```

会装 `@mcap/core` + `protobufjs`。

### 1.3 cookie

```bash
cp cookie.txt.template cookie.txt
# 在 https://publish.example.com/vendors 登录后,DevTools → Application → Cookies
# 复制 __session / __client / __client_uat 三个 cookie 的值
```

---

## 2. 用法 — 上传 (.hmd) Stereo 视图

```bash
cd vendor-upload-pkg
python3 upload_pkg.py \
    --cookie-file ./cookie.txt \
    --scenario "D01-S01-C01-T01" \
    --task-description "Sort snowflake blocks" \
    --environment-description "Factory floor, daylight" \
    --operator-name "Zhuoran Guo" \
    --capture-mode stereo \
    --session-dir ./captures/session_000001
```

CLI 会做这些事:

1. 校验 `--session-dir` 里 ≥ 1 个 `part_NNN.hmd` + 1 个 `metadata.json`
2. 调 `node hmd_to_mcap.js`:
   - **内联解析** Galaxea .hmd wire format(IMU / Galaxea glue / HEVC GOP chunk packet),拼出 left/right 双目 HEVC
   - 按 60 fps 交错规则拆出 left/right 双目流
   - 写 MCAP,topics:`/top-left-camera/image-raw`、`/top-right-camera/image-raw`、`/head-imu`(schema 用 frameforge 上游 `lib/mcap/proto.ts` 的 foxglove.CompressedVideo + google.protobuf.StringValue)
   - **统计 videoStats**(`fps` / `frameCount` / `durationSeconds`)由帧计数 + IMU `t_us` 范围算出,写到 stdout JSON 的 `stats.videoStats`
3. **读取 MCAP header 算 videoStats**(用了 `pip install mcap`)— 与 step 2 一致(等于本地转换后的 .mcap 重新解一次)
4. `GET /api/deliveries/task-boxes?filter=active` 列已有 box,按 5 元组找匹配:
   - 找到 + 状态 `approved` → 复用,调 `POST /api/deliveries/task-boxes/{id}/videos/stereo-hmd-initiate`
   - 没找到 → 调 `POST /api/deliveries/task-boxes` 创建新 box(stereo 模式下 box **自动 approved**,`reviewedBy='auto:stereo_hmd'`,不需要 admin 审核)
5. 对返回的 mcap + metadata.json 各调 `sign-parts` 拿预签名 URL,然后 S3 multipart PUT
6. 调 `POST /api/deliveries/videos/stereo-hmd-session/complete` 完成,**`videoStats` 一并提交**,frameforge 服务端会把它写到 `ff_vendor_video.fps` / `frameCount` / `durationSeconds`

整个流程的产物:

- 本地:`<work-dir>/session.mcap` + `<work-dir>/session.mcap.metadata.json`
- 远端:frameforge 的 S3 上有两个对象:`vendor-uploads/<vendorId>/<videoId>.mcap` + `…_metadata.json`,关联到一个 `approved` 的 task box

### 2.0 用法 — 上传已转好的 (.mcap) Stereo 视图

当 vendor 已经用 frameforge 前端 `/hmd-converter` 或其它合规工具把 `.hmd` 转好 `.mcap` 时,可直接传 `.mcap` 文件夹,跳过 Node 转换步骤:

```bash
cd vendor-upload-pkg
python3 upload_pkg.py \
    --cookie-file ./cookie.txt \
    --scenario "D01-S01-C01-T01" \
    --task-description "Sort snowflake blocks" \
    --environment-description "Factory floor, daylight" \
    --operator-name "Zhuoran Guo" \
    --capture-mode stereo \
    --mcap-dir ./converted/session_000001
```

`--mcap-dir` 目录里要求恰好有:

- 一个 `.mcap`(文件名随便,例如 `session_000001.mcap`)
- 一个 `metadata.json`(文件名固定,大小写不敏感)

行为:

1. 校验 `validate_mcap_dir`(恰好一个 .mcap + 恰好一个 metadata.json)
2. 用 `mcap` Python 库读 `.mcap` 的 summary,提取 `videoStats`:
   - `frameCount` = 任一 `/top-*-camera/image-raw` topic 的 message count
   - `durationSeconds` = `(max log_time - min log_time) / 1e9`
   - `fps` = `frameCount / durationSeconds`(降级:无 log_time 时按 60 fps 估算)
3. 走和 `--session-dir` 一样的 box 匹配 + initiate + sign-parts + complete 流程,把 `videoStats` 透传给服务端

`--mcap-dir` 与 `--session-dir` 二选一,CLI 不允许两个都给(互斥组)。

### 2.1 自动 box 复用 — 5 元组匹配

| 字段 | 来源 |
|---|---|
| `scenario` | `--scenario`(scene-taxonomy-v2 leaf-task id) |
| `taskDescription` | `--task-description` |
| `environmentDescription` | `--environment-description` |
| `operatorName` | `--operator-name` |
| `captureMode` | `--capture-mode`(默认 `stereo`) |

**任一字段不同就视为不同 box,创建新的**。stereo 模式下新 box 跳过 admin 审核。

### 2.2 `--scenario` 取值列表

`--scenario` 是 **scene-taxonomy-v2 leaf-task id**,形如 `D01-S01-C01-T01`(10 个 domain × 37 个 sector × 106 个 category × 647 个 leaf task)。

**完整取值表 + 中英对照**见 [`docs/scenario-taxonomy.md`](scenario-taxonomy.md)。从 `frameforge/src/lib/scene-taxonomy-v2.ts` 自动生成,可直接给前端管理界面作为 **预置选项**。

如果列表需要更新(frameforge 上游 taxonomy 改了),重新跑:

```bash
python tools/extract_scenario_taxonomy.py F:/path/to/frameforge/src/lib/scene-taxonomy-v2.ts
```

### 2.3 重要: stereo session **不受 10h 上限约束**

> frameforge upstream (`stereo-hmd-initiate/route.ts:21-22`): "The 10h duration cap does NOT apply to stereo sessions (.hmd has no duration)."

stereo 单文件上限放宽到 ~640 GiB(`VENDOR_UPLOAD_MAX_STEREO_FILE_BYTES = PART_SIZE × 9999`),绕过 S3 的 10k-part 硬限制。

### 2.4 Dry-run

```bash
python3 upload_pkg.py --dry-run --session-dir ./captures/session_000001 ...
```

只打印计划,不发起任何 API 请求,也不跑 Node 转换。

---

## 3. 文件 / 目录结构

```
vendor-upload-pkg/
├── upload_pkg.py          # CLI(本任务新建)— 上传到 task-box
├── upload.py              # 老 free-form uploader(继续工作,非 stereo)
├── hmd_to_mcap.js         # Node 脚本 — .hmd → MCAP(本任务新建)
├── requirements.txt       # Python 依赖(requests + mcap)
├── package.json           # Node 依赖(@mcap/core, protobufjs)
├── package-lock.json
├── node_modules/
├── cookie.txt.template
├── MCAP 交付规范（供应商版）.md   # 上游 stereo MCAP 的 schema 规范
├── docs/
│   └── README.md          # 本文件
├── tools/
│   ├── inspect_mcap.py            # 单个 .mcap 元数据 dump
│   ├── verify_mcap_matches_frontend.py  # 与 frameforge 前端转换结果对比
│   └── extract_scenario_taxonomy.py     # 从 frameforge src/lib/scene-taxonomy-v2.ts 生成 taxonomy 文档
└── static/
    └── hmd/
        └── hmd-decode.esm.js   # 本地预览解析器(只在 hmd_to_mcap.js 内部用)
```

---

## 4. 已知限制 / 边界

- **`environmentDescription` / `operatorName` 不参与列表层 5 元组匹配**:`GET /api/deliveries/task-boxes` 的响应里没有这两个字段(只有 `scenario` + `taskDescription` + `captureMode` + `status` + 时间戳)。CLI 在 listing 阶段按 scenario+taskDescription+captureMode 近似匹配;实际 server 端的 5 元组严格性需要 admin 看 portal 验证。要严格匹配的话每个候选 box 都需要单独 GET,太贵。
- **camera calibration / tf-static 不生成**:供应商 MCAP 规范里 `/top-left-camera/camera-info`、`/top-right-camera/camera-info`、`/tf-static` 这些 topic 需要供应商提供的内参 / 外参文件。`.hmd` 文件里没这些数据 — 后续如果要补全,需要 vendor 提供 calibration 文件,或者从设备标定文件生成。
- **front-end 上传走的是同一套 stereo 端点**,但前端有完整的 calibration + tf 数据,所以它的 MCAP 更"完整"。CLI 产出的 MCAP 是最小可用版,后续若 admin 拒收,需要补 calibration/tf。
- **videoStats 是估算值**:HMD 没有视频帧时间戳,只能用 IMU `t_us` 范围 ÷ 帧数算 fps 和 duration,精度受 IMU 采样率影响。若上游工作流要求精确值,请 vendor 提供带时间戳的 `.mcap`(用 `--mcap-dir` 模式,值由 `.mcap` header 直接读出)。

---

## 5. 故障排查

### 5.1 `parseStereoHmdFiles` 报 "Session folder is missing metadata.json"

确保 `--session-dir` 里直接有 `metadata.json`(不能放在子目录里)。

### 5.2 报 "filename has unsupported characters"

`.hmd` 文件名只允许 `[A-Za-z0-9._-]`,不能有中文、空格。rename 后重试。

### 5.3 401 → 自动轮转失败

- `__client` 过期了 — 重新登录浏览器,刷新 cookie.txt
- 本机访问 `clerk.publish.example.com` 被墙 — 检查网络/代理

### 5.4 `hmd_to_mcap.js` 找不到 Node

确认 `node --version` ≥ 18,`npm install` 已跑过(在 `vendor-upload-pkg/` 目录)。

---

## 6. 相关参考

- `MCAP 交付规范（供应商版）.md` — 同目录,frameforge stereo 上游要求的 schema / topics
- 上游 stereo 代码(参考,不可改):`frameforge/src/server/vendors/stereo-hmd.ts`、`frameforge/src/lib/mcap/{write,proto}.ts`、`frameforge/src/lib/hmd/parse.ts`
- 老 CLI:同目录 `upload.py`(继续用于 .mp4/.mov free-form 上传)
- 上游 task-box API:见 `frameforge/src/app/api/deliveries/task-boxes/` 和 `…/videos/stereo-hmd-initiate/`

## 7. 一致性验证 — hmd→mcap 与 frameforge 前端对齐

为保证本仓库的 `hmd_to_mcap.js` 与 frameforge 上游浏览器 `hmdToMcap` (`frameforge/src/lib/mcap/write.ts`) 产出字节级一致,提供两个验证工具。

### 7.1 `tools/inspect_mcap.py` — 单文件元数据 dump

```bash
python tools/inspect_mcap.py path/to/session.mcap
# 输出 schemas (含 FDS sha256 + bytes 数)、channels、每个 topic 的消息计数
python tools/inspect_mcap.py path/to/session.mcap --json
python tools/inspect_mcap.py path/to/session.mcap --quiet   # 只看 summary
```

### 7.2 `tools/verify_mcap_matches_frontend.py` — 与 frameforge 上游对比

校验项(按优先级):

1. **Schema 集合完整**:`foxglove.CompressedVideo` + `google.protobuf.StringValue` 必须都存在
2. **FileDescriptorSet 字节级一致**:两份 `.mcap` 的 schema.data 必须与上游 `lib/mcap/proto.ts` 里的 `COMPRESSED_VIDEO_FDS_B64` / `STRING_VALUE_FDS_B64` 字节完全相同 — 这是**最强信号**,FDS 不一致意味着 protobuf 解析器会拒绝 / 误读消息
3. **Topic 集合 + schema 映射**:`/top-left-camera/image-raw` + `/top-right-camera/image-raw` + `/head-imu` 都要在
4. **per-topic 消息数 sanity**:left / right 视频 topic 消息数应相等(frame-interleaved stereo);IMU 消息数 ≥ 视频帧 × 3(200 Hz vs 30 fps/eye)

```bash
# 单文件 vs 上游参考
python tools/verify_mcap_matches_frontend.py path/to/session.mcap

# 两两对比(本仓库 vs frameforge 前端各跑一次同一 .hmd session)
python tools/verify_mcap_matches_frontend.py ours.mcap --against theirs.mcap

# CI 模式:任何 error 直接 exit 1
python tools/verify_mcap_matches_frontend.py --strict session.mcap
```

参考的 FDS base64 字符串在 `tools/verify_mcap_matches_frontend.py` 顶部常量里硬编码。如果 frameforge 上游改了 `lib/mcap/proto.ts`,需要:

```bash
git -C F:/sys/o/frameforge/frameforge show origin/master:frameforge/src/lib/mcap/proto.ts
# 把新的 COMPRESSED_VIDEO_FDS_B64 / STRING_VALUE_FDS_B64 粘到
# vendor-upload-pkg/tools/verify_mcap_matches_frontend.py 顶部常量
```

如果上游加了新的 schema / topic,也要把 `EXPECTED_TOPICS` / `EXPECTED_SCHEMAS` 一起更新。