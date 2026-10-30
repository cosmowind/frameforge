# Dev Log — FrameForge (plan2)

> 实现 / 验证 / 回退 三段式。复盘与接手时读。

## 2026-07-11 — Phase 0 工程骨架（plan2）

### 实现

按 plan2 §9 Phase 0.2-0.9 执行：

| # | 步骤 | 关键产物 |
|---|---|---|
| 1 | 归档 ff → ff-v1-archive（独立 git 仓库 + 3 commits） | ff-v1-archive/ 完整保留 v1 成果 |
| 2 | 新 ff/ + git init | 干净仓库 |
| 3 | workspace 根 | `package.json` + `pnpm-workspace.yaml` + `tsconfig.base.json` + `.editorconfig` + `.prettierrc` + `.env.example` |
| 4 | Docker Compose 必用 | `docker-compose.yml` 含 mem_limit + cpus + named volumes + bull-board profile + local-s3 profile |
| 5 | infra docker | `infra/docker/web.Dockerfile` + `infra/docker/worker.Dockerfile` 多阶段 |
| 6 | packages/shared | constants (4 设备 code + 路由 + 状态) + types (Clerk claims) + 5 个 Zod schema + DeviceAdapter 接口 + utils (logger/paths) |
| 7 | packages/db-schema | schema.ts (pgSchema 'ff') + enums.ts (11 enum) + 15 张 ff_* 表 + migrations/v0_initial_v2.sql + scripts/migrate.ts + scripts/seed.ts |
| 8 | packages/adapters | registry.ts + 4 设备 Adapter 占位实现（DjiGoproDcim / HeadMountedUmi / GoproSessionMcap / GenericAviRecording）|
| 9 | apps/web-uploader | Next.js 15 App Router + Clerk middleware + 4 step 占位 + sign-in/sign-up + localStorage helper + api health route |
| 10 | apps/web-admin | Next.js 15 App Router + Clerk middleware + Dashboard + 7 菜单占位 + sign-in/sign-up |
| 11 | apps/worker | Node + BullMQ 4 queue (device-scan / preview / pull / backup) + ioredis + HTTP /health + SIGTERM graceful |
| 12 | WCS docs | wcs-manifest.yaml + 11 docs (9 基础 + 3 plan2 新增) + README |

### 验证

| 项 | 命令 | 期望 |
|---|---|---|
| pnpm install | `pnpm install` | 所有依赖装好 |
| 全量 typecheck | `pnpm -r typecheck` | 0 error |
| backend web-uploader build | `pnpm --filter @ff/web-uploader build` | Next.js 编译成功 |
| backend web-admin build | `pnpm --filter @ff/web-admin build` | 同上 |
| worker build | `pnpm --filter @ff/worker build` | tsc 通过 |
| 数据库迁移 | `pnpm db:migrate` | ff schema 11 enum + 15 表 |
| seed | `pnpm db:seed` | 1 region + 4 device types |
| 工作进程启动 | `pnpm --filter @ff/worker dev` | :3010 监听 |
| 前端 dev | `pnpm --filter @ff/web-uploader dev` | :3001 监听 |
| Clerk 中间件 | 访问 `/` 未登录 | 302 重定向到 /sign-in |

### 回退

如 docker compose 起不来：
```bash
docker compose down
# 修 docker-compose.yml
docker compose up -d
```

如 worker 启动 Redis 连不上：
```bash
docker compose logs redis
# 确认 REDIS_URL=redis://localhost:6379
```

如 migrate 失败：
```bash
psql $DATABASE_URL -c "DROP SCHEMA ff CASCADE"
pnpm db:migrate && pnpm db:seed
```

### 学到 / 待优化

- Phase 0 占位多 — Phase 1 才是业务核心
- v1 归档到 `../ff-v1-archive/`，独立 git 仓库 + 3 commits
- Clerk SaaS 需要用户先去 https://dashboard.clerk.com 申请应用，Phase 1 接 webhook
- 4 设备 Adapter 占位实现需要 Phase 1 替换为真实 ffmpeg / ROS / HMD decoder 调用
- 15 张表 + 11 enum + 1 trigger（D5 scan_date 不可减少）已通过手写 SQL migration 落库

### Phase 0 未做（推迟到 Phase 1）

- ❌ RHF + Zod 表单（Step 3）
- ❌ 4 设备 Adapter 真实实现
- ❌ Clerk webhook → ff_users 同步
- ❌ COS 直传 SDK 集成
- ❌ SCF 函数（部署在腾讯云）
- ❌ Puller 容器（家用 Linux 服务器）
- ❌ 域名 + HTTPS + CDN
- ❌ 飞书告警

### 下一步

Phase 1 Step 0（Clerk 接入 + dev 三端起来）+ Step 1（DjiGoproDcimAdapter 最先做，因为最简单 + 风险低）。

