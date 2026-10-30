-- FrameForge plan2 Phase 0 — 初始化迁移
-- 在 PG schema `ff`（默认）下创建 11 个 enum + 15 张表，全部加 ff_ 前缀
-- 旧 video_manager.public.* 数据零影响（schema 不同 + 表前缀不同）
-- 此版本需 PostgreSQL 14+（gen_random_uuid() 默认开启）

-- ====== ENUM (11) ======
CREATE TYPE "ff"."app_role" AS ENUM ('uploader', 'admin');
CREATE TYPE "ff"."session_naming" AS ENUM ('file', 'dir_session', 'dir_datetime');
CREATE TYPE "ff"."preview_engine" AS ENUM ('native', 'ffmpeg', 'hmd-decoder', 'mcap-extract');
CREATE TYPE "ff"."upload_prep" AS ENUM ('direct', 'concat-avi', 'extract-hmd', 'extract-mcap');
CREATE TYPE "ff"."lifecycle_state" AS ENUM (
  'SCANNED','PREVIEWING','PREVIEWED','META_FILLED','UPLOADING',
  'UPLOADED','LOCAL_DELETED','ARCHIVED','FAILED','RETRYING'
);
CREATE TYPE "ff"."upload_target" AS ENUM ('partner','backup','quark');
CREATE TYPE "ff"."upload_adapter" AS ENUM (
  'cos-direct','scf-cross-bucket','api','playwright','quark-rclone','local-puller'
);
CREATE TYPE "ff"."upload_status" AS ENUM ('pending','success','failed','retrying');
CREATE TYPE "ff"."cos_storage_class" AS ENUM ('standard','ia','archive','deep_archive');
CREATE TYPE "ff"."scf_trigger" AS ENUM ('cos-put','http','timer');
CREATE TYPE "ff"."run_status" AS ENUM ('running','success','failed');

-- ====== T1 regions ======
CREATE TABLE IF NOT EXISTS "ff"."ff_regions" (
  "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
  "code" text NOT NULL,
  "name_cn" text NOT NULL,
  "name_en" text,
  "is_active" boolean DEFAULT true NOT NULL,
  "created_at" timestamptz DEFAULT now() NOT NULL,
  "updated_at" timestamptz DEFAULT now() NOT NULL,
  CONSTRAINT "ff_regions_code_unique" UNIQUE("code")
);

-- ====== T2 users ======
CREATE TABLE IF NOT EXISTS "ff"."ff_users" (
  "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
  "clerk_user_id" text NOT NULL,
  "region_id" uuid NOT NULL REFERENCES "ff"."ff_regions"("id"),
  "app_role" "ff"."app_role" NOT NULL,
  "display_name" text NOT NULL,
  "phone" text,
  "is_active" boolean DEFAULT true NOT NULL,
  "last_login_at" timestamptz,
  "created_at" timestamptz DEFAULT now() NOT NULL,
  "updated_at" timestamptz DEFAULT now() NOT NULL,
  CONSTRAINT "ff_users_clerk_user_id_unique" UNIQUE("clerk_user_id")
);
CREATE INDEX IF NOT EXISTS "ff_users_clerk_idx" ON "ff"."ff_users" ("clerk_user_id");

-- ====== T0 device_types（被 ff_video_records FK 引用，先建）======
CREATE TABLE IF NOT EXISTS "ff"."ff_device_types" (
  "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
  "code" text NOT NULL,
  "name_cn" text NOT NULL,
  "name_en" text,
  "root_subdir" text NOT NULL,
  "session_naming" "ff"."session_naming" NOT NULL,
  "file_extensions" text[] NOT NULL,
  "preview_engine" "ff"."preview_engine" NOT NULL,
  "upload_prep" "ff"."upload_prep" NOT NULL,
  "is_active" boolean DEFAULT true NOT NULL,
  "version" integer DEFAULT 1 NOT NULL,
  "created_at" timestamptz DEFAULT now() NOT NULL,
  "updated_at" timestamptz DEFAULT now() NOT NULL,
  "created_by" uuid REFERENCES "ff"."ff_users"("id"),
  CONSTRAINT "ff_device_types_code_unique" UNIQUE("code")
);
CREATE INDEX IF NOT EXISTS "ff_device_types_active_idx" ON "ff"."ff_device_types" ("is_active");

