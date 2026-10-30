# codec-hmd

> ⚠️ **本仓库正在重构并入 `video-sort-package`**（2026-06 决策）。
> 重构完成前，本仓库只保留 HMD 解析/预览/转码相关代码，新功能（数据库、维表、配额、命名）到 video-sort-package 那边开发。

## 快速开始

### 浏览器内单目播放（当前还能用）

```bash
# 直接双击
hmd-preview.html
```

> ⚠️ hmd-decode.js 解析有 bug（见 `docs/error_book.md` E1），播放可能丢帧。

### 命令行 HMD → MP4

```bash
node hmd2mp4.js session_00000/part_000.hmd
# 输出 session_00000/part_000.mp4

node hmd2mp4.js --dedup --color --h265 --imu session_00000/part_000.hmd
# 去重参数集 + BT.709 + 原始 h265 + IMU JSON
```

### Node API

```js
const fs = require('fs');
const { parse } = require('./hmd-decode.js');
const buf = new Uint8Array(fs.readFileSync('part_000.hmd'));
const r = await parse(buf);
console.log(r.video[0].hevc);  // HEVC 字节流
console.log(r.imu.length);     // IMU 样本数
```

## 文档导航

| 想了解… | 读 |
|---------|-----|
| 当前能做什么 / 不能做什么 | [docs/project_status.md](docs/project_status.md) |
| 接下来要做什么 | [docs/dev_plan.md](docs/dev_plan.md) |
| 文件 / 模块怎么组织 | [docs/structure.md](docs/structure.md) |
| 用户视角能力清单 | [docs/features.md](docs/features.md) |
| 已知 bug | [docs/error_book.md](docs/error_book.md) |
| 编码规范 | [docs/CODING_STANDARDS.md](docs/CODING_STANDARDS.md) |
| 执行流程 | [docs/workflow.md](docs/workflow.md) |
| 实现记录 | [docs/dev_log.md](docs/dev_log.md) |
| 用户原始需求 | [prompt.txt](prompt.txt) |

## 依赖

- Node.js ≥ 18
- ffmpeg / ffprobe（系统 PATH）
- 浏览器：Chrome 94+ / Edge 88+（WebCodecs VideoDecoder）

## 仓库状态

| 状态 | 说明 |
|------|------|
| 维护中 | hmd-decode.js 解析 bug 修复 |
| 维护中 | 真实双目结构探测 |
| 暂缓 | 双目 UI |
| 计划中 | 整体并入 video-sort-package |

详见 [docs/dev_plan.md](docs/dev_plan.md)。
