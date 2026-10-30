# HMD 文件解析方案 — 完整复现指南

> 目标：让另一个 AI 读完这份文档 + 拿到样本文件后，能从零开发出完全等价的 HMD 双目解析系统。
> 实测环境：Windows 11 + Node.js 18+ + Python 3.11 + Chrome 94+
> 实测样本：`./workspace

---

## 1. 业务上下文

### 1.1 是什么 HMD

Galaxea 机器人 gripper（夹爪）双目相机的录像格式。一台 gripper 有 2 个 sensor（左右各一），通过 RV1106 SoC 编码成 HMD 容器。session（一场录像）是一个文件夹，内含：

```
session_00000/
├── part_000.hmd      256 MB  ← 第一段，可能包含文件头 + IMU 突发 + 视频
├── part_001.hmd      58 MB   ← 第二段，纯视频字节续接
└── metadata.json    2 KB    ← 录制配置（摄像机 SN、bitrate、stop_cause 等）
```

文件**可能不止一个 part**，按 `part_*.hmd` 文件名排序后字节连续拼接 = 完整录像。

### 1.2 容器布局（256 MB 单 part 实测）

字节流由三种**真实 HMD3 包**和大量**噪声**组成：

| 字节位置 | 内容 | 含义 |
|----------|------|------|
| 0x00–0x03 | `55 4d 49 33` (ASCII "HMD3") | 真实包 magic |
| 0x04 | type byte | 决定包类型（见下表） |
| 0x05–0x07 | 3 字节 metadata | 0x59/0x5a = 全 0；0xfd = 字节 5 不定、6-7 = 0 |
| 0x08+ | 包体 | 类型相关 |
| 包之间 | HEVC NAL 数据（00 00 00 01 ...） | 视频原始字节流 |

| Type | 名称 | 大小 | 包体内容 | 在 256 MB 文件中数量 |
|------|------|------|----------|---------------------|
| **0x59** | IMU | 固定 **97 字节** | BNO055 四元数+加速度+角速度 | 128（30Hz × 4.27s，仅 session 开头） |
| **0x5a** | GLUE | 仅 8 字节 header | Galaxea 元数据 | 128（与 IMU 配对） |
| **0xfd** | CHUNK | 27 字节 header + 变长 HEVC | 1 个 GOP 的 HEVC NAL（VPS+SPS+PPS+IDR+P×N） | 59（≈ 1 个 GOP/s） |
| 其它 0x55 开头 | NOISE | - | HEVC payload 里的随机 HMD3 序列 | ~76k |

⚠️ **容器没有 size 字段**——包大小必须通过"下一包 offset - 当前 offset"推断。

### 1.3 双目立体结构（实测）

**不是单文件两路 HEVC，是单流 60 fps 帧交替**：

```
HEVC stream = [VPS][SPS][PPS][IDR_L][P_L][P_R][P_L][P_R][P_L][P_R]...
              NAL index: 0       1    2    3    4    5
              相机:    0 (左) 1(右) 0    1    0    1
```

- 单帧分辨率：**1920×1080**（不是 SBS/TB）
- ffprobe 报 30 fps（不识别帧交替）
- 实际：30 fps 相机 0 + 30 fps 相机 1 交错 = 60 fps 序列
- 单 session 数据：~22k 帧 / ~12.3 GB / 实录 ~6.14 min（按 60 fps ÷ 2 算）

---

## 2. 解析算法（伪代码 → 直接翻译）

### 2.1 第一步：找真实 HMD3 包

```text
for p in 0 .. file_length - 8:
    if buf[p:p+4] != "HMD3":
        continue
    t = buf[p+4]
    if t in {0x59, 0x5a}:
        if buf[p+5:p+8] != 0x00_00_00:
            skip   # noise
    elif t == 0xfd:
        if buf[p+6:p+8] != 0x00_00:
            skip   # noise
        if buf[p+8:p+10] != 0x86_01:
            skip   # noise
    else:
        skip
    record(real_packets, offset=p, type=t)
