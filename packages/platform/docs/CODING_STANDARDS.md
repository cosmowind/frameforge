# Coding Standards — FrameForge (plan2)

> 写代码时必读。每条规则对应一条硬约束 + 一条历史 bug 防。

## 命名

| 规则 | 防的 bug |
|---|---|
| 文件名 kebab-case（`video-records.ts`）| P4 |
| 导出类型与文件名同名 PascalCase | — |
| 私有 helper 加 `_` 前缀（`_canon`）| — |
| 数据库表统一 `ff_` 前缀 | D7 命名空间 |
| 业务主键 `businessKey`（camelCase）→ DB 列 `business_key` | D2 |
| 布尔前缀 `is/has/can`（`isWearingGloves`）| — |
| 错误类 `XxxError extends AppError` | E14 |

## 格式

| 规则 | 防的 bug |
|---|---|
| Prettier：单引号 + 无分号 + 100 宽 | — |
| TypeScript 5.5 + ESM + Bundler resolution | — |
| **不得**在源码中写单引号跨物理行字符串 | **E15** |
| **不得**在 commit 之前未跑 `pnpm -r typecheck` | **E6** |

## 导入

| 规则 | 防的 bug |
|---|---|
| 公共类型从 `@ff/shared` import；DB schema 从 `@ff/db-schema` | F1 |
| 业务主键、版本号、生命周期状态名 = 共享常量唯一来源 | F1/D2/D4 |
| 路径处理 → `packages/shared/src/utils/paths.ts` 唯一入口 | P3/E18 |
| Hash → `@ff/shared/utils/hash` 唯一入口 | D6 |
| 设备 Adapter → `@ff/adapters` 索引 | D10 |

## 错误处理

| 规则 | 防的 bug |
|---|---|
| 抛业务异常用 `AppError` 子类 + 标准 statusCode | E14 |
| Next.js app/api 路由失败也要返回 JSON（不是 HTML）| E14 |
| Zod 校验失败 → 422 + `details: err.flatten()` | F6 |
| BullMQ 任务失败 retry exponential backoff（5 次）| L2 |

## 状态机

| 规则 | 防的 bug |
|---|---|
| `lifecycleState` 写必须在 service 层 | — |
| UPDATE 必带 `WHERE version = ?` + `source_device != ?` | **D4** |
| scan_date 永不减少（DB 触发器 D5 防破坏） | D5 |
| 状态转移来自 service，不是 view | — |
| adapter 的 `prepareForUpload` 输出后计算 file_hash | D6 |

## 设备适配（D10）

| 规则 | 防的 bug |
|---|---|
| 新增设备 = 加 Adapter + `ff_device_types` 加一行 + registry.ts 注册 | D10 |
| Adapter 接口必须实现 4 方法：scan / parseMetadata / getPreviewHandle / prepareForUpload | D10 |
| Preview handle 走 native/worker 两态 | — |
| Generic AVI 多 AVI 必须在 `prepareForUpload` 用 ffmpeg concat 输出单 MP4 | — |

## 测试纪律

| 规则 | 防的 bug |
|---|---|
| 写代码前列验收；写代码后加单测 | L3 |
| 改 schema 必加 migration + 回滚测试 | D7 |
| 改 API 必改 OpenAPI / 共享 schema | F1 |
| Worker 任务 handler 必须处理 retry 5x exponential backoff | L2 |

## 提交纪律

| 规则 | 防的 bug |
|---|---|
| `git commit` 信息前缀：feat/fix/chore/docs/refactor/test | — |
| 单 commit 不超 500 行（不含 lock 文件）| L3 |
| runtime/、.debug/、*.local、.env 永远不入仓（P6）| E16/P6 |
| 提交前必跑 `pnpm -r typecheck` | E6 |

## 容器化纪律（P7）

| 规则 | 防的 bug |
|---|---|
| 每个 Docker service 必含 `mem_limit` + `cpus` 限制 | 资源失控 |
| 应用 image 用 multi-stage build + tini 信号处理 | P2 残留 |
| Compose 用 named volume 不用 bind mount | 跨平台 |
| `.env` 通过 `env_file` 注入，容器内不硬编码 | P6 |

## 文档关联

- WCS 索引 → `wcs-manifest.yaml`
- 错误案例 → `docs/error_book.md`
- 实现记录 → `docs/dev_log.md`
- 提交流程 → `docs/workflow.md`
- 数据表字段 → `docs/data-dictionary.md`
- 存储架构 → `docs/storage-architecture.md`
- Adapter 扩展 → `docs/device-adapters.md`