---

## 2026-07-13 — /admin/tables 4 表浏览器 + 3 个 React 19 fix

### 实现（commit 650a268）

| # | 文件 | 作用 |
|---|---|---|
| 1 | `apps/web-admin/src/lib/table-config.ts` | 4 张表白名单 + 默认列 + 默认排序（前后端共用） |
| 2 | `apps/web-admin/src/app/api/admin/tables/schema/route.ts` | GET schema（information_schema.columns） |
| 3 | `apps/web-admin/src/app/api/admin/tables/data/route.ts` | GET data（白名单表 + 白名单列 + 参数化） |
| 4 | `apps/web-admin/src/app/admin/tables/page.tsx` | 服务端组件：拉 schema → 传给客户端 |
| 5 | `apps/web-admin/src/app/admin/tables/AdminTablesClient.tsx` | 客户端：tabs + 列设置 + 排序 + 搜索 + 分页 |
| 6 | `apps/web-admin/src/app/admin/db/page.tsx` | 顶部加「🗂 数据表」跳转 |
| 7 | `apps/web-admin/src/app/page.tsx` | admin 首页加「🗂 数据表浏览」卡片 |
| 8 | `docs/dev-process/features/admin-tables.md` | 验收 + 衔接记录 |
| 9 | `docs/dev-process/current-focus.md` | 当前迭代轮次状态 |

**关键设计**：
- 白名单表名（zod enum）+ 白名单列名（information_schema 动态拉）→ 防 SQL 注入
- limit 1-500（zod max）→ 防爆
- q 跨所有列 `::text ILIKE`（timestamp/numeric 安全转 text）
- 主键列加粗高亮 + 空值显 `—`（灰色）
- 客户端状态：visibleCols / orderedCols / sort / page / search
- 切 tab 时 setData(null) 强制空白 → 加载中 → 新数据 三态干净切换

### 验证（curl e2e 10/10 通过）

```bash
# 4 表都能加载
curl '...?table=recorders&limit=3'    → total: 14
curl '...?table=environments&limit=3'  → total: 19
curl '...?table=tasks&limit=3'        → total: 121
curl '...?table=videos&limit=3'        → total: 560
# 排序 / 分页
curl '...?table=tasks&sort=task_id&order=asc'  → 第一行 task_id=1_11a6724f...
curl '...?table=tasks&limit=5&offset=10'       → 第 11 行
# 跨列搜索
curl '...?table=tasks&q=水龙头' → total: 23
curl '...?table=videos&q=op8'   → total: 29
# SQL 注入兜底
curl '...?sort=__DROP__'        → sort 回退到 scan_date
curl '...?table=videos; DROP'   → 422 VALIDATION
curl '...?limit=99999'          → 422 VALIDATION (limit ≤ 500)
```

### 修复（commits ed33c4c / ca032e9 / 7040fac）

| Commit | Bug | 根因 | 修法 |
|---|---|---|---|
| ed33c4c | `Encountered two children with the same key, ''` | `String('' ?? i)` 不会回退到 i（`''` 不是 nullish）| primaryKey 缺失/空 → `row-${i}`；否则 `row-${pkVal}` |
| ca032e9 | 切 tab 后顶部 undefined 行 + 跨 tab 重复 key | 旧 data 还在 + 新列已就位 → row[colName] undefined | activeKey 变时 setData(null) + 表名 key 前缀隔离 |
| 7040fac | React 19 严格模式 dev 双渲染仍报 duplicate key | primaryKey 派生 key 不够稳 | `e${dataEpoch}-${activeKey}-r${i}` 三层兜底（useRef 计数器 + 行 index + 表名） |

### 学到

- **React 19 严格模式 dev 双渲染**会让同一次 fetch 的两个 `<tr>` 共享派生 key → 必须用单调计数器
- **空字符串不是 nullish**：`'' ?? fallback` 返回 `''` 不是 `fallback`，一定要 `=== ''` 显式判断
- **跨 tab 切换**要清 data，否则旧 tab 的行用新 tab 的列渲染 → undefined 单元格
- **数据库表 primary key 唯一** ≠ React 渲染唯一（dev 模式是另一回事）
- `data?.rows.map((row, i) => <tr key={`r${i}`}>)` 永远安全；用业务 key 作 React key 仅在数据完全静态时安全

### 下一步

- 录制员前端：浏览器内编辑 video.recorder_id / task_id / env_id / uploaded（写入必经 dry-run → 确认 → commit）
- 按录制员聚合总时长统计（柱状图 + CSV 导出）
- AI 工具流在录制员前端的封装（点「让 AI 批量补」→ dry-run 弹 diff → commit）

---

## 2026-07-13 — /admin/progress 实时开发进度仪表盘

### 实现

