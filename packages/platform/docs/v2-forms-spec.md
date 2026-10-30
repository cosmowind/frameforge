# FrameForge v2 表单结构 — 事实层

> **单一事实源（Single Source of Truth）**。所有 v2 表单的字段定义、必填策略、字段映射、跨表关系以此文档为准。
>
> **冲突优先级**：`docs/v2-forms-spec.md` > `docs/features.md` > `docs/dev_log.md` > 任何 API/前端注释。
>
> **维护时机**：字段变更（增/删/改 type）必须先改本文件，再写 SQL，再 commit。理由：表单结构决定了 4 类下游实现（schema / zod / 前端 label / 文档），单一来源才能避免记录漂移。

---

## 0. 元规则（5 条）

| 编号 | 规则 | 说明 |
|---|---|---|
| **R1** | **业务键 D2** | 每张业务表必含 `business_key text UNIQUE NOT NULL`，是面向业务的稳定键（区别于 `id` 这种技术键）。允许跨来源去重 / 上游对接迁移。 |
| **R2 A 类** | **A 系统必填** | `schema` 上 `NOT NULL DEFAULT`。机械约束，缺了插不进表。用于合规硬要求 / 系统状态字段（如 `consented_to_recording` / `accept_status`）。 |
| **R2 B 类** | **B 业务必填** | `schema` 上 nullable，业务接口 zod `.min(1)` 强校验。允许「已创建行 + 后续补字段」。前端 `*` 标记的就是 B 类。 |
| **R3** | **审计三件套保留** | `is_active boolean NOT NULL DEFAULT true` + `version integer NOT NULL DEFAULT 1` + `created_at timestamptz NOT NULL DEFAULT now()` + `updated_at timestamptz NOT NULL DEFAULT now()`。每张 v2 表全加，用于下架 + 乐观锁 + 审计时间。 |
| **R4** | **不建 `created_by` / 不接 Clerk** | Clerk 免费 10K MAU 之内不动。`v2-forms-spec v2.0` 故意留白，等真到多人协同时再加 `created_by uuid + ff_users` 表 + FK。在 docs/dev-process/clerk-bootstrap-plan.md（待写）落预算与接入 checklist。 |

### 表格标注说明

下表每字段后括号：
- `(A)` = A 类 — schema NOT NULL
- `(B)` = B 类 — schema nullable + zod min(1) 在业务流程接口
- `(N)` = 非业务必填 — schema nullable + zod 不强制
- `(S)` = 系统状态字段 — A 类，无 default 强制但有 default 值

---

## 1. ff_operators（操作员）

### 1.1 来源

前端调试参考 `docs/前端调试参考/operator0714.txt` 中的 New Operator 表单：

```
Alias *    Name *    Hand *    —
Hand size (cm)    Gender *    —
Age range *    —
Job / role *    Role experience *    Operator consented to recording *
Cancel    Save changes
```

### 1.2 字段

| 列 | 类型 | 类别 | 来源 | 说明 |
|---|---|---|---|---|
| `id` | uuid PK | A | new | gen_random_uuid() |
| `business_key` | text UNIQUE NOT NULL | A | R1 | 业务键（`op01` / `opsample` 等）|
| `alias` | text | B | 「Alias *」 | 录制员查引用 |
| `name` | text | B | 「Name *」 | 中文姓名 |
| `hand` | text | B | 「Hand *」 | 左手 / 右手（前端 select 2 选项，**对齐 dr 官方**：left / right；dr 没有「both」） |
| `hand_size_cm` | double precision | **N** | 「Hand size (cm)」 | 非业务必填（`<input min="0" step="0.1" type="number">`，无 max 约束） |
| `gender` | text | B | 「Gender *」 | 性别（前端 select 3 选项，**对齐 dr 官方**：male / female / prefer_not_to_say） |
| `age_range` | text | B | 「Age range *」 | 年龄段（前端 select 12 选项，**对齐 dr 官方**：15-20 / 20-25 / 25-30 / 30-35 / 35-40 / 40-45 / 45-50 / 50-55 / 55-60 / 60-65 / 65-70 / 70+，5 岁桶） |
| `job_role` | text | B | 「Job / role *」 | 工种/角色（自由文本） |
| `role_experience` | text | B | 「Role experience *」 | 经验段（自由文本） |
| `email` | text | **N** | 任务页 placeholder | 邮箱（本期不上 form，DB 列保留 phase 2） |
| `consented_to_recording` | boolean NOT NULL DEFAULT false | A | 「Operator consented to recording *」 | 合规硬要求 |
| `is_active` | boolean NOT NULL DEFAULT true | A | R3 | 审计三件套 |
| `version` | integer NOT NULL DEFAULT 1 | A | R3 | 审计三件套 |
| `created_at` | timestamptz NOT NULL DEFAULT now() | A | R3 | 审计三件套 |
| `updated_at` | timestamptz NOT NULL DEFAULT now() | A | R3 | 审计三件套 |

