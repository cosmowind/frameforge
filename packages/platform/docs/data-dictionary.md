# Data Dictionary — FrameForge (plan2)

> 15 张表字段详解 + ER 图。业务实现时必读本文 + `packages/db-schema/src/tables/` TypeScript 定义。

## 总览

```
       ┌──────────────┐
       │ff_regions  │ (T1 区域)
       └──────┬───────┘
              │ region_id
   ┌──────────┼─────────────┐
   │          │             │
▼  ▼          ▼             ▼
ff_users  ff_recorders ff_environments
(T2 账号)  (T3 录制员)   (T4 环境)
   │ ▲                      │
   │ │ region_id             │ product_id
   │ └─────────────────────┐ │
   │                       ▼ ▼
   │              ┌─────────────────┐
   │              │ff_products     │ (T5 产品)
   │              └──────┬──────────┘
   │                     │ product_id (D7 FK CASCADE)
   │                     ▼
   │              ┌─────────────────┐
   │              │ff_processes    │ (T6 工序)
   │              └─────────────────┘
   │                     ▲
   │                     │ process_id
   │           ┌─────────┴──────────────────┐
   │ createdBy │                     device_type_id
   ▼           ▼                             ▼
┌──────────────────────────────────────────────────┐
│                ff_video_records                  │ (T8 核心)
│              ┌──┬─────────┬────────┐              │
│              │  │scanner │region  │              │
│ recorder_key │  │device_id│         │             │
│ environment_key                           created_by
└──────┬─────────────────────────┬──────────────────┘
       │                         │
       │ file_hash               │ file_hash (UNIQUE D6)
       ▼                         ▼
┌────────────────┐        ┌─────────────────┐
│ff_upload_logs │        │ff_file_assets  │ (T9 三层存储)
│  (每条 target) │        │ L1 COS / 客户   │
└────────────────┘        │ L2 本地         │
                          │ L3 夸克         │
                          └─────────────────┘

┌─────────────────────────┐    ┌──────────────────────┐
│ff_device_types   (T0)  │    │ff_scf_invocations   │ (T12)
└─────────────────────────┘    └──────────────────────┘

┌─────────────────────────┐    ┌──────────────────────┐
│ff_devices       (T7)  │    │ff_puller_runs       │ (T13)
└─────────────────────────┘    └──────────────────────┘

┌────────────────────────────────────────────────────┐
│ff_quota_snapshots  (T11)  +  ff_audit_logs (T14) │
└────────────────────────────────────────────────────┘
```

## 11 个 PG enum

| enum | 值 |
|---|---|
| `ff.app_role` | uploader, admin |
| `ff.session_naming` | file, dir_session, dir_datetime |
| `ff.preview_engine` | native, ffmpeg, hmd-decoder, mcap-extract |
| `ff.upload_prep` | direct, concat-avi, extract-hmd, extract-mcap |
| `ff.lifecycle_state` | SCANNED, PREVIEWING, PREVIEWED, META_FILLED, UPLOADING, UPLOADED, LOCAL_DELETED, ARCHIVED, FAILED, RETRYING |
| `ff.upload_target` | partner, backup, quark |
| `ff.upload_adapter` | cos-direct, scf-cross-bucket, api, playwright, quark-rclone, local-puller |
| `ff.upload_status` | pending, success, failed, retrying |
| `ff.cos_storage_class` | standard, ia, archive, deep_archive |
| `ff.scf_trigger` | cos-put, http, timer |
| `ff.run_status` | running, success, failed |

## 15 张表

详见 `packages/db-schema/src/tables/ff_*.ts` 源码 + `migrations/v0_initial_v2.sql`。
每个表头注释列出：
- PK / UNIQUE / CHECK 约束
- INDEX 列表
- 物理命名（schema + ff_ 前缀）
- 引用关系（FK 到哪些 ff_* 表）

### T0 ff_device_types（设备类型，D10 核心）

关键字段：`code` UNIQUE、`root_subdir`、`session_naming` enum、`file_extensions[]`、`preview_engine` enum、`upload_prep` enum、`version`（D4）。

### T8 ff_video_records（核心）

- `device_type_id` NOT NULL REFERENCES ff_device_types(id)（D10 必填）
- `file_hash` UNIQUE NOT NULL（D6 去重）
- `original_path` / `original_filename` / `renamed_filename`
- `file_size_bytes` bigint NOT NULL（CHECK > 0）
- `original_format` CHECK ∈ {mp4, hmd, mcap, avi}
- `device_specific_metadata` JSONB（HMD 姿态 / MCAP topic / Generic AVI parts）
- `is_multi_part` boolean + `part_count` int（Generic AVI 多 AVI 标记）
- `task_description` text NOT NULL（Step 3 用户填）
- `score` int CHECK 1-5
- **D5 trigger**：BEFORE UPDATE 拒绝 scan_date 减少

### T10 ff_file_assets（三层存储）

每条 video_record 一行：
- **L1 COS**：cos_key / cos_bucket / cos_region / cos_storage_class enum / cos_uploaded_at
- **L1 客户 COS**：client_cos_key / client_cos_uploaded_at / client_cos_etag
- **L2 本地硬盘**：local_path / local_pulled_at / local_pull_attempts / local_size_bytes / local_checksum
- **L3 夸克网盘**：quark_backup_at / quark_backup_size_bytes / quark_backup_path
- **生命周期转换时间点**：transition_to_ia_at / transition_to_archive_at / transition_to_deep_at

### T12 ff_scf_invocations（SCF 调用审计）

- function_name / trigger_event / input_event JSONB / status / output / duration_ms / cost_cny

### T13 ff_puller_runs（L2 Puller 审计）

- run_started_at / run_finished_at / files_pulled / bytes_pulled / cost_cny / errors JSONB

### T14 ff_audit_logs（通用审计）

- actor_user_id / actor_app_role / action / target_table / target_id / before_state JSONB / after_state JSONB / ip_address / user_agent
