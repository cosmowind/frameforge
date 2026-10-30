# WORKFLOW — codec-hmd

> 执行流程协议 + 质量门。每次会话都按这个走。修改本文件需要先改 wcs-manifest.yaml 的 update_trigger。

## 0. 启动（v2.0 强制）

```
Step 1: 读 wcs-manifest.yaml
Step 2: 确认任务类型
Step 3: 按 task_mapping 加载 docs（不是全部）
Step 4: 跑 Phase 1 门
Step 5: 实现 → Phase 2 验证
Step 6: 按 update_trigger 同步 docs
Step 7: 出 handoff
```

## Phase 1 — Pre-Development Gate

实现前必做的清单：

- [ ] 读了 wcs-manifest.yaml（且知道当前 task 类型）
- [ ] 读了 task_mapping 列出的 docs（不是全部）
- [ ] 读了 docs/CODING_STANDARDS.md
- [ ] 知道要改的 file / module
- [ ] 写了实现 plan（写在哪里、怎么测）
- [ ] 准备了回滚策略（重构类改动）

门没走完 → 不写代码。

## Phase 2 — 实现纪律

- 先写最小正确实现，再优化
- 保持单一职责 + 显式命名
- 环境特定配置外置（路径、端口、token）
- 加 / 改 verify 脚本
- 改动 diff 聚焦，不夹带无关重构

## Phase 3 — 验证

- [ ] 改了的 scope 内的 verify 脚本全过
- [ ] 受影响 user flow 端到端跑通
- [ ] 无 blocker 级 lint / type / build 失败
- [ ] 验证证据写入 docs/dev_log.md

门没过 → 不 commit / 不 handoff。

## Phase 4 — 文档同步

按 wcs-manifest.yaml 的 update_trigger 决定动哪些 docs：

| 触发 | 更新 |
|------|------|
| 任务状态变化 | dev_plan.md |
| 完成 + 验证 | dev_log.md |
| 修了 bug | error_book.md |
| 架构变化 | project_status.md |
| 新能力 | features.md |
| 文件/模块变化 | structure.md |
| 用户行为变化 | README.md |
| 加/删/重命名 基线 doc | wcs-manifest.yaml |

**未触发不更新**——避免 doc 膨胀。

## Phase 5 — Handoff

出 handoff block 给下一个 AI / 工程师：

```
## Handoff
- Task: <ID + 名称>
- Outcome: ✅ 完成 / ⚠️ 部分完成 / 🚫 阻塞
- Files changed: <列表>
- Verification: <验证方法 + 结果>
- Known limits: <限制>
- Next recommended: <下一步建议>
```

## 紧急跳过门

只在以下情况可绕过 Phase 1：
- 用户明确说"直接动手"
- 阻塞别人工作的 hotfix
- 已经在 docs 里写过 plan

跳过要在 handoff 里说明。

## 协作约定

- 文件命名稳定（不改 verify_hmd_packets.js → verify_hmd_v2.js 这种）
- 头/字段名稳定（`recorder_id` 永远是 `recorder_id`）
- 链接用相对路径（`../video-sort-package/...`）
- 时间戳用 ISO 8601（`2026-06-16T10:00:00+08:00`）