### 1.3 zod 校验落点

| 接口 | min(1) 字段 |
|---|---|
| `POST /api/admin/operators` | alias + name + hand + gender + age_range + job_role + role_experience + **consented_to_recording=true** |

### 1.4 索引

- `ff_operators(is_active)` — 全部列表
- `ff_operators(job_role) WHERE is_active` — 按工种过滤

---

## 2. ff_locations（场所）

### 2.1 来源

前端调试参考 `docs/前端调试参考/location0714.txt`：

```
Alias *    Environment (L1) *    Venue (L2) *
Business name *    Business type *    Address * (搜索框)
Country *    City *    Region / state *    Zip / postal *
GPS: select an address to lock
Cancel    Save changes
```

L1 = 27 选项（如 `Retail and Consumer Goods`）；L2 = 228 选项（如 `Grocery Store`）。

### 2.2 字段

| 列 | 类型 | 类别 | 来源 | 说明 |
|---|---|---|---|---|
| `id` | uuid PK | A | new | |
| `business_key` | text UNIQUE NOT NULL | A | R1 | 场所简写 |
| `alias` | text | B | 「Alias *」 | |
| `environment_l1` | text | B | 「Environment (L1) *」 | 27 选项硬编码 |
| `venue_l2` | text | B | 「Venue (L2) *」 | 228 选项硬编码 |
| `business_name` | text | B | 「Business name *」 | |
| `business_type` | text | B | 「Business type *」 | |
| `address_line1` | text | B | 「Address *」 | 搜索 + select 后回填 |
| `address_line2` | text | **N** | 隐含 | 二级地址 |
| `country_code` | text | **N** | 「Country *」（前端 *） | **降级**：ff 录入端可空，未来地址搜索自动回填 |
| `city` | text | B | 「City *」 | |
| `region_state` | text | B | 「Region / state *」 | |
| `zip_postal` | text | B | 「Zip / postal *」 | |
| `lat` | double precision | **N** | 「GPS」 | 地址锁定后回填 |
| `lng` | double precision | **N** | 「GPS」 | 地址锁定后回填 |
| `is_active` | boolean NOT NULL DEFAULT true | A | R3 | |
| `version` | integer NOT NULL DEFAULT 1 | A | R3 | |
| `created_at` / `updated_at` | timestamptz NOT NULL DEFAULT now() | A | R3 | |

### 2.3 zod 校验落点

| 接口 | min(1) 字段 |
|---|---|
| `POST /api/admin/locations` | alias + env_l1 + venue_l2 + business_name + business_type + address_line1 + city + region_state + zip_postal |
| *地址搜索锁定接口（待建）* | country_code + lat + lng 自动回填，业务不校验 |

### 2.4 索引

- `ff_locations(is_active)`
- `ff_locations(environment_l1, venue_l2) WHERE is_active` — 按 L1+L2 过滤
- `ff_locations(country_code) WHERE is_active` — 按国家过滤

---

## 3. ff_scenes（dr 已开通 scene 白名单）

### 3.1 真实作用

> **scene 表的根本作用 = Playwright 上传按钮锁**。任务详情页可能有 N 个上传按钮（每个 scene 一个），录前上传时**必须**按 env/venue/scene/project/captureMode 5 元组锁到**唯一**一个按钮，否则选错。

截图示例（来自 `docs/前端调试参考/任务页面0714.txt`）：
```
Summit-02
零售与消费品 › 杂货店 › 超市货架
双目
2026-07-31
可接
剩余 76.9 小时
共 80 小时
```

### 3.2 字段