-- ====== T3 recorders ======
CREATE TABLE IF NOT EXISTS "ff"."ff_recorders" (
  "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
  "business_key" text NOT NULL,
  "name_cn" text NOT NULL,
  "name_en" text,
  "region_id" uuid NOT NULL REFERENCES "ff"."ff_regions"("id"),
  "phone" text,
  "remark" text,
  "is_active" boolean DEFAULT true NOT NULL,
  "version" integer DEFAULT 1 NOT NULL,
  "source_device" text,
  "created_at" timestamptz DEFAULT now() NOT NULL,
  "updated_at" timestamptz DEFAULT now() NOT NULL,
  "created_by" uuid REFERENCES "ff"."ff_users"("id"),
  CONSTRAINT "ff_recorders_business_key_unique" UNIQUE("business_key")
);
CREATE INDEX IF NOT EXISTS "ff_recorders_region_idx" ON "ff"."ff_recorders" ("region_id");

-- ====== T4 environments ======
CREATE TABLE IF NOT EXISTS "ff"."ff_environments" (
  "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
  "business_key" text NOT NULL,
  "name_cn" text NOT NULL,
  "name_en" text,
  "region_id" uuid NOT NULL REFERENCES "ff"."ff_regions"("id"),
  "env_type" text DEFAULT 'other' NOT NULL,
  "difficulty" text DEFAULT 'medium' NOT NULL,
  "remark" text,
  "is_active" boolean DEFAULT true NOT NULL,
  "version" integer DEFAULT 1 NOT NULL,
  "source_device" text,
  "created_at" timestamptz DEFAULT now() NOT NULL,
  "updated_at" timestamptz DEFAULT now() NOT NULL,
  "created_by" uuid REFERENCES "ff"."ff_users"("id"),
  CONSTRAINT "ff_environments_business_key_unique" UNIQUE("business_key")
);
CREATE INDEX IF NOT EXISTS "ff_environments_region_idx" ON "ff"."ff_environments" ("region_id");

-- ====== T5 products ======
CREATE TABLE IF NOT EXISTS "ff"."ff_products" (
  "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
  "business_key" text NOT NULL,
  "name_cn" text NOT NULL,
  "name_en" text,
  "region_id" uuid NOT NULL REFERENCES "ff"."ff_regions"("id"),
  "image_url" text,
  "image_cos_key" text,
  "is_active" boolean DEFAULT true NOT NULL,
  "version" integer DEFAULT 1 NOT NULL,
  "source_device" text,
  "created_at" timestamptz DEFAULT now() NOT NULL,
  "updated_at" timestamptz DEFAULT now() NOT NULL,
  "created_by" uuid REFERENCES "ff"."ff_users"("id"),
  CONSTRAINT "ff_products_business_key_unique" UNIQUE("business_key")
);
CREATE INDEX IF NOT EXISTS "ff_products_region_idx" ON "ff"."ff_products" ("region_id");

-- ====== T6 processes ======
CREATE TABLE IF NOT EXISTS "ff"."ff_processes" (
  "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
  "product_id" uuid NOT NULL REFERENCES "ff"."ff_products"("id"),
  "business_key" text NOT NULL,
  "name_cn" text NOT NULL,
  "name_en" text,
  "sequence" integer DEFAULT 0 NOT NULL,
  "is_active" boolean DEFAULT true NOT NULL,
  "version" integer DEFAULT 1 NOT NULL,
  "source_device" text,
  "created_at" timestamptz DEFAULT now() NOT NULL,
  "updated_at" timestamptz DEFAULT now() NOT NULL,
  "created_by" uuid REFERENCES "ff"."ff_users"("id"),
  CONSTRAINT "ff_processes_product_business_key_unique" UNIQUE("product_id","business_key")
);
CREATE INDEX IF NOT EXISTS "ff_processes_product_sequence_idx" ON "ff"."ff_processes" ("product_id","sequence");

