// v2 表单 zod schema（事实层：docs/v2-forms-spec.md）
// A 类系统必填在 schema 上 NOT NULL DEFAULT；B 类业务必填在这里 zod min(1) 强校验
// N 类非业务必填 → zod 接受 undefined，不强制
import { z } from 'zod'
import { BusinessKeySchema } from './common'
import {
  HAND_OPTIONS,
  GENDER_OPTIONS,
  AGE_RANGE_OPTIONS,
  CAPTURE_MODE_OPTIONS,
  SCENE_STATUS_OPTIONS,
  SCENE_ACCEPT_STATUS_OPTIONS,
  SCENE_SOURCE_OPTIONS,
  APPLICATION_STATUS_OPTIONS,
  SOURCE_FORMAT_OPTIONS,
  STORAGE_PROVIDER_OPTIONS,
} from '../constants/v2-options'

// ====== 1. ff_operators（POST 创建）======
// B 类：alias + name + hand + gender + age_range + job_role + role_experience + consented_to_recording=true
// A 类：business_key（NOT NULL，server-gen）
// N 类：hand_size_cm（DB 列保留，phase 2 用；email 同 v2-forms-spec §1.2 标记为 N，本期不上 form）
export const OperatorCreateSchema = z.object({
  alias: z.string().min(1, 'alias 必填').max(64),
  name: z.string().min(1, 'name 必填').max(64),
  hand: z.enum(HAND_OPTIONS),
  gender: z.enum(GENDER_OPTIONS),
  age_range: z.enum(AGE_RANGE_OPTIONS),
  job_role: z.string().min(1, 'job_role 必填').max(64),
  role_experience: z.string().min(1, 'role_experience 必填').max(64),
  consented_to_recording: z.literal(true, {
    errorMap: () => ({ message: '必须勾选 consented_to_recording（合规硬要求）' }),
  }),
  // 可选：手大小
  hand_size_cm: z.coerce.number().positive().max(50).optional(),
})
export type OperatorCreate = z.infer<typeof OperatorCreateSchema>

// 行：GET 返回（包含系统字段）
export const OperatorRowSchema = OperatorCreateSchema.partial().extend({
  id: z.string().uuid(),
  business_key: BusinessKeySchema,
  is_active: z.boolean(),
  version: z.number().int().min(0),
  created_at: z.string(),
  updated_at: z.string(),
})
export type OperatorRow = z.infer<typeof OperatorRowSchema>

// ====== 2. ff_locations（POST 创建 — phase 1.1 接）======
const OptionalText = (max: number) =>
  z.preprocess(
    (value) => (typeof value === 'string' && value.trim() === '' ? undefined : value),
    z.string().max(max).optional(),
  )

const OptionalCoordinate = (min: number, max: number) =>
  z.preprocess(
    (value) => (value === '' || value === null ? undefined : value),
    z.coerce.number().min(min).max(max).optional(),
  )

export const LocationCreateSchema = z.object({
  alias: z.string().trim().min(1, 'alias 必填').max(64),
  environment_l1: z.string().trim().min(1, 'environment_l1 必填').max(64),
  venue_l2: z.string().trim().min(1, 'venue_l2 必填').max(128),
  business_name: z.string().trim().min(1, 'business_name 必填').max(128),
  business_type: z.string().trim().min(1, 'business_type 必填').max(64),
  address_line1: z.string().trim().min(1, 'address_line1 必填').max(256),
  city: z.string().trim().min(1, 'city 必填').max(64),
  region_state: z.string().trim().min(1, 'region_state 必填').max(64),
  zip_postal: z.string().trim().min(1, 'zip_postal 必填').max(16),
  // N 类
  address_line2: OptionalText(256),
  country_code: OptionalText(8),
  lat: OptionalCoordinate(-90, 90),
  lng: OptionalCoordinate(-180, 180),
})
export type LocationCreate = z.infer<typeof LocationCreateSchema>

export const LocationRowSchema = LocationCreateSchema.partial().extend({
  id: z.string().uuid(),
  business_key: BusinessKeySchema,
  is_active: z.boolean(),
  version: z.number().int().min(0),
  created_at: z.string(),
  updated_at: z.string(),
})
export type LocationRow = z.infer<typeof LocationRowSchema>

// ====== 3. ff_scenes（POST 创建 — phase 1.2 接）======
export const SceneCreateSchema = z.object({
  alias: z.string().min(1).max(64),
  project_code: z.string().min(1).max(32),
  capture_mode: z.enum(CAPTURE_MODE_OPTIONS).optional(),
  environment_l1: z.string().min(1).max(64),
  venue_l2: z.string().min(1).max(128),
  scene_l3: z.string().min(1).max(128),
  deadline: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'YYYY-MM-DD').optional(),
  accept_status: z.enum(SCENE_ACCEPT_STATUS_OPTIONS).default('accepting'),
  total_hours_quota: z.coerce.number().positive().optional(),
  // phase 2 接图床
  environment_photo_url: z.string().url().optional().or(z.literal('').transform(() => undefined)),
})
export type SceneCreate = z.infer<typeof SceneCreateSchema>

// ====== 4. ff_scene_applications（POST 创建 — phase 1.3 接）======
export const SceneApplicationCreateSchema = z.object({
  alias: z.string().min(1).max(64),
  environment_l1: z.string().min(1).max(64),
  venue_l2: z.string().min(1).max(128),
  scene_l3: z.string().min(1).max(128),
  function_description: z.string().min(1).max(1024).optional(),
  dedup_against: z.string().min(1).max(1024).optional(),
  deadline: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional(),
  total_hours_quota: z.coerce.number().positive().optional(),
})
export type SceneApplicationCreate = z.infer<typeof SceneApplicationCreateSchema>

// ====== 5. ff_video_uploads（POST 创建 — uploader 端）======
// 拖完文件 preview：task_description 可空
export const VideoUploadPreviewSchema = z.object({
  path: z.string().min(1).max(512),
  source_format: z.enum(SOURCE_FORMAT_OPTIONS),
  capture_mode: z.enum(CAPTURE_MODE_OPTIONS).optional(),
  project_code: z.string().max(32).default('summit-02'),
  scene_id: z.string().uuid(),
  operator_id: z.string().uuid(),
  location_id: z.string().uuid(),
})
export type VideoUploadPreview = z.infer<typeof VideoUploadPreviewSchema>

// 完成上传：task_description 必填
export const VideoUploadCommitSchema = VideoUploadPreviewSchema.extend({
  task_description: z.string().min(1, '任务描述必填').max(500),
})
export type VideoUploadCommit = z.infer<typeof VideoUploadCommitSchema>

// 响应包装
export const DryRunResultSchema = z.object({
  mode: z.literal('dry-run'),
  business_key: z.string(),
  payload: z.record(z.unknown()),
  sql_preview: z.string(),
})
export type DryRunResult = z.infer<typeof DryRunResultSchema>

export const CommitResultSchema = z.object({
  mode: z.literal('commit'),
  business_key: z.string(),
  row: z.record(z.unknown()),
})
export type CommitResult = z.infer<typeof CommitResultSchema>