| 列 | 类型 | 类别 | 来源 | 说明 |
|---|---|---|---|---|
| `id` | uuid PK | A | new | |
| `business_key` | text UNIQUE NOT NULL | A | R1 | `summit02_grocery_supershelf` 等合成键 |
| `alias` | text | B | admin 录入 | admin 内部简写 |
| `project_code` | text | B | 「Summit-02」 | 项目编号（每条 scene 必属于某个项目） |
| `capture_mode` | text | B | 「双目」 | `single` / `three_views` / `stereo` |
| `environment_l1` | text | B | 27 选项 | |
| `venue_l2` | text | B | 228 选项 | |
| `scene_l3` | text | B | 1590 选项 | |
| `deadline` | date | B | 「2026-07-31」 | 任务截止 |
| `accept_status` | text NOT NULL DEFAULT 'accepting' | A (S) | 「可接」 | `accepting` / `closed` / `filled` |
| `total_hours_quota` | double precision | B | 「共 80 小时」 | |
| `used_hours` | double precision NOT NULL DEFAULT 0 | A | 「剩余 76.9 小时」 | 由 worker 累计写入 |
| `source` | text NOT NULL DEFAULT 'manual' | A (S) | new | `manual` / `frameforge` |
| `status` | text NOT NULL DEFAULT 'available' | A (S) | 申请流程 | `available` / `pending` / `retired` |
| `environment_photo_url` | text | **N** | 新增指令 | phase 2 接图床，先留空 |
| `is_active` | boolean NOT NULL DEFAULT true | A | R3 | |
| `version` | integer NOT NULL DEFAULT 1 | A | R3 | |
| `created_at` / `updated_at` | timestamptz NOT NULL DEFAULT now() | A | R3 | |

### 3.3 CHECK 约束

```sql
accept_status IN ('accepting','closed','filled')
status        IN ('available','pending','retired')
capture_mode  IS NULL OR capture_mode IN ('single','three_views','stereo')
source        IN ('manual','frameforge')
used_hours    >= 0
              AND (total_hours_quota IS NULL OR used_hours <= total_hours_quota)
```

### 3.4 索引

- `ff_scenes(project_code)` — 项目维度
- `ff_scenes(status) WHERE is_active` — 白名单过滤
- `ff_scenes(accept_status) WHERE is_active` — 收片状态过滤
- `ff_scenes(environment_l1, venue_l2, scene_l3)` — 5 元组锁定

### 3.5 守门员约束（业务层）

```
1. video_uploads.scene_id 只能选 status='available' AND accept_status='accepting' AND used_hours < total_hours_quota 的行
2. source='manual' 的行可随时建；source='frameforge' 的行 v2 不接 DR API，未来加
3. environment_photo_url 接受 cos://bucket/key / https://，phase 2 接图床时才校验
```

---

## 4. ff_scene_applications（dr 未开通 scene 申请池）

### 4.1 角色

培训员 / 录制员发现 dr 没开通某 scene，但这个场景有需求 → 在本表新建申请（多走 `application_status='draft'` → 提交给 dr → dr 批了 → 自动 `approved_scene_id` 指向新建的 ff_scenes 行）。

### 4.2 字段

| 列 | 类型 | 类别 | 来源 | 说明 |
|---|---|---|---|---|
| `id` | uuid PK | A | new | |
| `business_key` | text UNIQUE NOT NULL | A | R1 | |
| `alias` | text | B | admin 录入 | 申请内部编号 |
| `environment_l1` | text | B | 27 选项 | |
| `venue_l2` | text | B | 228 选项 | |
| `scene_l3` | text | B | 1590 选项（申请的） | |
| `deadline` | date | **N** | new | 申请场景不一定有截止 |
| `total_hours_quota` | double precision | **N** | new | 同上 |
| `application_status` | text NOT NULL DEFAULT 'draft' | A (S) | new | `draft` / `submitted_to_dr` / `approved` / `rejected` |
| `applied_by_user_key` | text | A | dev cookie 占位 | 未来接 Clerk 后接 `user_xxx`，字段不改 |
| `function_description` | text | B | 「场景职能」 | 与 scenes 区别字段 |
| `dedup_against` | text | B | 「与现有 scene 对比」 | 防重复 |
| `approved_scene_id` | uuid FK→ff_scenes(id) ON DELETE SET NULL | **N** | dr 批了后回填 | |
| `environment_photo_url` | text | **N** | new | 申请附图（phase 2 接图床）|
| `decided_at` | timestamptz | **N** | new | 决策时间 |
| `is_active` | boolean NOT NULL DEFAULT true | A | R3 | |
| `version` | integer NOT NULL DEFAULT 1 | A | R3 | |
| `created_at` / `updated_at` | timestamptz NOT NULL DEFAULT now() | A | R3 | |

