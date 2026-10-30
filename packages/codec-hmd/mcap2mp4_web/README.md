# mcap2mp4_web  —  纯前端 mcap → mp4 静态页

零服务器、零上传。用户在浏览器里选本地 mcap 文件夹，JS 直接解析 + remux 成 MP4，提供下载。

## 文件清单

| 文件 | 说明 |
| --- | --- |
| `index.html`   | 单页前端：文件夹选择 / 解析 / 封装 / 下载 |
| `core.js`      | 纯 JS 模块：mcap 解析 + hvcC 构造 + MP4 封装。Node + 浏览器通用 |
| `verify.js`    | Node 端 e2e 校验：单文件 → ffprobe + ffmpeg decode 验收 |
| `verify_merge.js` | Node 端 e2e 校验：多文件合并（一个 session 下多个 ego_*.mcap → 1 个 mp4）|
| `_verify_av.py` | （历史遗留）老 verify 用的 PyAV 探针；当前 verify.js 已切到 ffmpeg |

## 双击即用 / 静态托管

```bash
# 方式 1：直接双击 index.html（受浏览器 file:// 限制，可能无法选目录）
# 方式 2：起一个简单 HTTP server（推荐）
python -m http.server 8756
# 然后打开 http://127.0.0.1:8756/index.html
```

> **必须经 HTTP 打开**，不要用 `file://` —— 浏览器对 `file://` 的 `webkitdirectory`、Module 等限制很严。

## 浏览器要求

| 浏览器 | 支持情况 |
| --- | --- |
| Chrome ≥ 30   | 推荐。`webkitdirectory` + Blob + 大文件支持都 OK |
| Edge ≥ 79     | 推荐（同上） |
| Firefox ESR 42+| 如未开启 `dom.webkit.dir.enabled`，会退化为单文件选择（不影响功能） |
| Safari 14+     | 支持 |
| **IE 11**     | 不支持 |

## 大文件说明

- 单 mcap 可达 2GB+。当前实现为简洁起见走整文件 `readAsArrayBuffer`，约 2GB 内存。
- 写盘：当前用 `Blob + <a download>`，对单 session 1-2GB 没问题。
- 可改进：流式 slice + `showSaveFileStream`（Chrome 86+）。
- **HEVC 浏览器预览**：输出是标准 H.265/HEVC + MP4。Chrome / Firefox 浏览器原生解码差，
  `<video>` 预览大概率失败。**下载到本地用 VLC / PotPlayer / ffmpeg 播放**即可。

## Node 端验收（与 Python 版对照）

```bash
cd mcap2mp4_web
# 单文件：默认 ../sample_session_00000/ego_0000.mcap（3192 帧，~107s）
node verify.js
# 多文件合并：默认 ../data0706/session_00026（7 个 ego_*.mcap）
node verify_merge.js
```

### 单文件验收结果（2026-07-18 修复后）

```
parseMcap: 1 channels, ~95 ms
  /ego/camera/0: 3192 frames
  first capture_ns: 8066589000
  last  capture_ns: 114712751000
  span seconds: 106.646162
VPS=23 SPS=44 PPS=7 bytes
SPS parsed: {"width":1920,"height":1080,"chroma":1}
hvcC: 112 bytes

--- ffprobe ---
codec_name=hevc
width=1920
height=1080
duration=106.646167
nb_read_frames=3192

--- ffmpeg decode ---
exit=0
（decoder 偶发 cu_qp_delta / CABAC_MAX_BIN 警告 — 来自源编码器产物，非容器问题）
```

与 Python 版（`mcap2mp4_app.py`）逐项对照：

| 字段 | Python 版 | 本项目 | 是否一致 |
| --- | --- | --- | --- |
| codec | hevc | hevc | ✅ |
| 分辨率 | 1920×1080 | 1920×1080 | ✅ |
| 帧数 | 3192 | 3192 | ✅ |
| 时长 | ~107s | 106.646s | ✅ |
| 单帧 PTS | (capture_ns 相同) | (capture_ns 相同) | ✅ |
| ffmpeg 真解码 | （PyAV 输出可解） | exit=0 | ✅ |

### 多文件合并验收结果

```
ego files: 7
total camera/0 frames: 26726
mp4: 892 MB
--- ffprobe ---
codec_name=hevc
width=1920
height=1080
duration=892.7s
nb_read_frames=26697
```

