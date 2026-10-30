// T2 — 账号（与 Clerk 1:1）
import { uuid, text, boolean, timestamp, index } from 'drizzle-orm/pg-core'
import { ffSchema } from '../schema'
import { appRoleEnum } from '../enums'
import { regions } from './ff_regions'

export const users = ffSchema.table(
  'ff_users',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    clerkUserId: text('clerk_user_id').notNull(),
    regionId: uuid('region_id').notNull().references(() => regions.id),
    appRole: appRoleEnum('app_role').notNull(),
    displayName: text('display_name').notNull(),
    phone: text('phone'),
    isActive: boolean('is_active').notNull().default(true),
    lastLoginAt: timestamp('last_login_at', { withTimezone: true }),
    createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull(),
  },
  (t) => ({
    clerkIdx: index('ff_users_clerk_idx').on(t.clerkUserId),
  }),
)

export type User = typeof users.$inferSelect
export type NewUser = typeof users.$inferInsert
