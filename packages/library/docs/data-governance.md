# 数据治理文档

> 规范视频管理器所有数据的存储载体、生命周期行为、流转路径、冲突处理与备份策略。
> 与 `file-lifecycle.md`（视频文件生命周期）配套阅读。

---

## 一、数据要素总览

| 要素 | 存储载体 | 持久化方式 | 说明 |
|------|---------|-----------|------|
| **视频文件**（原始） | 本地磁盘 | 文件系统 | MP4 / HMD session / Data session |
| **用户标注** | `video_manager.csv` + PostgreSQL `videos` 表 | 双向同步 | `recorder_id` / `task_id` / `env_id` 等字段 |
| **维表数据** | CSV 文件 + PostgreSQL 各表 | 双向同步 | `tasks` / `recorders` / `sd_cards` / `environments` |
| **运行时产物** | `runtime/` 目录 | 文件系统 | 缩略图、HMD 预处理缓存、预览帧、状态文件 |
| **系统配置** | `runtime/data/config.json` | JSON 文件 | 列定义、扫描目录、排序状态、筛选器状态 |
| **上传凭证** | `<视频路径>.uploaded` | 标记文件 | 上传成功双重判重 |

---

## 二、存储载体详解

### 2.1 视频文件（原始）

| 类型 | 路径格式 | 持久化 |
|------|---------|--------|
| MP4 | `<dest_base>/<MMDD>/<文件名>.mp4` | ✅ 永久 |
| HMD session | `<dest_base>/<MMDD>/hmd/<MMDD>_<device_id>_<session>/` | ✅ 永久（上传后可选删除） |
| Data session | `<dest_base>/<MMDD>/data/<MMDD>_<device_id>_<session>/` | ✅ 永久 |

### 2.2 用户标注（主表）

**载体**：`runtime/data/video_manager.csv` ↔ PostgreSQL `videos` 表

**读写策略**（`USE_PG` 控制）：

```
USE_PG = False（纯 CSV 模式）
  read_csv()  → 直接读 CSV 文件
  write_csv() → 直接写 CSV 文件

USE_PG = True（双写模式）
  read_csv()  → 优先本地 CSV（30s TTL 内）；过期则查 PG，同时同步本地 CSV
  write_csv() → UPSERT 写 PG（ON CONFLICT DO UPDATE），成功后同步本地 CSV
```

> **设计原则**：本地 CSV 是 PG 的持久化缓存，不是独立数据源。任何写入必须同时落 PG 和 CSV。

### 2.3 维表数据

| 维表 | CSV 路径 | PG 表名 |
|------|---------|---------|
| 录入员 | `runtime/data/recorders.csv` | `recorders` |
| SD 卡 | `runtime/data/sd_cards.csv` | `sd_cards` |
| 任务 | `runtime/data/tasks.csv` | `tasks` |
| 环境 | `runtime/data/environments.csv` | `environments` |

**读写策略**：

```
USE_PG = True
  _read_dim_rows()  → 从 PG 表读取，60s TTL 缓存
  atomic_write_dim() → 先 TRUNCATE+INSERT 写 PG，再同步写 CSV

USE_PG = False
  _read_dim_rows()  → 直接读 CSV
  atomic_write_dim() → 直接写 CSV
```

> **⚠️ 关键规则**：`_atomic_write_dim` 是维表写的唯一入口，所有增删改必须经过此函数。

### 2.4 运行时产物（缓存，不可作为数据源）

| 产物 | 路径 | TTL | 说明 |
|------|------|-----|------|
| 缩略图 | `runtime/thumbnails/<sha1>.jpg` | 永久 | 一次性生成，路径 = `sha1(path\|mtime\|size)` |
| HMD 预览 MP4 | `runtime/hmd_cache/<date>/<basename>/<session>.mp4` | 永久 | 仅用于本地预览，不上传 |
| HMD 封面 | `.../cover.jpg` | 永久 | 一次性生成 |
| 6 帧预览 | `.../frames/frame_00~05.jpg` | 永久 | 画廊卡片展示 |
| 预处理状态 | `.../preprocess_status.json` | 永久 | 记录处理阶段和进度 |
| H265 流 | `.../left.h265` | **处理后即删除** | Stage 2 完成后自动删除，节省空间 |

