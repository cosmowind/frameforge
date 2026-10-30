// T9 — 上传日志（partner + backup + quark 三目标）
import { uuid, text, integer, timestamp, index } from 'drizzle-orm/pg-core'
import { vumSchema } from '../schema'
import { uploadTargetEnum, uploadAdapterEnum, uploadStatusEnum } from '../enums'
import { videoRecords } from './ff_video_records'

export const uploadLogs = vumSchema.table(
  'ff_upload_logs',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    videoRecordId: uuid('video_record_id')
      .notNull()
      .references(() => videoRecords.id, { onDelete: 'cascade' }),
    target: uploadTargetEnum('target').notNull(),
    adapterKind: uploadAdapterEnum('adapter_kind').notNull(),
    status: uploadStatusEnum('status').notNull().default('pending'),
    attempt: integer('attempt').notNull().default(1),
    remoteId: text('remote_id'),
    remoteUrl: text('remote_url'),
    errorMessage: text('error_message'),
    startedAt: timestamp('started_at', { withTimezone: true }).defaultNow().notNull(),
    finishedAt: timestamp('finished_at', { withTimezone: true }),
    durationMs: integer('duration_ms'),
  },
  (t) => ({
    videoTargetIdx: index('ff_upload_logs_video_target_idx').on(t.videoRecordId, t.target),
    statusIdx: index('ff_upload_logs_status_idx').on(t.status),
    startedAtIdx: index('ff_upload_logs_started_at_idx').on(t.startedAt),
  }),
)

export type UploadLog = typeof uploadLogs.$inferSelect
export type NewUploadLog = typeof uploadLogs.$inferInsert
