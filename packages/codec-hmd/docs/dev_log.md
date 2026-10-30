# DEV LOG — codec-hmd

> 实现记录 / 验证证据 / 回顾。事实记录，不是聊天记录。

## 2026-06-16 — 重构启动

### 启动
- 读 `wcs-manifest.yaml` 后识别任务类型 = `new_feature + bug_fix + refactor`
- 按 task_mapping 加载 docs
- 读完发现 codec-hmd 项目原本无任何 WCS 文档，全部新建

### 决策（写入 docs/dev_plan.md）
- 整体并入 video-sort-package（用户拍板）
- 存储选 SQLite，CSV 仅导入导出（推翻 prompt.txt "暂定 CSV"）
- 双目方案：用户拍板"两条独立 HEVC 流"——但实测 session_00000/part_000.hmd 只有一个连续 HEVC 流，必须先探测（Task #16）再实现

### WCS 基线文档创建
- `wcs-manifest.yaml` + 9 个 docs/* + `README.md`

### Task #15 ✅ FIXED — hmd-decode.js 包边界检测

**问题**：原 `findPackets` 用 `p += total` 跳到下一包，但 `total` 把 type 字节当 u32 LE 读（= type），`total = type + 8` 远小于真实包大小。

**根因**：HMD 容器**没有 size 字段**。包大小只能硬编码：IMU=97 字节（固定），glue=8 字节（仅 header 已知，payload 大小未知）。

**修复**（hmd-decode.js + hmd-decode.esm.js）：
1. 用 3 字节零判别 + type ∈ {0x59, 0x5a} 双重过滤真实包
2. 排除 76,541 个 HEVC payload 里的伪 HMD3
3. parse 循环按"真实包占用字节"步进 cursor，间隙归 HEVC

**验证**（verify_hmd_packets.js 12/12 通过）：
- 256 真实包（128 IMU + 128 glue）
- HEVC 流 256MB，19,400 start codes
- hevc(268418371) + umi3(13440) = file_size(268431811) 字节数对账通过
- 588 IDR 帧匹配 32min × 30fps / GOP

**回顾**：
- 原代码"用 size 字段算下一包 offset" 的思路从根上就是错的
- 正确做法是"先枚举真实包 → 把间隙当 HEVC"
- 后续移植到 video-sort-package 时保留此算法，API 兼容

### 任务清单创建
- 14 个任务 + 2 个新增（#15 解析修正 / #16 双目探测）

### Task #3 + #18 ✅ COMPLETED — splitStereo 60fps 帧流拆左右

**用户反馈**：每个 session 是一个独立视频，.hmd 被切成多个 part；且 metadata cameras 数组是真实双相机（不是占位），HMD 文件里**两条相机流被交错成 60 fps 帧序列**。

**实测验证**（抽帧 + 拆分后对比）：
- session_00000: 22,121 帧 @ 30 fps 交错 → splitStereo → 11,061 left + 11,060 right @ 30 fps
- session_00001: 15,047 帧 → 7,524 left + 7,523 right
- session_00002: 48,195 帧 → 24,098 left + 24,097 right
- 抽 seq_01/02 视觉确认：同一桌面场景不同角度（计算器、橙钳、纸张位置都不同）
- ffprobe 验证：left/right 各自报 HEVC 1920x1080 30 fps

**实现**（hmd-decode.js 加 `splitStereo`）：
- 入参：parse() 返回的单 HEVC 流（60 fps 帧交替）
- 处理：splitNals() 拆 NAL，param set (VPS/SPS/PPS) 双写，frame NAL 按 index 奇偶分流
- 出参：{ left, right, stats: { leftFrames, rightFrames, totalFrames } }
- 实际录制时长：22,121 / 60 / 2 ≈ 6.14 min（不是 metadata 的 32 min）

**回顾**：
- Task #16 subagent 错过 60 fps 帧交错是因为只看了 SPS 没算帧率
- 用户"通过 live preview 可以看到两个画面"是双相机流被交错为 60 fps 序列的强证据
- splitStereo 实现后，前端可以分别用 2 个 `<video>` 渲染 left/right，或合并为 SBS 1920x1080 side-by-side

**3 个 session 实测数据**：
| Session | Parts | Total MB | Frames | Left | Right | Duration |
|---------|-------|----------|--------|------|-------|----------|
| 00000   | 2     | 312.1    | 22,121 | 11,061 | 11,060 | 6.14 min |
| 00001   | 2     | 260.0    | 15,047 | 7,524 | 7,523 | 4.18 min |
| 00002   | 3     | 744.8    | 48,195 | 24,098 | 24,097 | 13.4 min |

**待办（下一步）**：
- 启动 Task #4 移植到 video-sort-package（Flask + Vue）
- 启动 Task #5 自动扫描 / Task #7 元数据 / Task #8 SQLite 表 / Task #11 配额 / Task #12 命名
- 启动 Task #14 文档同步

---

> 后续每完成一个任务，追加一条带日期的小节。完成时记录：实现位置、验证方法、结果、回顾。