---

## 三、数据行为与流转路径

### 3.1 读取（Load）— 目标是毫秒级响应

```
┌─────────────────────────────────────────────────────┐
│ 前端页面加载 / 切换 Tab                               │
│  ① 检查前端内存缓存（tableData / dimCache）           │ ← 即时
│  ② 若空 → /api/dim/<name>                          │
│       ↓                                             │
│  ③ 服务端：get_dim(name) → 60s TTL 内直接返回       │ ← 即时
│  ④ 若过期 → _read_dim_from_pg() → PG 查询          │
│       ↓                                             │
│  ⑤ 缓存填充 → 返回前端                              │
└─────────────────────────────────────────────────────┘
```

**加载优化策略**：
- **启动预热**：`loadConfig()` 时并行预热所有维表（`Promise.all`），页面切换不触发网络请求
- **内存缓存优先**：前端 `dimCache` / `tableData` 不失效不重请求
- **TTL 保活**：视频缓存 30s、维表缓存 60s，频繁切页不击穿 PG

### 3.2 创建（Create）

| 场景 | 写入路径 | 载体 |
|------|---------|------|
| 设备导入（SD 卡） | `device_monitor.py` | CSV 新增行 |
| 手动扫描 | `/api/scan` → `write_csv()` | PG + CSV 同步 |
| 维表新增行 | `/api/dim/<name>` mode=insert → `atomic_write_dim()` | PG + CSV 同步 |
| 视频标注（新增字段） | `/api/save` → `write_csv()` | PG + CSV 同步 |

### 3.3 更新（Update）

| 场景 | 写入路径 | 载体 |
|------|---------|------|
| 预览表单填写保存 | `saveAll()` → `/api/save` → `write_csv()` | PG + CSV 同步 |
| 维表行内编辑保存 | `dimRowBlur` → `dimSaveOne()` → `/api/dim/<name>` | PG + CSV 同步 |
| 批量保存维表 | `dimSaveDirtyRows()` → 循环 `dimSaveOne()` | PG + CSV 同步 |

> **⚠️ 写入后必须调用 `cache.invalidate_xxx()`**：使 TTL 失效，保证下次读取拿到最新数据。

### 3.4 删除（Delete）

| 场景 | 写入路径 | 说明 |
|------|---------|------|
| 维表行删除 | `dimDeleteRow()` → `/api/dim/<name>/<key>` DELETE | PG + CSV 同步 |
| 视频记录删除 | `deleteSingle()` → `/api/videos/<idx>` DELETE | PG + CSV 同步 |
| 已上传视频源清理 | `/api/clean-uploaded-cache` | 仅删文件，不删 CSV 行 |

---

## 四、多设备数据管理

### 4.1 当前架构：单设备工作流

```
  本机                          PostgreSQL（共享）
 ┌──────────┐                  ┌──────────────┐
 │ 设备 A   │ ←── CSV 缓存 ──→ │  videos 表   │
 │ (本机)   │ ←── 维表同步 ──→ │  tasks 表   │
 └──────────┘                  │  recorders  │
                               │  sd_cards   │
                               │  environ-    │
                               │  ments      │
                               └──────────────┘
```

- **所有设备共用同一个 PG 数据库**（`VIDEO_MANAGER_DB_DSN` 指向同一 PG 实例）
- PG 是数据的"真实来源"，CSV 是各设备的本地缓存
- 任何设备写入后，**立即同步 CSV**（修复后），其他设备下次访问时 PG 已有最新数据

### 4.2 多设备写入规则

| 场景 | 解决策略 |
|------|---------|
| 同一视频记录在两台设备同时编辑 | `write_csv()` 用 `ON CONFLICT (path) DO UPDATE`，后写覆盖先写（Last-Write-Wins） |
| 同一维表行在两台设备同时修改 | `atomic_write_dim()` 用 `TRUNCATE + 全量 INSERT`，后写全量覆盖 |
| 设备 A 创建的任务在设备 B 的视频中被引用 | 引用通过 `task_id` 主键，维表先行创建，视频侧无冲突 |

### 4.3 多设备数据隔离（将来扩展）

若需要完全隔离（例如临时离线接入），采用以下方案：