| # | 文件 | 作用 |
|---|---|---|
| 1 | `apps/web-admin/src/app/api/dev/progress/route.ts` | GET 进度：解析 features.md + project_status.md checkbox + git log 最近 10 commits |
| 2 | `apps/web-admin/src/app/admin/progress/page.tsx` | 服务端组件壳 |
| 3 | `apps/web-admin/src/app/admin/progress/ProgressClient.tsx` | 客户端渲染：总进度条 + Phase 卡片 + commits 时间线 + 30s 自动刷新 |
| 4 | `apps/web-admin/src/app/admin/db/page.tsx` | 加「📊 开发进度」跳转链 |
| 5 | `apps/web-admin/src/app/page.tsx` | admin 首页加卡片 |

**关键设计**：
- 数据源 = `docs/features.md` + `docs/project_status.md` + `git log`，**不读业务表** → 与 `/admin/tables` 完全隔离
- 总进度条三色：绿（完成）/ 黄（进行中）/ 灰（待开始）
- 完成一项开发只需把 `- [ ]` 改成 `- [x]`，30s 后页面自动绿色

### 验证（curl e2e）

```bash
curl /api/dev/progress → HTTP 200 · 2292 bytes
  features.totals: { done: 37, inProgress: 0, pending: 23, total: 60 }
  features.phases: 14
  status.totals:   { done: 8, inProgress: 0, pending: 0, total: 8 }
  status.phases:   1
  commits: 10
  latest: a666b41 - docs(wcs): 维护 /admin/tables 落地 + 3 个 React 19 fix
curl /admin/progress → HTTP 200 · 32269 bytes
```

### 修复（bug 排查 4 次 commit）

| 尝试 | 路径 | 结果 |
|---|---|---|
| 1 | `path.resolve(cwd, '../../..')` | 解析到 `claudecode/`（少一层）— ENOENT |
| 2 | `path.resolve(__dirname, '../../../../')` | 编译后 __dirname = .next 路径，不可预测 |
| 3 | `path.resolve(__dirname, '../../../../../')` | 同上，Next App Router 编译改了 __dirname 解析 |
| ✅ 4 | `findRepoRoot()` 上溯 cwd 找 `docs/features.md` 标记 | 稳定工作 |

### 学到

- **Next.js App Router 编译后 route.ts 的 `__dirname` 不可靠**——会被替换为 .next 编译目录
- 用 `process.cwd()` + 上溯找标记文件是更稳的定位 monorepo 根的方案
- 「实时进度看板」替代长 plan 文件：HTML 自动从 docs 解析 checkbox，开发节奏更轻

### 下一步

- 录制员前端（video.recorder_id / task_id / env_id 编辑）
- stats 页增加可视化（recharts 接入）

---

## 2026-07-14 — /admin/tables 批量编辑（videos 4 字段）

### 实现

| # | 文件 | 作用 |
|---|---|---|
| 1 | `apps/web-admin/src/app/api/admin/tables/bulk/route.ts` | POST 批量更新（默认 dry-run，`?commit=true` 真改） |
| 2 | `apps/web-admin/src/app/admin/tables/BulkEditDrawer.tsx` | 批量编辑抽屉（字段选 + 预览 + 确认） |
| 3 | `apps/web-admin/src/app/admin/tables/AdminTablesClient.tsx` | 加 checkbox 列 + 选中条 + 抽屉触发 |

**关键设计**：
- 字段白名单 per-table：videos 4 字段可改；tasks/recorders/environments 拒绝批量（必须走专用 CRUD）
- WHERE `path = ANY($1::text[])` + max 500 行/次
- dry-run 返回 `{ affected, sampleBefore: 3行BEFORE, sql }`
- 抽屉流程：选字段 → 输入新值 → 「预览」→ 看到 SQL + 抽样 → 「确认提交」
- 选中条：仅 videos tab 显示；切 tab / fetch 成功 / 列变化时清空选中

### 验证

```bash
# dry-run 真实路径
POST /api/admin/tables/bulk
{"table":"videos","pks":["/media/..."],"updates":{"recorder_id":"C05"}}
→ 200 · {mode: "dry-run", affected: 0, sql: "UPDATE public.videos..."}

# 字段白名单拦截
POST {"updates": {"duration_sec": 999}}  → 403 FORBIDDEN

# 字典表拒绝批量
POST {"table": "tasks", ...}  → 403 FORBIDDEN
```

### 修复（E24）

| 现象 | 根因 | 修法 |
|---|---|---|
| `could not determine data type of parameter $1` | countSql 引用 `$2`（SET 子句占用 `$1`）但 params 传 `[pks]` 长度 1 | 拆出独立 `pkWhere = "path" = ANY($1::text[])"`，countSql/sample 用独立 $1，UPDATE 用共用 params |

