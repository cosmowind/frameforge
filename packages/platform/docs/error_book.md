# Error Book — FrameForge (plan2)

> 缺陷根因 + 修复手册 + 预防要点。排查 bug 时读。
>
> **历史 bug E1-E19**（来自旧项目 `video_manager/`，plan2 §13 速查）作为本项目**根因教训**，不再迁移代码，仅作为约束来源。
>
> 本文件是 FrameForge plan2 项目**新发生**缺陷的活档。

## 模板

```yaml
- id: E20
  status: open / fixed / wontfix
  title: <一句话>
  root_cause: <根因 + 引用代码路径>
  discovered: <YYYY-MM-DD>
  trigger: <如何触发 — 步骤/输入>
  fix: <修复 commit + 文件>
  prevention: <架构/流程约束哪一条>
  tests: <回归测试名 + 命令>
```

## 当前条目

### E20 — React 19 duplicate key `''`（空字符串兜底失效）

- **id**: E20
- **status**: fixed
- **title**: 行 key 在 primaryKey 为空字符串时退化为空，React 19 抛 duplicate key
- **root_cause**: `String(row[primaryKey] ?? i)` 中 `'' ?? i` 不会回退（`??` 只对 `null`/`undefined` 兜底，空字符串不是 nullish）→ 多行空 primaryKey 共享空 key
- **discovered**: 2026-07-13
- **trigger**: `/admin/tables` 切到任何 tab，浏览器 console 出现 `Encountered two children with the same key, ''`
- **fix**: commit `ed33c4c` `apps/web-admin/src/app/admin/tables/AdminTablesClient.tsx` — primaryKey 缺失/空 → `row-${i}`；否则 `row-${pkVal}`
- **prevention**: F3 单引号跨行 / 兜底写法纪律：`=== ''` 显式判断，不要用 `??` 兜空串
- **tests**: 浏览器手工验证 4 个 tab + 切换

### E21 — 跨 tab 切换后顶部 undefined 单元格

- **id**: E21
- **status**: fixed
- **title**: 切 tab 时旧 data 还在 + 新列已就位 → row[colName] undefined
- **root_cause**: `useEffect` on activeKey 只 `setPage(0)`，没清 `data` / `err` / `search`；旧 tab 的行（用旧列名）被新列 schema 渲染 → row[c] undefined → 单元格显 "undefined"
- **discovered**: 2026-07-13
- **trigger**: 在 videos tab 加载完后切到 tasks/recorders/environments，顶部出现 "undefined" 行
- **fix**: commit `ca032e9` `AdminTablesClient.tsx` — activeKey 变时 `setData(null) + setErr(null) + setSearchInput('') + setSearch('')` 强制走「加载中」中间态
- **prevention**: 状态机切换时统一清空；任何依赖表/视图切换的 useEffect 必须先 reset 所有派生 state
- **tests**: 浏览器切 4 tab × 多次

### E22 — React 19 严格模式 dev 双渲染仍报 duplicate key

- **id**: E22
- **status**: fixed
- **title**: 即便 primaryKey 唯一，React 19 严格模式 dev 双渲染让两个 `<tr>` 看到同 key
- **root_cause**: React 19 strict mode 渲染两次。primaryKey 派生 key 在两次 render 之间不变 → React 视为重复。E20 的 `row-${pkVal}` 修法只解决了「pkVal 为空」一种情况，没解决「pkVal 重复 + 双渲染」
- **discovered**: 2026-07-13
- **trigger**: 修复 E20/E21 后，tasks/recorders/environments 三个 tab 仍偶发 `Encountered two children with the same key, 'tasks-worksh3301_...'`
- **fix**: commit `7040fac` `AdminTablesClient.tsx` — key 改为 `e${dataEpoch}-${activeKey}-r${i}` 三层兜底：useRef 计数器（每次成功 fetch / 切 tab 都 +1）+ 行 index（单次 render 唯一）+ 表名（跨 tab 隔离）
- **prevention**: F3 兜底写法纪律 + 新规则：**React 19 dev/strict mode 下，不要用业务字段作 React key，必须用单调计数器或纯 index**
- **tests**: 浏览器刷新 + 4 tab 切换 + 列勾选 + 排序 + 搜索 + 翻页

