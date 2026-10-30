// POST /api/ai/db/commit — 给 AI agent 用的真实写入（事务内）
// body: { updates: [{ where: { path }, set: {...} }], confirm: true }
// 必须 confirm:true 才执行

import type { NextRequest } from 'next/server'
import { Pool } from 'pg'
import { z } from 'zod'
import { commitBatchUpdate } from '@ff/db-schema'
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
  confirm: z.literal(true), // 强制要求 confirm=true
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
    if (!parsed.success) {
      throw new ApiError('VALIDATION', 'invalid body or confirm: true required', 422, parsed.error.flatten())
    }
    const r = await commitBatchUpdate(pool(), parsed.data.table, parsed.data.updates)
    return ok({ total: r.total, updated: r.updated, notFound: r.notFound })
  } catch (err) {
    if (err instanceof ApiError) return fail(err.code, err.message, err.status, err.details)
    return handleApiError(err)
  }
}