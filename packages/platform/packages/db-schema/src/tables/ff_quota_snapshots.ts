// T11 — 多样性/配额日快照（新增以 recorder_key 维度）
import { uuid, text, integer, date, jsonb, timestamp, uniqueIndex, index } from 'drizzle-orm/pg-core'
import { vumSchema } from '../schema'
import { regions } from './ff_regions'
import { processes } from './ff_processes'

export const quotaSnapshots = vumSchema.table(
  'ff_quota_snapshots',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    snapshotDate: date('snapshot_date').notNull(),
    regionId: uuid('region_id').notNull().references(() => regions.id),
    recorderKey: text('recorder_key').notNull(),
    processId: uuid('process_id').notNull().references(() => processes.id),
    environmentKey: text('environment_key').notNull(),
    countVideos: integer('count_videos').notNull().default(0),
    countMinutes: integer('count_minutes').notNull().default(0),
    quotaWarning: jsonb('quota_warning').$type<Record<string, unknown>>(),
    createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
  },
  (t) => ({
    uniqSnapshot: uniqueIndex('ff_quota_snapshots_uniq').on(
      t.snapshotDate,
      t.regionId,
      t.recorderKey,
      t.processId,
      t.environmentKey,
    ),
    regionDateIdx: index('ff_quota_snapshots_region_date_idx').on(t.regionId, t.snapshotDate),
  }),
)

export type QuotaSnapshot = typeof quotaSnapshots.$inferSelect
export type NewQuotaSnapshot = typeof quotaSnapshots.$inferInsert
