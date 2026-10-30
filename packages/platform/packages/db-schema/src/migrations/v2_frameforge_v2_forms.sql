-- FrameForge plan2 v2 migration — 5 张 v2 表（ff_operators / ff_locations / ff_scenes / ff_scene_applications / ff_video_uploads）
-- 时间：2026-07-15
-- 触发：调研 frontend/docs/前端调试参考/ 下 4 个 HTML 片段（location0714 / operator0714 / 上传页面0714 / 任务页面0714）
-- 红线：
--   1. 只 CREATE TABLE IF NOT EXISTS；不改已有列；不 DROP COLUMN
--   2. 所有表用 ff_ 前缀；schema ff
--   3. 一律保留 D2 业务键 business_key UNIQUE NOT NULL
--   4. 必填分两类：A 系统必填（NOT NULL DEFAULT）/ B 业务必填（前端 *，schema nullable，zod min(1) 在业务流程接口强制）
--   5. 不建 created_by（Clerk 暂不装，10K MAU free，等真用再加）
--   6. v2 不接 DR 同步钩子，scenes.source 全部 default 'manual'
--   7. scenes / scene_applications 加 environment_photo_url text 字段，phase 2 接图床

-- ====== T2: ff_operators（操作员）======
CREATE TABLE IF NOT EXISTS "ff"."ff_operators" (
  "id"                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  "business_key"            text UNIQUE NOT NULL,
  "alias"                   text,
  "name"                    text,
  "hand"                    text,
  "hand_size_cm"            double precision,
  "gender"                  text,
  "age_range"               text,
  "job_role"                text,
  "role_experience"         text,
  "email"                   text,
  "consented_to_recording"  boolean NOT NULL DEFAULT false,
  "is_active"               boolean NOT NULL DEFAULT true,
  "version"                 integer NOT NULL DEFAULT 1,
  "created_at"              timestamptz NOT NULL DEFAULT now(),
  "updated_at"              timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS "ff_operators_active_idx"    ON "ff"."ff_operators" ("is_active");
CREATE INDEX IF NOT EXISTS "ff_operators_role_idx"      ON "ff"."ff_operators" ("job_role") WHERE "is_active";

-- ====== T4: ff_locations（场所）======
CREATE TABLE IF NOT EXISTS "ff"."ff_locations" (
  "id"              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  "business_key"    text UNIQUE NOT NULL,
  "alias"           text,
  "environment_l1"  text,
  "venue_l2"        text,
  "business_name"   text,
  "business_type"   text,
  "address_line1"   text,
  "address_line2"   text,
  "country_code"    text,
  "city"            text,
  "region_state"    text,
  "zip_postal"      text,
  "lat"             double precision,
  "lng"             double precision,
  "is_active"       boolean NOT NULL DEFAULT true,
  "version"         integer NOT NULL DEFAULT 1,
  "created_at"      timestamptz NOT NULL DEFAULT now(),
  "updated_at"      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS "ff_locations_active_idx"        ON "ff"."ff_locations" ("is_active");
CREATE INDEX IF NOT EXISTS "ff_locations_env_venue_idx"     ON "ff"."ff_locations" ("environment_l1", "venue_l2") WHERE "is_active";
CREATE INDEX IF NOT EXISTS "ff_locations_country_idx"       ON "ff"."ff_locations" ("country_code") WHERE "is_active";

-- ====== T5: ff_scenes（Playwright 上传按钮选择器锁 — dr 已开通的 scene 白名单）======
CREATE TABLE IF NOT EXISTS "ff"."ff_scenes" (
  "id"                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  "business_key"            text UNIQUE NOT NULL,
  "alias"                   text,
  "project_code"            text,
  "capture_mode"            text,
  "environment_l1"          text,
  "venue_l2"                text,
  "scene_l3"                text,
  "deadline"                date,
  "accept_status"           text NOT NULL DEFAULT 'accepting',
  "total_hours_quota"       double precision,
  "used_hours"              double precision NOT NULL DEFAULT 0,
  "source"                  text NOT NULL DEFAULT 'manual',
  "status"                  text NOT NULL DEFAULT 'available',
  "environment_photo_url"   text,
  "is_active"               boolean NOT NULL DEFAULT true,
  "version"                 integer NOT NULL DEFAULT 1,
  "created_at"              timestamptz NOT NULL DEFAULT now(),
  "updated_at"              timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT "ff_scenes_accept_status_chk" CHECK ("accept_status" IN ('accepting','closed','filled')),
  CONSTRAINT "ff_scenes_status_chk"         CHECK ("status" IN ('available','pending','retired')),
  CONSTRAINT "ff_scenes_capture_mode_chk"   CHECK ("capture_mode" IS NULL OR "capture_mode" IN ('single','three_views','stereo')),
  CONSTRAINT "ff_scenes_source_chk"         CHECK ("source" IN ('manual','frameforge')),
  CONSTRAINT "ff_scenes_quota_chk"          CHECK ("used_hours" >= 0 AND ("total_hours_quota" IS NULL OR "used_hours" <= "total_hours_quota"))
);
CREATE INDEX IF NOT EXISTS "ff_scenes_project_idx"     ON "ff"."ff_scenes" ("project_code");
CREATE INDEX IF NOT EXISTS "ff_scenes_status_idx"      ON "ff"."ff_scenes" ("status")      WHERE "is_active";
CREATE INDEX IF NOT EXISTS "ff_scenes_accept_idx"      ON "ff"."ff_scenes" ("accept_status") WHERE "is_active";
CREATE INDEX IF NOT EXISTS "ff_scenes_env_venue_idx"   ON "ff"."ff_scenes" ("environment_l1", "venue_l2", "scene_l3");

-- ====== T6: ff_scene_applications（dr 未开通 scene 申请池）======
CREATE TABLE IF NOT EXISTS "ff"."ff_scene_applications" (
  "id"                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  "business_key"            text UNIQUE NOT NULL,
  "alias"                   text,
  "environment_l1"          text,
  "venue_l2"                text,
  "scene_l3"                text,
  "deadline"                date,
  "total_hours_quota"       double precision,
  "application_status"      text NOT NULL DEFAULT 'draft',
  "applied_by_user_key"     text,
  "function_description"    text,
  "dedup_against"           text,
  "approved_scene_id"       uuid REFERENCES "ff"."ff_scenes"("id") ON DELETE SET NULL,
  "environment_photo_url"   text,
  "decided_at"              timestamptz,
  "is_active"               boolean NOT NULL DEFAULT true,
  "version"                 integer NOT NULL DEFAULT 1,
  "created_at"              timestamptz NOT NULL DEFAULT now(),
  "updated_at"              timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT "ff_scene_applications_status_chk" CHECK ("application_status" IN ('draft','submitted_to_dr','approved','rejected'))
);
CREATE INDEX IF NOT EXISTS "ff_scene_applications_status_idx"   ON "ff"."ff_scene_applications" ("application_status") WHERE "is_active";
CREATE INDEX IF NOT EXISTS "ff_scene_applications_applied_idx"  ON "ff"."ff_scene_applications" ("applied_by_user_key") WHERE "is_active";

-- ====== T7: ff_video_uploads（上传有效性表单 + 上传状态机）======
CREATE TABLE IF NOT EXISTS "ff"."ff_video_uploads" (
  "id"                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  "business_key"          text UNIQUE NOT NULL,
  "path"                  text NOT NULL,
  "source_format"         text,
  "capture_mode"          text,
  "project_code"          text,
  "scene_id"              uuid REFERENCES "ff"."ff_scenes"("id")     ON DELETE RESTRICT,
  "operator_id"           uuid REFERENCES "ff"."ff_operators"("id")  ON DELETE RESTRICT,
  "location_id"           uuid REFERENCES "ff"."ff_locations"("id")  ON DELETE RESTRICT,
  "task_description"      text,
  "notes"                 text,
  "recorded_at"           timestamptz,
  "duration_seconds"      integer,
  "score_composite"       integer,
  "uploaded"              boolean NOT NULL DEFAULT false,
  "uploaded_at"           timestamptz,
  "storage_provider"      text NOT NULL DEFAULT 'cos',
  "file_size_bytes"       bigint,
  "fps"                   double precision,
  "frame_count"           integer,
  "is_active"             boolean NOT NULL DEFAULT true,
  "version"               integer NOT NULL DEFAULT 1,
  "created_at"            timestamptz NOT NULL DEFAULT now(),
  "updated_at"            timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT "ff_video_uploads_capture_mode_chk"   CHECK ("capture_mode" IS NULL OR "capture_mode" IN ('single','three_views','stereo')),
  CONSTRAINT "ff_video_uploads_source_format_chk"  CHECK ("source_format" IS NULL OR "source_format" IN ('mp4','mcap','hmd')),
  CONSTRAINT "ff_video_uploads_storage_chk"        CHECK ("storage_provider" IN ('cos','aws_s3','tencent_cos')),
  CONSTRAINT "ff_video_uploads_score_chk"          CHECK ("score_composite" IS NULL OR "score_composite" BETWEEN 0 AND 100),
  CONSTRAINT "ff_video_uploads_fps_chk"            CHECK ("fps" IS NULL OR "fps" > 0),
  CONSTRAINT "ff_video_uploads_business_key_eq_path_chk" CHECK ("business_key" = "path")
);
CREATE INDEX IF NOT EXISTS "ff_video_uploads_scene_idx"      ON "ff"."ff_video_uploads" ("scene_id")    WHERE "is_active";
CREATE INDEX IF NOT EXISTS "ff_video_uploads_operator_idx"   ON "ff"."ff_video_uploads" ("operator_id") WHERE "is_active";
CREATE INDEX IF NOT EXISTS "ff_video_uploads_location_idx"   ON "ff"."ff_video_uploads" ("location_id") WHERE "is_active";
CREATE INDEX IF NOT EXISTS "ff_video_uploads_path_idx"       ON "ff"."ff_video_uploads" ("path");
CREATE INDEX IF NOT EXISTS "ff_video_uploads_uploaded_idx"   ON "ff"."ff_video_uploads" ("uploaded", "uploaded_at");
