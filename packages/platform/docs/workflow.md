# Workflow — FrameForge (plan2)

> 执行流程 + 质量门禁。提 PR 前必读。

## 开发循环

```
启动 → 读 wcs-manifest.yaml → 按 task_mapping 加载 docs
     → 实现（先列验收 + 写代码 + 加单测）
     → 验证（typecheck + lint + 业务冒烟）
     → 更新 docs（按 update_trigger）
     → commit（fix/feat/chore）
```

## Phase 0 门禁清单（提 PR 前必跑）

```bash
# A. 工程完整性
pnpm install                   # 0 error
pnpm -r typecheck              # 0 error（5 个包）
pnpm --filter @ff/web-uploader build
pnpm --filter @ff/web-admin build
pnpm --filter @ff/worker build

# B. Docker Compose
docker compose up -d            # pg + redis healthy
docker compose ps               # 服务全 healthy

# C. 数据库
pnpm db:migrate                 # 11 enum + 15 表 ff.* 落 ff schema
pnpm db:seed                    # 1 region + 4 device types
pnpm db:status                  # 验证

# D. 后端冒烟
curl -sf :3001/api/health       # uploader 200
curl -sf :3002/api/health       # admin 200

# E. Worker 冒烟
curl -sf :3010/health           # worker 200

# F. WCS 文档完整性
ls docs/{project_status,structure,dev_plan,dev_log,error_book,features,CODING_STANDARDS,workflow,prompt,data-dictionary,storage-architecture,device-adapters}.md
grep -oE 'docs/[a-z_-]+\.md' README.md | xargs -I{} ls {}
```

## 提交信息模板

```
<type>: <subject>

<body — 解释动机 / 设计权衡 / 影响范围>

Refs: <plan 章节 / bug 编号 / issue #>
```

| type | 用途 |
|---|---|
| feat | 新功能 |
| fix | bug fix（关联 E{n}）|
| chore | 工程结构 / 依赖 |
| docs | 仅文档 |
| refactor | 同语义重构 |
| test | 单测 / E2E |

## 多 AI 交接

每个 session 结束前用 `docs/dev_log.md` 末尾追加一段「handoff」：

```yaml
- date: 2026-07-11
  done:
    - Phase 0 完成
    - dev_log 已记录
  todo:
    - Phase 1 Step 0（Clerk 接入）
  context_loaded:
    - wcs-manifest.yaml
    - docs/dev_plan.md
  known_issues:
    - <id 简述>
```

## 容器调试清单

```bash
# 看 PG 健康
docker compose logs pg
docker exec -it ff-pg psql -U ff -d ff -c "SELECT count(*) FROM pg_tables WHERE schemaname='ff';"

# 看 Redis 健康
docker compose logs redis
docker exec -it ff-redis redis-cli ping

# 重启单个服务
docker compose restart web-uploader

# 重建 image
docker compose build web-uploader --no-cache
docker compose up -d web-uploader
```