### 学到

- **PG 参数化查询**：传 `params` 数量必须 ≥ SQL 占位符最大编号；未使用的占位符也会报「could not determine data type」
- 批量写 UI 范式：dry-run preview → 用户确认 → 提交，三步分离，把"不可逆"挡在最后
- 切 tab/fetch 成功必须清选中态（防 pk 漂移导致误改）

### 下一步

- 录制员端：`/devices` 真实设备 Adapter 扫描（先用 DjiGoproDcim 最简单）
- stats 页 recharts 可视化
- 录制员端手机适配（PWA）

---

## 2026-07-14 — frameforge 上传参数字段调研 + v1 migration + uploader 3 页面

### 调研

| 来源 | 关键字段 |
|---|---|
| frameforge `vendorVideos` | countryCode / region / recorderName / sceneCategory / sceneSubcategory / sceneCustomLabel / notes / captureMode / folderName / storageProvider / fileSizeBytes / fps / frameCount |
| frameforge `vendorTaskBoxes` | scenario / taskDescription / environmentDescription / operatorName / captureMode / status |
| frameforge `vendors` | userId / companyId / role / ndaSignedAt 等（NDA 流程，FrameForge 暂不需要） |

### v1 migration (packages/db-schema/src/migrations/v1_frameforge_fields.sql)

```sql
ALTER TABLE public.videos ADD COLUMN country_code / region / folder_name / storage_provider
                          / file_size_bytes / fps / frame_count;
ALTER TABLE public.environments ADD COLUMN country_code / region / scene_custom_label;
CREATE INDEX videos_country_idx / videos_region_idx / videos_storage_idx / environments_country_idx;
```

**14/14 ALTER OK**（每条 20-50ms），无破坏。`/api/admin/db/migrate` 新增：白名单关键字（ALTER TABLE / CREATE INDEX / CREATE TABLE / CREATE TYPE）+ dry-run preview + 自动跳过已存在。

### uploader 3 页面 + 3 API

| 页面 | API | 写入表 |
|---|---|---|
| `/login` | `/api/uploader/me` GET/POST | ff_users（dev: cookie）|
| `/devices` | `/api/uploader/devices` GET/POST | public.videos INSERT（path 唯一，ON CONFLICT DO NOTHING）|
| `/tasks` | `/api/uploader/tasks` GET/POST | public.videos UPDATE task_id |

**所有写入强制 dry-run preview**（plan2 D1 写操作纪律）：POST 默认 dryRun=true，?commit=true 真改。

### 验证

```bash
# 4 设备 + 19 envs + 14 recorders 列表
GET /api/uploader/devices → 200 · devices[4] + environments[19] + recorders[14]

# 录制员身份（dev 模式）
GET /api/uploader/me → { signedIn: false, recorderId: null }

# dry-run 字段校验
POST /api/uploader/devices {envId: "E001"...} → 422 FORBIDDEN（env_id 不存在）
```

### 修复

| 现象 | 修法 |
|---|---|
| 3 个 uploader 页面 500 — `You're importing a component that needs useEffect` | 加 `'use client'` directive（之前漏掉）|
| `@clerk/nextjs/server` import 失败 | uploader 没装 Clerk；改为 cookie 模式（dev）|

### 学到

- **'use client' directive 必加**：任何文件用 `useState` / `useEffect` 都必须在第一行
- **frameforge 字段映射**：场景类用 `environment.scene` / `environment.environment` 老字段；新增字段用 ADD COLUMN 不破坏老行
- **dev mode cookie 模式**：未装 Clerk 时用 `ff_dev_recorder=xxx` cookie 模拟登录状态

### 下一步

- uploader Step 1/2/3 真实实现（接 4 Adapter + ffmpeg + COS STS）
- admin 端 `/devices` `/tasks` `/recorders` 专用 CRUD 页面

---

## 2026-07-15 — v2 表单结构事实层固化 + 4 张 v2 表落库

### 背景

调研 `docs/前端调试参考/`（4 个 HTML 片段：location0714 / operator0714 / 上传页面0714 / 任务页面0714）后，确认**ff 新表单**和 dr / public.* 老旧模型完全不同。要同时满足：

- 培训员 / 管理员在 admin 录入 operator / location / scene
- 录制员在 uploader 选 / 建 operator / location / scene（双端口都可填）
- videoupload 表单必须从 scene 白名单选，确保 Playwright 上传按钮不会选错

### 实现

