# Project Status — video-sort-package

> 2026-06-19 当前状态。AI 接手时第一眼读 wcs-manifest.yaml + 本文件。

---

## 🚦 总状态

**生产可用 + 重构演进中**。Flask 单进程 + 单页前端 + CSV 存储；2026-06-16~17 集成 HMD 双目预览到主页面。

| 维度 | 当前 | 备注 |
|---|---|---|
| 入口 | `python app.py` → http://localhost:5000 | 也可 `python run.py` 或 `启动视频管理.bat` |
| 视频格式 | MP4（FFprobe） + HMD（WebCodecs HEVC） | 单目流；真双目=两独立设备的两个 session |
| 数据存储 | `video_manager.csv`（20 列）+ `config.json` | 未来可迁 SQLite/MySQL（prompt 标记） |
| 元数据 | 录制人 / 设备编号 / 任务 ID / 时长 | 部分字段已加，CSV 写入兼容 13→20 |
| 命名 | 原文件路径；自动重命名待 PR | mmdd-DevID-RecID-TaskCode 模式 |
| 上传器 | 旧逻辑保留（不主动适配） | 等待 frameforge 后台端口规范 |
| WebCodecs | 必需 Edge 88+ / Chrome 94+ | Linux 无系统 HEVC 解码器 |

---

## ✅ 已实现能力（2026-06-19 快照）

### 后端（app.py，~1850 行）

| 能力 | 端点 | 状态 |
|---|---|---|
| 单页 + 配置读写（`/` no-cache） | `GET /`, `GET/POST /api/config` | ✅ |
| 表格数据 + 保存 | `GET /api/data`, `POST /api/save` | ✅ |
| 扫描 mp4/HMD（scope=current） | `POST /api/scan` | ✅ |
| 视频流（Range） | `GET /api/video` | ✅ |
| 目录选择对话框 | `POST /api/pick-directory` | ✅ |
| HMD session 扫描 | `POST /api/hmd/scan` | ✅ |
| HMD session 元数据 | `GET /api/hmd/info` | ✅ |
| HMD 部分文件流 | `GET /api/hmd/raw` | ✅ |
| HMD 单文件流（API 兼容） | `GET /api/hmd/file` | ✅ |
| HMD duration 回填 | `POST /api/hmd/duration` | ✅ |
| HMD 注册为 CSV 行 | `POST /api/hmd/register` | ✅ |
| 独立 HMD 预览页 | `GET /hmd-preview` | ✅ |
| 维表 CRUD 通用端点 | `GET/POST/DELETE /api/dim/<name>` | ✅ |
| 任务时长配额聚合 | `GET /api/dim/tasks/with-usage` | ✅ |
| 缩略图（MP4 + HMD + smart-seek + luma） | `GET /api/thumbnail` | ✅ |
| 缩略图批量预热 | `POST /api/thumbnail/warm` | ✅ |
| 上传脚本生成 + 执行 | `/api/upload-*` | ⚠️ 旧逻辑，未适配 |
| 数据迁移一次性 | `/api/fix-dates`, `/api/fix-empty-scan-dates` | ✅ |

### 前端（templates/index.html，~2400 行）

| 能力 | 状态 |
|---|---|
| 列控制（chip / 拖宽 / 拖序） | ✅ |
| 多列排序栈 | ✅ |
| 行预览（MP4 单视频） | ✅ |
| 行预览（HMD 双 canvas 内嵌） | ✅ |
| 1× / 5× / 10× / 16× 速度按钮 | ✅ |
| IDR-aware seek | ✅ |
| WebCodecs HEVC 解码 | ✅ |
| splitStereo 双目 | ✅ |
| 中英自动补全 | ✅ |
| 批量上传 + 进度终端 | ✅ |
| 导出 TXT | ✅ |
| 撤销 Ctrl+Z | ✅ |
| 5 tab 页面框架（视频/录入员/SD卡/任务/设置） | ✅ |
| 维表 CRUD UI（3 个页面） | ✅ |
| `select-dimension:` 列类型（recorder_id/device_id/task_id 已升级） | ✅ |
| 任务时长配额进度条（5 档色） | ✅ |
| recorder 自动收录（首次 GET recorders） | ✅ |
| **维表主键连续改名保留 original_key** | ✅ |
| **画廊视图（缩略图 + 全屏 + 多选 + 筛选）** | ✅ |
| **Build 标记戳（console 首行）** | ✅ |