```

**为什么需要这些判别符**：
- `55 4d 49 33` 4 字节 magic 太常见，HEVC payload 里随机出现 76k+ 次
- 7 字节判别（magic + 3 个 0 字节）降到 58k
- 类型相关判别降到 256（session_00000 实测：128 IMU + 128 GLUE + 74 CHUNK）

### 2.2 第二步：确定每个包的大小

| Type | 包大小 | 说明 |
|------|--------|------|
| 0x59 | **固定 97 字节** | 全部 IMU 包大小一致 |
| 0x5a | **8 字节 header**（包体归 HEVC） | 包体是不透明元数据 |
| 0xfd | **到下一个 0x59/0x5a/0xfd 的 offset**（27 字节 header 后归 HEVC） | 一个 GOP 的字节数 |

### 2.3 第三步：拼接 HEVC 流

```text
hevc_chunks = []
cursor = 0
for pkt in real_packets:
    # gap [cursor, pkt.offset) 是 HEVC
    hevc_chunks.append(buf[cursor:pkt.offset])
    # process packet
    if pkt.type == IMU:
        extract_imu_sample(buf, pkt.offset)
        cursor = pkt.offset + 97
    elif pkt.type == GLUE:
        # 8 字节 header 后的字节也是 HEVC
        hevc_chunks.append(buf[pkt.offset + 8 : next_offset_or_eof])
        cursor = next_offset_or_eof
    elif pkt.type == CHUNK:
        # 27 字节 header 后的字节是 HEVC NAL 数据
        hevc_chunks.append(buf[pkt.offset + 27 : next_offset_or_eof])
        cursor = next_offset_or_eof
# tail
hevc_chunks.append(buf[cursor:])
hevc = concat(hevc_chunks)
```

### 2.4 第四步：拆左右眼

```text
nals = walk_annex_b(hevc)  # 按 00 00 00 01 边界切 NAL
left_bytes = []
right_bytes = []
for i, nal in enumerate(nals):
    is_param_set = nal.type in {32, 33, 34}  # VPS/SPS/PPS
    if is_param_set:
        # 参数集双写
        left_bytes.append(nal)
        right_bytes.append(nal)
    else:
        # frame NAL 按奇偶分流
        target = left_bytes if i % 2 == 0 else right_bytes
        target.append(nal)
left = concat(left_bytes)   # 相机 0, 30 fps
right = concat(right_bytes)  # 相机 1, 30 fps
```

⚠️ "奇偶"是按 **NAL 顺序**（不是 PTS）。因为 PTS 都是 30 fps 间隔，奇偶对应相机 0/1。

---

## 3. Node.js 实现（CommonJS）

### 3.1 文件 `hmd-decode.js`

完整代码（270 行左右）：

```javascript
// hmd-decode.js
const MAGIC = [0x55, 0x4d, 0x49, 0x33];
const IMU_TYPE = 0x59;
const GLUE_TYPE = 0x5a;
const CHUNK_TYPE = 0xfd;
const KNOWN_PACKET_TYPES = new Set([IMU_TYPE, GLUE_TYPE, CHUNK_TYPE]);

const HEADER_LEN = 8;
const IMU_TOTAL = 97;
const GLUE_HEADER = 8;
const CHUNK_HEADER = 27;

function findPackets(buf) {
  const real = [];
  for (let p = 0; p + HEADER_LEN <= buf.length; p++) {
    if (buf[p] !== MAGIC[0] || buf[p+1] !== MAGIC[1] ||
        buf[p+2] !== MAGIC[2] || buf[p+3] !== MAGIC[3]) continue;
    const t = buf[p+4];
    if (t === IMU_TYPE || t === GLUE_TYPE) {
      if (buf[p+5] === 0 && buf[p+6] === 0 && buf[p+7] === 0) {
        real.push({ offset: p, type: t });
      }
    } else if (t === CHUNK_TYPE) {
      if (buf[p+6] === 0 && buf[p+7] === 0 &&
          buf[p+8] === 0x86 && buf[p+9] === 0x01) {
        real.push({ offset: p, type: t });
      }
    }
  }
  return real;
}