| # | 文件 | 作用 |
|---|---|---|
| 1 | `docs/v2-forms-spec.md` | **v2 表单结构事实层**。5 张表字段、B/A/S 必填分类、FK、zod 校验点、CHECK 约束、业务守门员。单一事实源，所有冲突以此为准 |
| 2 | `packages/db-schema/src/migrations/v2_frameforge_v2_forms.sql` | 21 条 SQL：4 张表 + 14 索引 + CHECK |
| 3 | `apps/web-admin/src/app/api/admin/db/migrate/route.ts`（已存在） | 跑 v2 SQL（dry-run → commit）|
| 4 | `wcs-manifest.yaml` | `doc_index.v2_forms_spec` 加一行（manifest 是事实来源，新文档必须先注册）|

### v2 表单结构定稿（5 条核心规则）

| 规则 | 内容 |
|---|---|
| **R1 D2 业务键** | 每张表必含 `business_key text UNIQUE NOT NULL`，面向业务的稳定键 |
| **R2 A 类** | schema `NOT NULL DEFAULT`，机械约束（合规硬要求 / 系统状态字段）|
| **R2 B 类** | schema nullable，业务接口 zod `.min(1)` 强校验（前端 `*` 标记）|
| **R3 审计三件套** | `is_active + version + created_at + updated_at` 全部保留 |
| **R4 不接 Clerk** | 故意留白。Clerk free 10K MAU 之内不动，`created_by` 不建，未来再加 |

### 4 张表（按业务层级）

| 表 | 业务角色 | 关键 FK / 关系 |
|---|---|---|
| `ff_operators` | 操作员 | 14 字段（含 `consented_to_recording` 合规硬要求）|
| `ff_locations` | 场所 | env_l1(27) + venue_l2(228) + GPS 地址锁定 |
| `ff_scenes` | **dr 已开通 scene 白名单**（Playwright 按钮锁）| 5 元组锁定：env_l1 + venue_l2 + scene_l3 + project_code + capture_mode + accept_status/used_hours 守门 |
| `ff_scene_applications` | **dr 未开通 scene 申请池** | 与 scenes 字段一致 + 4 申请态字段（function_description / dedup_against / approved_scene_id / decided_at）|
| `ff_video_uploads` | 上传有效性 + 状态机 | FK 到 scenes/operators/locations，全部 `ON DELETE RESTRICT`（防丢历史）|

### 验证

```bash
# dry-run
curl -X POST 'http://localhost:3002/api/admin/db/migrate?file=v2_frameforge_v2_forms.sql'
→ 21 statements parsed, 0 illegal keyword

# commit
curl -X POST 'http://localhost:3002/api/admin/db/migrate?file=v2_frameforge_v2_forms.sql&dryRun=false'
→ 21/21 ok, totalMs: 21736
→ 4 CREATE TABLE + 14 CREATE INDEX + 3 CREATE CONSTRAINT 全部成功
```

**0 error, 0 数据漂移**。ff/ff_operators / ff_locations / ff_scenes / ff_scene_applications / ff_video_uploads 共 5 张表进入 PG。

### 学到 / 沉淀

- **事实层先于实现**：`v2-forms-spec.md` 必须先写，5 张表 + 14 索引 SQL 才能引用它的字段名。如果直接动 SQL 不写 spec，未来每改一个字段名就得改 3 个下游（zod / 前端 label / docs），**记录一致性灾难**
- **业务必填 vs 系统必填** 是两个不同的概念。A 类（机械）必须 schema 兜底；B 类（流程）schema 放空、业务接口 zod 拦截。混在一起就出现「要么插不进表 / 要么上传按钮按下去才发现空了」的两难
- **WCS 自迭代规则 4** 实测：新增文档必须先改 `wcs-manifest.yaml` 的 `doc_index`。这次先改 manifest、再建 v2-forms-spec，没有违反
- **行业约定调研后再设计**：直接读 `docs/前端调试参考/` 的真实字段（HTML 片段），不脑补。这次硬性纪律保证字段定义跟前端实际一致

### 下一步

- **新对话**：4 张 v2 表的占位页（admin + uploader 双端口）
- doc-process/clerk-bootstrap-plan.md（记 Clerk 接入预算 + checklist，等真用上）
- 第一个 phase 2 图床接入：`ff_scenes.environment_photo_url` 上传接口

---

## 2026-07-15 — /admin/operators 端到端闭环（突破 4 占位绿框）

### 背景

首版 4 个 v2 表单占位页（绿框 + 字段表 + 链接进首页）已完成（commit `9f1f02f`）。
**新需求**：要做「具体的页面」，不要只占位。**先做 1 张做完整闭环**作为模板，其余 3 张 + upload 沿用同模式。

用户决策（AskUserQuestion 2026-07-15）：

| 决策 | 选项 |
|---|---|
| 起步线 | 先 admin operators（最简、零 FK）|
| L1/L2/L3 选项来源 | 硬编码到 TS 常量（`packages/shared/src/constants/v2-options.ts`）|
| list 视图 | 简单：一次拉全部，前端过滤 |

### 实现

