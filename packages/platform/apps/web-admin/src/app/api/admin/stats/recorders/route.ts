// GET /api/admin/stats/recorders?from=&to=
// 聚合：每个 recorder 在 [from, to] 期间的视频数 / 时长 / 任务数
// 数据源：public.videos (有 recorder_id 关联) + public.recorders + public.tasks

import type { NextRequest } from 'next/server'
import { queryCrossSchema } from '@/lib/db'
import { handleApiError, ok } from '@/lib/api-error'

export interface RecorderStatsRow {
  recorder_id: string
  recorder_name: string | null
  phone: string | null
  operator_job: string | null
  task_count: number
  video_count: number
  duration_sec_total: number
  duration_min_total: number
  uploaded_count: number
  first_seen_at: string | null
  last_seen_at: string | null
}

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url)
    const from = searchParams.get('from') ?? '1970-01-01'
    const to = searchParams.get('to') ?? '2999-12-31'

    const rows = await queryCrossSchema<{
      recorder_id: string
      recorder_name: string | null
      phone: string | null
      operator_job: string | null
      task_count: string
      video_count: string
      duration_sec_total: string
      uploaded_count: string
      first_seen_at: string | null
      last_seen_at: string | null
    }>(
      `
      SELECT
        c.id                                    AS recorder_id,
        c.name                                  AS recorder_name,
        c.phone                                 AS phone,
        c.operator_job                          AS operator_job,
        COUNT(DISTINCT v.task_id)               AS task_count,
        COUNT(v.path)                           AS video_count,
        COALESCE(SUM(
          CASE WHEN v.duration_sec ~ '^[0-9]+$' THEN v.duration_sec::bigint ELSE 0 END
        ), 0)::bigint                            AS duration_sec_total,
        COUNT(*) FILTER (WHERE v.uploaded = 'Yes') AS uploaded_count,
        MIN(v.scan_date)                        AS first_seen_at,
        MAX(v.scan_date)                        AS last_seen_at
      FROM public.recorders c
      INNER JOIN public.videos v ON v.recorder_id = c.id
      LEFT JOIN public.tasks t ON t.task_id = v.task_id
      WHERE v.scan_date BETWEEN $1 AND $2
      GROUP BY c.id
      ORDER BY video_count DESC, recorder_name NULLS LAST
      `,
      [from, to],
    )

    const normalized = rows.map((r) => ({
      recorder_id: r.recorder_id,
      recorder_name: r.recorder_name,
      phone: r.phone,
      operator_job: r.operator_job,
      task_count: Number(r.task_count ?? 0),
      video_count: Number(r.video_count ?? 0),
      duration_sec_total: Number(r.duration_sec_total ?? 0),
      duration_min_total: Math.round(Number(r.duration_sec_total ?? 0) / 60),
      uploaded_count: Number(r.uploaded_count ?? 0),
      first_seen_at: r.first_seen_at,
      last_seen_at: r.last_seen_at,
    }))

    return ok({ from, to, rows: normalized, count: normalized.length })
  } catch (err) {
    return handleApiError(err)
  }
}