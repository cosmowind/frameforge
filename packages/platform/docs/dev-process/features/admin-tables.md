# /admin/tables — 数据表浏览（4 表通用）

> 一次性看 4 张业务表（videos / tasks / recorders / environments）的所有字段。
> 自由勾选列、排序、搜索、分页。**只读**，写入请走 `/library/fill` 或 AI 数据库工具。

## 入口

- 页面：`/admin/tables`（已挂在 admin 首页 + `/admin/db` 顶部）
- 数据 API：`GET /api/admin/tables/data?table=&limit=&offset=&sort=&order=&q=`
- Schema API：`GET /api/admin/tables/schema`

## 白名单（防 SQL 注入）

| 表 | 物理名 | 主键 | 默认排序 | 默认显示列 |
|---|---|---|---|---|
| `videos` | `public.videos` | `path` | `scan_date DESC` | path / recorder_id / task_id / env_id / duration_sec / file_type / device_id / uploaded / score / scan_date / extra_description |
| `tasks` | `public.tasks` | `task_id` | `task_id ASC` | task_id / task / process / process_en / product / tool / difficulty / quota_min / scene / environment |
| `recorders` | `public.recorders` | `id` | `id ASC` | id / name / phone / operator_job / age_range / gender / handedness / gloves / workforce_type / collection_experience_days / notes |
| `environments` | `public.environments` | `env_id` | `env_id ASC` | env_id / scene / environment / environment_description / environment_description_en / location_address / facility_venue / notes |

- 表名：zod enum 白名单，非白名单 → 422
- 排序列：从 information_schema.columns 动态拉，非白名单 → 回退默认
- limit：1-500，超界 422；防止误操作拉爆内存
- q 搜索：所有列 `::text ILIKE %q%`（timestamp/numeric 安全转 text）

## UI 能力

- 4 tabs 切换（videos / tasks / recorders / environments）
- 列头点击切换 asc/desc（高亮当前排序列）
- ⚙ 列设置弹层：勾选列显隐 + ←/→ 调列顺序 + 「全选」/「只看主键」快捷
- 搜索框（300ms debounce，跨所有列模糊）
- 每页 50/100/200/500
- 分页：首页 / 上一页 / 下一页 / 末页 + 行号
- 主键列加粗高亮
- 空 / 加载 / 错误 三态

## 验收（curl e2e，2026-07-13 通过）

```bash
# 4 表都能加载
curl -s 'http://localhost:3002/api/admin/tables/data?table=recorders&limit=3'    # total: 14
curl -s 'http://localhost:3002/api/admin/tables/data?table=environments&limit=3'  # total: 19
curl -s 'http://localhost:3002/api/admin/tables/data?table=tasks&limit=3'        # total: 121
curl -s 'http://localhost:3002/api/admin/tables/data?table=videos&limit=3'        # total: 560

# 排序 + 分页
curl -s '...&table=tasks&sort=task_id&order=asc' → 第一行 task_id=1_11a6724f...
curl -s '...&table=tasks&limit=5&offset=10'      → 第 11 行

# 跨列搜索
curl -s '...&table=tasks&q=水龙头'   → total: 23
curl -s '...&table=videos&q=op8'     → total: 29

# SQL 注入兜底
curl -s '...&sort=__DROP__' → sort 回退到 scan_date
curl -s '...&table=videos; DROP' → 422 VALIDATION
curl -s '...&limit=99999' → 422 VALIDATION (limit ≤ 500)
```

## 衔接（下一步）

- **录制员前端**（下一步要做）：复用本组件的 4 表壳子，给 admin 看 + 单条编辑视频的 `recorder_id` / `task_id` / `env_id` / `uploaded`
- **统计**（后续）：用 ff_audit_logs + 录制员聚合得到「每个录制员总时长」—— 数据源仍然是 public.videos（duration_sec 字段）
- **AI 调整数据库**（用户每次对话中需要的）：依然走 `/api/ai/db/{query,dry-run,commit}` 三件套，不直接改本组件

## 文件清单

| 文件 | 角色 |
|---|---|
| `apps/web-admin/src/lib/table-config.ts` | 4 表白名单 + 默认列 + 默认排序（前后端共享） |
| `apps/web-admin/src/app/api/admin/tables/schema/route.ts` | GET schema（information_schema.columns） |
| `apps/web-admin/src/app/api/admin/tables/data/route.ts` | GET data（白名单表 + 白名单列 + 参数化） |
| `apps/web-admin/src/app/admin/tables/page.tsx` | 服务端组件：拉 schema → 传给客户端 |
| `apps/web-admin/src/app/admin/tables/AdminTablesClient.tsx` | 客户端：tabs + 列设置 + 排序 + 搜索 + 分页 |
