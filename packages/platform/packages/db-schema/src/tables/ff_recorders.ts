// T3 — 录制员
import { uuid, text, boolean, integer, timestamp, uniqueIndex, index } from 'drizzle-orm/pg-core'
import { vumSchema } from '../schema'
import { regions } from './ff_regions'
import { users } from './ff_users'

export const recorders = vumSchema.table(
  'ff_recorders',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    businessKey: text('business_key').notNull(),
    nameCn: text('name_cn').notNull(),
    nameEn: text('name_en'),
    regionId: uuid('region_id').notNull().references(() => regions.id),
    phone: text('phone'),
    remark: text('remark'),
    isActive: boolean('is_active').notNull().default(true),
    version: integer('version').notNull().default(1),
    sourceDevice: text('source_device'),
    createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull(),
    createdBy: uuid('created_by').references(() => users.id),
  },
  (t) => ({
    businessKeyIdx: uniqueIndex('ff_recorders_business_key_idx').on(t.businessKey),
    regionIdx: index('ff_recorders_region_idx').on(t.regionId),
  }),
)

export type Recorder = typeof recorders.$inferSelect
export type NewRecorder = typeof recorders.$inferInsert
