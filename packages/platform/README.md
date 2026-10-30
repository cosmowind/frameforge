# FrameForge — 视频录入员 SOP 工具（plan2）

> **核心价值**：降低示例工厂 4 种异构设备（DJI/GoPro / 头环 HMD / GoPro MCAP / Generic AVI AVI）
> 与录制员之间的摩擦；135 TB/月规模；3 步流程（选设备+扫 → 预览 → 填参+上传）。
>
> 详细方案见 `~/

## 技术栈（plan2 §7 D1-D10）

| 层 | 选型 |
|---|---|
| 后端 | **Next.js 15 (App Router + Turbopack)** × 2（uploader + admin 路由）|
| Workers | **Node 独立进程 + BullMQ**（device-scan / preview / pull / backup）|
| 鉴权 | **Clerk SaaS**（Phase 1 webhook 同步 → ff_users）|
| 数据 | **PostgreSQL 16 + Drizzle ORM 0.31**（schema `ff` + 表前缀 `ff_*`，共 15 张表）|
| 缓存/队列 | **Redis 7** + BullMQ |
| 存储 | **腾讯云 COS**（L1 中转 + SCF 跨桶同步到客户 COS）+ **本地硬盘**（L2 Puller）+ **夸克网盘**（L3 季度备份）|
| 容器 | **Docker Compose** 必用（PG + Redis + MinIO + web-uploader + web-admin + worker）|
| 容器化 FC/SCF | SCF 触发器（cos:ObjectCreated:Put → 跨桶复制）|

## 仓库结构

```
ff/
├── apps/
│  ├── web-uploader/        Next.js 15（端口 3001，uploader role）
│  ├── web-admin/           Next.js 15（端口 3002，admin role）
│  └── worker/              Node + BullMQ 4 个队列 consumer
├── packages/
│  ├── shared/              Zod schema + 共享类型 + DeviceAdapter 接口
│  ├── db-schema/           Drizzle 15 张表 ff_ 前缀
│  └── adapters/            4 设备 DeviceAdapter 实现
├── infra/
│  └── docker/              web/worker 多阶段 Dockerfile
├── docs/                   WCS v2.0 docs（11 个）见下方索引
├── docker-compose.yml      必用：PG + Redis + web + worker
├── wcs-manifest.yaml       WCS 中央索引（v2.0）
└── .env.example
```

## 3 步流程（plan2 §2.1）

```
[TF Card / 设备存储]
  ↓ Step 1 选设备 + 扫描（不落库，前端临时缓存）
[Step 1 选设备+扫]
  ↓ Step 2 预览（按 device_type 选用 native/ffmpeg/hmd-decoder/mcap-extract）
[Step 2 预览]
  ↓ Step 3 填参 + 上传（localStorage 预填 → Adapter.prepareForUpload → COS STS 直传）
[Step 3 填参+上传]
  ↓ POST /uploader/videos/import
SCANNED → UPLOADING → UPLOADED → LOCAL_DELETED → ARCHIVED
```

## 4 设备规格（plan2 §5.2）

| code | 设备 | 根目录 | 文件 | 预览策略 | 上传准备 |
|---|---|---|---|---|---|
| `dji-gopro-dcim` | DJI/GoPro | `DCIM/` | `.mp4` | native HTML5 | direct |
| `head-mounted-hmd` | 头环 | `hmd/` | `.hmd` + `.json` | hmd-decoder | extract-hmd |
| `gopro-session-mcap` | GoPro MCAP | `data/` | `.mcap` + `.json` | mcap-extract | extract-mcap |
| `generic-avi-recording` | Generic AVI | `recordings/<date>_<ts>/` | `.avi` × N | native + JS 顺序播放 | concat-avi |

## 快速上手

```bash
# 1. 装 pnpm（已装跳过）
npm i -g pnpm@10.19.0

# 2. 装依赖
pnpm install

# 3. 启基础设施（开发）
cp .env.example apps/web-uploader/.env
cp .env.example apps/web-admin/.env
cp .env.example apps/worker/.env
docker compose up -d         # PG + Redis 容器

# 4. 数据库迁移 + seed（dev 用本地 PG）
pnpm db:migrate             # 11 enum + 15 表
pnpm db:seed                # 默认 region + 4 device types

# 5. 启动 dev
pnpm dev                    # uploader (3001) + admin (3002) + worker (3010)
```

## 文档索引（11 个）

| 路径 | 用途 |
|---|---|
| [wcs-manifest.yaml](wcs-manifest.yaml) | WCS 中央索引（v2.0）|
| [docs/project_status.md](docs/project_status.md) | 当前架构 + 已实现能力 |
| [docs/structure.md](docs/structure.md) | 目录结构 + 模块职责 |
| [docs/dev_plan.md](docs/dev_plan.md) | 路线图 + Phase 0-4 |
| [docs/dev_log.md](docs/dev_log.md) | 实现 + 验证 + 复盘 |
| [docs/error_book.md](docs/error_book.md) | E1-E19 历史根因 + 新缺陷活档 |
| [docs/features.md](docs/features.md) | 已实现能力索引 |
| [docs/CODING_STANDARDS.md](docs/CODING_STANDARDS.md) | 代码规范纲领 |
| [docs/workflow.md](docs/workflow.md) | 质量门禁 + 提交流程 |
| [docs/data-dictionary.md](docs/data-dictionary.md) | **新** 15 张表字段详解 + ER 图 |
| [docs/storage-architecture.md](docs/storage-architecture.md) | **新** COS + 本地硬盘 + 夸克 三层 + SCF |
| [docs/device-adapters.md](docs/device-adapters.md) | **新** 4 设备 Adapter 实现 + 扩展指南 |
| [docs/prompt.txt](docs/prompt.txt) | 用户原始需求 |

## 与 v1（Fastify + self-JWT）的关键差异

| 维度 | v1 | **v2（当前）** |
|---|---|---|
| 后端 | Fastify 4 | **Next.js 15 App Router** |
| 鉴权 | 自实现 JWT | **Clerk SaaS** |
| 流程 | 4 步 | **3 步** |
| 存储 | 单 COS | **COS + 本地 + 夸克**（+SCF 事件驱动）|
| 设备 | 通用 MP4 | **4 设备 + 可扩展**（D10）|
| 表前缀 | 无 | **ff_** |
| 表数 | 11 | **15**（+ device_types / scf_invocations / puller_runs / audit_logs）|
| Docker | 可选 | **必用** |
| 队列 | 无 | **BullMQ** |
| 业务规模 | 1 TB/月 | **135 TB/月** |

> v1 已完整归档到 `../ff-v1-archive/`（独立 git 仓库 + 3 commits）

## Phase 路线图（plan2 §9）

- **Phase 0 — 工程骨架**（1-2 周，当前）
- **Phase 1 — Uploader MVP + 设备适配**（3-4 周）
  - DjiGoproDcim / GenericAviRecording / GoproSessionMcap Adapter 先做
  - HeadMountedUmi 待 HMD decoder 确认
- **Phase 2 — Admin MVP + 健壮性**（2 周）
- **Phase 3 — 资源包 + 异构优化**（2 周）
- **Phase 4 — 完整版**（按需：Capacitor 移动端 / SSO / 多档位 / 冷归档 / K8s）

## License

MIT
