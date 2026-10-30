# PROJECT STATUS — codec-hmd

> 2026-06-16 当前状态。本文件是"功能开关"面板。
> 跟 dev_plan.md 配合使用：plan 是"要做什么"，status 是"已能做到什么"。

---

## 🚦 总状态

**重构启动中**。本仓库即将被并入 video-sort-package 仓库，本文档记录重构前后的状态切换。

| 维度 | 当前 | 目标 |
|------|------|------|
| 入口 | 双击 `hmd-preview.html`（file://） | video-sort-package 启动器（`python run.py`） |
| 视频格式 | 单目 HEVC 0x5b（解析有 bug） | 双目（待探测） |
| 数据存储 | 无（HTML 临时） | SQLite（video-sort-package 内） |
| 元数据 | 无 | 录制人 / 设备编号 / 任务 / 配额 |
| 命名 | 原文件名 | `mmdd-DevID-RecID-TaskCode` |

---

## ✅ 已实现能力（重构前）

| 能力 | 文件 | 状态 | 备注 |
|------|------|------|------|
| HMD 解析（HEVC + IMU） | `hmd-decode.js` | ⚠️ 有 bug | 包边界检测丢 99% 数据 |
| HMD → MP4 转码 | `hmd2mp4.js` | ✅ | CLI 工具，ffmpeg remux |
| 单目浏览器播放 | `hmd-preview.html` | ⚠️ 解析依赖 | WebCodecs VideoDecoder |
| Side-by-side 比较 | `side-by-side.html` | ✅ | 用于两个 mp4 对比 |
| 播放器打包版 | `hmd-player-all-in-one.html` | ✅ | 单文件 HTML |

---

## 🚧 重构中能力

| 能力 | 目标 | 进度 | 阻塞 |
|------|------|------|------|
| 包边界检测修正 | 99% 数据不丢 | 探测完成，待写代码 | — |
| 双目解析 | 真实 2 路 | 待探测 | 16 |
| 单入口（Flask） | 共用 video-sort-package | 待启动 | 4 |

---

## ❌ 不实现 / 暂缓

| 项 | 原因 |
|----|------|
| frameforge 上传器 | prompt.txt 明确"先不用适配" |
| 旧 CSV 字段迁移到 SQLite 的回退路径 | prompt.txt 决策"CSV 仅导入导出"，不需要双轨 |
| SD 卡自动复制 | prompt.txt 标"低优先级" |

---

## 🔗 上游依赖

| 依赖 | 版本 | 用途 | 备注 |
|------|------|------|------|
| Node.js | ≥ 18 | hmd-decode.js 运行环境 | CLI 工具 |
| 浏览器 | Chrome 94+ / Edge 88+ | WebCodecs VideoDecoder | hmd-preview.html |
| ffmpeg / ffprobe | latest | hmd → mp4 转码 | 系统 PATH |
| Python | 3.x | video-sort-package 后端 | 重构后主语言 |
| Flask | latest | video-sort-package Web | 重构后 |

---

## 📁 当前文件清单

| 文件 | 用途 | 状态 |
|------|------|------|
| `prompt.txt` | 用户原始需求 | 📌 不动 |
| `wcs-manifest.yaml` | WCS 中央索引 | 🆕 2026-06-16 |
| `docs/dev_plan.md` | 路线图 | 🆕 2026-06-16 |
| `docs/project_status.md` | 本文件 | 🆕 2026-06-16 |
| `docs/structure.md` | 目录映射 | 🆕 2026-06-16 |
| `docs/features.md` | 能力索引 | 🆕 2026-06-16 |
| `docs/dev_log.md` | 实现记录 | 🆕 2026-06-16 |
| `docs/error_book.md` | bug 库 | 🆕 2026-06-16 |
| `docs/CODING_STANDARDS.md` | 编码规范 | 🆕 2026-06-16 |
| `docs/workflow.md` | 流程协议 | 🆕 2026-06-16 |
| `hmd-decode.js` | HMD 容器解析 | ⚠️ 待修正 |
| `hmd-decode.esm.js` | ES module 版本 | ⚠️ 同步修正 |
| `hmd2mp4.js` | HMD → MP4 CLI | ✅ |
| `hmd-preview.html` | 单目浏览器播放 | ⚠️ 依赖修正后解析 |
| `hmd-player.html` | 旧版播放器 | 📦 历史 |
| `hmd-player-all-in-one.html` | 打包版播放器 | ✅ |
| `side-by-side.html` | 双视频对比 | ✅ |
| `serve.ps1` | 本地 HTTP 服务器（ffmpeg 流） | ✅ |
| `session_00000/`, `session_00001/`, `session_00002/` | 样本 HMD 数据 | 📌 不动 |
| `mp4-muxer.mjs` | mp4-muxer 库 | ✅ 工具库 |

---

## 🛡 兼容性矩阵（重构后）

| 旧功能 | 新位置 | 兼容性 |
|--------|--------|--------|
| 双击 `hmd-preview.html` | `python run.py` 后访问 `/hmd?path=…` | ⚠️ 入口变更 |
| CLI: `node hmd2mp4.js …` | `python -m hmd2mp4 …` | ⚠️ 命令变更 |
| JS API: `require('./hmd-decode')` | ESM import from `/static/hmd/hmd-decode.esm.js` | ⚠️ 路径变更 |
