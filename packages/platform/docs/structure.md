# Structure — FrameForge (plan2)

> 模块职责映射。代码定位时读本文。

## 总览

```
ff/
├── apps/
│  ├── web-uploader/                  Next.js 15（端口 3001，uploader role）
│  │  ├── src/
│  │  │  ├── middleware.ts            Clerk 中间件（uploader role）
│  │  │  ├── app/
│  │  │  │  ├── layout.tsx            ClerkProvider + globals.css
│  │  │  │  ├── page.tsx             4 步 SPA 入口（占位）
│  │  │  │  ├── step1-scan/           Step 1
│  │  │  │  ├── step2-preview/        Step 2
│  │  │  │  ├── step3-fill-upload/    Step 3
│  │  │  │  ├── library/              视频库
│  │  │  │  ├── sign-in/              Clerk 登录
│  │  │  │  ├── sign-up/              Clerk 注册
│  │  │  │  └── api/health/route.ts   Phase 0 health
│  │  │  └── lib/
│  │  │      ├── localstorage.ts      §2.5 预填表单
│  │  │      └── api-client.ts        fetch wrapper
│  │  ├── next.config.ts
│  │  ├── tailwind.config.ts
│  │  └── postcss.config.cjs
│  │
│  ├── web-admin/                     Next.js 15（端口 3002，admin role）
│  │  ├── src/
│  │  │  ├── middleware.ts            Clerk 中间件（admin role）
│  │  │  └── app/
│  │  │      ├── layout.tsx
│  │  │      ├── page.tsx             Dashboard + 7 菜单
│  │  │      ├── device-types/        Phase 1 填 CRUD
│  │  │      ├── recorders/
│  │  │      ├── environments/
│  │  │      ├── products/             嵌套 processes
│  │  │      ├── users/               Phase 1 接 Clerk API
│  │  │      ├── regions/
│  │  │      ├── audit/                ff_audit_logs 查询
│  │  │      ├── sign-in/
│  │  │      └── sign-up/
│  │  └── (配置同 uploader)
│  │
│  └── worker/                        Node 独立进程 + BullMQ
│     ├── src/
│     │  ├── main.ts                  HTTP /health + SIGTERM
│     │  ├── config/env.ts            Zod 校验
│     │  ├── queue/redis.ts           ioredis + buildQueue/Worker
│     │  └── jobs/
│     │      ├── device-scan.ts       Adapter.scan 调度
│     │      ├── preview.ts           ffmpeg/HMD/MCAP
│     │      ├── pull.ts              COS → 本地硬盘
│     │      └── backup.ts            pg_dump
│     └── Dockerfile → infra/docker/worker.Dockerfile
│
├── packages/
│  ├── shared/                         @ff/shared
│  │  └── src/
│  │      ├── constants.ts            4 设备 code + 路由 + 状态机
│  │      ├── types.ts                Clerk claims + API 响应
│  │      ├── schemas/                Zod（common/device/scan/video/metadata）
│  │      ├── adapters/               DeviceAdapter 接口 + 共享类型
│  │      └── utils/
│  │          ├── logger.ts           pino
│  │          └── paths.ts            P3 路径归一化
│  │
│  ├── db-schema/                     @ff/db-schema
│  │  └── src/
│  │      ├── schema.ts               pgSchema('ff')
│  │      ├── enums.ts                11 个 PG enum（ff.* 命名）
│  │      ├── tables/                 15 张表（ff_* 前缀）
│  │      │  ├── ff_device_types.ts  T0
│  │      │  ├── ff_regions.ts
│  │      │  ├── ff_users.ts
│  │      │  ├── ff_recorders.ts
│  │      │  ├── ff_environments.ts
│  │      │  ├── ff_products.ts
│  │      │  ├── ff_processes.ts
│  │      │  ├── ff_devices.ts
│  │      │  ├── ff_video_records.ts  T8 核心
│  │      │  ├── ff_upload_logs.ts
│  │      │  ├── ff_file_assets.ts
│  │      │  ├── ff_quota_snapshots.ts
│  │      │  ├── ff_scf_invocations.ts
│  │      │  ├── ff_puller_runs.ts
│  │      │  └── ff_audit_logs.ts
│  │      ├── migrations/v0_initial_v2.sql
│  │      └── scripts/
│  │          ├── migrate.ts          --stage up|down|status
│  │          └── seed.ts             默认 region + 4 device types
│  │
│  └── adapters/                      @ff/adapters
│     └── src/
│        ├── registry.ts              buildAdapterRegistry()
│        └── device/
│           ├── dji-gopro-dcim.ts     Adapter A（最简单）
│           ├── head-mounted-hmd.ts   Adapter B（HMD 私有格式）
│           ├── gopro-session-mcap.ts Adapter C
│           └── generic-avi-recording.ts   Adapter D（多 AVI）
│
├── infra/
│  └── docker/
│     ├── web.Dockerfile              Next.js 15 多阶段
│     └── worker.Dockerfile           Node + ffmpeg + rclone 多阶段
│
├── docs/                             WCS 11 文档
│  ├── project_status.md
│  ├── structure.md                   ← 本文
│  ├── dev_plan.md
│  ├── dev_log.md
│  ├── error_book.md
│  ├── features.md
│  ├── CODING_STANDARDS.md
│  ├── workflow.md
│  ├── data-dictionary.md             ← 新（plan2 §3 全字段 + ER 图）
│  ├── storage-architecture.md        ← 新（plan2 §6 三层 + SCF）
│  ├── device-adapters.md             ← 新（plan2 §5 Adapter + 扩展）
│  └── prompt.txt
│
├── docker-compose.yml                必用：PG + Redis + web + worker
├── wcs-manifest.yaml                 WCS v2.0 中央索引
├── .env.example                      含 Clerk + COS + SCF + Quark 全字段
├── tsconfig.base.json
├── package.json + pnpm-workspace.yaml
└── README.md
```

## 模块职责速查

| 模块 | 职责 | 防的 bug |
|---|---|---|
| `apps/web-uploader/middleware.ts` | Clerk uploader role gate | F2 路由串扰 |
| `apps/web-admin/middleware.ts` | Clerk admin role gate | F2 |
| `apps/worker/jobs/device-scan.ts` | 调度 4 设备 Adapter.scan() | D10 |
| `apps/worker/jobs/preview.ts` | ffmpeg / hmd / mcap 转码 | M1/M2/M3 |
| `apps/worker/jobs/pull.ts` | CDN 回源 → 本地硬盘 | S1 L2 |
| `apps/worker/queue/redis.ts` | BullMQ 队列 + Worker 工厂 | L2 批次失败不阻塞 |
| `packages/db-schema/scripts/migrate.ts` | 单脚本 --stage up | L1 防 v1→v8 爆炸 |
| `packages/adapters/registry.ts` | 4 设备 Adapter 索引 | D10 插件扩展 |
| `packages/shared/utils/paths.ts` | P3 路径归一化唯一入口 | E18 |
| `packages/shared/schemas/video.ts` | VideoRecord Zod schema | F1 前后端一致 |

## 数据库迁移

```bash
# 第一次（创建 ff schema + 11 enum + 15 表）
pnpm db:migrate

# 查看当前 schema
pnpm db:status

# 重置（手动）── 这会 DROP SCHEMA ff CASCADE
psql $DATABASE_URL -c "DROP SCHEMA ff CASCADE"
pnpm db:migrate && pnpm db:seed
```

## Worker 启动

```bash
pnpm --filter @ff/worker dev
# 监听 :3010（health check）
# BullMQ 4 个队列：device-scan / preview / pull / backup
```
