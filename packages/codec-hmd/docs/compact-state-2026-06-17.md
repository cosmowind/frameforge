# COMPACT-STATE-2026-06-17

> **目的**：context 压缩前的快照。所有有效信息集中此处，便于压缩后恢复上下文。
> **备份**：git tag `handoff-2026-06-17` in `handoff-workspace/`（97 文件 + 完整 git 历史）

---

## 1. 项目结构

```
./workspace
├── codec-hmd/                        ← HMD 容器解析器
│   ├── hmd-decode.js                   (270 行, Node CommonJS)
│   ├── hmd-decode.esm.js                (270 行, 浏览器 ESM, 必须与 CJS 同步)
│   ├── verify_hmd_packets.js            (17 项自测)
│   ├── session_00000/  part_000.hmd 256MB + part_001.hmd 58MB + metadata.json
│   ├── session_00001/  260MB
│   ├── session_00002/  744MB (3 parts)
│   └── docs/
│       ├── hmd-parse-solution.md        ← **关键**，完整复现指南
│       ├── handoff-2026-06-17.md
│       ├── compact-state-2026-06-17.md   ← 本文件
│       ├── project_status.md / dev_plan.md / dev_log.md
│       ├── error_book.md (E1/E2/E4 FIXED)
│       └── features.md
│
├── video-sort-package/                  ← Flask Web 管理界面
│   ├── app.py                            (2200 行, 含 10 个 HMD 路由 + 维表 CRUD)
│   ├── run.py
│   ├── 启动视频管理.bat
│   ├── video_manager.csv                 (12 MP4 + 3 HMD rows)
│   ├── recorders.csv / sd_cards.csv / tasks.csv   ← 维度表空壳
│   ├── vendor-upload-pkg/                ← 旧上传器，待适配 frameforge
│   ├── static/hmd/hmd-decode.esm.js      ← Flask 默认 static 目录（必须！）
│   ├── templates/
│   │   ├── index.html                    (3700+ 行, 含内嵌 HMD 双目预览面板)
│   │   ├── hmd_preview.html              (独立预览页)
│   │   └── ...
│   ├── tools/hmd_preprocess.py           (服务端 splitStereo + ffmpeg → MP4)
│   └── _upload_now.py / _upload_now.cmd / copy_progress_window.py
│
├── handoff-workspace/                   ← 新建 git workspace（两个项目副本 + .git）
├── handoff-2026-06-17-pre-frameforge.zip ← 旧版纯 zip 备份 (771 MB)
└── 其它无关项目（不要碰）
```

---

## 2. HMD 容器核心算法（最重要的知识）

### 容器布局（实测）
| Type | 字节 | 名称 | 数量 | 包体 |
|------|------|------|------|------|
| 0x59 | 固定 97 字节 | IMU | 128 | BNO055 四元数+加速度+角速度 |
| 0x5a | 8 字节 header | GLUE | 128 | Galaxea 元数据（不透明）|
| 0xfd | 27 字节 header | CHUNK | 74/session | 1 个 GOP 的 HEVC NAL 数据 |
| 其它 0x55 开头 | - | NOISE | ~76k/256MB | HEVC payload 里的伪 HMD3 |

### 判别符（关键！错了就找不到真实包）
- 0x59 / 0x5a：HMD3 magic + byte[5,6,7] = 0x00 0x00 0x00
- 0xfd：HMD3 magic + byte[6,7] = 0x00 0x00 + byte[8,9] = 0x86 0x01（byte[5] 是变化的 stream ID）

### 双目结构（**实测**）
- **不是** SBS / TB / 双流 / 两个独立文件
- **是** 60 fps 帧交替立体：NAL index 0,2,4... = camera 0（左）；1,3,5... = camera 1（右）
- 帧率 30 fps × 2 相机 = 60 fps
- 单帧 1920×1080（不是 3840×1080）