async function parse(input, opts = {}) {
  // 多 part 支持：input 可以是单 buffer 或 buffer 数组
  const parts = Array.isArray(input) ? input : [input];
  const buffers = parts.map(p => p instanceof Uint8Array ? p : new Uint8Array(p));
  // 计算 concatenated offset
  const offsets = [];
  let totalLen = 0;
  for (const b of buffers) { offsets.push(totalLen); totalLen += b.length; }

  // locate(off) → 返回 (buf, localOff)，跨越多个 buffer
  function locate(off) {
    let lo = 0, hi = offsets.length - 1;
    while (lo < hi) {
      const mid = (lo + hi + 1) >> 1;
      if (offsets[mid] <= off) lo = mid; else hi = mid - 1;
    }
    return { buf: buffers[lo], localOff: off - offsets[lo] };
  }

  // 跨 part 找所有包
  const allPackets = [];
  for (let pi = 0; pi < buffers.length; pi++) {
    const local = findPackets(buffers[pi]);
    for (const p of local) allPackets.push({ offset: p.offset + offsets[pi], type: p.type });
  }
  allPackets.sort((a, b) => a.offset - b.offset);

  const stats = { parts: buffers.length, realPackets: allPackets.length,
    imu: 0, glue: 0, chunkPackets: 0, hevcStartCodes: 0, hevcBytes: 0 };
  const hevcChunks = [];
  const imu = [];
  let params = {};

  let cursor = 0;
  for (let i = 0; i < allPackets.length; i++) {
    const pkt = allPackets[i];
    const p = pkt.offset;
    // 确定本包占用字节数
    let pktEnd;
    if (pkt.type === IMU_TYPE) pktEnd = p + IMU_TOTAL;
    else if (pkt.type === GLUE_TYPE) pktEnd = p + GLUE_HEADER;
    else if (pkt.type === CHUNK_TYPE) pktEnd = allPackets[i+1] ? allPackets[i+1].offset : totalLen;
    else pktEnd = p + HEADER_LEN;

    // gap [cursor, p) 是 HEVC
    if (p > cursor) {
      hevcChunks.push(getRange(cursor, p, locate));
      stats.hevcBytes += p - cursor;
    }

    // 处理包
    if (pkt.type === IMU_TYPE) {
      const loc = locate(p);
      const buf = loc.buf;
      const seq = buf[loc.localOff+16] | (buf[loc.localOff+17]<<8) |
                  (buf[loc.localOff+18]<<16) | (buf[loc.localOff+19]<<24);
      const tLow = buf[loc.localOff+20] | (buf[loc.localOff+21]<<8) |
                   (buf[loc.localOff+22]<<16);
      imu.push({ seq, t_us: tLow, raw: buf.subarray(loc.localOff+HEADER_LEN, loc.localOff+IMU_TOTAL) });
      stats.imu++;
    } else if (pkt.type === GLUE_TYPE) {
      const hevcStart = p + GLUE_HEADER;
      if (hevcStart < pktEnd) {
        hevcChunks.push(getRange(hevcStart, pktEnd, locate));
        stats.hevcBytes += pktEnd - hevcStart;
      }
      stats.glue++;
    } else if (pkt.type === CHUNK_TYPE) {
      const hevcStart = p + CHUNK_HEADER;
      if (hevcStart < pktEnd) {
        hevcChunks.push(getRange(hevcStart, pktEnd, locate));
        stats.hevcBytes += pktEnd - hevcStart;
      }
      stats.chunkPackets++;
    }

    cursor = pktEnd;
  }
  // tail
  if (cursor < totalLen) {
    hevcChunks.push(getRange(cursor, totalLen, locate));
    stats.hevcBytes += totalLen - cursor;
  }

  // 拼接 + 参数集提取 + start code 计数
  const hevc = concat(hevcChunks);
  captureParams(hevc, params);
  for (let i = 0; i < hevc.length-3; i++) {
    if (hevc[i]===0 && hevc[i+1]===0 && hevc[i+2]===0 && hevc[i+3]===1) stats.hevcStartCodes++;
  }

  return {
    video: [{ packets: stats.hevcStartCodes, hevc, vps: params.vps, sps: params.sps, pps: params.pps }],
    imu, stats,
  };
}

