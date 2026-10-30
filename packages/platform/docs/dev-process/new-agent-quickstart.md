# 新 Agent 接入 quickstart（new-agent-quickstart.md）

> 这是给**新开的 claude code 对话**准备的第一份必读文档。
> 新 agent 读这一份 + `database-policy.md` + `ai-db-workflow.md` 就够了。**不需要重读 plan2.md**。

## 0. 你在哪

- 项目：**FrameForge**（视频上传与管理，示例工厂 4 设备录入员 SOP 工具）
- 仓库：`./workspace
- plan2 已落地骨架；现在主攻**视频元数据补全** + **AI 协作调整数据**
- 你的角色：**通过 HTTP/CLI 工具帮用户调整 PG 数据**

## 1. 启动清单（用户已部署）

| 服务 | URL | 状态 |
|---|---|---|
| web-admin (3002) | http://localhost:3002 | 工资 + 统计 + /admin/db |
| web-uploader (3001) | http://localhost:3001 | /library/fill 视频补全 |
| 远端 PG | `db.example.com:5432/video_manager` | schema `ff`（ff_* 镜像表）+ public.*（旧业务真相）|

## 2. 你能调用的接口（3 个 HTTP 端点 + 1 个 CLI）

### A. 查询（SELECT only，拒绝写）

```bash
curl -X POST http://localhost:3002/api/ai/db/query \
  -H 'Content-Type: application/json' \
  -d '{"sql":"SELECT count(*) FROM public.videos"}'
```

### B. 干跑预览（不写库，返回 diff）

```bash
curl -X POST http://localhost:3002/api/ai/db/dry-run \
  -H 'Content-Type: application/json' \
  -d '{
    "updates":[
      {"where":{"path":"/media/videos/..."},"set":{"recorder_id":"op3","uploaded":"Yes"}}
    ]
  }'
```

### C. 真正提交（事务 + 强制 confirm:true）

```bash
curl -X POST http://localhost:3002/api/ai/db/commit \
  -H 'Content-Type: application/json' \
  -d '{
    "updates":[
      {"where":{"path":"/media/videos/..."},"set":{"recorder_id":"op3","uploaded":"Yes"}}
    ],
    "confirm": true
  }'
```

### D. CLI 一行命令（更方便）

```bash
cd F:\sys\...ff
tsx tools/ai-cli.ts query "SELECT count(*) FROM public.videos"
tsx tools/ai-cli.ts dry-run '[{"where":{"path":"..."},"set":{"recorder_id":"op3"}}]'
tsx tools/ai-cli.ts commit '[{"where":{"path":"..."},"set":{"recorder_id":"op3"}}]' --yes
tsx tools/ai-cli.ts health   # 8 表行数 + 填充率 + 备份
```

## 3. 红线（database-policy.md 简版）

- ✅ 允许：SELECT / UPDATE public.videos WHERE path / INSERT ff.*
- ❌ 禁止：`DROP` / `TRUNCATE` / `DELETE` 无 WHERE / `UPDATE` 无 WHERE / `ALTER TABLE`（除非 ADD COLUMN）
- 🔒 兜底：`/api/ai/db/query` 强制 SELECT only + 禁词黑名单
- 🔒 兜底：`commit` 必须 `confirm:true`

## 4. 标准工作流（每次必走）

```
Step 1: SELECT 看现状（query 接口）
   ↓
Step 2: 描述变更 → 用户确认意图
   ↓
Step 3: dry-run 拿 diff → 给用户看 → 等 OK
   ↓
Step 4: 用户说 OK → commit
   ↓
Step 5: 再次 query 验证生效
```

**示例对话**：
```
👤 用户：把前 10 条空 recorder 的视频都设成 op3

🤖 AI：
1. SELECT 找前 10 条 path
2. dry-run 准备 10 条 update，每条 recorder_id = 'op3'
3. 给用户看 diff：10 条 × 1 字段 = 10 处变更
4. 等用户确认

👤 用户：OK

🤖 AI：commit，✅ 更新 10/10
```

## 5. 数据库 schema（你必知）

### public.*（业务真相，**只 UPDATE 不 DROP**）

| 表 | 行数 | 用途 |
|---|---|---|
| videos | 560 | 视频主表 |
| video_batch_config | 261 | 批次元数据 |
| recorders | 14 | 录制员 |
| tasks | 121 | 任务/工序 |
| environments | 19 | 拍摄环境 |
| sd_cards | 4 | SD 卡 / 设备 |
| videos_backup_focused | 606 | 备份明细 |
| app_config | 1 | 配置 |

### ff.ff_*（plan2 新表）

15 张表已落库（ff_regions / ff_users / ff_video_records / ff_device_types / ...）。**目前业务数据仍在 public.* 里**；ff.* 由 ETL 后续迁移。

## 6. 备份（操作前必看）

```bash
# 一键备份
curl -X POST http://localhost:3002/api/admin/db/backup

# 或 CLI
tsx tools/ai-cli.ts health   # 看最近备份列表

# 回滚命令（紧急）
psql $DATABASE_URL < runtime/backups/manual/all-YYYYMMDD-HHMMSS.sql.gz | gunzip
```

## 7. 验收 checklist（每个 commit 前必跑）

```bash
cd F:\sys\...ff
pnpm typecheck
curl http://localhost:3002/api/admin/db/health
```

## 8. 不要做的事

- 不要读 plan1 / plan2 / plan2 完整文件（除非用户明确要）
- 不要写前端 UI（除非用户明确要）
- 不要新建表 / 加列（除非用户明确要）
- 不要"先重构再实现"（plan1 教训）
- 不要 LWW（last-write-wins）覆盖别人未确认的改动

## 9. 你不知道的，问用户

- "改这个会影响哪个业务？"（旧业务真相不能动）
- "这条记录是异常还是合规？"（不要批量删疑似重复）
- "要不要先备份再改 schema？"（默认要）
- "commit 前要不要再 dry-run 一次？"（默认要）

## 10. 完整参考

- `docs/dev-process/database-policy.md` — 完整红线
- `docs/dev-process/ai-db-workflow.md` — AI 对话操作示例
- `packages/db-schema/src/lib/ai-db.ts` — dryRun + commit 实现