### splitStereo 实现
```js
function splitStereo(hevc) {
  const nals = splitNals(hevc);  // 按 00 00 00 01 切片
  const left = [], right = [];
  let frameIdx = 0;
  for (const nal of nals) {
    const isPS = nal.nalType === 32 || nal.nalType === 33 || nal.nalType === 34;
    if (isPS) { left.push(nal.data); right.push(nal.data); continue; }
    const target = (frameIdx % 2 === 0) ? left : right;
    target.push(nal.data);
    frameIdx++;
  }
  return { left: concat(left), right: concat(right), stats: {...} };
}
```

---

## 3. hmd-decode.js API

### Node CommonJS
```js
const { parse, splitStereo, dedupParamSets, findPackets,
        IMU_TYPE, GLUE_TYPE, CHUNK_TYPE,
        KNOWN_PACKET_TYPES, HEADER_LEN } = require('./hmd-decode');

// 多 part 数组（推荐）或单 buffer
const parts = [part0Buf, part1Buf, part2Buf];  // 按 part_000/001/002 顺序
const r = await parse(parts);
// r.video[0].hevc = 60fps 帧交替单流（Uint8Array）
// r.video[0].vps/sps/pps = 第一套参数集
// r.imu = [{seq, t_us, raw}]
// r.stats = {parts, realPackets, imu, glue, chunkPackets,
//             hevc1StartCodes, hevc1Bytes,
//             hevc2StartCodes, hevc2Bytes}  // 注意是 1/2 后缀（旧版本）

const hevc = dedupParamSets(r.video[0].hevc);  // 去重 VPS/SPS/PPS
const { left, right, stats } = splitStereo(hevc);
// stats = { leftFrames: 11061, rightFrames: 11060, totalFrames: 22121 }
```

### 浏览器 ESM
```js
import { parse, splitStereo, dedupParamSets } from '/static/hmd/hmd-decode.esm.js';
// API 一致
```

### 已知陷阱
- ❌ 旧的 `p += total` 步进是错的（容器无 size 字段）→ 用"下一包 offset - 当前 offset"
- ❌ `findPackets` 返回 `{offset, type}`，需要 type ∈ {0x59, 0x5a, 0xfd} 才算真实包
- ❌ 浏览器端 esm.js 没导 splitStereo 会报 `does not provide an export named 'splitStereo'` → 必须两版本同步

---

## 4. video-sort-package 集成

### Flask 路由（10 个 HMD 相关）
| 端点 | 方法 | 用途 |
|------|------|------|
| `/` | GET | 主页面 |
| `/hmd-preview` | GET | 独立 HMD 预览页 |
| `/api/hmd/scan` | GET | 扫描目录找 HMD session |
| `/api/hmd/info?path=` | GET | 返回 part 列表 + metadata |
| `/api/hmd/raw?path=&file=` | GET | HTTP Range 流 .hmd 字节 |
| `/api/hmd/mp4?path=&eye=left\|right` | GET | **HTTP Range 流预渲染 MP4**（秒开） |
| `/api/hmd/process` | POST | 启动后台预处理 |
| `/api/hmd/process-status?path=` | GET | 轮询状态 |
| `/api/hmd/duration` | POST | 写回真实 duration_sec |
| `/api/hmd/register` | POST | 注册新 session 到 CSV |
| `/api/hmd/file?path=` | GET | 单 .hmd 文件下载 |
| `/api/dim/<name>` | GET/POST | 维度表 CRUD（recorders/sd_cards/tasks） |
| `/api/dim/<name>/<key>` | DELETE | 按主键删除 |
| `/api/dim/tasks/with-usage` | GET | 任务列表 + 实际已用时长 |
| `/api/upload-generate` / `-batch` / `-run` | POST | 现有 MP4 上传（待适配 frameforge） |

### 字段（video_manager.csv）
```
新增列：file_type, session_path, device_id, recorder_id, task_id, task_name, recorded_duration_sec
```
定义在 `app.py DEFAULT_FIELDNAMES`。

