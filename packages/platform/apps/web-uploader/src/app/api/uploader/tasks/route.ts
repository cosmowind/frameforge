// /api/uploader/tasks
// GET  列出 public.tasks（按 scene / env_id 过滤）
// POST body: { path, taskId } — 写入 videos.task_id（录制员登记任务）
// 写入前 dry-run 预览（plan2 D1）
import { NextRequest, NextResponse } from 'next/server'
import { z } from 'zod'
import { queryCrossSchema } from '@/lib/db'
import { fail, handleApiError, ApiError } from '@/lib/api-error'

export const dynamic = 'force-dynamic'

export async function GET(req: NextRequest) {
  try {
    const sp = req.nextUrl.searchParams
    const envId = sp.get('envId') ?? ''
    const q = sp.get('q') ?? ''
    const limit = Math.min(Number(sp.get('limit') ?? 100), 500)
    const where: string[] = []
    const params: unknown[] = []
    if (envId) {
      params.push(envId)
      where.push(`environment = $${params.length}`)
    }
    if (q) {
      params.push(`%${q}%`)
      const i = params.length
      where.push(`(task ILIKE $${i} OR process ILIKE $${i} OR product ILIKE $${i} OR tool ILIKE $${i})`)
    }
    const whereSql = where.length > 0 ? `WHERE ${where.join(' AND ')}` : ''
    params.push(limit)
    const limitIdx = params.length
    const rows = await queryCrossSchema<Record<string, unknown>>(
      `SELECT task_id, task, process, process_en, product, tool, difficulty, quota_min, scene, environment
       FROM public.tasks ${whereSql}
       ORDER BY task_id ASC
       LIMIT $${limitIdx}`,
      params,
    )
    return NextResponse.json({ ok: true, data: { tasks: rows, count: rows.length } })
  } catch (err) {
    console.error('[uploader/tasks GET] error:', err)
    return handleApiError(err)
  }
}

const PostBody = z.object({
  path: z.string().min(1).max(2000),
  taskId: z.string().min(1).max(100),
})

export async function POST(req: NextRequest) {
  try {
    const json = await req.json().catch(() => null)
    const parsed = PostBody.safeParse(json)
    if (!parsed.success) throw new ApiError('VALIDATION', 'invalid body', 422, parsed.error.flatten())
    const commit = req.nextUrl.searchParams.get('commit') === 'true'

    // 验证 task 存在
    const ts = await queryCrossSchema<{ task_id: string; task: string }>(
      `SELECT task_id, task FROM public.tasks WHERE task_id = $1 LIMIT 1`,
      [parsed.data.taskId],
    )
    if (ts.length === 0) {
      throw new ApiError('FORBIDDEN', `task_id "${parsed.data.taskId}" 不存在`, 422)
    }

    // 验证 video 存在
    const vs = await queryCrossSchema<{ path: string; recorder_id: string | null; env_id: string | null }>(
      `SELECT path, recorder_id, env_id FROM public.videos WHERE path = $1 LIMIT 1`,
      [parsed.data.path],
    )
    if (vs.length === 0) {
      throw new ApiError('FORBIDDEN', `video path "${parsed.data.path}" 不存在，请先在 /devices 登记`, 422)
    }

    if (!commit) {
      return NextResponse.json({
        ok: true,
        data: {
          mode: 'dry-run',
          willUpdate: {
            path: parsed.data.path,
            task_id: parsed.data.taskId,
            task_name: ts[0]!.task,
          },
        },
      })
    }
    await queryCrossSchema(
      `UPDATE public.videos SET task_id = $1, updated_at = now() WHERE path = $2`,
      [parsed.data.taskId, parsed.data.path],
    )
    return NextResponse.json({
      ok: true,
      data: { mode: 'commit', path: parsed.data.path, taskId: parsed.data.taskId, taskName: ts[0]!.task },
    })
  } catch (err) {
    if (err instanceof ApiError) return fail(err.code, err.message, err.status, err.details)
    console.error('[uploader/tasks POST] error:', err)
    return handleApiError(err)
  }
}