// T0 — 设备类型字典（plan2 核心：D10 设备适配可扩展）
import { uuid, text, boolean, integer, timestamp, index, uniqueIndex } from 'drizzle-orm/pg-core'
import { vumSchema } from '../schema'
import { sessionNamingEnum, previewEngineEnum, uploadPrepEnum } from '../enums'
import { users } from './ff_users'

export const deviceTypes = vumSchema.table(
  'ff_device_types',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    code: text('code').notNull(),
    nameCn: text('name_cn').notNull(),
    nameEn: text('name_en'),
    rootSubdir: text('root_subdir').notNull(),
    sessionNaming: sessionNamingEnum('session_naming').notNull(),
    fileExtensions: text('file_extensions').array().notNull(),
    previewEngine: previewEngineEnum('preview_engine').notNull(),
    uploadPrep: uploadPrepEnum('upload_prep').notNull(),
    isActive: boolean('is_active').notNull().default(true),
    version: integer('version').notNull().default(1),
    createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull(),
    createdBy: uuid('created_by').references(() => users.id),
  },
  (t) => ({
    codeIdx: uniqueIndex('ff_device_types_code_idx').on(t.code),
    activeIdx: index('ff_device_types_active_idx').on(t.isActive),
  }),
)

export type DeviceType = typeof deviceTypes.$inferSelect
export type NewDeviceType = typeof deviceTypes.$inferInsert
