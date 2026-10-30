# Dev Plan — video-sort-package

> 路线图 + 进行中 + 待办。完成任务或调整计划时同步更新。

---

## 🎯 总体目标

构建一站式 HMD 视频接入管理工具：扫描 → 预览 → 元数据 → 上传。
底层暂用 CSV；2026 Q3 评估迁移到 SQLite。

---

## 📋 任务状态

| 状态 | 含义 |
|---|---|
| 🔵 进行中 | 当前 PR 正在做 |
| ✅ 已完成 | 已验证 + 文档同步 |
| ⏸ 暂缓 | 明确暂停（等上游规范） |
| ❌ 待办 | 排队中 |

---

## ✅ 已完成（2026-06）

- [x] **PR 1.1**: 把 `hmd-decode.esm.js` 从 codec-hmd 复制到 `static/hmd/`
- [x] **PR 1.2**: 提取 `hmd-player-core.js`（WebCodecs 封装）
- [x] **PR 1.3**: app.py 加 `/api/hmd/scan`、`/info`、`/raw`、`/file`、`/duration`、`/register`
- [x] **PR 1.4**: `/hmd-preview` 独立页面（带 splitStereo + 进度 UI）
- [x] **PR 2.1**: HMD 解析核心 + 单流预览（独立页）
- [x] **PR 3.1**: IDR keyframe required 修复
- [x] **PR 3.2**: HMD 预览嵌入主页面
- [x] **PR 4.1**: 表格预览按钮支持 HMD（合并入口）
- [x] **PR 4.2**: 扫描目录 scope=current（不再扩散到其它路径）
- [x] **PR 4.3**: 播放速度 1× / 5× / 10× / 16× 按钮
- [x] **PR 5.1**: WCS v2.0 文档基线建立（manifest + 10 docs）
- [x] **PR 6.1**: 维表主键连续改名保留 original_key（避免 lx→…→op02 丢数据）
- [x] **PR 6.2**: 画廊缩略图服务端化（HMD + MP4 + smart-seek + luma 兜底）
- [x] **PR 6.3**: `/` 路由 no-cache + build 标记戳（防浏览器缓存陷阱）
- [x] **PR 6.4**: `pack.ps1` 递归排除（zip 1.4GB → 340KB）

---

## 🔵 进行中

暂无

---

## ⏸ 暂缓（等上游规范）

- [ ] **深度上传器适配**：等 frameforge 后台端口规范（prompt.txt 明确"先不用适配"）
- [ ] **CSV → SQLite/MySQL 迁移**：等数据规模突破 1000 行 + 复杂查询需求
- [ ] **自动重命名 mmdd-DevID-RecID-TaskCode**：等维表系统稳定后做

---

## ❌ 待办（按优先级）

### P0 — 立即做

- [x] **维表 CRUD 端点 + dialog**：recorders / sd_cards / tasks 三个 CSV
  - `/api/dim/<name>` 通用 GET/POST
  - `_atomic_write` 抽取（10 份备份 + os.replace）复用
  - 维表管理 dialog（3 tabs + 进度条）
  - 预估：1 PR
- [x] **recorder 字段 → select-dimension**：从 recorders.csv 取值
  - 配 `dimCache` 预加载
  - 兼容无匹配项时回退 `<input>`

### P1 — 重要

- [x] **任务表 + 时长配额**：
  - `tasks.csv`（场景*产品*任务*工具*工序 + difficulty + quota_min）
  - `/api/dim/tasks/with-usage` 聚合（实时算已用秒数）
  - 进度条 5 档色（绿/蓝/黄/红/灰）
  - task_id 命名规则校验 `[a-z]+_[a-z]+_[a-z]+_\d{3}`
- [ ] **SD 卡 → 设备编号自动识别**：
  - `device_monitor.py` 加 `_get_volume_serial`（Win32 API）
  - 复制 .hmd 时查 `sd_cards.csv` 填 device_id
- [ ] **device_monitor.py 扩 .hmd 支持**：file_extensions 加 `.hmd`，复制 session 文件夹而非单文件

### P2 — 后续 PR

- [x] **画廊视图**（PR 6.2）：
  - 缩略图（服务端 ffmpeg 截帧 + 缓存；HMD 用 left.mp4，MP4 用直接路径）
  - CSS grid 4-6 列自适应
  - 点击 → 全屏 overlay（MP4 走 `<video>`，HMD 走 splitStereo 双 canvas）
  - 左右键切下一个 / Esc 退出
  - 筛选（device / recorder / task / uploaded）
  - 多选（Shift 区间 / Ctrl 切换）
  - 详见 features.md "画廊视图" 章节
- [ ] **画廊批量操作**：批量标记上传、批量删除（多选已实现，批量操作未接）

### P3 — 长期

- [ ] **CSV → SQLite 迁移**：评估后端性能 + 查询复杂度
- [ ] **HEVC 帧率自适应**：从 SPS 的 `vui_parameters` 解析真实 fps（当前硬编码 30）
- [ ] **Linux 兼容方案**：ffmpeg.wasm 后端转码回退（WebCodecs 在 Linux 不可用）
- [ ] **hmd-preview 性能优化**：大文件（>300MB）做 chunked loading

---

## 📊 风险与依赖

| 风险 | 缓解 |
|---|---|
| 浏览器不支持 WebCodecs | 启动时检测，禁用 HMD 按钮 + tooltip |
| HMD duration 不可靠（metadata.frame_counts 为空） | 客户端首次打开时回填；服务端兜底用 part_000 头切片 |
| Flask debug reloader 子进程残留 | 已知问题，运维时手动 kill PID |
| 并排第二 session 内存翻倍 | 按需加载（点"并排"才 fetch） |
| 上传器适配卡住 frameforge 端口规范 | 暂缓，明确 prompt |

---

## 🎯 里程碑

- **M1（已完成）**：HMD 集成 + 单流预览 + IDR fix（2026-06-16~17）
- **M2（已完成）**：维表系统 + 任务配额 + select-dimension 升级（2026-06-17）
- **M3（已完成）**：画廊视图服务端化 + 浏览器缓存修复（2026-06-19）
- **M4（计划中）**：画廊批量操作 + 自动重命名（预计 1-2 周）
- **M5（远期）**：SQLite 迁移 + Linux 兼容（按需）