| # | 文件 | 作用 |
|---|---|---|
| 1 | `packages/shared/src/constants/v2-options.ts`（新）| L1(27) + L2(20 高频) + L3(空) + 6 套枚举（HAND / GENDER / AGE_RANGE / CAPTURE_MODE / SCENE_STATUS / SCENE_ACCEPT_STATUS / SCENE_SOURCE / APPLICATION_STATUS / SOURCE_FORMAT / STORAGE_PROVIDER）|
| 2 | `packages/shared/src/schemas/v2-forms.ts`（新）| 5 个 zod schema：OperatorCreateSchema / LocationCreateSchema / SceneCreateSchema / SceneApplicationCreateSchema / VideoUploadPreviewSchema / VideoUploadCommitSchema |
| 3 | `packages/shared/src/schemas/index.ts` | 加 `export * from './v2-forms'` |
| 4 | `packages/shared/package.json` exports | 加 `./constants/v2-options` 子路径 |
| 5 | `apps/web-admin/src/app/api/admin/operators/route.ts`（新）| GET 全表 is_active=true；POST zod 422 + business_key server-gen（`op_<slug>_<8hex>`，3 次查重退避）+ dry-run → commit 两步 |
| 6 | `apps/web-admin/src/app/admin/operators/page.tsx`（重写）| list 视图（搜索 + showInactive toggle + 表格 9 列）+ 新建表单 Step 1（9 字段）+ Step 2（dry-run 预览，含 SQL preview 折叠）+ Confirm 按钮 → 提交后回列表 + toast |

### 验证（联调全部走通）

```bash
# GET 列表
curl http://127.0.0.1:3002/api/admin/operators
→ {"ok":true,"data":{"rows":[…],"total":1}}

# POST dry-run
curl -X POST 'http://127.0.0.1:3002/api/admin/operators?dryRun=true' \
  -d '{"alias":"op-test-01","name":"测试操作员",...,"consented_to_recording":true}'
→ {"mode":"dry-run","business_key":"op_op_test_01_02ea03a1","sql_preview":"INSERT INTO …"}

# POST commit
curl -X POST 'http://127.0.0.1:3002/api/admin/operators?dryRun=false' \
  -d '{"alias":"op-test-01",...}'
→ {"mode":"commit","row":{"id":"6e28ce3e-…","business_key":"op_op_test_01_31459139","version":1,...}}

# POST zod 422
curl -X POST 'http://127.0.0.1:3002/api/admin/operators?dryRun=true' -d '{"alias":"x","name":""}'
→ 422 + fieldErrors { name, hand, gender, age_range, job_role, role_experience, consented_to_recording }
```

`pnpm typecheck` 通过。**0 error**。

### 学到 / 沉淀

- **business_key server-gen**：A 类（NOT NULL）但 zod 不强校验 → 走 server-gen（`op_<slug>_<8hex>`），3 次查重避冲突。**好处**：用户少填一个字段，**坏处**：用户无法选择有意义的 key（如 `opsample`）。phase 1.1 可以加 `?businessKey=xxx` override
- **`z.literal(true)` + boolean state 的矛盾**：表单 state 需要 `boolean`（用户取消勾选时是 false），但 zod 强校验必须 `true`。解决：定义 `FormState = Omit<OperatorCreate,'consented_to_recording'> & { consented_to_recording: boolean }`，提交时 zod 拦截
- **soft-delete 缺失**：当前 API 没有 PATCH/DELETE。测试行 `op_op_test_01_31459139` 在 dev 库保留，DB 直连被 allowlist 拒，无法命令行清。**TODO**：加 PATCH /api/admin/operators/[id]（is_active toggle）+ 列表行内小按钮
- **Phase 0 → 1 切换**：「占位 → 真实」是质变。占位只画绿框；真实页要 zod 422 + dry-run 预览 + commit 确认 + 列表自动重拉 + 错误 toast。**最大单页代码量**（460 行 page.tsx）属合理范围
- **package.json exports 同步**：`./constants/v2-options` 新子路径要显式注册，否则 `import` 找不到。**经验**：每次新建 `src/constants/*.ts` 都同步 `exports` 字段

### 下一步

- **加 PATCH /api/admin/operators/[id]**：is_active toggle + name/alias 改写（避免 DELETE 误操作 + 软删审计）
- **3 张复制模式**：locations（最复杂：L1/L2 真实 select + 地址搜索 phase 2）、scenes（5 元组锁 + 配额）、scene-applications（申请流）
- **uploader /upload 主对话框**：GET /api/uploader/options?kind=scenes|operators|locations + drag-drop preview + 真上传
- **3 个 quick modal 接入 501 → 200**：替换 POST /api/uploader/{operators,locations,scene-applications} 占位
- **测试行清理**：DB 直连权限开后清 `op_op_test_01_31459139`