### 4.3 CHECK 约束

```sql
application_status IN ('draft','submitted_to_dr','approved','rejected')
```

### 4.4 与 ff_scenes 的字段一致性

> scenes 与 applications 的 5 个核心字段（alias + env_l1 + venue_l2 + scene_l3 + 项目/接入/配额）结构一致。区别仅在：
> - applications 多 4 个申请态字段（function_description / dedup_against / approved_scene_id / decided_at）
> - applications 无 capture_mode / project_code（这两个由 dr 决定，dr 批了之后由 admin 在 ff_scenes 补）

---

## 5. ff_video_uploads（上传有效性表单 + 上传状态机）

### 5.1 双重身份

| 用途 | 说明 |
|---|---|
| **有效性表单** | 录入视频元数据（路径 / 格式 / scene / operator / location / task_description） |
| **上传状态机** | `uploaded=false → uploaded=true` 的状态切换；`uploaded_at` 是写入时点 |

### 5.2 来源

前端调试参考 `docs/前端调试参考/上传页面0714.txt` 上传对话框字段：

```
接入模式 (必填)    来源 (HMD 分段 / MCAP+元数据 / PICO/OAK mcap / Fisheye MP4)
预览（drag-drop）
地点 (必填)    操作员 (必填)
任务描述 (必填, 500 字符)
"上传到服务器（请先拖入文件）"
```

### 5.3 字段

| 列 | 类型 | 类别 | 来源 | 说明 |
|---|---|---|---|---|
| `id` | uuid PK | A | new | |
| `business_key` | text UNIQUE NOT NULL | A | R1 | **CHECK `business_key = path`** |
| `path` | text NOT NULL | A | 文件路径 | 唯一技术标识 |
| `source_format` | text | B | `mp4` / `mcap` / `hmd` | 选完文件就锁 |
| `capture_mode` | text | B | 来源于 scenes | `single` / `three_views` / `stereo` |
| `project_code` | text | B | 来源于 scenes | 默认 `summit-02` |
| `scene_id` | uuid FK→ff_scenes(id) ON DELETE RESTRICT | B | 上传对话框「scene」字段 | **必须从 scenes 白名单选** |
| `operator_id` | uuid FK→ff_operators(id) ON DELETE RESTRICT | B | 「操作员」 | |
| `location_id` | uuid FK→ff_locations(id) ON DELETE RESTRICT | B | 「地点」 | |
| `task_description` | text | B | 「任务描述」（上传按钮前 zod min(1)） | 允许 NULL 暂存；完成上传动作时强制非空 |
| `notes` | text | N | new | 备注 |
| `recorded_at` | timestamptz | N | 任务页 date input | |
| `duration_seconds` | integer | N | new | 时长 |
| `score_composite` | integer (0-100) | N | 任务页 min=0 max=100 | |
| `uploaded` | boolean NOT NULL DEFAULT false | A (S) | 状态机 | |
| `uploaded_at` | timestamptz | N | 状态机 | |
| `storage_provider` | text NOT NULL DEFAULT 'cos' | A (S) | V1 | `cos` / `aws_s3` / `tencent_cos` |
| `file_size_bytes` | bigint | N | V1 | |
| `fps` | double precision | N | V1 | |
| `frame_count` | integer | N | V1 | |
| `is_active` | boolean NOT NULL DEFAULT true | A | R3 | |
| `version` | integer NOT NULL DEFAULT 1 | A | R3 | |
| `created_at` / `updated_at` | timestamptz NOT NULL DEFAULT now() | A | R3 | |

### 5.4 CHECK 约束

```sql
capture_mode     IS NULL OR capture_mode IN ('single','three_views','stereo')
source_format    IS NULL OR source_format IN ('mp4','mcap','hmd')
storage_provider IN ('cos','aws_s3','tencent_cos')
score_composite  IS NULL OR score_composite BETWEEN 0 AND 100
fps              IS NULL OR fps > 0
business_key     = path
```

### 5.5 zod 校验落点

| 接口 | 时机 | min(1) 字段 |
|---|---|---|
| `POST /api/uploader/video-uploads` （**按下「上传到服务器」按钮**） | 入库前 | path + source_format + capture_mode + scene_id + operator_id + location_id + **task_description** |
| `POST /api/uploader/video-uploads/preview` （**拖完文件预览**） | 暂存 | path + source_format + capture_mode + scene_id + operator_id + location_id（task_description 可空） |