### 离线工具

| 能力 | 文件 | 状态 |
|---|---|---|
| HMD 解析器（CJS） | `hmd-decode.js` | ✅ |
| HMD 解析器（ESM） | `static/hmd/hmd-decode.esm.js` | ✅ |
| WebCodecs 播放核心 | `static/hmd/hmd-player-core.js` | ✅ |
| HMD → MP4 命令行 | `hmd2mp4.js` | ✅ |
| USB 监听 + 自动复制 | `device_monitor.py` | ✅（mp4 only，未含 .hmd） |
| 视频旋转 + 分割 | `rotate_video.py` / `split_video.py` | ✅ |

---

## 🚧 待办（按优先级）

详见 `docs/dev_plan.md`。摘要：
- 画廊批量操作（多选已实现，批量标记/删除未接）
- HMD 端到端：扫描 → 注册 → 字段填写 → 上传
- SD 卡卷标 → 设备编号自动识别
- 视频自动重命名（mmdd-DevID-RecID-TaskCode）
- 深度上传器（适配 frameforge 后台端口）

---

## 🔗 上游依赖

| 依赖 | 版本 | 用途 | 备注 |
|---|---|---|---|
| Python | 3.11+ | 后端 | 已验证 |
| Flask | latest | Web 框架 | pip install flask |
| FFmpeg / FFprobe | latest | mp4 旋转/分割/时长 | 系统 PATH |
| 浏览器 | Edge 88+ / Chrome 94+ | WebCodecs HEVC | HMD 必需 |
| Node.js | 18+ | `verify_hmd_packets.js` | 离线测试用 |

---

## 📁 文件清单

| 文件 | 用途 | 状态 |
|---|---|---|
| `app.py` | Flask 后端 | ✅ |
| `templates/index.html` | 单页前端 | ✅ |
| `templates/hmd_preview.html` | 独立 HMD 预览页 | ✅ |
| `static/hmd/hmd-decode.esm.js` | HMD ESM 解析 | ✅ |
| `static/hmd/hmd-player-core.js` | WebCodecs 封装 | ✅ |
| `config.json` | 列定义 + 扫描目录 | ✅ |
| `video_manager.csv` | 主数据（20 列） | ✅ |
| `device_monitor.py` | USB 监听 | ⚠️ mp4 only |
| `vendor-upload-pkg/` | 上传脚本（vendor） | ✅ |
| `csv_backups/` | 自动备份（10 份） | ✅ |
| `wcs-manifest.yaml` | WCS 中央索引 | 🆕 |

---

## 🛡 兼容性矩阵

| 旧行为 | 新位置 | 兼容 |
|---|---|---|
| 双击 hmd-preview.html | `/hmd-preview?path=...` | ✅ 仍可用 |
| `node hmd2mp4.js` | 不变 | ✅ |
| `python hmd_decompile.py` | 已移除 | ⚠️ |
| 13 列 CSV | 20 列（向后兼容） | ✅ |
| 旧扫描（保留历史） | `scope=all` 参数 | ✅ |
| 客户端 video.seek 抓帧 | 服务端 `/api/thumbnail` | ✅（更稳定） |

---

## ⚠️ 已知限制

1. HMD duration 仅靠客户端首次打开时回填，依赖浏览器
2. WebCodecs 在 Linux 上不可用（无系统 HEVC 解码器）
3. 并排第二 session 暂未实现（E2 真双目场景）
4. 上传器未适配 frameforge 后台端口（明确暂缓）
5. 没有单元测试，靠 `verify_pages.py` 集成脚本验证
6. Flask debug 模式 reloader 子进程残留（手动 kill PID 解决）
7. 浏览器缓存陷阱：单文件 SPA 必须 `Cache-Control: no-cache`，否则改 templates 不生效（E9）
8. 缩略图首次生成走 ffmpeg 约 0.5-2s，未做 lazy warm 预热