---

## 2026-07-15 — operators 3 用户反馈修（删 email / 侧抽屉 / 中文乱码）

### 反馈

| # | 反馈 | 根因 |
|---|---|---|
| 1 | 表格里中文显示为 `���Բ���Ա` | bash on Windows 把 UTF-8 中文转 GBK 字节后才发 curl，Node.js 当 UTF-8 解析失败，存进 PG 的 bytes 是无效 UTF-8 + 残存 GBK |
| 2 | 新建时看不到现有行 | 3 态视图（list / form-fill / form-dry-run）切换时 form 把 list 整个换掉 |
| 3 | 不需要 email 字段 | v2-forms-spec §1.2 email 标 N，本期不上 form |

### 实现（commit `a151bd2`）

| 修复 | 文件 | 关键 |
|---|---|---|
| 1. 中文编码兜底 | `apps/web-admin/src/lib/db.ts` | pool `options` 加 `-c client_encoding=UTF8` |
| 2. 侧抽屉布局 | `apps/web-admin/src/app/admin/operators/page.tsx` | header + toolbar 顶部；主区 2 栏（左 list flex-1 / 右抽屉 480px）；list 始终可见；工具条加 active 计数 + 上一 alias 提示 |
| 3. 删 email | `packages/shared/src/schemas/v2-forms.ts` + `apps/.../page.tsx` + `apps/.../route.ts` | zod 删 email 字段；form 删 email 输入框；row 拼装删 email |
| 4. PATCH/DELETE | `apps/.../api/admin/operators/route.ts` | PATCH `?id=` 改 alias/name/hand_size/is_active（乐观锁 version+1）；DELETE `?id=` 软删（is_active=false） |
| 5. 行内下架 | `page.tsx` | 表格操作列「下架」按钮 → DELETE |

### 验证

```bash
# 中文编码（用 file 走 UTF-8）
echo '{"name":"张三",...}' > op.json
curl -X POST --data-binary @op.json 'http://127.0.0.1:3002/api/admin/operators?dryRun=false'
→ {"row":{"name":"张三","business_key":"op_op_zhangsan_b87c3225",...}}   # ✅ 中文正确

# 软删
curl -X DELETE 'http://127.0.0.1:3002/api/admin/operators?id=6e28ce3e-...'
→ {"row":{"id":"6e28ce3e-...","is_active":false,"version":2}}   # ✅ version+1 乐观锁

# 列表（含下架）
curl 'http://127.0.0.1:3002/api/admin/operators?includeInactive=true'
→ 1 active + 1 inactive
```

`pnpm typecheck` 0 error。

### 学到 / 沉淀

- **PowerShell / Git Bash 编码锅**：在 Windows 上用 curl 写中文，shell 会按系统 codepage（GBK）转换。**解决**：把 JSON 写到文件（`echo '{...}' > op.json` + `file op.json` 验 `JSON text data`），再 `curl --data-binary @op.json`。或 `Content-Type: application/json; charset=utf-8` 强制声明
- **pool client_encoding 兜底**：就算 shell 转换错，pg client 显式声明 UTF-8 也能挡住。**防御性深度**：DB 端 server_encoding 是 UTF-8，client 显式声明一致最稳
- **「新建时看不到现有行」= 表单设计反模式**：用户需要边填边对照（看现有 alias 编号 / 看是否已存在同名 / 看上次填的值）。**模式**：侧抽屉 / 模态 / 列表 + 详情侧栏，而不是全屏切换
- **Next 15 dev mode dynamic [id] 路由偶发 500**：「Jest worker encountered 2 child process exceptions」— dev 编译 worker 在动态路由上卡死。**绕过**：用 `?id=` 查参代替 `[id]` 子路由。生产 build 不会出问题
- **dev_log 文档纪律**：用户反馈的「3 个问题」也要按「问题→根因→修复→验证」4 段写，下次遇到类似问题直接对号入座

### 下一步

- **/admin/locations**（最复杂：L1=27 真实 select + L2=228 cascade + 地址搜索 phase 2 + GPS 锁定）
- **/admin/scenes**（5 元组锁 + 配额管理 + accept_status 守门员）
- **/admin/scene-applications**（申请流：draft → submitted_to_dr）
- **uploader /upload** 主对话框（接 GET options + drag-drop preview + 真上传）
- **3 个 quick modal 501 → 200**：直接复制 operators 的 API 模式即可
- **测试行 op_op_test_01_31459139** 软删保留（数据已 inactive，不再显示在 active 列表）

---

## 2026-07-15 — step1-scan 真实功能 + 完整生产部署手册

### 背景

用户要求 ff uploader 端 (3001) step1-scan 真实实现（手机/电脑都能用），并部署到腾讯云 CVM（自有 `vps.example.com`）让另一台手机测试。

