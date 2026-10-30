# FrameForge 开发规范（2026-07-13）

> 这份文档聚焦"**如何开发**"（流程、规范、约束），不重复 plan2.md 的"开发什么"。
> 单个功能开发时优先看 `docs/dev-process/current-focus.md`，不要重读整个 plan。

## 1. 总体约束

| 约束 | 含义 |
|---|---|
| **PG 不可 DROP** | `public.videos` 等 8 张旧表是业务真相，禁止 `DROP TABLE / TRUNCATE`。改 schema 走 `ALTER TABLE ADD COLUMN` 增量方式。 |
| **新增表加 `ff_` 前缀** | 与 plan2 §7 D7 一致；新业务数据全部进 `schema ff.ff_*`。 |
| **CSV 仅缓存，不入仓** | plan1 教训 E18：禁止把 public.* 镜像到 git 或本地 CSV 作为唯一数据源。 |
| **AI 必须 dry-run** | 任何 UPDATE/INSERT > 1 行 / 修改 ≥2 列 → 先 dry_run 返回 diff → 用户确认才执行。 |
| **保留 git history** | 一次 commit 一个功能；msg 写明目的 + 影响范围 + 防 bug 编号。 |
| **port 不冲突** | web-uploader=3001 / web-admin=3002 / worker=3010；启动前先查端口。 |

## 2. 单个功能开发的 4 步模板（避免重 plan 占上下文）

```
Step 1：写 task list（一句话 ≤ 20 字，最多 5 条）              ← 占小上下文
Step 2：写代码（API + UI + 必要的 lib）                         ← 主要工作
Step 3：dev 服起来 + curl / 浏览器 端到端验证                  ← 占小上下文
Step 4：commit + 更新 docs/dev-process/current-focus.md 进度   ← 占小上下文
```

**要点**：
- 不要重读整个 plan2.md
- 不重新设计已定的架构（Next.js + Clerk 跳过 + raw SQL 直查）
- 不要每步都 review，先做完再验证

## 3. 代码组织（每个功能都按这个目录）

```
apps/web-admin/src/app/admin/<feature>/           # 页面
apps/web-admin/src/app/api/admin/<feature>/       # API route handler
apps/web-uploader/src/app/library/<feature>/      # uploader 页面
apps/web-uploader/src/app/api/admin/<feature>/    # uploader API（如要）
packages/shared/src/schemas/<feature>.ts          # 共享 Zod schema（如要）
docs/dev-process/features/<feature>.md             # 完成后写 mini-doc
```

## 4. 数据库管理优先级

1. **备份**：见 `database-policy.md` §3（自动 cron + 手动按钮）
2. **AI 操作边界**：见 `database-policy.md` §4
3. **写操作必须事务**：`BEGIN ... COMMIT`，失败 `ROLLBACK`
4. **写操作必须有 WHERE**：UPDATE 必须 `WHERE path = $1`（或主键），避免"无 WHERE 全表更新"误操作

## 5. 当前迭代（2026-07-13）

看 `current-focus.md`。本轮重点：
- **视频信息补全**（/library/fill）让管理员补录制员归属
- **数据库仪表盘**（/admin/db）让 AI / 管理员有全局视图
- **AI 安全工具**（lib/ai-db.ts）让 AI 操作可审计可回滚

## 6. 与既有交付的衔接

| 已交付（commit）| 状态 | 本轮如何衔接 |
|---|---|---|
| 22ec989 admin: 工资管理 + 统计 + CSV | ✅ 已上线 | 工资页接 /admin/db 看数据健康 |
| cd64f97 uploader: /library/fill | ✅ 已上线 | 本轮加 dry-run + commit modal |
| ba6b175 plan2 骨架 + 15 表 ff_ | ✅ 已落地 | 旧数据读 public.*；新数据写 ff.* |