# 预处理管理器 (Preprocess Manager)

> HMD session 批量预处理工具集。用于重新生成所有本地视频的预览文件（mp4 + cover + frames）。

---

## 场景

当 `runtime/hmd_cache` 被清空，或需要重新生成预览文件时使用。典型场景：
- 迁移后缓存丢失
- 预览文件损坏（mp4 无法播放）
- 重新整理预处理状态

---

## 脚本清单

### 1. `src/scripts/check_source_integrity.py`

**用途**：预处理前置检查——验证 HMD session 源文件完整性。

```bash
python src/scripts/check_source_integrity.py
```

**检查项**：
| 检查项 | 说明 |
|--------|------|
| session 目录存在 | 路径有效 |
| `metadata.json` 有效 | JSON 可解析 |
| 至少一个 `part_*.hmd` 存在 | 有内容可解码 |
| 每个 `.hmd` 文件 > 1MB | 排除空文件/过小文件 |

**输出三级**：
- `ERROR` — 源文件不完整，无法预处理（必须先修复）
- `WARN` — 有小问题，可尝试预处理
- `OK` — 源文件完整，可以开始预处理

**输出文件**：`runtime/source_integrity_check.csv`

---

### 2. `src/scripts/preprocess_manager.py`

**用途**：批量执行 HMD 预处理全流程（fast 管线），管理状态。

```bash
# 完整管线（fast + mp4）
python src/scripts/preprocess_manager.py --skip-extra-desc="1"

# 仅 fast（快速验证，不生成 mp4）
python src/scripts/preprocess_manager.py --fast-only

# dry-run（只扫描，不实际处理）
python src/scripts/preprocess_manager.py --dry-run

# 强制重跑已完成的项目
python src/scripts/preprocess_manager.py --force
```

**完整管线流程**（`process_fast` 一体化完成）：
```
HMD (part_*.hmd)
  └─> 解码 → left.h265
        └─> remux → left.mp4  （或 {session}.mp4）
              ├─> 6 帧预览图  → frames/frame_00~05.jpg
              └─> 封面图      → cover.jpg
  └─> 清理 left.h265（mp4 验证完好后自动删除）
```

**管理 CSV**：`runtime/preprocess_manager.csv`

| 字段 | 说明 |
|------|------|
| `pm_id` | 唯一标识（UUID，前 8 位） |
| `video_id` | 对应 video_manager.csv 行索引 |
| `session_path` | HMD session 源路径 |
| `status` | `pending` / `processing_fast` / `done` / `error` |
| `has_mp4` | mp4 是否存在（Y/N） |
| `has_cover` | cover.jpg 是否存在（Y/N） |
| `has_frames` | frames >= 3 张（Y/N） |
| `frames_count` | 实际帧数 |
| `mp4_path` / `cover_path` / `frames_dir` | 产物路径 |
| `cache_dir` | hmd_cache 目录 |
| `error_msg` | 错误信息 |
| `progress_pct` | 总进度 0-100 |
| `started_at` / `finished_at` | 时间戳 |

**通过 `video_id` 或 `session_path` 与 `video_manager.csv` 跨表关联。**

**成功标准**：
- `has_mp4 = Y` + ffprobe 可解析
- `has_cover = Y`
- `frames_count >= 3`

**清理逻辑**：mp4 验证完好后，`left.h265` 被自动删除（冗余中间产物）。

---

## 生命周期核心原则

> 参考 `docs/file-lifecycle.md`

1. **核心预览文件是 mp4**，不是 h265
2. h265 是中间产物，mp4 验证完好后可删除
3. frames 和 cover.jpg 都从 mp4 切出来
4. 上传后源文件删除，**cover.jpg 保留**

---

## 典型使用流程

```
1. 清空 / 损坏 hmd_cache
       ↓
2. python check_source_integrity.py    ← 前置检查，确认源文件 OK
       ↓
3. python preprocess_manager.py --dry-run --skip-extra-desc="1"   ← 预览要处理哪些
       ↓
4. python preprocess_manager.py --skip-extra-desc="1"   ← 正式跑
       ↓
5. 检查 runtime/preprocess_manager.csv  ← 确认全部 done
```

---

## 跳过规则

### 命令行参数

`--skip-extra-desc="1"` 会跳过 video_manager.csv 中 `extra_description = 1` 的 session（标记为无需预处理的视频）。

### 自动预热跳过规则（`auto_warm_all`）

> 🆕 2026-06-30：前端「全部预热」按钮和扫描后自动预热统一遵循文件生命周期过滤：

| 条件 | 行为 | 原因 |
|------|------|------|
| `uploaded = "Yes"` | 跳过 | 已上传完成 |
| `location_status = "history"` | 跳过 | 源文件已删除 |
| HMD 源目录不存在或无 `part_*.hmd` | 跳过 | 无源文件 |
| 后台已有处理任务 | 前端不启动 | 防重复（`GET /api/hmd/is-processing`） |

> 缩略图生成（`_ensure_thumbnail`）同样遵循 `uploaded=Yes` / `location_status=history` 跳过规则。
