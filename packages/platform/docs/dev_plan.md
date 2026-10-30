# Dev Plan — FrameForge (plan2)

> 路线图 + 进行中 + 待办。规划任务时读本文。
>
> 完整 plan2 §9 见本仓库的 `docs/dev_plan.md` 全文。

## Phase 状态

| Phase | 内容 | 周期目标 | 状态 |
|---|---|---|---|
| **0** | 工程骨架 | 1-2 周 | ✅ 完成（2026-07-11） |
| 1 | Uploader MVP + 设备适配 | 3-4 周 | ⏳ 在途 |
| 2 | Admin MVP + 健壮性 | 2 周 | ⏸ 待 Phase 1 |
| 3 | 资源包 + 异构优化 | 2 周 | ⏸ 待 Phase 2 |
| 4 | 完整版（Capacitor/SSO/多档位/K8s）| 按需 | ⏸ 待 Phase 3 |

## Phase 0 完工（plan2 §9 0.2-0.9）

- [x] 0.2 pnpm workspace + Next.js 15 monorepo
- [x] 0.3 Docker Compose 必用（PG+Redis+web+worker，含 mem_limit/cpus）
- [x] 0.4 Drizzle 15 张表 ff_ 前缀（含 device_types + scf/puller/audit_logs）
- [x] 0.5 Clerk middleware（@clerk/nextjs 占位，Phase 1 webhook 接 ff_users）
- [x] 0.6 .env + .gitignore 隔离凭证
- [x] 0.7 WCS v2.0 docs（11 个 = 9 基础 + 3 新增）
- [x] 0.8 DeviceAdapter 接口 + Zod schema（packages/shared + packages/adapters）
- [x] 0.9 Phase 0 验收

## Phase 1 — Uploader MVP + 设备适配（plan2 §9 Phase 1）

### Step 0：CI 准备 + Clerk 接入

| 任务 | 验收 |
|---|---|
| Clerk 应用创建 + webhook 配置 | `/api/clerk/webhook` 接 user.created/user.updated 写 ff_users |
| `pnpm dev` 起 uploader/admin/worker 三端 | 5173 端口 |
| Domain + Clerk 公网配置 | production URL 上能登 |

### Step 1：4 设备 Adapter 实现

| 设备 | 工时 | 风险 |
|---|---|---|
| **DjiGoproDcimAdapter** | 2-3 天 | 低 — fluent-ffmpeg 读 metadata 即可 |
| **GenericAviRecordingAdapter** | 2-3 天 | 低 — ffmpeg concat 成熟 |
| **GoproSessionMcapAdapter** | 3-5 天 | 中 — MCAP 提取视频需 ROS 工具链 |
| **HeadMountedHmdAdapter** | 5-10 天 | **高** — HMD decoder 需对接供应商；降级方案：只上传原 .hmd + .json |

### Step 2：3 步流程前端

| Step | 任务 | 验收 |
|---|---|---|
| Step 1 | 选设备 + Adapter.scan() 客户端调用 | 列表显示 session，**不落库** |
| Step 2 | 选 session + Adapter.getPreviewHandle() | DCIM/Generic AVI → `<video>`；HMD/MCAP → worker 转码流 |
| Step 3 | RHF + Zod + localStorage 预填 | 提交后写 ff_video_records + COS STS 直传 |

### Step 3：上传链路

| 任务 | 验收 |
|---|---|
| COS STS 临时凭证 + 前端 cos-js-sdk-v5 multipart | 上传中进度回调 |
| 上传日志 ff_upload_logs（双 target：partner + backup） | 双成功 |
| file_hash 计算在 prepareForUpload 输出之后（D6） | 重复 hash 不重复上传 |

### Step 4：SCF 跨桶同步

| 任务 | 验收 |
|---|---|
| SCF 函数（cos:ObjectCreated:Put 触发） | COS 1 分钟内到客户 COS |
| ff_scf_invocations 审计 | 每次调用有记录 + cost_cny |

### Step 5：Puller（L2 本地硬盘）

| 任务 | 验收 |
|---|---|
| Cron `0 */1 * * *` 拉最新上传到本地 | 本地硬盘出现文件 |
| ff_puller_runs 审计 | 每次 run 有 records_pulled/cost_cny |

### Step 6：监控 + 域名 + HTTPS

| 任务 | 验收 |
|---|---|
| 腾讯云监控 + 飞书 webhook 告警 | 飞书收到测试告警 |
| 域名 `ff.example.com` 备案 + 切换 | HTTPS 强制 301 |
| CDN 加速 + 防盗链 + URL 鉴权 | `cdn.ff.example.com` 200 |

## Phase 2 — Admin MVP + 健壮性

| 任务 | 验收 | 防的 bug |
|---|---|---|
| 7 菜单 CRUD（device-types / recorders / environments / products×processes / users / regions / audit）| 改名不丢数据 | D2/D3/E10 |
| Clerk webhook → ff_users 同步 | 创建用户自动入 ff_users | D8 |
| 用户/区域管理 | 示例市账号看不到示例省 | D7/§10 |
| 配额日报表 | Admin 端看历史 | B1/B2 |
| 审计日志 | 任意修改可追溯 | D4 |
| OpenTelemetry/Sentry/限流（按需）| — | — |

## Phase 3 — 资源包 + 异构优化

| 任务 | 验收 |
|---|---|
| 腾讯云 COS 资源包预付费 | 账单降 30-50% |
| COS 生命周期 30/90/180d 自动转层 | 观察 1 月 |
| 夸克网盘季度备份脚本（rclone） | 手动验证恢复 |
| 性能压测（百 TB/月量级并发） | P99 < 5s |
| 数据归档报表 Admin 端 | 各类存储视频数 + 成本 |

## Phase 4 — 完整版

| 任务 | 说明 |
|---|---|
| PWA → Capacitor 打包 iOS/Android | 移动端原生能力 |
| SSO / OIDC | 企业账号 |
| 多档位转码（480p/720p/1080p） | 按需生成 |
| 深度归档 → 冷存储 | 180d 后切深度归档 |
| K8s 迁移（Compose → Pods/Deployments）| 多节点水平扩展 |
| 新设备适配（Insta360/DJI Mavic）| 复制 Adapter pattern |

## 待用户/业务侧确认（plan2 §12.2 必填）

| 项 | 决策影响 |
|---|---|
| 合作平台 API 能力（URL 拉取？API？） | SCF 跨桶函数实现方式 |
| HMD decoder 由设备供应商提供？ | 影响 Step 1 的 HMD Adapter 优先级 |
| MCAP 文件是否含视频轨道？ | 影响 MCAP Adapter 完整性 |
| 客户 COS 桶名/地域/凭据 | L1 跨桶目标 |
| 域名 + 备案主体 | 上线硬约束 |
| 自建服务器情况（OS / 带宽 / RAID）| Puller 部署模型 |
