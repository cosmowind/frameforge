# Features — FrameForge (plan2)

> 已实现能力索引。评估进度时读。

## Phase 0（当前）— 工程骨架

### 工程骨架

- [x] pnpm monorepo workspace
- [x] TypeScript strict + shared tsconfig.base.json
- [x] ESLint + Prettier 配置占位
- [x] `.gitignore`（含 runtime/、.debug/、node_modules/、dist/、.env、Clerk）

### Docker Compose 必用

- [x] PG 16 + Redis 7 + bull-board (profile) + MinIO (profile local-s3)
- [x] web-uploader + web-admin + worker 三个服务，含 mem_limit + cpus + healthcheck
- [x] 资源限制：PG 1G/CPU 1.0, Redis 512M/0.5, web-* 512M/0.75, worker 1G/1.0
- [x] named volumes（pg-data, redis-data, minio-data）持久化

### 后端 Next.js 15

- [x] `apps/web-uploader` 端口 3001，App Router，4 步 + sign-in/up + health route
- [x] `apps/web-admin` 端口 3002，App Router，Dashboard + 7 菜单 + sign-in/up
- [x] Clerk middleware（uploader / admin role gate）
- [x] Tailwind 3 + globals.css
- [x] Build 标记戳（layout.tsx head meta name="build"）
- [x] localStorage 预填 helper（§2.5 核心 UX 在 Step 3 启用）

### 数据库（Drizzle 0.31）

- [x] **15 张表 ff_ 前缀**（含 ff_device_types + ff_scf_invocations + ff_puller_runs + ff_audit_logs）
- [x] **11 个 PG enum**（ff_app_role / session_naming / preview_engine / upload_prep / lifecycle_state / upload_target / upload_adapter / upload_status / cos_storage_class / scf_trigger / run_status）
- [x] **DB trigger**：ff_video_records scan_date 不可减少（D5）
- [x] CHECK 约束：file_size_bytes > 0 / score 1-5 / original_format ∈ {mp4,hmd,mcap,avi} / is_multi_part 与 part_count 一致
- [x] 单脚本 migrate.ts --stage up|status

### Worker（BullMQ 4 队列）

- [x] worker-device-scan（Adapter.scan 调度 + 写 ff_video_records）
- [x] worker-preview（ffmpeg/HMD/MCAP 转码）
- [x] worker-pull（CDN → L2 本地硬盘）
- [x] worker-backup（pg_dump 占位）
- [x] BullMQ prefix 隔离（ff:）
- [x] HTTP /health 监听 :3010
- [x] SIGTERM graceful shutdown

### DeviceAdapter（4 设备）

- [x] `DjiGoproDcimAdapter`（最简单，MP4 直传）
- [x] `HeadMountedHmdAdapter`（HMD 私有格式 placeholder）
- [x] `GoproSessionMcapAdapter`（MCAP placeholder）
- [x] `GenericAviRecordingAdapter`（多 AVI placeholder）
- [x] Registry 通过 `buildAdapterRegistry()` 索引

### WCS v2.0 文档

- [x] wcs-manifest.yaml 中央索引
- [x] 9 基础 docs (project_status/structure/dev_plan/dev_log/error_book/features/CODING_STANDARDS/workflow/prompt)
- [x] 3 plan2 新增 docs（data-dictionary / storage-architecture / device-adapters）
- [x] README + .env.example + LICENSE

### 数据库（Drizzle 0.31）

- [x] **15 张表 ff_ 前缀**（含 ff_device_types + ff_scf_invocations + ff_puller_runs + ff_audit_logs）
- [x] **11 个 PG enum**（ff_app_role / session_naming / preview_engine / upload_prep / lifecycle_state / upload_target / upload_adapter / upload_status / cos_storage_class / scf_trigger / run_status）
- [x] **DB trigger**：ff_video_records scan_date 不可减少（D5）
- [x] CHECK 约束：file_size_bytes > 0 / score 1-5 / original_format ∈ {mp4,hmd,mcap,avi} / is_multi_part 与 part_count 一致
- [x] 单脚本 migrate.ts --stage up|status

### v2 表单（2026-07-15 新增）

- [x] **v2-forms-spec.md 事实层**（`docs/v2-forms-spec.md`）—— 5 张表字段定稿，A/B/S 必填分级，zod 校验点单一来源
- [x] **v2 migration 落库**（`packages/db-schema/src/migrations/v2_frameforge_v2_forms.sql`）—— 4 张 v2 表 + 14 索引 + CHECK
- [ ] v2 占位页（admin + uploader 双端口）—— **开新对话做**

