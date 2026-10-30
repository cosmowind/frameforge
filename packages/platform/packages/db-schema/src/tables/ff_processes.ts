// T6 — 工序（FK → products，D7）
import { uuid, text, boolean, integer, timestamp, uniqueIndex, index } from 'drizzle-orm/pg-core'
import { vumSchema } from '../schema'
import { products } from './ff_products'
import { users } from './ff_users'

export const processes = vumSchema.table(
  'ff_processes',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    productId: uuid('product_id').notNull().references(() => products.id),
    businessKey: text('business_key').notNull(),
    nameCn: text('name_cn').notNull(),
    nameEn: text('name_en'),
    sequence: integer('sequence').notNull().default(0),
    isActive: boolean('is_active').notNull().default(true),
    version: integer('version').notNull().default(1),
    sourceDevice: text('source_device'),
    createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull(),
    createdBy: uuid('created_by').references(() => users.id),
  },
  (t) => ({
    productKeyIdx: uniqueIndex('ff_processes_product_key_idx').on(t.productId, t.businessKey),
    productSequenceIdx: index('ff_processes_product_sequence_idx').on(t.productId, t.sequence),
  }),
)

export type Process = typeof processes.$inferSelect
export type NewProcess = typeof processes.$inferInsert