-- ====== T7 devices ======
CREATE TABLE IF NOT EXISTS "ff"."ff_devices" (
  "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
  "device_id" text NOT NULL,
  "fingerprint_hash" text NOT NULL,
  "platform" text NOT NULL,
  "hostname" text,
  "cpu_model" text,
  "mac_addresses" text[],
  "win_machine_guid" text,
  "salt" text NOT NULL,
  "last_seen_at" timestamptz,
  "first_seen_at" timestamptz DEFAULT now() NOT NULL,
  "is_active" boolean DEFAULT true NOT NULL,
  CONSTRAINT "ff_devices_device_id_unique" UNIQUE("device_id")
);
CREATE INDEX IF NOT EXISTS "ff_devices_fingerprint_idx" ON "ff"."ff_devices" ("fingerprint_hash");

-- ====== T8 video_records（plan2 核心）======
CREATE TABLE IF NOT EXISTS "ff"."ff_video_records" (
  "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
  "device_type_id" uuid NOT NULL REFERENCES "ff"."ff_device_types"("id"),
  "session_folder_name" text,
  "recorder_key" text NOT NULL,
  "environment_key" text NOT NULL,
  "process_id" uuid NOT NULL REFERENCES "ff"."ff_processes"("id"),
  "file_hash" text NOT NULL,
  "original_path" text NOT NULL,
  "original_filename" text NOT NULL,
  "renamed_filename" text NOT NULL,
  "file_size_bytes" bigint NOT NULL,
  "original_format" text NOT NULL,
  "device_specific_metadata" jsonb,
  "is_multi_part" boolean DEFAULT false NOT NULL,
  "part_count" integer DEFAULT 1 NOT NULL,
  "scan_date" timestamptz DEFAULT now() NOT NULL,
  "recorded_at" timestamptz,
  "duration_sec" integer,
  "resolution" text,
  "codec" text,
  "task_description" text DEFAULT '' NOT NULL,
  "is_wearing_gloves" boolean,
  "score" integer,
  "lifecycle_state" "ff"."lifecycle_state" DEFAULT 'SCANNED' NOT NULL,
  "source_device" text NOT NULL,
  "version" integer DEFAULT 1 NOT NULL,
  "region_id" uuid NOT NULL REFERENCES "ff"."ff_regions"("id"),
  "created_by" uuid NOT NULL REFERENCES "ff"."ff_users"("id"),
  "created_at" timestamptz DEFAULT now() NOT NULL,
  "updated_at" timestamptz DEFAULT now() NOT NULL,
  CONSTRAINT "ff_video_records_file_hash_unique" UNIQUE("file_hash"),
  CONSTRAINT "ff_video_records_score_range_chk" CHECK (score IS NULL OR (score >= 1 AND score <= 5)),
  CONSTRAINT "ff_video_records_part_count_chk" CHECK (is_multi_part = false OR part_count >= 2),
  CONSTRAINT "ff_video_records_size_positive_chk" CHECK (file_size_bytes > 0),
  CONSTRAINT "ff_video_records_format_chk" CHECK (original_format IN ('mp4','hmd','mcap','avi'))
);
CREATE INDEX IF NOT EXISTS "ff_video_records_device_type_scan_idx"
  ON "ff"."ff_video_records" ("device_type_id","scan_date");
CREATE INDEX IF NOT EXISTS "ff_video_records_recorder_scan_idx"
  ON "ff"."ff_video_records" ("recorder_key","scan_date");
CREATE INDEX IF NOT EXISTS "ff_video_records_process_scan_idx"
  ON "ff"."ff_video_records" ("process_id","scan_date");
CREATE INDEX IF NOT EXISTS "ff_video_records_state_idx"
  ON "ff"."ff_video_records" ("lifecycle_state");
CREATE INDEX IF NOT EXISTS "ff_video_records_region_scan_idx"
  ON "ff"."ff_video_records" ("region_id","scan_date");