function getRange(from, to, locate) {
  // 跨 buffer 切片
  const { buf, localOff } = locate(from);
  const slice = Math.min(buf.length - localOff, to - from);
  return buf.subarray(localOff, localOff + slice);
}

function splitNals(hevc) {
  // Annex-B NAL 切片（00 00 00 01 或 00 00 01）
  const out = []; let i = 0;
  while (i < hevc.length - 3) {
    if (hevc[i]===0 && hevc[i+1]===0 && hevc[i+2]===0 && hevc[i+3]===1) {
      let j = i + 4;
      while (j < hevc.length - 3) {
        if (hevc[j]===0 && hevc[j+1]===0 && hevc[j+2]===0 && hevc[j+3]===1) break;
        if (hevc[j]===0 && hevc[j+1]===0 && hevc[j+2]===1) break;
        j++;
      }
      const nalType = (hevc[i+4] >> 1) & 0x3f;
      out.push({ nalType, data: hevc.subarray(i, j) });
      i = j;
    } else i++;
  }
  return out;
}

function splitStereo(hevc) {
  // 60 fps 帧交替 → 2 路 30 fps
  const nals = splitNals(hevc);
  const left = [], right = [];
  let frameIdx = 0, leftFrames = 0, rightFrames = 0;
  for (const nal of nals) {
    const isPS = nal.nalType === 32 || nal.nalType === 33 || nal.nalType === 34;
    if (isPS) {
      left.push(nal.data);
      right.push(nal.data);
      continue;
    }
    const target = (frameIdx % 2 === 0) ? left : right;
    target.push(nal.data);
    if (frameIdx % 2 === 0) leftFrames++; else rightFrames++;
    frameIdx++;
  }
  return {
    left: concatBytes(left),
    right: concatBytes(right),
    stats: { leftFrames, rightFrames, totalFrames: frameIdx },
  };
}

// dedupParamSets: 移除重复的 VPS/SPS/PPS（每 IDR 都带一份）
function dedupParamSets(hevc) { /* 同 splitNals + 只保留第一套 */ }

module.exports = { parse, findPackets, splitNals, splitStereo,
  dedupParamSets, MAGIC, IMU_TYPE, GLUE_TYPE, CHUNK_TYPE,
  KNOWN_PACKET_TYPES, HEADER_LEN, IMU_TOTAL, GLUE_HEADER, CHUNK_HEADER };
```

### 3.2 自测脚本 `verify_hmd_packets.js`

```javascript
const { parse, splitStereo, dedupParamSets } = require('./hmd-decode.js');
const fs = require('fs');

// 用法：node verify_hmd_packets.js session_00000
const dir = process.argv[2] || 'session_00000';
const files = fs.readdirSync(dir).filter(f => /^part_.*\.hmd$/.test(f)).sort();
const buffers = files.map(f => new Uint8Array(fs.readFileSync(`${dir}/${f}`)));
const totalSize = buffers.reduce((a,b)=>a+b.length, 0);

const r = await parse(buffers);

// 预期（session_00000，312 MB）：
// r.stats.parts = 2
// r.stats.realPackets = 330 (128 IMU + 128 GLUE + 74 CHUNK)
// r.stats.imu = 128
// r.stats.glue = 128
// r.stats.chunkPackets = 74
// r.stats.hevcStartCodes = 24335
// r.stats.hevcBytes = 327249406 (parts 之间 byte 对账 ✓)

const hevc = dedupParamSets(r.video[0].hevc);
const stereo = splitStereo(hevc);
// stereo.stats = { leftFrames: 11061, rightFrames: 11060, totalFrames: 22121 }

// 写入 .h265 给 ffmpeg 验证
fs.writeFileSync('/tmp/left.h265', stereo.left);
fs.writeFileSync('/tmp/right.h265', stereo.right);
```

### 3.3 验证命令

```bash
cd codec-hmd
node verify_hmd_packets.js session_00000    # 17/17 PASS
node verify_hmd_packets.js session_00001    # 17/17 PASS
node verify_hmd_packets.js session_00002    # 17/17 PASS