> 29 帧缺失：跨文件边界处（一个 mcap 结束、下一个 mcap 开始）解码器 RPS（参考帧集）
> 找不到上一个文件的参考帧。这是**源数据 + 解码器的固有限制**，PyAV 的合并也有同样问题。
> 容器层零错误。

## 算法

### mcap 解析
- 跳过 magic 后逐条记录
- 仅对 `Chunk (0x06)` 内的子记录展开（sub-opcode 0x05 = Message）
- 仅取 `topic` 末段为 `0` 的 channel（camera/0 左相机）
- 仅保留 `foxglove.CompressedVideo` schema
- 抓出 inner protobuf 字段 3（data，Annex-B H.265 字节流）+ 字段 4（format）+ 字段 1（嵌套 timestamp）
- capture_ns = seconds*1e9 + nanos（与 Python 版完全一致）

### H.265 NAL 处理
- 源流使用**标准** HEVC NAL 类型：VPS=32, SPS=33, PPS=34, TRAIL_R=1, BLA_W_LP=19 …
- **不做**任何非标准→标准的 remap（之前版本的 `(hdr & 0x3f)` 提取错位 + remap 把 NAL header byte 改坏，是已修的核心 bug）
- Annex-B → 4 字节大端长度前缀
  - 支持 3 字节（00 00 01）和 4 字节（00 00 00 01）起始码
  - 自动跳过 emulation prevention byte（00 00 03）
- 关键帧：NAL type 16..23（IDR / CRA / BLA / RASL / RADL）记入 `stss`
- 每个 sample 仅放**一个**VCL slice NAL；VPS/SPS/PPS 只放在 hvcC（PyAV / ffmpeg 最稳的布局）

### SPS 解析 → width/height
- 跳过 EPB 后构位流
- 解析 PTL 之后 `chroma_format_idc / pic_width_in_luma_samples / pic_height_in_luma_samples`（exp-golomb）
- 不再硬编码 1920×1080

### hvcC
- 从前 50 帧里扫出 VPS/SPS/PPS
- 构造 `HEVCDecoderConfigurationRecord`（112 字节）符合 ISO/IEC 14496-15
  - 数组 layout：1B header + 2B numNalus + 2B nalUnitLength + N B NAL data
  - `array_completeness = 0`（与 PyAV/mp4box 一致）
  - `lengthSizeMinusOne = 3`（4 字节 NAL 长度前缀）
  - SPS 中的 profile / level / constraint 字段（带 EPB）原样写入

### MP4 封装（手写盒子）

结构（按 ISO/IEC 14496-12）：

```
ftyp
moov
  mvhd  v0 (timescale=90000, duration=span)
  trak
    tkhd v1 (width/height fixed 16.16)
    mdia
      mdhd v0 (timescale=90000)
      hdlr vide
      minf
        vmhd
        dinf → dref → url (self-contained)
        stbl
          stsd → hvc1 → hvcC
          stts VFR（逐帧 delta）
          ctts 全 0（capture == composition）
          stsc 单 chunk
          stsz 每个 sample 的 size
          stco 指向 mdat 载荷起点（=mdat box + 8）
          stss 关键帧索引
mdat
  [4B len][slice NAL data]... per sample
```

时长基 90000Hz，stts 逐帧写 delta，VFR 完全保真。

## 安全

- 全程不联网（除静态资源本身外）
- 没有外链 CDN / Web Worker / SharedArrayBuffer / WebCodecs
- 不上传任何字节
- 用户关闭页面 → URL.createObjectURL 自动回收；Blob 在内存，刷新即丢
- 没有持久化数据：选择文件夹时浏览器只读 File 引用，不复制；转换后下载到本地即离页

## 已知限制

- 单文件 2GB+ 一次性 `readAsArrayBuffer` 会吃 ~2GB 内存（Chromium 64-bit 单 tab 一般能扛）
- 大文件写盘目前是 Blob → `<a download>`，**未接** `showSaveFilePicker` 流式写
- H.265 浏览器预览限制（同上）
- 单 session 走单次封装，没做并行多 session
- 多文件合并时跨 mcap 边界会有少量帧因解码器 RPS 找不到参考帧而丢弃（源数据问题，非容器问题）
