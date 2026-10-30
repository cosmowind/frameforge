// T12 — SCF 函数调用审计（plan2 新增）
import { uuid, text, integer, numeric, timestamp, jsonb, index } from 'drizzle-orm/pg-core'
import { sql } from 'drizzle-orm'
import { vumSchema } from '../schema'
import { scfTriggerEnum, runStatusEnum } from '../enums'

export const scfInvocations = vumSchema.table(
  'ff_scf_invocations',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    functionName: text('function_name').notNull(),
    triggerEvent: scfTriggerEnum('trigger_event').notNull(),
    inputEvent: jsonb('input_event').notNull(),
    status: runStatusEnum('status').notNull(),
    output: jsonb('output'),
    errorMessage: text('error_message'),
    durationMs: integer('duration_ms'),
    costCny: numeric('cost_cny', { precision: 10, scale: 6 }),
    startedAt: timestamp('started_at', { withTimezone: true }).defaultNow().notNull(),
    finishedAt: timestamp('finished_at', { withTimezone: true }),
  },
  (t) => ({
    functionIdx: index('ff_scf_invocations_function_idx').on(t.functionName),
    statusIdx: index('ff_scf_invocations_status_idx').on(t.status),
    startedAtIdx: index('ff_scf_invocations_started_at_idx').on(t.startedAt),
  }),
)

export type ScfInvocation = typeof scfInvocations.$inferSelect
export type NewScfInvocation = typeof scfInvocations.$inferInsert
