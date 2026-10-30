# AI 数据库对话操作规范（ai-db-workflow.md）

> 这份文档讲**AI（claude code / 我）和数据库的对话工作流**。
> 配合 `packages/db-schema/src/lib/ai-db.ts` 使用。

## 核心原则

1. **永远 SELECT 看现状** — 任何写操作之前先 SELECT 看目标行
2. **永远先 DRY-RUN** — `dryRunUpdate` / `dryRunBatchUpdate` 返回 before/after diff
3. **用户确认** — diff 给用户看 → 用户说 OK → 才 commit
4. **兜底关键词黑名单** — `lib/ai-db.ts::assertSafeSql` 拦截 DROP/TRUNCATE/无 WHERE UPDATE/DELETE/ALTER
5. **不可逆操作禁止** — DROP TABLE public.videos / TRUNCATE / 全表 DELETE → 不论用户怎么确认都不允许

## 工作流示例（典型 AI 对话）

### 例 1: 给 5 条视频补 recorder_id

```
👤 用户：把最近 5 条没填 recorder 的视频都设成 op3 + uploaded Yes

🤖 AI:
   1) SELECT 找 5 条未填 path
   2) dryRunBatchUpdate 准备批量
   3) 给用户看 diff：
      - path/0625/hmd/..._00000: recorder_id '' → 'op3', uploaded '' → 'Yes'
      - path/0625/hmd/..._00001: 同上
      - 共 2 字段 × 5 条 = 10 处变更
   4) 等待用户确认

👤 用户：OK

🤖 AI:
   commitBatchUpdate (事务)
   ✅ 已更新 5/5 行
```

### 例 2: 用户说"删掉重复的 ff.users"

```
👤 用户：把 ff.users 里的重复数据删掉

🤖 AI:
   1) SELECT 看是否有重复
   2) 列出每组的 clerk_user_id 出现次数
   3) 给用户看哪些要删
   4) ⚠️ AI 主动拒绝：ff.users 是 Clerk 同步数据，删除会破坏一致性
   5) 建议用 is_active=false 软删，或修复 Clerk webhook
```

### 例 3: 用户说"备份后改 public.videos 加列"

```
👤 用户：public.videos 加一个 score_value 列

🤖 AI:
   1) 先触发备份 POST /api/admin/db/backup → 等待完成
   2) SELECT 看现有列
   3) 准备 ALTER TABLE public.videos ADD COLUMN ...
   4) ⚠️ AI 主动确认：是否仅 ADD COLUMN（不 DROP 现有）
   5) 确认后执行 ALTER
   6) 验证：SELECT column_name FROM information_schema.columns WHERE ...
```

## AI 不允许的操作（不论用户怎么确认）

- `DROP TABLE public.videos` / `DROP TABLE public.*` / `DROP SCHEMA public`
- `TRUNCATE public.*`
- `DELETE FROM public.videos`（无 WHERE 或影响 >10 行）
- `ALTER TABLE public.* DROP COLUMN`
- 任何 ff.* 表的 DROP / TRUNCATE

## 工具 API（AI 调用入口）

```ts
// 读
import { query } from '@/lib/db'
const rows = await query('SELECT ... FROM ...')

// 写（两步走）
import { dryRunUpdate, commitUpdate } from '@ff/db-schema'

// 第一步：dry-run
const preview = await dryRunUpdate(pool, {
  table: 'public.videos',
  where: { path: 'D:/sp/...' },
  set: { recorder_id: 'op3' },
})
// 用户看 preview.diffs → OK

// 第二步：commit
const r = await commitUpdate(pool, { ...same args })
```

## 调试技巧

- **AI 不确定时**：先 SELECT 看现状（不要盲改）
- **AI 改完想验证**：再 SELECT 一次 diff 行
- **rollback 命令**（紧急）：
  ```bash
  psql $DATABASE_URL < runtime/backups/manual/all-YYYYMMDD-HHMMSS.sql.gz | gunzip
  ```
- **发现误改**：立刻写 `docs/error_book.md` 一条新 E{n}

## 当前已有数据（基线 2026-07-13）

- public.videos：560 行
- 待补：419 行（recorder_id/task_id/env_id 空 或 uploaded != Yes）
- 14 recorder + 121 task + 19 env 已 seed

→ **核心 AI 工作流**：用 `dryRunBatchUpdate` 给这些空字段批量预填 → 用户确认 → commit