### 沉淀的强约束（提案，待评审）

- **WCS 硬约束 L4 候选**：React 列表 key 禁止仅依赖业务字段；必须 `单调计数器 + 业务字段` 或 `单调计数器 + 纯 index`

### E23 — Next.js App Router 编译后 `__dirname` 不可靠

- **id**: E23
- **status**: fixed
- **title**: 在 Next.js App Router route.ts 里用 `__dirname` 上溯 monorepo 根，编译后路径被替换为 .next 目录
- **root_cause**: Next.js App Router 把 route.ts 编译到 `.next/server/app/...` 目录，运行时 `__dirname` 是编译产物目录，不是源码目录。所有 `path.resolve(__dirname, '../../../')` 类计算都会指向错误位置
- **discovered**: 2026-07-13
- **trigger**: `/api/dev/progress` 接口返回 `features.phases=[]` / `commits=[]`，dev 日志报 `ENOENT ... apps/docs/features.md`（预期路径 `ff/docs/features.md`）
- **fix**: 改用 `findRepoRoot()`：从 `process.cwd()` 上溯找 `docs/features.md` 标记文件，命中即仓库根；同时支持 `process.env.FF_REPO_ROOT` 覆盖
- **prevention**:
  - **L5 决策**：Next.js App Router 里禁止用 `__dirname` 做路径计算；用 cwd 上溯 + 标记文件，或 `import.meta.url`（ESM）
  - 或用 `process.cwd()` + 上溯 `path.dirname` 迭代
- **tests**: curl `/api/dev/progress` 验证 features.phases > 0

### E24 — PG 参数化查询占位符错位（count vs UPDATE）

- **id**: E24
- **status**: fixed
- **title**: 共用 `params` 数组时 countSql 引用 `$2`，但只传 `[pks]` → `could not determine data type of parameter $1`
- **root_cause**: countSql 和 UPDATE 共享 SET 子句的占位符编号。countSql 实际只引用 `$N::text[]` (pkParamIdx)，但 params 含 `[updateVal, pks]` 共 2 个值。简化「只传 pks」时 PG 找不到对应 `$1` 占位符的实参（虽然 SQL 里只引 `$2`，但 params 长度 1 短于 2，PG 校验失败）
- **discovered**: 2026-07-14
- **trigger**: POST /api/admin/tables/bulk dry-run → 500，dev log 报 `could not determine data type of parameter $1`
- **fix**: 拆出独立 `pkWhere = "pk" = ANY($1::text[])`，countSql / sampleSql / UPDATE 各自用独立 params（不共享）；UPDATE 保留 SET + pkParams 顺序
- **prevention**:
  - 任何混合查询（不同 SQL 不同占位符）必须用独立 params
  - 或者严格按 `$1..$N` 顺序 push，不简化
- **tests**: dry-run 真实路径 + 错误路径 403 + 字段白名单 403

### E25 — 客户端组件漏 'use client' 致 useEffect 报错

- **id**: E25
- **status**: fixed
- **title**: uploader 3 个新页面（/login /devices /tasks）useEffect 报 `Module build failed` → 整站 500
- **root_cause**: 文件首行只有 `// 注释` 没有 `'use client'`，Next.js App Router 默认所有 page.tsx 是 Server Component；Server Component 不能用 useState / useEffect
- **discovered**: 2026-07-14
- **trigger**: 3 个新页面全部 HTTP 500，HTML body 含 `You're importing a component that needs useEffect`
- **fix**: 在每个 page.tsx 第 2 行加 `'use client'`
- **prevention**:
  - **L6 决策**：任何含 `useState` / `useEffect` / `onClick` / `onChange` 的 page.tsx 第一行必须是 `'use client'`
  - 用 ESLint 规则 `react-hooks/exhaustive-deps` 配合 plugin `next/script` 强制
- **tests**: typecheck 仍通过（Client Component 检查不在 tsc 范围）+ 浏览器验证

### E26 — 表单结构定义抢先于文档事实层（v2-forms-spec 落地）