-- D5: scan_date 不可减少（DB 触发器）
CREATE OR REPLACE FUNCTION "ff"."guard_scan_date_not_decrease"() RETURNS trigger AS $$
BEGIN
  IF NEW.scan_date < OLD.scan_date THEN
    RAISE EXCEPTION 'scan_date cannot decrease (was %, now %)', OLD.scan_date, NEW.scan_date;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS ff_video_records_scan_date_guard ON "ff"."ff_video_records";
CREATE TRIGGER ff_video_records_scan_date_guard
BEFORE UPDATE ON "ff"."ff_video_records"
FOR EACH ROW EXECUTE FUNCTION "ff"."guard_scan_date_not_decrease";

-- ====== T9 upload_logs ======
CREATE TABLE IF NOT EXISTS "ff"."ff_upload_logs" (
  "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
  "video_record_id" uuid NOT NULL REFERENCES "ff"."ff_video_records"("id") ON DELETE CASCADE,
  "target" "ff"."upload_target" NOT NULL,
  "adapter_kind" "ff"."upload_adapter" NOT NULL,
  "status" "ff"."upload_status" DEFAULT 'pending' NOT NULL,
  "attempt" integer DEFAULT 1 NOT NULL,
  "remote_id" text,
  "remote_url" text,
  "error_message" text,
  "started_at" timestamptz DEFAULT now() NOT NULL,
  "finished_at" timestamptz,
  "duration_ms" integer
);
CREATE INDEX IF NOT EXISTS "ff_upload_logs_video_target_idx" ON "ff"."ff_upload_logs" ("video_record_id","target");
CREATE INDEX IF NOT EXISTS "ff_upload_logs_status_idx" ON "ff"."ff_upload_logs" ("status");
CREATE INDEX IF NOT EXISTS "ff_upload_logs_started_at_idx" ON "ff"."ff_upload_logs" ("started_at");

-- ====== T10 file_assets（三层存储索引）======
CREATE TABLE IF NOT EXISTS "ff"."ff_file_assets" (
  "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
  "video_record_id" uuid NOT NULL REFERENCES "ff"."ff_video_records"("id") ON DELETE CASCADE,
  "file_hash" text NOT NULL,
  "file_size_bytes" bigint NOT NULL,
  "cos_key" text,
  "cos_bucket" text,
  "cos_region" text,
  "cos_storage_class" "ff"."cos_storage_class" DEFAULT 'standard' NOT NULL,
  "cos_uploaded_at" timestamptz,
  "client_cos_key" text,
  "client_cos_uploaded_at" timestamptz,
  "client_cos_etag" text,
  "local_path" text,
  "local_pulled_at" timestamptz,
  "local_pull_attempts" integer DEFAULT 0 NOT NULL,
  "local_size_bytes" bigint,
  "local_checksum" text,
  "quark_backup_at" timestamptz,
  "quark_backup_size_bytes" bigint,
  "quark_backup_path" text,
  "transition_to_ia_at" timestamptz,
  "transition_to_archive_at" timestamptz,
  "transition_to_deep_at" timestamptz,
  "extra" jsonb,
  "created_at" timestamptz DEFAULT now() NOT NULL,
  "updated_at" timestamptz DEFAULT now() NOT NULL,
  CONSTRAINT "ff_file_assets_video_unique" UNIQUE("video_record_id"),
  CONSTRAINT "ff_file_assets_hash_unique" UNIQUE("file_hash")
);
CREATE INDEX IF NOT EXISTS "ff_file_assets_cos_class_idx" ON "ff"."ff_file_assets" ("cos_storage_class","cos_uploaded_at");
CREATE INDEX IF NOT EXISTS "ff_file_assets_local_pull_idx" ON "ff"."ff_file_assets" ("local_pulled_at");
CREATE INDEX IF NOT EXISTS "ff_file_assets_quark_idx" ON "ff"."ff_file_assets" ("quark_backup_at");

