# Current Focus — 2026-07-13

> 当前开发轮次的状态。每完成一个功能就更新这里，避免重读整个 plan2。

## 正在做

| 项 | 状态 | 验收 |
|---|---|---|
| /admin/tables 4 表浏览器 | ✅ 2026-07-13 落地 | curl 10/10 e2e 通过；typecheck clean；与 /admin/db 入口互通 |

## 下一步（按用户最新指示）

| 序 | 项 | 关键点 |
|---|---|---|
| 1 | 录制员前端（video 补全页升级） | 让 admin 在浏览器里编辑 public.videos 的 recorder_id / task_id / env_id / uploaded（必须走 dry-run → 确认 → commit）|
| 2 | 按录制员聚合总时长统计 | 数据源 public.videos.duration_sec（注意是 text 字段，先 ::int）；前端柱状图 + 导出 |
| 3 | AI 对话调数据库工作流（已在 `/api/ai/db/*`） | 接入录制员前端：点「让 AI 批量补」按钮 → 把当前未填项发给 dry-run → 用户在 modal 看 diff → commit |

## 不重读的文件

- `docs/dev_plan.md` 路线图
- `docs/data-dictionary.md` 完整字段
- `docs/dev-process/plan.md` 单功能开发 4 步模板

## 重读一遍就够的文件（每次新功能开始时）

- `docs/dev-process/plan.md` §2 4 步模板 + §3 代码组织
- `docs/dev-process/database-policy.md` §1 红线（不能 DROP / TRUNCATE / 无 WHERE UPDATE）
- `docs/dev-process/features/admin-tables.md` 上一轮交付的入口（要衔接时读）

## 数据真相

- public.videos：560 行（其中 419 行未填 recorder/task/env 或 uploaded ≠ Yes）
- public.recorders：14 行
- public.tasks：121 行
- public.environments：19 行
- ff.*（plan2 新表）已落 15 张；业务数据仍走 public.*，ff.* 待 ETL

## 端口 / 服务

- web-uploader 3001（Clerk uploader role）
- web-admin 3002（Clerk admin role，dev 可 CLERK_BYPASS=true 跳过）
- worker 3010（health only）
- 远端 PG `db.example.com:5432/video_manager` schema `ff`
