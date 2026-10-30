# 数据库管理规范（database-policy.md）

> 重点：**保护现有 public.* 8 张表（业务真相）+ AI 操作可审计可回滚**。
> 任何数据库改动先读本文。

## 1. 红线（绝对禁止）

| 操作 | 禁止原因 | 替代方案 |
|---|---|---|
| `DROP TABLE public.videos` | 业务唯一真相，560 行数据 | 只用 UPDATE/INSERT |
| `TRUNCATE public.*` | 不可逆 | 只 DELETE 单条 + WHERE 精确 |
| `DROP SCHEMA public CASCADE` | 系统表 + 旧业务全毁 | 绝对禁止 |
| `DELETE FROM public.videos WHERE ...` 无 WHERE 验证 | 误清全表 | 必须先 SELECT COUNT 确认范围 |
| `UPDATE ...` 漏 WHERE | 全表更新 | 必须 WHERE path=$1 或 主键 |
| 改 public.* schema（ALTER TABLE DROP COLUMN） | 不可逆丢失字段 | 只 ADD COLUMN；不改已有列类型 |
| 把视频文件移动/删除（OS 层） | 路径与 videos.path 对应 | 只改 videos 表；不碰 TF 卡 |
| 在 ff.* 表里 DROP COLUMN | 旧业务可能 join | 不删；用 is_active 软删 |
| 直接 COMMIT 大批量 INSERT（>100 行）不确认 | 误写难回滚 | 走 dry-run preview |

## 2. 命名规范

| 类型 | 规范 | 例 |
|---|---|---|
| 新业务表 | `ff.ff_<feature>` | `ff.ff_video_records` |
| 列名 | snake_case + ff_ 前缀（PG enum）/ business_key | `recorder_key`, `region_id` |
| 业务主键 | `business_key TEXT UNIQUE NOT NULL` | D2 plan2 §5 |
| 乐观锁 | `version INT NOT NULL DEFAULT 1` | D4 |
| 软删除 | `is_active BOOLEAN NOT NULL DEFAULT true` | 替代 DELETE |
| 审计字段 | `created_at / updated_at / created_by / source_device` | plan2 §5.1 |

## 3. 备份策略（plan2 §11 + §6.6 简化版）

| 项 | 频率 | 保留 | 位置 |
|---|---|---|---|
| `pg_dump --schema=public` | 每天 03:00 | 最近 10 份 | `runtime/backups/` |
| `pg_dump --schema=ff` | 每天 03:00 | 最近 10 份 | `runtime/backups/ff/` |
| 手动一键备份 | 改 schema 前 | 不限 | `runtime/backups/manual/` |

**关键脚本**：`scripts/backup-videos.sh`（cron 可调）+ `lib/backup.ts`（API 触发）。

**回滚命令**：`psql $DATABASE_URL < runtime/backups/manual/videos-YYYYMMDD-HHMMSS.sql.gz | gunzip`

## 4. AI 操作边界（核心安全规范）

> AI（包括我）操作数据库时**必须遵守**的约束。

### 4.1 允许的只读操作（无需确认）

- `SELECT * FROM public.videos` / `ff.ff_*`
- `SELECT ... FROM pg_tables / pg_class / pg_namespace`
- `EXPLAIN ANALYZE SELECT ...`
- `SHOW search_path`

### 4.2 允许的写操作（必须 dry-run + 用户确认）

| 操作 | 必须项 |
|---|---|
| `UPDATE public.videos SET ... WHERE path = $1` | 单条 OK；多条 → dry-run 先返回 diff |
| `INSERT INTO ff.ff_*` | 列出每条 → 用户逐条确认 |
| `CREATE TABLE` / `ALTER TABLE ADD COLUMN` | 显示 DDL → 用户确认 |

### 4.3 绝对禁止（AI 自身校验）

- 任何 `DROP` / `TRUNCATE`
- 任何 `UPDATE` / `DELETE` 漏 `WHERE`
- 修改 `public.*` 表结构（ALTER）
- `DELETE FROM public.videos`（如确需删除，先备份再询问）
- 任何把 ff.* 镜像表 DROP 的操作

### 4.4 dry-run 强制模板

```ts
// lib/ai-db.ts
async function dryRunUpdate(
  table: 'public.videos',
  set: Record<string, string>,
  where: { path: string },
): Promise<{ old: Row; new: Row; diff: { field: string; from: string; to: string }[] }> {
  const old = await query(`SELECT * FROM ${table} WHERE path = $1`, [where.path])
  if (old.length === 0) throw new Error('row not found')
  const proposed = { ...old[0], ...set }
  const diff = Object.entries(set).map(([k, v]) => ({ field: k, from: old[0][k], to: v }))
  return { old: old[0], new: proposed, diff }
}
// 用户在 UI 看到 diff 后调用 commitUpdate 执行
```

## 5. 紧急回滚流程

```
发现误操作
  ↓
1. 立即停止所有写入（pg_terminate_backend 强制 rollback）
2. 查看最近备份：ls -lt runtime/backups/manual/ | head -3
3. psql $DATABASE_URL < <备份文件>
4. ff_audit_logs 查误操作记录
5. 写 error_book.md（按 plan2 §3 E{n}）
```

## 6. 数据库健康检查（每天 cron + /admin/db 页面）

| 检查项 | 阈值 |
|---|---|
| public.videos 总行数 | 不应突减 >5%（除非明确删除） |
| ff.* 表数 | 应 ≥ 15（plan2 §3） |
| 最近备份时间 | 应 ≤ 24h |
| public.videos.recorder_id 空值率 | 应 ≤ 20%（持续监控补全进度） |
| pgcrypto 备份完整性 | 应有最近 10 份 |