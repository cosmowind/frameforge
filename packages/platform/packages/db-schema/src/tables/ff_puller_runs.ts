// T13 — Puller 拉取记录（plan2 新增）
import { uuid, integer, bigint, numeric, timestamp, jsonb, index } from 'drizzle-orm/pg-core'
import { vumSchema } from '../schema'
import { runStatusEnum } from '../enums'

export const pullerRuns = vumSchema.table(
  'ff_puller_runs',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    runStartedAt: timestamp('run_started_at', { withTimezone: true }).defaultNow().notNull(),
    runFinishedAt: timestamp('run_finished_at', { withTimezone: true }),
    filesPulled: integer('files_pulled').notNull().default(0),
    bytesPulled: bigint('bytes_pulled', { mode: 'number' }).notNull().default(0),
    costCny: numeric('cost_cny', { precision: 10, scale: 4 }),
    errors: jsonb('errors').$type<Array<Record<string, unknown>>>(),
    status: runStatusEnum('status').notNull(),
  },
  (t) => ({
    statusIdx: index('ff_puller_runs_status_idx').on(t.status),
    startedAtIdx: index('ff_puller_runs_started_at_idx').on(t.runStartedAt),
  }),
)

export type PullerRun = typeof pullerRuns.$inferSelect
export type NewPullerRun = typeof pullerRuns.$inferInsert