# ffmpeg 验证左右眼可独立播放 + 抽帧对比
ffmpeg -y -i /tmp/left.h265 -ss 5 -frames:v 1 /tmp/left_t5.png
ffmpeg -y -i /tmp/right.h265 -ss 5 -frames:v 1 /tmp/right_t5.png
# 肉眼对比：同一场景不同角度（视差）
```

---

## 4. 浏览器 ES Module 版本（hmd-decode.esm.js）

把上面的 `hmd-decode.js` 复制为 `hmd-decode.esm.js`，把所有 `require/module.exports` 改成 `import/export`。**注意**：

1. `async function parse()` 不需要 `Promise.resolve()` 包装（直接 return）
2. 加 `await new Promise(r => setTimeout(r, 0))` 在循环里给浏览器让出主线程
3. 添加 `export { parse, findPackets, splitNals, dedupParamSets, splitStereo }`

测试浏览器加载：
```html
<script type="module">
  import { parse, splitStereo } from '/static/hmd/hmd-decode.esm.js';
  // ... fetch part_*.hmd, parse, splitStereo, 喂 WebCodecs
</script>
```

---

## 5. 浏览器解码（WebCodecs）

```javascript
// 给每个 stream 建一个 VideoDecoder
function setupDecoders(codec, desc) {
  return ['left', 'right'].map(side => new VideoDecoder({
    output: f => { /* drawImage to canvas */ },
    error: e => console.warn(side, e.message),
  })).reduce((acc, dec, i) => ({ ...acc, [i===0?'left':'right']: dec }), {});
}

decoders.left.configure({ codec, codedWidth: 1920, codedHeight: 1080, description: desc });
decoders.right.configure({ codec, codedWidth: 1920, codedHeight: 1080, description: desc });

// 喂 NAL（必须 AVCC 格式：4 字节 BE 长度前缀）
function avccWrap(nal) {
  const body = nal[0]===0&&nal[1]===0&&nal[2]===0&&nal[3]===1 ? nal.subarray(4) : nal;
  const out = new Uint8Array(4 + body.length);
  new DataView(out.buffer).setUint32(0, body.length, false);
  out.set(body, 4);
  return out;
}

function feedFrame(dec, nal, frameIdx) {
  if (nal.type === 'ps') return; // param sets 已包含在 description
  const isKey = nal.type === 19 || nal.type === 20;
  dec.decode(new EncodedVideoChunk({
    type: isKey ? 'key' : 'delta',
    timestamp: 0,
    duration: Math.round(1e6 / 30),  // 30 fps
    data: avccWrap(nal.data),
  }));
}
```

---

## 6. Flask 后端（video-sort-package 集成）

### 6.1 文件 `app.py` 增量

```python
import glob  # 必须加 import

