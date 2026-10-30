# DEV PLAN — codec-hmd → 并入 video-sort-package

> **2026-06-16** 重构启动。prompt.txt 提的"hmd 远不如预期 + 与 video-sort-package 合并"是一次大重构，不是小修。
> 当前文件状态由 `.claude/` 上下文捕获。本文件是路线图 + 任务状态 + 决策记录。

---

## 🎯 重构目标（prompt.txt 拆解）

| # | 目标 | 优先级 | 状态 |
|---|------|--------|------|
| G1 | HMD 解析升级为双目 | 高 | 🔍 探测中 |
| G2 | HMD 预览并入 video-sort-package（Flask 单入口） | 高 | 待启动 |
| G3 | 5 张 CSV 维表：recorders / devices / sd_cards / task_keywords / recordable_tasks | 高 | 待启动 |
| G4 | 录制人字段从 free-text 升级为单选（数据来自 recorders） | 高 | 待启动 |
| G5 | SD 卡自动识别设备编号（volume serial → device_id） | 中 | 待启动 |
| G6 | 可录制任务 + 时长配额（1h / 2h / 10h） | 高 | 待启动 |
| G7 | 命名规范：mmdd-设备编号-数采员id-任务关键词 | 高 | 待启动 |
| G8 | 自动扫描 HMD 视频目录（一文件夹 = 一视频） | 高 | 待启动 |
| G9 | SD 卡自动复制 HMD 到工作盘 | 低 | 排后 |
| G10 | HMD 元数据（时长、创建时间、metadata.json）写入 CSV | 高 | 待启动 |
| G11 | 上传器适配 frameforge 后台 | **暂缓** | prompt.txt 明确说先不动 |

---

## 🚦 决策记录（2026-06-16）

| 决策项 | 选择 | 反方案 | 理由 |
|--------|------|--------|------|
| 子系统边界 | **整体并入 video-sort-package** | 双仓并存 / 子目录 | 单入口 / 共用 CSV / 共用启动器 |
| 存储介质 | **SQLite**（CSV 仅导入导出） | 纯 CSV + DAL 抽象 | 5+ 表的 join / 事务 / 索引；DAL 抽象也能换但工作量更大 |
| 双目方案 | **两条独立 HEVC 流**（按用户拍板） | SBS / 上下分 / 帧交替 | 待 Task #16 探测验证后再定具体实现 |
| SD 卡自动化 | **低优先级** | 优先做 | prompt.txt 明确"低优先级" |

---

## 📋 任务清单

> 序号 = Task ID。状态：`🔍 探测中` `⏳ 待启动` `🚧 进行中` `✅ 完成` `🚫 阻塞`。
> 完整描述见 `.claude/.../tasks/<id>.json`（harness 维护）。

| ID | 任务 | 状态 | 阻塞于 |
|----|------|------|--------|
| 1  | WCS 引导：建立 wcs-manifest 与基线文档 | 🚧 进行中 | — |
| 2  | 需求拆解：与 video-sort-package 的子系统边界 | ✅ 完成 | — |
| 15 | **修正 hmd-decode.js：当前包边界检测丢 99% 数据** | 🚧 进行中 | — |
| 16 | **真实双目结构探测** | 🔍 探测中 | — |
| 3  | HMD 双目解析：把单 HEVC 拆为左右眼两路 | ⏳ 待启动 | 15, 16 |
| 4  | 将 HMD 预览/解析移植到 video-sort-package 的 templates/ | ⏳ 待启动 | 3, 2 |
| 5  | 新扫描：可指定目标文件夹，自动收录 HMD 视频（一文件夹=一视频） | ⏳ 待启动 | 2, 3 |
| 6  | 新扫描：从 SD 卡自动复制 HMD 到工作盘 | ⏳ 低优 | 2 |
| 7  | 时长/创建时间等元数据记录 | ⏳ 待启动 | 5 |
| 8  | CSV 表结构升级：录制人/设备编号/任务关键词/可录制任务四张表 | ⏳ 待启动 | 5 |
| 9  | 录制人字段升级为单选框 | ⏳ 待启动 | 8 |
| 10 | SD 卡 → 设备编号 自动识别 | ⏳ 待启动 | 8, 5 |
| 11 | 可录制任务管理 + 时长配额 | ⏳ 待启动 | 8, 7 |
| 12 | 命名规范：mmdd-设备编号-数采员id-任务关键词 | ⏳ 待启动 | 9, 10, 11 |
| 13 | 端到端验证：扫描 → 入库 → 配额 → 命名 | ⏳ 待启动 | 12, 5, 7 |
| 14 | 文档与代码同步 | ⏳ 待启动 | 13 |

> ⚠️ 决策变更影响：
> 1. **存储选 SQLite** → Task #8 标题要改（"四张 CSV 表" → "四张 SQLite 表 + 导入导出 CSV 入口"），原 prompt.txt 说"暂定 CSV"被推翻
> 2. **整体并入 video-sort-package** → codec-hmd 仓库的 docs/ 在并入完成后转入历史；codec-hmd 仓库本身会被打 deprecated 标签

---

## 🔁 双目探测：必做先行任务

在动手写代码前，必须先用 ffprobe + node 脚本确认 HMD 真实结构：