- **id**: E26
- **status**: fixed
- **title**: v2 表单字段直接动 SQL / frontend，缺事实层文档 → 字段定义 3 处飘移（SQL、前端 label、文档描述）
- **root_cause**: 调研 `docs/前端调试参考/` 后直接动 SQL（v2_frameforge_v2_forms.sql）但没建事实层文档。如果 SQL 是事实源，未来任一处文档引用字段都得查 SQL hardcode；多个 frontend 表单 share 同一组字段时极易出现 SQL/前端 label/文档描述三者漂移。
- **discovered**: 2026-07-15
- **trigger**: 用户指令「这几个表单结构落实一下，避免其它文档没有描述或者错误描述...」
- **fix**: commit（待）——
  - `docs/v2-forms-spec.md`：5 张表字段定稿（A/B/S 必填分级、zod 校验点、CHECK、FK、命名）
  - `docs/v2-forms-spec.md` 第 0 节「元规则」5 条：R1 D2 业务键 / R2 A 系统必填 / R2 B 业务必填 / R3 审计三件套 / R4 不接 Clerk
  - `wcs-manifest.yaml` 加 `doc_index.v2_forms_spec` 一行（WCS 自迭代规则 4：新增文档必须先改 manifest）
- **prevention**:
  - **L7 决策**：v3+ 任何业务表单结构变更都必须先改 `docs/v2-forms-spec.md`（或后续 v3-forms-spec），再动 SQL / frontend / zod。三个下游只能引用事实层，**字段名必须以 spec 为准**
  - 单源引用：features / dev_log / 占位页前端任意处出现字段名都必须 === spec.sql 字段名
  - spec 变更必须 commit message 标 `[spec-change]`
- **tests**: 后续任何「字段对不上」bug 都从 spec 入手查；typecheck 时让 zod schema import spec 字段元数据

## 附录：plan1 19 类 bug → plan2 硬约束映射

| 旧 Bug | 旧根因 | 新项目根治 | 约束 |
|---|---|---|---|
| E1 WebCodecs 首帧非 IDR | setupDecoders 后立即喂帧 | ffmpeg worker 转码 + 首 IDR 偏移 | M1 |
| E2 HMD 双目误解 | 文档未声明 | schema 注解 + README 强校验 | N1 |
| E3 scan 复活历史行 | existing_map 累积 | scan 不直接落库（Step 1 只缓存前端） | D3 |
| E4 HMD 16× | primeDecoders 灌 60 帧 | frame-debt 累积器 | M4 |
| E5 Flask reloader 子进程残留 | debug=True 多进程 | Next.js + worker 独立进程 + SIGTERM | P2 |
| E6 JS `Unexpected token '}'` | 大段重写 | pre-commit `node --check` + no-floating-promises | F3 |
| E7 缩略图黑帧 | 取非 IDR | ffmpeg `-skip_frame nokey` | M3 |
| E8 thumb 404 | 路由仅 MP4 | 路由统一 4 设备 → native/ffmpeg/hmd-decoder/mcap-extract | M3 |
| E9 浏览器缓存 | 无 cache-control | Next.js 默认 + build 标记戳 | P1 |
| E10 维表改键丢数据 | current-key 反推 | D2 business_key UNIQUE | D2 |
| E11 docstring `\u` | Python docstring | TypeScript 全栈 + 路径归一 | — |
| E12 HMD 缺 .cjs | 打包 exclude | P5 + Next.js dockerfile 多阶段 | P5 |
| E13 auto_upload 路径 404 | 启动 cwd 错 | worker 进程 cd 固定 | — |
| E14 NameError + HTML 500 | 错误处理缺失 | Next.js App Router 统一 JSON 错误 | B1 |
| E15 单引号跨行 JS | 多行未转义 | ESLint + tsc | F3 |
| E16 v1→v8 爆炸 | 反复 copy-paste | L1 单脚本 --stage | L1 |
| E17 9 bug 叠加 | selector 漂移 + BOM | Zod 单一 schema + UTF-8 | F1 |
| E18 CSV+PG 大量重复 | 双写无事务 | D1 PG 唯一源 | D1 |
| E19 + 新增 失效 | 搜索框取错列 | RHF + Zod + Field 数组 | F1 |