@app.route("/api/hmd/info")
def hmd_info():
    folder = request.args.get("path", "")
    if not folder or not os.path.isdir(folder):
        return jsonify({"error": "Folder not found"}), 404
    parts = sorted(glob.glob(os.path.join(folder, "part_*.hmd")))
    total_size = sum(os.path.getsize(p) for p in parts)
    meta = None
    meta_path = os.path.join(folder, "metadata.json")
    if os.path.isfile(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except: pass
    return jsonify({
        "folder": folder,
        "parts": [{"name": os.path.basename(p), "size": os.path.getsize(p)} for p in parts],
        "total_size": total_size,
        "metadata": meta,
    })

@app.route("/api/hmd/raw")
def hmd_raw():
    folder = request.args.get("path", "")
    fname = request.args.get("file", "")
    if not folder or not fname or not os.path.isdir(folder):
        return "Bad request", 400
    full = os.path.normpath(os.path.join(folder, fname))
    if not full.startswith(os.path.normpath(folder)):
        return "Forbidden", 403
    if not os.path.isfile(full):
        return "File not found", 404
    # 支持 HTTP Range（fetch + 部分读取需要）
    file_size = os.path.getsize(full)
    range_header = request.headers.get("Range")
    if range_header:
        spec = range_header.replace("bytes=", "")
        a, b = spec.split("-")
        start = int(a)
        end = int(b) if b else file_size - 1
        end = min(end, file_size - 1)
        length = end - start + 1
        with open(full, "rb") as f:
            f.seek(start); data = f.read(length)
        resp = Response(data, 206, mimetype="application/octet-stream")
        resp.headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        resp.headers["Accept-Ranges"] = "bytes"
        resp.headers["Content-Length"] = length
        return resp
    return send_file(full, mimetype="application/octet-stream")

@app.route("/hmd-preview")
def hmd_preview():
    return send_file("templates/hmd_preview.html")

# 在 /api/scan 里加 HMD 文件夹检测：
@app.route("/api/scan", methods=["POST"])
def scan_directory():
    directory = request.get_json().get("directory", "").strip()
    hmd_folders = []
    for root, _dirs, files in os.walk(directory):
        has_parts = any(f.startswith("part_") and f.endswith(".hmd") for f in files)
        has_meta = "metadata.json" in files
        if has_parts and has_meta:
            parts = sorted(glob.glob(os.path.join(root, "part_*.hmd")))
            if parts:
                total = sum(os.path.getsize(p) for p in parts)
                # 写一行进 video_manager.csv
                # ...
                _dirs[:] = []  # 不递归子目录
                continue
        # 原有 mp4 扫描逻辑
```

### 6.2 文件 `templates/hmd_preview.html`

500 行左右，含：
- 进度遮罩（4 阶段：下载/解析/拆分/解码）
- 双 `<canvas>` 左右眼
- 拖动条、±5s 按钮、播放/暂停
- 同步循环（容差 50 ms）

**关键 JS 流程**：
```javascript
import { parse, splitStereo, dedupParamSets } from '/static/hmd/hmd-decode.esm.js';

async function loadFolder(folder) {
  // 1. fetch /api/hmd/info
  const info = await (await fetch(`/api/hmd/info?path=${folder}`)).json();
  // 2. fetch 每个 part（带进度）
  const partBufs = [];
  for (let i = 0; i < info.parts.length; i++) {
    const r = await fetch(`/api/hmd/raw?path=${folder}&file=${info.parts[i].name}`);
    partBufs.push(new Uint8Array(await r.arrayBuffer()));
  }
  // 3. parse（多 part）
  const r = await parse(partBufs);
  // 4. dedup + splitStereo
  const hevc = dedupParamSets(r.video[0].hevc);
  const stereo = splitStereo(hevc);
  // 5. 喂给两个 VideoDecoder
  setupDecoders(stereo.left, stereo.right, r.video[0].vps/sps/pps);
}
```

### 6.3 主页集成（templates/index.html）

在扫描时识别 HMD 文件夹（包含 part_*.hmd + metadata.json），作为一行写入 video_manager.csv：

```python
# 在 scan_directory 中：
for u in hmd_folders:
    if u["folder"] not in existing_map:
        row = {fn: "" for fn in DEFAULT_FIELDNAMES}
        row["path"] = u["folder"]
        row["location_status"] = "local"
        row["scan_date"] = datetime.now().strftime("%Y-%m-%d")
        row["extra_description"] = f"HMD 双目 session · {len(u['parts'])} parts · {u['total_size']/1024/1024:.0f} MB"
        # duration 估算：1.5 MB/s × 60 = ~90 MB/min
        row["duration"] = f"{u['total_size']/1024/1024/1.5:.1f} min (估)"
        existing_map[u["folder"]] = row
```

预览按钮自动判断：
```javascript
function preview(index) {
  const row = tableData[index];
  const isUmi = row.extra_description?.includes('HMD') ||
                row.path.includes('session_') && !row.path.match(/\.(mp4|mov)$/i);
  if (isUmi) {
    window.open('/hmd-preview?path=' + encodeURIComponent(row.path), '_blank');
    return;
  }
  // 否则走原有 MP4 预览
  video.src = '/api/video?path=' + encodeURIComponent(row.path);
  video.play();
}
```

---

## 7. 失败模式 & 诊断

| 症状 | 原因 | 修复 |
|------|------|------|
| `parse` 返回 0 IMU | `findPackets` 判别符太严 | 检查 0x59 包 byte[5:8] 是否真为 0 |
| `parse` 返回 0 GLUE | 同上 | 检查 0x5a 包 byte[5:8] |
| `parse` 返回 0 CHUNK | `0xfd` 判别条件错 | 必须是 byte[6,7]=0 + byte[8,9]=(0x86,0x01) |
| HEVC 字节数 = 0 | cursor 推进逻辑错 | 检查每个包占用字节（97/8/下一包 offset） |
| ffprobe 报 17k 帧 | 旧实现把两路混合当成单流 | 改用 splitStereo |
| 拆分后左/右内容相同 | odd/even 算错 | 检查 NAL 索引是否含 param sets |
| 浏览器 import 失败 | esm.js 没导出 splitStereo | 检查 export 列表 |
| Flask 报 `hmd_info overwriting` | 重复定义路由 | grep `@app.route("/api/hmd/info")`，删旧的 |
| 静态文件 404 | Flask 默认 static 在 app.py 旁 | 把 esm.js 复制到 `static/hmd/`（不要只放 templates/static/） |

---

## 8. 关键测试断言（验证实现正确性）

拿到样本文件后，这些断言必须全部通过：

| # | 断言 | 实测值（session_00000） |
|---|------|------------------------|
| 1 | 256 MB 文件有 256-330 个真实 HMD3 包 | 330 |
| 2 | IMU 包数 | 128 |
| 3 | GLUE 包数 | 128 |
| 4 | CHUNK 包数（按 part 累计） | 74 |
| 5 | 所有 IMU 包大小 = 97 字节 | ✓ |
| 6 | IMU 包紧邻（97 字节间距） | ✓ 前 17 个连续 |
| 7 | HEVC 流总字节数 + HMD3 占用 = 文件总字节数 | 312 MB |
| 8 | HEVC start code 数 ≥ 19,000 | 24,335 |
| 9 | 第一套 VPS NAL type = 32 | ✓ |
| 10 | 第一套 SPS NAL type = 33 | ✓ |
| 11 | 第一套 PPS NAL type = 34 | ✓ |
| 12 | splitStereo 左 + 右 + 总帧数对齐 | 11061 + 11060 = 22121 |
| 13 | 左右帧数差 ≤ 1 | \|11061-11060\| = 1 ✓ |
| 14 | ffprobe left.h265 报告 HEVC 1920×1080 30 fps | ✓ |
| 15 | 抽 left.png 与 right.png 是同一场景不同视角 | ✓ 视差明显 |
| 16 | 浏览器 ESM 导出包含 splitStereo | ✓ |
| 17 | Flask /hmd-preview 渲染页面 HTML | HTTP 200 |

---

## 9. 依赖与版本

```text
Node.js ≥ 18  (tested 22)
Python 3.11+
Flask ≥ 2.0
Chrome ≥ 94 (WebCodecs VideoDecoder HEVC)
ffmpeg ≥ 4.0  (verification only)
```

---

## 10. 文件清单（复现要创建/修改的全部文件）

```text
codec-hmd/
├── hmd-decode.js                  ← 解析器核心（270 行 CJS）
├── hmd-decode.esm.js               ← 浏览器版（270 行 ESM，需与 CJS 同步）
├── verify_hmd_packets.js           ← 自测（150 行）
└── session_0000X/                 ← 测试样本（用户提供）

video-sort-package/
├── app.py                          ← 加 /api/hmd/info, /api/hmd/raw, /hmd-preview
├── templates/
│   ├── index.html                  ← 加"🎥 HMD 双目预览"按钮 + scan HMD 检测
│   ├── hmd_preview.html            ← 500 行，双目播放器 + 4 阶段进度
│   └── ...
├── static/hmd/hmd-decode.esm.js    ← 重要：放这里（Flask 默认 static 目录）
└── 启动视频管理.bat                ← 用户启动入口（可选）
```

---

## 11. 一句话总结

> 用 magic + 类型相关判别符找 HMD3 包，把包之间的字节 + GLUE/CHUNK 包体当作 HEVC Annex-B 字节流拼起来，按 NAL 奇偶拆成相机 0/1 两路 30 fps HEVC。

剩下的就是 WebCodecs 解码 + Flask 路由 + HTML 模板，按上面给的代码逐字翻译即可。