**方案 A：设备专属数据目录**
```
runtime/
  data_A/  ← 设备 A 的 CSV 和 config
  data_B/  ← 设备 B 的 CSV 和 config
  data_shared/  ← 共享维表（通过 PG 同步）
```
> 缺点：需要修改 `RUNTIME_DIR` 逻辑，改动较大

**方案 B：设备标记 + PG 分区（推荐）**
```
videos 表新增 column: source_device TEXT
```
- 每台设备扫描时标记 `source_device`
- 跨设备查询用 `WHERE source_device = ?` 隔离
- PG 作为中央节点，天然支持多设备并发

---

## 五、冲突治理方案

### 5.1 冲突分类

| 类型 | 冲突内容 | 影响 |
|------|---------|------|
| **写入冲突** | 两设备同时修改同一行 | Last-Write-Wins，丢失一方修改 |
| **引用冲突** | 视频引用了已被删除的 `task_id` | 显示为空，需重建维表记录 |
| **路径冲突** | 不同设备扫描到相同文件 | PG 的 `path` 是唯一键，后者覆盖前者 |
| **上传冲突** | 同一视频两设备同时上传 | `.uploaded` 标记文件双重保险 |

### 5.2 Last-Write-Wins（当前策略）

所有写入操作使用"后写覆盖"策略：

```
videos 表：       ON CONFLICT (path) DO UPDATE SET  ← 覆盖
dim 表（全量）：  TRUNCATE + INSERT                 ← 全量覆盖
```

**优点**：实现简单，无锁竞争，适合单用户/单设备工作流
**缺点**：先写入方的修改可能丢失

### 5.3 冲突检测与告警（优化方向）

```python
# 在 write_csv 路径增加冲突检测
def write_csv(rows):
    existing = read_csv()  # 当前 PG 数据
    for row in rows:
        if row['path'] in existing:
            old = existing[row['path']]
            # 检测字段差异
            diff_fields = [f for f in FIELDNAMES if old.get(f) != row.get(f)]
            if diff_fields:
                logger.warning(f"冲突覆盖：{row['path']}，差异字段：{diff_fields}")
                # 可选择：写入冲突日志，不直接覆盖
```

### 5.4 引用完整性保护

维表删除前检查被引用情况：

```
删除 task_id = "xxx" 前：
  1. 查询 videos 表 WHERE task_id = "xxx" → 若有结果则拒绝删除
  2. 提示用户：先清除引用此任务的视频记录
```

---

## 六、备份策略

### 6.1 CSV 备份

| 备份类型 | 路径 | 触发时机 | 保留份数 |
|---------|------|---------|---------|
| 维表备份 | `runtime/csv_backups/dim_<name>_<ts>.csv` | `atomic_write_dim()` 每次写入前 | 10 份轮转 |
| 主表备份 | `runtime/csv_backups/video_manager_<ts>.csv` | `save_data()` / `save_rows()` 前 | 由调用方控制 |

**轮转策略**：保留最近 10 份，最旧自动删除。

### 6.2 PostgreSQL 备份

| 备份类型 | 方式 | 频率 | 说明 |
|---------|------|------|------|
| 物理备份 | `pg_basebackup` | 每日 | 全量快照 |
| 逻辑备份 | `pg_dump --format=plain` | 每周 | SQL 文本，可查看 |
| WAL 归档 | `archive_mode = on` | 持续 | Point-in-time 恢复 |

> 推荐：每天凌晨 `pg_dump -Fc` 一次，保留 7 天。

### 6.3 文件备份

| 内容 | 备份方式 | 说明 |
|------|---------|------|
| 视频文件 | 磁盘快照 / NAS 副本 | 依赖基础设施 |
| 缩略图 / 预览帧 | 可选备份 | 丢失可重新生成 |
| config.json | Git 纳入版本控制 | 推荐 |

---

## 七、性能优化：消除前端与 PG 交互延迟

### 7.1 已知延时瓶颈

