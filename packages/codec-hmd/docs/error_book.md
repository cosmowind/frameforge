# ERROR BOOK — codec-hmd

> 已知 bug / 失败案例 / 根因 / 修复 / 预防。每次填新条目都按 schema 写。

## E1. ✅ FIXED — HMD 包边界检测丢 99% 数据

| 字段 | 内容 |
|------|------|
| 发现时间 | 2026-06-16 |
| 修复时间 | 2026-06-16 |
| 报告者 | wcs self-audit |
| 影响 | HMD 解析得到的视频 NAL 数远小于真实包数；duration / IMU / 帧数全部偏少 |
| 复现 | 旧：`node verify_hmd_packets.js` → 0/12 通过（hevcBytes=0, hevcStartCodes=0） |
| 期望 | 12/12 通过，HEVC 流 256MB，19400 个 start code |
| 根因 | 旧 `findPackets` 用 `p += total` 跳到下一包，但 `total = sizeField + 8` 而 `sizeField` 是把 type 字节当 u32 LE 读。`total = TT + 8` 远小于真实包大小，导致步进错误。**HMD 容器没有 size 字段**，包大小只能硬编码：IMU=97 字节，glue header=8 字节 |
| 错误尝试 | 1) "3 字节零判别"扫出 58913 候选，但 41286 是 HEVC payload 里的假 HMD3；2) 距离法（next-cur）会把 HEVC 间隙吞到上一包 |
| 正确方案 | 1) 用 3 字节零判别 + type ∈ {0x59, 0x5a} 双重过滤；2) `total` 硬编码（IMU=97, glue=8）；3) parse 循环按"真实包占用字节"步进 cursor，间隙归 HEVC |
| 验证 | `node verify_hmd_packets.js` 12/12 通过；hevc(268418371) + hmd3(13440) = 268431811 = file_size 字节数对得上；588 IDR 帧 |
| 预防 | 1) hmd-decode.js 顶部加注释明确"容器无 size 字段"；2) verify_hmd_packets.js 包含字节数对账断言；3) 改 API 时保留 `parse/findPackets` 函数签名 |
| 关联 | Task #15 ✅ |

## E2. ✅ FIXED — hmd-decode.js 注释中 type 字节与实测不符

| 字段 | 内容 |
|------|------|
| 影响 | 注释误导后续维护者；包类型识别写错就解析错 |
| 详情 | 旧注释写"0x89 (auxiliary), 0x91 (HEVC video)"，实测只有 0x59 (IMU) 和 0x5a (glue) 两种真实包类型；其他 76k 个 HMD3-like 序列都是 HEVC payload 噪声 |
| 根因 | 早期 spec 不完整，按猜测写注释 |
| 修复 | 改注释为实测值（IMU=0x59, glue=0x5a），用 KNOWN_PACKET_TYPES 集合显式声明 |
| 关联 | E1 |

## E3. (空) — 等待发现新问题

> 新 bug 发现时按 E1 格式追加。不要删除已修复的条目（加 ✅ FIXED 标记即可）

## E4. ✅ FIXED — HMD 双目结构推测错误（最终结论：60fps 帧交替）

| 字段 | 内容 |
|------|------|
| 发现时间 | 2026-06-16 |
| 修复时间 | 2026-06-16（用户反馈 + 抽帧验证） |
| 影响 | Task #16 推测"两个独立 .hmd 文件"是单目方案，错过真实结构 |
| 期望 | 单个 .hmd 含两路 HEVC（SBS / TB / 帧交替 / 独立双 SPS） |
| 实测 | **60 fps 帧交替立体**：metadata `cameras:[{0:...},{1:...}]` 都是 1920x1080@30fps；HMD 文件里两条流被交错成 60 fps（30 fps 相机 0 + 30 fps 相机 1，frame n=0 是左眼，n=1 是右眼） |
| 验证 | 抽帧 seq_01 vs seq_02 视觉确认：同一场景不同角度（计算器、纸张、橙钳位置都不同）；splitStereo() 后 left/right 帧数各 11,061/11,060，ffprobe 各自报 30 fps 1920x1080 |
| 根因 | Task #16 只看 SPS 1920x1080 没注意帧率 60 fps；也没注意到 metadata cameras[1] 是真实流（不是占位） |
| 修复 | 1) `hmd-decode.js` 加 `splitStereo(hevc)` 函数，按 NAL index 奇偶拆分；2) verify_hmd_packets.js 加 4 项 splitStereo 测试；3) docs 更新；4) memory 存 splitStereo 经验 |
| 关联 | Task #3 ✅、Task #18 ✅、Task #16 ✅（结论被用户修正） |
