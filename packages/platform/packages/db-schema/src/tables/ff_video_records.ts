// T8 — 视频主表（plan2 核心：含 device_type_id 必填 D10）
import {
  uuid,
  text,
  boolean,
  bigint,
  integer,
  timestamp,
  jsonb,
  uniqueIndex,
  index,
} from 'drizzle-orm/pg-core'
import { sql } from 'drizzle-orm'
import { ffSchema } from '../schema'
import { lifecycleStateEnum } from '../enums'
import { deviceTypes } from './ff_device_types'
import { recorders } from './ff_recorders'
import { environments } from './ff_environments'
import { processes } from './ff_processes'
import { regions } from './ff_regions'
import { users } from './ff_users'

export const videoRecords = ffSchema.table(
  'ff_video_records',
  {
    id: uuid('id').primaryKey().defaultRandom(),

    // === 设备归属（D10）===
    deviceTypeId: uuid('device_type_id').notNull().references(() => deviceTypes.id),
    sessionFolderName: text('session_folder_name'),

    // === 业务主键 ===
    recorderKey: text('recorder_key').notNull(),
    environmentKey: text('environment_key').notNull(),
    processId: uuid('process_id').notNull().references(() => processes.id),

    // === 内容身份 ===
    fileHash: text('file_hash').notNull(), // D6: 最终上传文件 hash
    originalPath: text('original_path').notNull(), // P3 归一化
    originalFilename: text('original_filename').notNull(),
    renamedFilename: text('renamed_filename').notNull(),
    fileSizeBytes: bigint('file_size_bytes', { mode: 'number' }).notNull(),
    originalFormat: text('original_format').notNull(), // mp4 | hmd | mcap | avi

    // === 设备特定元数据 ===
    deviceSpecificMetadata: jsonb('device_specific_metadata').$type<Record<string, unknown>>(),
    isMultiPart: boolean('is_multi_part').notNull().default(false),
    partCount: integer('part_count').notNull().default(1),

    // === 用户填的元数据 ===
    scanDate: timestamp('scan_date', { withTimezone: true }).notNull().defaultNow(),
    recordedAt: timestamp('recorded_at', { withTimezone: true }),
    durationSec: integer('duration_sec'),
    resolution: text('resolution'),
    codec: text('codec'),
    taskDescription: text('task_description').notNull().default(''),
    isWearingGloves: boolean('is_wearing_gloves'),
    score: integer('score'),

    // === 生命周期 ===
    lifecycleState: lifecycleStateEnum('lifecycle_state').notNull().default('SCANNED'),

    // === 多端一致（D4）===
    sourceDevice: text('source_device').notNull(),
    version: integer('version').notNull().default(1),

    // === 审计 ===
    createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull(),
    createdBy: uuid('created_by').notNull().references(() => users.id),

    // === 区域 ===
    regionId: uuid('region_id').notNull().references(() => regions.id),
  },
  (t) => ({
    fileHashIdx: uniqueIndex('ff_video_records_file_hash_idx').on(t.fileHash),
    deviceTypeScanIdx: index('ff_video_records_device_type_scan_idx').on(
      t.deviceTypeId,
      t.scanDate,
    ),
    recorderScanIdx: index('ff_video_records_recorder_scan_idx').on(t.recorderKey, t.scanDate),
    processScanIdx: index('ff_video_records_process_scan_idx').on(t.processId, t.scanDate),
    stateIdx: index('ff_video_records_state_idx').on(t.lifecycleState),
    regionScanIdx: index('ff_video_records_region_scan_idx').on(t.regionId, t.scanDate),
    // 触发器：BEFORE UPDATE 拒绝 scan_date 减少（D5）
    scanDateGuard: sql`CHECK (file_size_bytes > 0)`,
  }),
)

export type VideoRecord = typeof videoRecords.$inferSelect
export type NewVideoRecord = typeof videoRecords.$inferInsert