### 工具函数（供其他模块调用）
- `_fmt_duration(seconds)` → "M:SS" 或 "H:MM:SS"
- `_get_video_duration(filepath)` → 调 ffprobe
- `_get_file_date(filepath)` → 文件创建时间
- `_atomic_write_csv(path, rows, fieldnames, backup_prefix)` → 原子写 + 10 份备份轮转

### 预处理流程
1. scan 检测 HMD 文件夹 → 触发 `hmd_preprocess.start_async(folder)`
2. 后台线程跑 `tools/hmd_preprocess.py` 逻辑：
   - 写 parts.json 临时文件
   - 写 .js 临时脚本（避免 node -e argv 坑）
   - 设环境变量 HMD_PARTS_FILE / HMD_LEFT_OUT / HMD_RIGHT_OUT
   - 跑 `node script.js` → splitStereo 写出 left.h265 + right.h265
   - 跑 `ffmpeg -c:v copy -tag:v hvc1` 转 MP4
3. 写 `.hmd_process.json` 状态文件
4. 浏览器用 `<video src="/api/hmd/mp4?...">` 秒开

### 实测时间
| Session | 大小 | 耗时 |
|---------|------|------|
| 00001 | 260 MB | **6.1 s** |
| 00000 | 312 MB | ~6 s |
| 00002 | 744 MB | ~13 s |

---

## 5. 任务清单（Tasks）

### ✅ 已完成（Tasks #1, 3, 4, 5, 15, 16, 18, 19, 20）
- **#1** WCS 引导 + 基线文档
- **#3** HMD 双目解析（实测 60fps 帧交替拆分）
- **#4** HMD 预览移植到 video-sort-package
- **#5** 新扫描：自动收录 HMD 文件夹
- **#15** hmd-decode.js 包边界修正
- **#16** 双目结构探测（结论：60fps 帧交替）
- **#18** splitStereo 实现
- **#19** 服务端预处理 splitStereo + ffmpeg → MP4
- **#20** 写状态摘要给并行 agent

### ⏳ 待开发（Tasks #6-14, 17）
| Task | 内容 | 集成点 |
|------|------|--------|
| #6 | SD 卡自动复制 HMD | device_monitor.py L268-281 |
| #7 | 时长/创建时间元数据 | 已有 `/api/hmd/duration` |
| #8 | 录制人/设备/任务 4 张表 | 已有 `/api/dim/*` + 空 CSV |
| #9 | 录制人字段改单选 | templates/index.html |
| #10 | SD 卡 → 设备编号 | 新 API + sd_cards 表已有 |
| #11 | 任务配额 1h/2h/10h | `/api/dim/tasks/with-usage` 已实现查询 |
| #12 | 命名规范 mmdd-DevID-RecID-Task | 新 API `/api/hmd/suggest-name` |
| #13 | 端到端验证 | 跑完整流程 |
| #14 | 文档同步（wcs update_trigger） | docs/* |
| #17 | MP4 50% 缺口 | 实际是 sensor 写入率 < 30fps |

---

## 6. 浏览器播放实现（WebCodecs）

### 独立预览页（templates/hmd_preview.html）
- 4 阶段进度遮罩（下载/解析/拆分/解码）
- 双 `<canvas>` 渲染
- 拖动条、±5s、播放/暂停、50ms 同步循环

### 主界面内嵌（templates/index.html L303-335）
- `#hmdPanel` 内嵌 div
- `openHmdPreviewInline(folder)` 函数
- 关键：检测 row.file_type === 'hmd' 或 extra_description 含 "HMD 双目"

### 待做：HMD 优先用 `<video>` MP4 fallback WebCodecs
当前内嵌面板强制 WebCodecs。如果 `left.mp4 / right.mp4` 已预处理，应该用 `<video>` 秒开。

---

## 7. 注意事项（开发新功能必看）

