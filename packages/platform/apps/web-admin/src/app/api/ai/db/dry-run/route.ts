// POST /api/ai/db/dry-run — 给 AI agent 用的 dry-run 预览
// body: { updates: [{ where: { path }, set: {...} }] }
// 返回每条 before / proposed / diffs（不写）

import type { NextRequest } from 'next/server'
import { Pool } from 'pg'
import { z } from 'zod'
import { dryRunBatchUpdate } from '@ff/db-schema'
import { ok, fail, ApiError, handleApiError } from '@/lib/api-error'

const Body = z.object({
  table: z.enum(['public.videos']).default('public.videos'),
  updates: z
    .array(
      z.object({
        where: z.object({ path: z.string().min(1) }),
        set: z.record(z.string(), z.string().nullable()),
      }),
    )
    .min(1)
    .max(500),
})

let _pool: Pool | null = null
function pool(): Pool {
  if (_pool) return _pool
  _pool = new Pool({
    connectionString: process.env.DATABASE_URL!,
    options: `-c search_path=${process.env.DATABASE_SCHEMA ?? 'ff'},public`,
    max: 5,
  })
  return _pool
}

export async function POST(req: NextRequest) {
  try {
    const json = await req.json()
    const parsed = Body.safeParse(json)
    if (!parsed.success) throw new ApiError('VALIDATION', 'invalid body', 422, parsed.error.flatten())
    const r = await dryRunBatchUpdate(pool(), parsed.data.table, parsed.data.updates)
    return ok({
      totalRows: r.totalRows,
      totalChanges: r.totalChanges,
      results: r.results,
    })
  } catch (err) {
    if (err instanceof ApiError) return fail(err.code, err.message, err.status, err.details)
    return handleApiError(err)
  }
}