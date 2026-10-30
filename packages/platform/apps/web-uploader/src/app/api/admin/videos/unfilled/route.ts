// GET /api/admin/videos/unfilled?limit=50&offset=0&recorder=&task=&env_id=&uploaded=
// 列"未填全"视频：recorder_id/task_id/env_id 为空 或 uploaded != 'Yes'
// 数据源：public.videos (旧表)

import type { NextRequest } from 'next/server'
import { queryCrossSchema } from '@/lib/db'
import { handleApiError, ok } from '@/lib/api-error'

export interface UnfilledVideoRow {
  path: string
  scan_date: string | null
  duration_sec: string | null
  file_type: string | null
  device_id: string | null
  recorder_id: string | null
  recorder_name: string | null
  task_id: string | null
  task_product: string | null
  task_process: string | null
  difficulty: string | null
  env_id: string | null
  env_name: string | null
  uploaded: string | null
  score: string | null
  // 标记哪些字段缺失
  missing: ('recorder' | 'task' | 'env' | 'uploaded')[]
}

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url)
    const limit = Math.min(Number(searchParams.get('limit') ?? 50), 200)
    const offset = Math.max(Number(searchParams.get('offset') ?? 0), 0)
    const recorderFilter = searchParams.get('recorder') || null
    const taskFilter = searchParams.get('task') || null
    const envFilter = searchParams.get('env_id') || null
    const uploadedFilter = searchParams.get('uploaded') // 'yes' | 'no' | null

    const where: string[] = [
      `(v.recorder_id IS NULL OR v.recorder_id = '' OR v.task_id IS NULL OR v.task_id = '' OR v.env_id IS NULL OR v.env_id = '' OR v.uploaded IS NULL OR v.uploaded != 'Yes')`,
    ]
    const params: unknown[] = []
    if (recorderFilter) {
      params.push(recorderFilter)
      where.push(`v.recorder_id = $${params.length}`)
    }
    if (taskFilter) {
      params.push(taskFilter)
      where.push(`v.task_id = $${params.length}`)
    }
    if (envFilter) {
      params.push(envFilter)
      where.push(`v.env_id = $${params.length}`)
    }
    if (uploadedFilter === 'yes') where.push(`v.uploaded = 'Yes'`)
    if (uploadedFilter === 'no') where.push(`(v.uploaded IS NULL OR v.uploaded != 'Yes')`)

    params.push(limit)
    const limitIdx = params.length
    params.push(offset)
    const offsetIdx = params.length

    const rows = await queryCrossSchema<{
      path: string
      scan_date: string | null
      duration_sec: string | null
      file_type: string | null
      device_id: string | null
      recorder_id: string | null
      recorder_name: string | null
      task_id: string | null
      task_product: string | null
      task_process: string | null
      difficulty: string | null
      env_id: string | null
      env_name: string | null
      uploaded: string | null
      score: string | null
    }>(
      `
      SELECT
        v.path, v.scan_date, v.duration_sec, v.file_type, v.device_id,
        NULLIF(v.recorder_id, '') AS recorder_id,
        c.name AS recorder_name,
        NULLIF(v.task_id, '') AS task_id,
        t.product AS task_product,
        t.process AS task_process,
        t.difficulty,
        NULLIF(v.env_id, '') AS env_id,
        e.environment AS env_name,
        v.uploaded,
        v.score
      FROM public.videos v
      LEFT JOIN public.recorders c ON c.id = v.recorder_id
      LEFT JOIN public.tasks t ON t.task_id = v.task_id
      LEFT JOIN public.environments e ON e.env_id = v.env_id
      WHERE ${where.join(' AND ')}
      ORDER BY v.scan_date DESC NULLS LAST, v.path ASC
      LIMIT $${limitIdx} OFFSET $${offsetIdx}
      `,
      params,
    )

    const totalRow = await queryCrossSchema<{ count: string }>(
      `SELECT COUNT(*) AS count FROM public.videos v WHERE ${where
        .filter((w) => !/LIMIT|FETCH|OFFSET/.test(w))
        .join(' AND ')}`,
      params.slice(0, params.length - 2),
    )

    const normalized = rows.map((r) => {
      const missing: UnfilledVideoRow['missing'] = []
      if (!r.recorder_id) missing.push('recorder')
      if (!r.task_id) missing.push('task')
      if (!r.env_id) missing.push('env')
      if ((r.uploaded ?? '').toLowerCase() !== 'yes') missing.push('uploaded')
      return { ...r, missing }
    })

    return ok({
      rows: normalized,
      total: Number(totalRow[0]?.count ?? 0),
      limit,
      offset,
    })
  } catch (err) {
    return handleApiError(err)
  }
}