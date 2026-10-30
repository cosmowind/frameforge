# FEATURES — codec-hmd

> 用户视角的能力索引。每条 = 一个 user-visible 行为 + 实现位置 + 状态。
> 与 project_status.md 不同：status 是开关面板，features 是目录。

## F1. HMD 容器解析
- **行为**：给定 .hmd 文件路径，返回 HEVC 字节流 + IMU 样本 + 视频/IMU/辅助 包计数
- **实现**：`hmd-decode.js:parse(buf)`，浏览器内 inlined 在 `hmd-preview.html`
- **状态**：⚠️ 解析有 bug（包边界检测丢 99% 数据），见 error_book.md E1
- **测试**：`verify_hmd_packets.js`（待写）

## F2. HMD → MP4 CLI
- **行为**：`node hmd2mp4.js part_000.hmd` 输出 `part_000.mp4`
- **实现**：`hmd2mp4.js`，ffmpeg remux
- **状态**：✅
- **选项**：`--dedup`（去重 VPS/SPS/PPS）/ `--color`（BT.709 full range）/ `--h265`（输出 .h265）/ `--imu`（输出 _imu.json）

## F3. 浏览器内单目播放
- **行为**：双击 `hmd-preview.html`，拖入 .hmd 文件即可播放
- **实现**：`hmd-preview.html`，WebCodecs VideoDecoder + AVCC 包装
- **状态**：⚠️ 解析依赖
- **功能**：播放/暂停/前后 IDR/0.25-4× 倍速/拖动 seek

## F4. 双视频 Side-by-Side 对比
- **行为**：双击 `side-by-side.html`，拖入两个 .hmd 文件并排比较
- **实现**：`side-by-side.html`
- **状态**：✅

## F5. 打包版播放器
- **行为**：`hmd-player-all-in-one.html` 内联全部 JS，无外部依赖
- **实现**：单 HTML
- **状态**：✅
- **用途**：离线分享

## F6. 本地 HTTP 流（ffmpeg）
- **行为**：`serve.ps1` 启动 HTTP server，将 .hmd 转 mp4 流给浏览器
- **实现**：`serve.ps1`，ffmpeg subprocess
- **状态**：✅

---

## 🚧 重构中（并入 video-sort-package 后）

## F7. 双目 HMD 解析与播放
- **行为**：60 fps 帧交替立体 → 拆出左眼（30 fps）/ 右眼（30 fps）两路独立流；前端可独立播放 / 并排 / 红蓝立体
- **实现**：`hmd-decode.js` 的 `splitStereo(hevc)` 函数（按 NAL index 奇偶拆分）；前端用 2 个 `<video>` 渲染或合并为 SBS
- **状态**：✅ Task #3 + #18 完成（2026-06-16）；3 个 session 实测通过，ffprobe 验证 30 fps 1920x1080，left/right 抽帧视觉确认不同视角

## F8. HMD 视频入库（一文件夹=一视频）
- **行为**：扫描指定目录，自动发现 .hmd 文件夹（含 metadata.json）并写入 video_manager
- **实现**：`/api/hmd/scan`（video-sort-package）
- **状态**：⏳ Task #5

## F9. SD 卡 → 设备编号自动识别
- **行为**：SD 卡插入时，根据 volume serial 查 sd_cards 表得到 device_id
- **实现**：`/api/hmd/identify-device` + `device_monitor.py` watcher
- **状态**：⏳ Task #10

## F10. 录制人管理（4 维表之一）
- **行为**：维护 name/alias/phone/note；video_manager.recorder_id 外键引用
- **实现**：`/api/recorders` CRUD
- **状态**：⏳ Task #8 + #9

## F11. 设备编号管理
- **行为**：device_id / model / sn / location；sd_cards 引用
- **实现**：`/api/devices` CRUD
- **状态**：⏳ Task #8

## F12. 任务关键词 + 可录制任务
- **行为**：5 维（场景*产品*任务*工具*工序）→ keyword；keyword + 难度（1h/2h/10h）+ 序号 → task_code
- **实现**：`/api/task-keywords` + `/api/recordable-tasks` CRUD
- **状态**：⏳ Task #8 + #11

## F13. 任务时长配额预警
- **行为**：actual/planned ≥ 0.8 黄、≥ 1.0 红；任务列表标色
- **实现**：`/api/recordable-tasks/<code>/progress` + 前端渲染
- **状态**：⏳ Task #11

## F14. 命名规范自动拼接
- **行为**：保存 video_manager 行时计算建议命名：`mmdd-DevID-RecID-TaskCode`
- **实现**：`/api/video_manager` POST 时派生
- **状态**：⏳ Task #12

## F15. SD 卡自动复制 HMD
- **行为**：监听 SD 卡插入，复制 .hmd 文件夹到工作盘，删除原文件
- **实现**：`device_monitor.py` 加 hmd handler
- **状态**：⏳ Task #6（低优）

## ❌ 暂不实现

- **F16. frameforge 上传器集成** — prompt.txt 明确"先不用适配"
- **F17. 自动翻译（中英）** — video-sort-package 已删除
