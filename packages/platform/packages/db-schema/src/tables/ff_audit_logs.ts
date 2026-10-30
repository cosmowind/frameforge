// T14 — 通用审计日志（plan2 新增，who/when/action/target/before/after）
import { uuid, text, jsonb, timestamp, index } from 'drizzle-orm/pg-core'
import { vumSchema } from '../schema'
import { appRoleEnum } from '../enums'
import { users } from './ff_users'
import { regions } from './ff_regions'

export const auditLogs = vumSchema.table(
  'ff_audit_logs',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    actorUserId: uuid('actor_user_id').notNull().references(() => users.id),
    actorAppRole: appRoleEnum('actor_app_role').notNull(),
    actorRegionId: uuid('actor_region_id').references(() => regions.id),
    action: text('action').notNull(),
    targetTable: text('target_table').notNull(),
    targetId: uuid('target_id').notNull(),
    beforeState: jsonb('before_state').$type<Record<string, unknown>>(),
    afterState: jsonb('after_state').$type<Record<string, unknown>>(),
    sourceDevice: text('source_device'),
    ipAddress: text('ip_address'),
    userAgent: text('user_agent'),
    createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
  },
  (t) => ({
    actorIdx: index('ff_audit_logs_actor_idx').on(t.actorUserId),
    actionIdx: index('ff_audit_logs_action_idx').on(t.action),
    targetIdx: index('ff_audit_logs_target_idx').on(t.targetTable, t.targetId),
    createdAtIdx: index('ff_audit_logs_created_at_idx').on(t.createdAt),
  }),
)

export type AuditLog = typeof auditLogs.$inferSelect
export type NewAuditLog = typeof auditLogs.$inferInsert
