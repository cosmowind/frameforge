# Project Status — FrameForge (plan2)

> 最近更新：2026-07-15（v2 表单结构事实层固化 + 4 张 v2 表落库）

## 当前阶段

| 字段 | 值 |
|---|---|
| 项目 | FrameForge — 视频录入员 SOP 工具 |
| Plan | **plan2 v2**（实时进度看板：`/admin/progress`） |
| Phase | **0 — 工程骨架** ✅ 完成 + **1 — Uploader MVP** 进行中 |
| 开始日 | 2026-07-11 |
| 当前版本 | `0.2.0` |
| 最新 commits | v2-forms-spec.md 事实层 + 4 张 v2 表（operators/locations/scenes/scene_applications/video_uploads）|
| 下一里程碑 | 4 张 v2 表的 admin/uploader 双端口占位页（开新对话做） |
| 业务规模锚定 | **135 TB/月** |

## 已落实（plan2 Phase 0.2-0.9 ✅）

- [x] **0.2** pnpm workspace 根 + Next.js 15 monorepo 骨架
- [x] **0.3** Docker Compose（PG + Redis + web + worker，**含 mem_limit + cpus**）
- [x] **0.4** Drizzle schema — **15 张表 ff_ 前缀**（含 device_types + scf/puller/audit）
- [x] **0.5** Clerk middleware（@clerk/nextjs 占位）→ Phase 1 webhook 同步到 ff_users
- [x] **0.6** `.env` + .gitignore（P6 凭证不入仓）
- [x] **0.7** WCS docs（11 个 = 9 基础 + 3 plan2 新增）
- [x] **0.8** DeviceAdapter 接口定义（packages/shared + 4 实现占位在 packages/adapters）
- [x] **0.9** Phase 0 验收脚本（README + dev_plan）

## 工程产物

| 项 | 路径 | 状态 |
|---|---|---|
| 后端 uploader | `apps/web-uploader/` Next.js 15 | 占位 3 步 + Clerk middleware + `/library/fill` 补全页 |
| 后端 admin | `apps/web-admin/` Next.js 15 | 7 菜单 + `/admin/db` 数据库仪表盘 + `/admin/tables` 4 表浏览器 + `/payroll` + `/stats` + Clerk middleware |
| Worker | `apps/worker/` Node + BullMQ | 4 队列：device-scan / preview / pull / backup |
| 共享 schema | `packages/shared/` Zod + types + utils | ✅ |
| DB schema | `packages/db-schema/` Drizzle 0.31 + 11 enum + 15 表 | ✅ |
| Device adapter | `packages/adapters/` 4 设备 Adapter 接口 + 占位实现 | ✅ |
| Docker infra | `infra/docker/{web,worker}.Dockerfile` 多阶段 | ✅ |
| 容器编排 | `docker-compose.yml` (PG + Redis + bull-board + minio profile + web-uploader + web-admin + worker) | ✅ |
| AI 工具 API | `/api/ai/db/{query,dry-run,commit}` + `tools/ai-cli.ts` | ✅ |
| 数据备份 | `/api/admin/db/backup` + cron 计划 | ✅ |

## 数据库（plan2 §3 全字段）

| 项 | 值 |
|---|---|
| 数据库 DSN | `postgresql://ff:ff@localhost:5432/ff`（开发 / Docker 容器）|
| 数据库 schema | `ff`（与旧 public.* 完全隔离）|
| 数据库表前缀 | `ff_*`（物理命名 `ff.ff_video_records`）|
| 表数 | 15 |
| enum 数 | 11 |
| trigger 数 | 1（D5 scan_date 不可减少）|
| 旧 v1 兼容性 | `ff.video_records`(11 表) 保留为历史，全部更新为 `ff.ff_*` |

## 容器清单（plan2 §9 Phase 0.3）

| 容器 | 镜像 | 端口 | 资源限制 |
|---|---|---|---|
| pg | postgres:16-alpine | 5432 | 1G / 1.0 CPU |
| redis | redis:7-alpine | 6379 | 512M / 0.5 CPU |
| bull-board | mrf1957/bull-board | 3010 (profile) | — |
| minio | minio/minio:2024-05 | 9000/9001 (profile local-s3) | 512M / 0.5 |
| web-uploader | Dockerfile web | 3001 | 512M / 0.75 |
| web-admin | Dockerfile web | 3002 | 512M / 0.75 |
| worker | Dockerfile worker | 3010 (health only) | 1G / 1.0 |

## 未落实（按 plan2 §9 Phase 1-4）

| Phase | 主要工作 |
|---|---|
| 1 | Adapter 4 设备真实实现（HMD decoder 风险高）+ 3 步流程 + localStorage 预填 + SCF 函数 |
| 2 | 3 维表 CRUD + Clerk webhook 同步 + 配额报表 + 审计日志 |
| 3 | 资源包预付费 + 夸克季度备份 + 性能压测 + 备份恢复演练 |
| 4 | Capacitor / SSO / 多档位转码 / K8s 迁移 |

## 业务侧待确认（plan2 §12.2 必填）

- ❓ HMD 格式对接（设备供应商 decoder？）
- ❓ MCAP 文件是否含视频轨道
- ❓ 客户 COS 桶名/地域/凭据
- ❓ 域名 (`ff.example.com` 可申请否？备案主体？)
- ❓ 家用服务器情况（OS / 公网 IP / 带宽 / 硬盘 RAID）
- ❓ 首批录制员数量 + 设备型号清单
- ❓ Generic AVI 单 session 最多几个 AVI？平均时长？