```
实验 1：ffprobe 看 extracted.mp4
  ffprobe -show_streams session_00000/extracted.mp4
  ffprobe -show_packets session_00000/extracted.mp4 | head -20
  → 期望：width/height 是 1920x1080 还是 3840x1080？
  → 期望：PTS 间隔是否规律 30fps？

实验 2：写 verify_hmd_stereo.js
  - 修正后的 parseUmi() 解析 session_00000/part_000.hmd
  - 抽 0x5b 全部 NAL，统计 IDR 周期
  - 抽 0x5b 第 1 帧的 SPS，看 pic_width_in_luma_samples
  - 抽 0x5b 第 1 帧 decoded 后的 raw 像素，看是否 3840x1080

实验 3：联系 Galaxea 拿容器规范
  - 当前注释里说 "0x89, 0x90 auxiliary" 但实测 type 是 0x5a, 0x5b
  - 注释与实际不符 → 找官方确认
```

根据探测结果决定：
- 真实 SBS：实现成"每帧左半/右半切换播放"
- 真实双流：拆分两个 0x5b 帧到两路
- 真实帧交替：按 PTS 奇偶切分

---

## 🛠 执行顺序（按依赖）

```
[1 WCS 引导] ─────────────────────────────┐
[15 修正解析] ─┐                            │
[16 双目探测] ─┤                            │
              ├→ [3 双目解析] ─┐            │
[5 自动扫描] ──┤                ├→ [7 元数据] │
              │                │            ├→ [8 4 张维表] ─┐
              │                │            │                ├→ [9 单选]
              │                │            │                ├→ [10 SD卡]
              │                │            │                ├→ [11 配额]
              │                │            │                └→ [12 命名]
              │                │            │                       │
[4 移植] ─────┘                │            │                       │
                               │            │                       ↓
                               └────────────┴──────────→ [13 端到端] → [14 文档]
```

---

## 📁 关键文件归属（迁移后）

| 文件 | 当前位置 | 迁移后位置 |
|------|----------|------------|
| `hmd-decode.js` | codec-hmd/ | video-sort-package/templates/static/hmd/hmd-decode.js |
| `hmd-preview.html` | codec-hmd/ | video-sort-package/templates/hmd_preview.html |
| `hmd2mp4.js` | codec-hmd/ | video-sort-package/tools/hmd2mp4.js |
| `side-by-side.html` | codec-hmd/ | video-sort-package/templates/static/hmd/side-by-side.html |
| `session_*/` | codec-hmd/（样本） | video-sort-package/test_samples/ |
| `video_manager.csv` | video-sort-package/ | 不变，schema 升级 |
| `recorders.csv` 等 | （新建） | video-sort-package/ |
| `verify_*.js/.py` | video-sort-package/ | 不变，新增 `verify_hmd_*.js/.py` |

---

## 🧪 验证清单

| # | 测试 | 状态 |
|---|------|------|
| V1 | hmd-decode.js 修正后能正确解析 3 个 session 的 part_000.hmd | ⏳ |
| V2 | extracted.mp4 帧数 / 时长 与 hmd-decode 输出一致 | ⏳ |
| V3 | 双目渲染：左右眼两路可单独 / 并排 / 红蓝立体播放 | ⏳ |
| V4 | /api/hmd/scan 扫出 session_00000/0001/0002 共 3 行 | ⏳ |
| V5 | duration 累加正确（多 part 求和） | ⏳ |
| V6 | recorders / devices / sd_cards / task_keywords / recordable_tasks CRUD | ⏳ |
| V7 | SD 卡 → device_id 自动识别 | ⏳ |
| V8 | 配额标色：<0.8 绿 / 0.8-1.0 黄 / ≥1.0 红 | ⏳ |
| V9 | 命名建议：mmdd-D02-LX01-P2G1-2-INS-RG-WL | ⏳ |
| V10 | 端到端：扫描 → 入库 → 配额 → 命名 全流程 | ⏳ |

---

## 🔑 关键代码位置（待更新）

> 待代码动手后回填

```
hmd-decode.js:L47 findPackets  ← 待修正
hmd-decode.js:L82 parse        ← 待修正
app.py:? scan_directory        ← 加 hmd 分支
app.py:? new /api/hmd/scan
app.py:? new /api/recorders
app.py:? new /api/devices
app.py:? new /api/sd-cards
app.py:? new /api/tasks
templates/index.html:? recorder columnType
templates/index.html:? 新增 hmd 视图入口
db.py:? SQLite schema (recorders/devices/sd_cards/task_keywords/recordable_tasks/video_manager)
```

---

## ⚠️ 已知风险

1. **HMD 容器规范不公开**：实测 type 0x59/0x5a/0x5b 与原注释 0x89/0x90/0x91 矛盾，缺少官方文档
2. **双目方案不确定**：用户拍板"双流"但实测只有 1 个视频 type，需要 Task #16 探测
3. **SQLite 切换破坏现有 verify 脚本**：video-sort-package/verify_*.js/.py 直读 CSV，新版要走 SQLite，需要更新
4. **数据迁移**：现有 video_manager.csv 11 行数据，schema 扩展（加 device_id/recorder_id/task_code）后需一次迁移
5. **frameforge 上传器集成未做**：prompt.txt 明确"先不用适配"，但相关代码不能删，标 deprecated
