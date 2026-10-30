// T1 — 区域字典
import { uuid, text, boolean, timestamp, uniqueIndex } from 'drizzle-orm/pg-core'
import { vumSchema } from '../schema'

export const regions = vumSchema.table(
  'ff_regions',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    code: text('code').notNull(),
    nameCn: text('name_cn').notNull(),
    nameEn: text('name_en'),
    isActive: boolean('is_active').notNull().default(true),
    createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull(),
  },
  (t) => ({
    codeIdx: uniqueIndex('ff_regions_code_idx').on(t.code),
  }),
)

export type Region = typeof regions.$inferSelect
export type NewRegion = typeof regions.$inferInsert