### 5.6 索引

- `ff_video_uploads(scene_id) WHERE is_active` — 按 scene 查视频
- `ff_video_uploads(operator_id) WHERE is_active` — 按 operator 聚合
- `ff_video_uploads(location_id) WHERE is_active` — 按 location 聚合
- `ff_video_uploads(path)` — 路径唯一性
- `ff_video_uploads(uploaded, uploaded_at)` — 队列调度

### 5.7 ON DELETE RESTRICT 原则

| FK | 删除策略 | 原因 |
|---|---|---|
| `scene_id → ff_scenes.id` | **RESTRICT** | scene 被删会丢历史视频，拒绝 |
| `operator_id → ff_operators.id` | **RESTRICT** | 同上 |
| `location_id → ff_locations.id` | **RESTRICT** | 同上 |

要让某 scene/operator/location 不再可用，**走 `is_active=false`** 而非 DELETE。

---

## 6. 跨表关系

```
                                    ┌──────────────────────────┐
                                    │ ff_scene_applications   │
                                    │ - applied_by_user_key    │
                                    │ - application_status     │
                                    │ - function_description   │
                                    │ - dedup_against          │
                                    │ - environment_photo_url  │
                                    │ - decided_at             │
                                    └─────────────┬────────────┘
                                                  │ approved_scene_id
                                                  ▼ (SET NULL on delete)
┌────────────────┐   FK (RESTRICT)   ┌──────────────┐
│ ff_operators  │──────────────────►│              │
└────────────────┘                   │              │
                                     │ ff_scenes   │
┌────────────────┐   FK (RESTRICT)   │              │
│ ff_locations  │──────────────────►│              │
└────────────────┘                   │              │
                                     │              │
                                     └──────┬───────┘
                                            │ FK (RESTRICT)
                                            ▼
                                     ┌──────────────────────┐
                                     │ ff_video_uploads    │
                                     │ + uploaded 状态机     │
                                     └──────────────────────┘
```

无 `ff_users`：dev 阶段 `applied_by_user_key` 用文本 cookie 模拟，未来 Clerk 接上后字段名为字符串 `user_xxx`，**字段类型不变**。

---

## 7. 业务流程校验点汇总

| 流程 | 接口 | schema 端 | zod 校验端 |
|---|---|---|---|
| 创建 operator | `POST /api/admin/operators` | business_key + consented + 审计唯一 NOT NULL | alias/name/hand/gender/age_range/job_role/role_experience + consent=true |
| 创建 location | `POST /api/admin/locations` | business_key + 审计唯一 NOT NULL | alias/env_l1/venue_l2/business_name/business_type/address_line1/city/region_state/zip |
| 创建 scene | `POST /api/admin/scenes` | business_key + accept_status/used_hours/source/status/审计 NOT NULL | alias/project_code/capture_mode/env_l1/venue_l2/scene_l3/deadline/accept_status/total_hours_quota |
| 创建 scene 申请 | `POST /api/admin/scene-applications` | business_key + application_status + applied_by_user_key + 审计 NOT NULL | alias/env_l1/venue_l2/scene_l3 |
| 上传视频（预览） | `POST /api/uploader/video-uploads/preview` | path + business_key + uploaded/storage_provider + 审计 NOT NULL | source_format/capture_mode/project_code/scene_id/operator_id/location_id |
| 上传视频（完成） | `POST /api/uploader/video-uploads` | 同上 | **+ task_description** |

---

## 8. 版本历史

| 版本 | 日期 | 变更 |
|---|---|---|
| v2.0 | 2026-07-15 | 首版。4 张表全字段定稿（A/B 分类、Z/A/S 标注）；与 v1 public.* 表完全隔离；与 V1 migration 错位共存 |

---

## 9. 引用本文件的地方

- SQL 单一来源：`packages/db-schema/src/migrations/v2_frameforge_v2_forms.sql`
- WCS docs：`docs/features.md` · `docs/dev_log.md` · `docs/error_book.md` · `docs/project_status.md`
- 占位页：`apps/web-admin/src/app/admin/{operators,locations,scenes,scene-applications}/page.tsx`
- 上传页：`apps/web-uploader/src/app/upload/page.tsx`
- 未来 Clerk 入口：`docs/dev-process/clerk-bootstrap-plan.md`（**待写**）