1. **hmd-decode.js 双版本同步**：改 .js 也要改 .esm.js，export 列表必须完全一致。
2. **Flask static 路径**：必须放 `static/hmd/`，不要只放 `templates/static/`。Flask 默认 static 是 app.py 旁的 `static/`。
3. **app.py 不要大改**：现有 2200 行含完整功能。新功能通过**新增路由**加。
4. **OneDrive I/O**：资料盘在 OneDrive 时，写大文件可能触发同步冲突 → 慢。
5. **device_id 取末 6 位**：metadata.json `identity.device_id` 取后 6 位。
6. **预处理左 30 fps，右 30 fps**：不能合到一个 stream（虽然源是 60 fps 帧交替）。
7. **ffmpeg 必须 `-tag:v hvc1`**：否则 `<video>` 标签不识别 HEVC。
8. **Node.js argv 坑**：用 `node -e` 时 argv 索引不可靠。改用临时 .js 文件 + 环境变量。
9. **Python sys.path 注入**：`sys.path.insert(0, _TOOLS_DIR)` 在 `app.py` 顶部会失败（BASE_DIR 还没定义）。改用函数内 lazy import。
10. **CSS 路径**：浏览器 esm.js 必须从 `/static/hmd/` 加载（Flask 路由 `/static/<path:filename>`）。

---

## 8. Memory（/memory 索引）

```
~/.claude/projects/F--sys-o-OneDrive---LightGroup-programs-2-bytools-claudecode-codec-hmd/memory/
├── MEMORY.md
├── hmd-stereo-60fps-interleaved.md    ← 60fps 帧交替详解 + API
├── hmd-stereo-rendering.md            ← 浏览器渲染方案（已过时但有参考）
└── video-sort-frontend-stack.md        ← Vue 3 CDN 选型
```

---

## 9. 重要文件位置速查

### 解析器
- `codec-hmd/hmd-decode.js`
- `codec-hmd/hmd-decode.esm.js`（浏览器版本）
- `codec-hmd/verify_hmd_packets.js`
- `codec-hmd/docs/hmd-parse-solution.md`（**最完整**）

### Web 服务
- `video-sort-package/app.py`
- `video-sort-package/run.py`
- `video-sort-package/templates/index.html`
- `video-sort-package/templates/hmd_preview.html`
- `video-sort-package/tools/hmd_preprocess.py`
- `video-sort-package/static/hmd/hmd-decode.esm.js`

### 文档
- `codec-hmd/docs/handoff-2026-06-17.md`（给并行 agent）
- `codec-hmd/docs/compact-state-2026-06-17.md`（本文件）
- `codec-hmd/docs/error_book.md`（E1/E2/E4 FIXED）
- `codec-hmd/wcs-manifest.yaml`（handoff 段在第 7 节）

### 备份
- `./workspace
- `./workspace

---

## 10. 一句话总结

> HMD = 60fps 帧交替立体（实测）。解析=包边界判别+间隙拼接。拆分=NAL 奇偶。批量预览=服务端 splitStereo + ffmpeg → MP4，浏览器用 `<video>` 秒开。Web 服务用 Flask + ES module WebCodecs fallback。完整复现指南在 `codec-hmd/docs/hmd-parse-solution.md`。

---

## 11. 后续会话快速恢复清单

新会话恢复上下文只需读这 3 个文件：
1. **本文件**（`docs/compact-state-2026-06-17.md`）— 整体状态
2. **`docs/hmd-parse-solution.md`** — 解析器实现细节
3. **`wcs-manifest.yaml` handoff 段** — 给并行 agent 的指引

如果做修改，必查：
- `app.py` L182 (scan) / L482-617 (HMD 路由) / L1320+ (上传)
- `templates/index.html` L303-335 (内嵌 HMD 面板)
- `tools/hmd_preprocess.py` (服务端预处理)
- `verify_hmd_packets.js` (验证解析器没坏)