| 瓶颈场景 | 原因 | 优化方案 |
|---------|------|---------|
| **维表校验提示**（如 task_id 格式校验）| 每次字段变化都调 `/api/dim/tasks/next-id` | 本地正则预校验，真实校验仅在 blur 或保存时触发 |
| **选择任务后填充 business_type/name** | 每次切换任务都查 PG | 前端 `dimCache['tasks']` 预加载，按 `task_id` O(1) 查找 |
| **维表保存后刷新重置**（已修复）| `atomic_write_dim` 不写 CSV，缓存未失效 | 修复：写 PG 时同步写 CSV + `cache.invalidate_dim()` |
| **首次加载慢** | PG 查询冷启动 | 启动预热：Flask 启动后立即加载维表到缓存 |

### 7.2 维表校验优化：本地预检 + 按需请求

```
错误做法（高延时）：
  input onchange → fetch('/api/dim/tasks/next-id') → 每次击穿 PG

正确做法（无延时）：
  input oninput  → 本地正则校验 task_id 格式（无网络）
  input onblur   → 仅当 task_id 合法时调 /api/dim/tasks/next-id（仅一次）
  保存时         → 批量校验 + 真实写入
```

### 7.3 维表数据本地索引

维表数据预加载后，在前端构建查找索引：

```javascript
// 初始化时构建
const taskIndex = {};
dimCache['tasks'].forEach(t => taskIndex[t.task_id] = t);

// 查找时 O(1)，无网络请求
const task = taskIndex['xxx_xxx_xxx_001'];
if (task) {
    row.business_type = task.business_type;
    row.business_name = task.business_name;
}
```

### 7.4 启动预热（Startup Warm-up）

Flask 启动后立即执行，不等用户请求：

```python
# app.py 或 run.py 启动时
@app.before_first_request
def warm_up():
    from models.pg_dim import read_dim_rows
    from config import _DIM_REGISTRY
    for name in ['tasks', 'recorders', 'sd_cards', 'environments']:
        spec = _DIM_REGISTRY[name]
        read_dim_rows(spec['path'], spec['schema'], spec['key'])
    # 视频缓存也预热
    from models.pg_store import read_csv
    read_csv()
```

> 效果：首屏加载时间从 "PG 查询耗时" → "内存缓存命中，毫秒级"。

### 7.5 写入后不阻塞读

```
dimSaveOne() 执行流程（优化后）：
  1. fetch POST /api/dim/<name>  → 后端写入 PG + CSV
  2. 后端返回 { ok: true, action: 'updated' }
  3. 前端 dimRenderTable()        → 读前端内存 dimCache（已由写入更新）
  4. 不需要再次 fetch GET         → 节省一次 PG 查询
```

**实现关键**：`dimSaveOne` 成功后，用服务器返回的 `data.row` 更新 `dimPageState[name].rows`，而不是重新拉取。

---

## 八、数据健康检查清单

| 检查项 | 检查方法 | 异常处理 |
|-------|---------|---------|
| PG 与 CSV 行数一致 | `SELECT COUNT(*) FROM tasks` vs `wc -l tasks.csv` | 触发全量同步 |
| PG 无 null 主键 | `SELECT * FROM tasks WHERE task_id IS NULL` | 不应出现，排查写入逻辑 |
| 视频引用的 task_id 在 tasks 表存在 | 每日定时任务检查 | 告警 + 日志 |
| CSV 无孤立行（视频引用了不存在的维表记录） | 定期扫描 `video_manager.csv` | 提示用户清理 |
| `.uploaded` 标记与 CSV `uploaded` 字段一致 | 上传后双重校验 | 以标记文件为准 |
| 磁盘空间充足 | `df -h` 或 `os.statvfs()` | 低于 20% 告警 |

---

## 九、配置与环境变量

| 变量 | 默认值 | 说明 |
|------|-------|------|
| `VIDEO_MANAGER_DB_DSN` | 空（使用 CSV 模式） | PostgreSQL 连接串，例如 `postgresql://user:pass@host:5432/db` |
| `USE_PG` | `bool(DATABASE_DSN)` | 自动检测，无须手动设置 |
| `CACHE_TTL` | `30` 秒 | 视频缓存 TTL |
| `DIM_CACHE_TTL` | `60` 秒 | 维表缓存 TTL |
| `SCAN_DIRECTORY` | `/media` | 默认扫描目录 |

---

## 十、版本历史

| 日期 | 变更 |
|------|------|
| 2026-07-03 | 初始版本；补充维表 PG+CSV 双写同步规则；明确多设备 Last-Write-Wins 策略；增加性能优化章节 |