### 实现（commit `1d4c3fe` + `5a826a5`）

**step1-scan 真实功能**：

- 4 设备卡单选（DjiGoPro / HeadMountedUmi / GoproSessionMcap / GenericAviRecording）
- 「选择文件夹」按钮 → `<input type="file" webkitdirectory multiple>`（手机/Android Chrome/iOS Safari 13.4+ 全支持）
- JS 遍历 FileList，按 `webkitRelativePath` 建虚拟目录树
- 4 套 pattern 匹配：
  - DJI: `DCIM/*.{mp4}`（含嵌套 `DCIM/100GOPRO/`）
  - HMD: `hmd/session_*/{*.hmd}`（session 目录）
  - MCAP: `data/session_*/{*.mcap}`
  - Generic AVI: `recordings/<日期>_<ts>/*.{avi}`（多 part）
- 候选列表（relPath / 文件数 / 总大小 / 多 part 标记）多选
- 下一步 → `localStorage` 存 metadata + 跳 /step2-preview

**联调**（unit test 4 设备 pattern 匹配）：

```
[dji]   DCIM/100GOPRO (2 files) + DCIM/101GOPRO (1)
[hmd]   hmd/session_2025_07_15_14_30 (2) + hmd/session_2025_07_15_15_45 (1)
[mcap]  data/session_2025_07_15 (1)
[generic-avi] recordings/2025-07-15_14-30-22 (3) + recordings/2025-07-15_15-45-01 (1)
```

README.txt + misc/random.mp4 干扰项正确忽略。

### 部署决策（commit `5a826a5`）

| 决策 | 选项 |
|---|---|
| 云 | 腾讯云 CVM（OpenCloudOS 9 + 宝塔）|
| IP | `vps.example.com` |
| 部署路径 | `/www/wwwroot/projects/ff`（宝塔默认）|
| 域名 | 已有（用户未提供具体值）|
| 规模 | 生产长期（web + worker + Redis + PG）|
| PG | 复用 8.x 主机已有 ff 库（plan2 v2 migration 5 张表已建）|
| Redis | 服务器本地装（dnf install redis）|
| CI/CD | **GitHub Actions private repo 免费 2000 分钟/月，0 成本** |
| GitHub repo | `https://github.com/cosmowind/ff.git` |

### 7 个新文件

| 文件 | 用途 |
|---|---|
| `docs/deploy-production.md` | 全套部署手册（拓扑 / 准备 / DNS / HTTPS / CI / 健康检查 / 故障排查 / 回滚）|
| `docs/DEPLOY-CHECKLIST.md` | 用户逐步执行清单（11 步：服务器 → DNS → HTTPS → PG → GitHub → deploy key → 首次部署 → nginx → secrets → 触发 → 跨手机测试）|
| `.github/workflows/deploy.yml` | 2 步：build (typecheck + 4 build) → SSH 部署（pull + install + build + pm2 reload + 3 路健康检查）|
| `deploy/deploy.sh` | 服务器端 pull 脚本（git reset + pnpm install + build + psql IF NOT EXISTS + pm2 reload）|
| `deploy/ecosystem.config.cjs` | pm2 3 进程配置（web-uploader 3001 / web-admin 3002 / worker 3010）|
| `deploy/nginx-ff.conf` | 443 反代模板（client_max_body_size 10G / WebSocket / gzip / 静态缓存 365d / 安全头）|
| `.env.production.example` | 生产 env 模板（DATABASE_URL / REDIS_URL / 域名 / Clerk / COS），真值 .env 不入仓 |

### 纪律

- `.env` / `.env.production` 已在 `.gitignore`，私钥走 GitHub Secrets
- deploy 脚本走 `IF NOT EXISTS` 兜底，可重复跑
- 健康检查 3 路（web-uploader / web-admin / redis）任一失败 → deploy 失败
- 客户端直传 COS 暂未启用（phase 2 接），先落本地磁盘
- Clerk 走 dev 模式（占位 keys 时自动跳过），用户申请真 keys 后自动启用

### 日常 dev 流

```bash
# 本地
git commit -m "..."
git push origin main
# → 1-2 分钟后 https://ff.your-domain.com 自动生效
```

### 下一步

- 等用户在服务器跑 `DEPLOY-CHECKLIST.md` 11 步
- push to main 触发第一次自动 deploy
- 跨手机测 step1（4 设备 pattern 匹配 + 手机 webkitdirectory）
- 域名证书 Let's Encrypt 续期监控（宝塔自动 / certbot timer）
- phase 1.1：COS 真接（client 直传 STS 凭证）
- phase 1.2：4 设备 Adapter 真 worker 实现（ffmpeg / hmd-decoder / mcap-extract）
- phase 2：图床（ff_scenes.environment_photo_url）+ Clerk 接入
