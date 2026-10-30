// POST /api/admin/videos/batch-fill
// 批量更新 public.videos 一行或多行的 recorder_id / task_id / env_id / uploaded / score
// body: { updates: [{ path, recorder_id?, task_id?, env_id?, uploaded?, score? }] }

import type { NextRequest } from 'next/server'
import { z } from 'zod'
import { queryCrossSchema, pool } from '@/lib/db'
import { handleApiError, ok, ApiError } from '@/lib/api-error'

const UpdateSchema = z.object({
  path: z.string().min(1),
  recorder_id: z.string().nullable().optional(),
  task_id: z.string().nullable().optional(),
  env_id: z.string().nullable().optional(),
  uploaded: z.enum(['Yes', 'No']).optional(),
  score: z.string().nullable().optional(),
})

const BodySchema = z.object({
  updates: z.array(UpdateSchema).min(1).max(500),
})

export async function POST(req: NextRequest) {
  try {
    const json = await req.json()
    const parsed = BodySchema.safeParse(json)
    if (!parsed.success) {
      throw new ApiError('VALIDATION', 'invalid payload', 422, parsed.error.flatten())
    }
    const { updates } = parsed.data

    // 单条 SQL：跨 schema 写
    const c = await pool.connect()
    try {
      await c.query(`SET search_path TO public`)
      await c.query('BEGIN')
      const results: { path: string; updated: boolean }[] = []
      for (const u of updates) {
        const sets: string[] = []
        const params: unknown[] = []
        if (u.recorder_id !== undefined) {
          params.push(u.recorder_id ?? '')
          sets.push(`recorder_id = $${params.length}`)
        }
        if (u.task_id !== undefined) {
          params.push(u.task_id ?? '')
          sets.push(`task_id = $${params.length}`)
        }
        if (u.env_id !== undefined) {
          params.push(u.env_id ?? '')
          sets.push(`env_id = $${params.length}`)
        }
        if (u.uploaded !== undefined) {
          params.push(u.uploaded)
          sets.push(`uploaded = $${params.length}`)
        }
        if (u.score !== undefined) {
          params.push(u.score ?? '')
          sets.push(`score = $${params.length}`)
        }
        if (sets.length === 0) {
          results.push({ path: u.path, updated: false })
          continue
        }
        sets.push(`updated_at = now()`)
        params.push(u.path)
        const sql = `UPDATE public.videos SET ${sets.join(', ')} WHERE path = $${params.length}`
        const r = await c.query(sql, params as unknown[])
        results.push({ path: u.path, updated: (r.rowCount ?? 0) > 0 })
      }
      await c.query('COMMIT')
      return ok({
        results,
        total: updates.length,
        updated_count: results.filter((r) => r.updated).length,
      })
    } catch (e) {
      await c.query('ROLLBACK').catch(() => {})
      throw e
    } finally {
      c.release()
    }
  } catch (err) {
    return handleApiError(err)
  }
}