## Phase 1（进行中）— Uploader MVP

### 业务流

- [ ] 设备 Adapter 真实实现（HMD/MCAP 待供应商）
- [ ] Step 1：选设备 + scan + 浏览器侧 TS AdapterRegistry 调用
- [ ] Step 2：选 session + native `<video>` / worker SSE 转码流
- [ ] Step 3：RHF + Zod + localStorage 预填 + COS STS 直传
- [x] `/library/fill` 视频补全页（cd64f97）
- [ ] `/library` 视频库

### 管理员辅助

### 录制员端（3001）

- [x] **`/login` 录制员登录** —— dev 模式从 recorders 列表选，cookie 关联；生产模式等 Clerk webhook
- [x] **`/devices` 设备/环境登记** —— 4 设备 4 选 1 + env + recorder + 元信息 → 写 public.videos 1 行（frameforge 字段映射：captureMode / fileSizeBytes / fps / frameCount / folderName / storageProvider）
- [x] **`/tasks` 任务登记** —— 按 env_id / 搜索过滤 tasks 列表 → 选 task → UPDATE videos.task_id

### 管理员端（3002）

- [x] **`/admin/tables` 4 表通用浏览器**（650a268）—— 一次性看 videos / tasks / recorders / environments
  - 白名单表名 + 白名单列名 + 参数化 → SQL 注入兜底
  - 列勾选显隐 + 顺序调整 + 全选/只看主键
  - 列头点击切换 asc/desc 排序
  - 跨列模糊搜索（300ms debounce，timestamp/numeric 安全 `::text`）
  - 分页 50/100/200/500 + 首页/上一页/下一页/末页
  - React 19 严格模式兼容（epoch + index 三层 key 兜底，见 E22）
  - **批量编辑**（videos 表专用）：多选行 → 抽屉选字段（recorder_id / task_id / env_id / uploaded）→ dry-run 预览 SQL + BEFORE 抽样 → 确认提交
    - 后端 `POST /api/admin/tables/bulk`（默认 dry-run，`?commit=true` 真改）
    - 字段白名单：videos 限 4 字段；字典表（tasks/recorders/environments）拒绝批量
    - WHERE `path = ANY($1::text[])` + max 500 行/次
  - 入口：admin 首页 + `/admin/db` 顶部跳转
  - 文档：`docs/dev-process/features/admin-tables.md`

- [x] **`/admin/progress` 实时开发进度仪表盘**（plan2 §1.2）—— 替代 plan2 长文件
  - 后端：`/api/dev/progress` 聚合 `docs/features.md` + `docs/project_status.md` checkbox + `git log` 最近 10 commits
  - 解析算法：行级 `- [x]` / `- [ ]` + 标题 `##/###` 分组，正则匹配
  - 仓库根定位：`findRepoRoot()` 上溯找 `docs/features.md` 标记（Next.js 编译后 `__dirname` 不可靠，见下方「已知陷阱」）
  - 前端：总进度条（绿/黄/灰三色）+ Phase 卡片 + 最近 commits 时间线
  - 自动刷新 30s
  - 入口：admin 首页 + `/admin/db` 顶部跳转

### Clerk

- [ ] Clerk 应用创建 + webhook `/api/clerk/webhook` 接 user.created/updated 写 ff_users
- [ ] uploader / admin role 强校验（中间件 + webhook 同步）

### 上传链路

- [ ] cos-js-sdk-v5 multipart + 断点续传
- [ ] hash 计算在 prepareForUpload 输出后（D6 实际起作用）

## Phase 2（待开发）— Admin MVP

- [ ] 7 菜单 CRUD（device-types/recorders/environments/products×processes/users/regions/audit）
- [ ] Clerk backend API 列用户
- [ ] 配额日报表 ff_quota_snapshots
- [ ] 审计日志 ff_audit_logs 过滤 + 分页

## Phase 3（待开发）— 资源包 + 异构优化

- [ ] COS 资源包预付费
- [ ] COS 生命周期规则（30/90/180d 自动转层）
- [ ] 夸克网盘季度备份（rclone）
- [ ] 性能压测（百 TB/月量级并发）
- [ ] 备份恢复演练

## Phase 4（按需）

- [ ] Capacitor 移动端打包
- [ ] SSO / OIDC
- [ ] 多档位转码（480p/720p/1080p）
- [ ] 冷归档
- [ ] K8s 迁移