-- ====== T11 quota_snapshots ======
CREATE TABLE IF NOT EXISTS "ff"."ff_quota_snapshots" (
  "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
  "snapshot_date" date NOT NULL,
  "region_id" uuid NOT NULL REFERENCES "ff"."ff_regions"("id"),
  "recorder_key" text NOT NULL,
  "process_id" uuid NOT NULL REFERENCES "ff"."ff_processes"("id"),
  "environment_key" text NOT NULL,
  "count_videos" integer DEFAULT 0 NOT NULL,
  "count_minutes" integer DEFAULT 0 NOT NULL,
  "quota_warning" jsonb,
  "created_at" timestamptz DEFAULT now() NOT NULL,
  CONSTRAINT "ff_quota_snapshots_uniq_unique" UNIQUE("snapshot_date","region_id","recorder_key","process_id","environment_key")
);
CREATE INDEX IF NOT EXISTS "ff_quota_snapshots_region_date_idx" ON "ff"."ff_quota_snapshots" ("region_id","snapshot_date");

-- ====== T12 scf_invocations ======
CREATE TABLE IF NOT EXISTS "ff"."ff_scf_invocations" (
  "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
  "function_name" text NOT NULL,
  "trigger_event" "ff"."scf_trigger" NOT NULL,
  "input_event" jsonb NOT NULL,
  "status" "ff"."run_status" NOT NULL,
  "output" jsonb,
  "error_message" text,
  "duration_ms" integer,
  "cost_cny" numeric(10,6),
  "started_at" timestamptz DEFAULT now() NOT NULL,
  "finished_at" timestamptz
);
CREATE INDEX IF NOT EXISTS "ff_scf_invocations_function_idx" ON "ff"."ff_scf_invocations" ("function_name");
CREATE INDEX IF NOT EXISTS "ff_scf_invocations_status_idx" ON "ff"."ff_scf_invocations" ("status");
CREATE INDEX IF NOT EXISTS "ff_scf_invocations_started_at_idx" ON "ff"."ff_scf_invocations" ("started_at");

-- ====== T13 puller_runs ======
CREATE TABLE IF NOT EXISTS "ff"."ff_puller_runs" (
  "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
  "run_started_at" timestamptz DEFAULT now() NOT NULL,
  "run_finished_at" timestamptz,
  "files_pulled" integer DEFAULT 0 NOT NULL,
  "bytes_pulled" bigint DEFAULT 0 NOT NULL,
  "cost_cny" numeric(10,4),
  "errors" jsonb,
  "status" "ff"."run_status" NOT NULL
);
CREATE INDEX IF NOT EXISTS "ff_puller_runs_status_idx" ON "ff"."ff_puller_runs" ("status");
CREATE INDEX IF NOT EXISTS "ff_puller_runs_started_at_idx" ON "ff"."ff_puller_runs" ("run_started_at");

-- ====== T14 audit_logs ======
CREATE TABLE IF NOT EXISTS "ff"."ff_audit_logs" (
  "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
  "actor_user_id" uuid NOT NULL REFERENCES "ff"."ff_users"("id"),
  "actor_app_role" "ff"."app_role" NOT NULL,
  "actor_region_id" uuid REFERENCES "ff"."ff_regions"("id"),
  "action" text NOT NULL,
  "target_table" text NOT NULL,
  "target_id" uuid NOT NULL,
  "before_state" jsonb,
  "after_state" jsonb,
  "source_device" text,
  "ip_address" text,
  "user_agent" text,
  "created_at" timestamptz DEFAULT now() NOT NULL
);
CREATE INDEX IF NOT EXISTS "ff_audit_logs_actor_idx" ON "ff"."ff_audit_logs" ("actor_user_id");
CREATE INDEX IF NOT EXISTS "ff_audit_logs_action_idx" ON "ff"."ff_audit_logs" ("action");
CREATE INDEX IF NOT EXISTS "ff_audit_logs_target_idx" ON "ff"."ff_audit_logs" ("target_table","target_id");
CREATE INDEX IF NOT EXISTS "ff_audit_logs_created_at_idx" ON "ff"."ff_audit_logs" ("created_at");
