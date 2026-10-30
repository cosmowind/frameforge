// GET /api/admin/stats/tasks?from=&to=
// 聚合：每个 task（按 product/task/process 三段粒度）在 [from, to] 期间的视频/时长
// 数据源：public.videos (有 recorder_id 关联) + public.tasks

import type { NextRequest } from 'next/server'
import { queryCrossSchema } from '@/lib/db'
import { handleApiError, ok } from '@/lib/api-error'

export interface TaskStatsRow {
  task_id: string
  product: string | null
  task: string | null
  process: string | null
  process_en: string | null
  difficulty: string | null
  quota_min: string | null
  video_count: number
  duration_sec_total: number
  distinct_recorders: number
  uploaded_count: number
}

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url)
    const from = searchParams.get('from') ?? '1970-01-01'
    const to = searchParams.get('to') ?? '2999-12-31'

    const rows = await queryCrossSchema<{
      task_id: string
      product: string | null
      task: string | null
      process: string | null
      process_en: string | null
      difficulty: string | null
      quota_min: string | null
      video_count: string
      duration_sec_total: string
      distinct_recorders: string
      uploaded_count: string
    }>(
      `
      SELECT
        t.task_id,
        t.product                                AS product,
        t.task                                   AS task,
        t.process                                AS process,
        t.process_en                             AS process_en,
        t.difficulty                             AS difficulty,
        t.quota_min                              AS quota_min,
        COUNT(v.path)                            AS video_count,
        COALESCE(SUM(
          CASE WHEN v.duration_sec ~ '^[0-9]+$' THEN v.duration_sec::bigint ELSE 0 END
        ), 0)::bigint                             AS duration_sec_total,
        COUNT(DISTINCT v.recorder_id)           AS distinct_recorders,
        COUNT(*) FILTER (WHERE v.uploaded = 'Yes') AS uploaded_count
      FROM public.tasks t
      INNER JOIN public.videos v ON v.task_id = t.task_id
      WHERE v.scan_date BETWEEN $1 AND $2
        AND v.recorder_id <> ''
      GROUP BY t.task_id
      ORDER BY video_count DESC, task NULLS LAST
      `,
      [from, to],
    )

    return ok({
      from,
      to,
      rows: rows.map((r) => ({
        task_id: r.task_id,
        product: r.product,
        task: r.task,
        process: r.process,
        process_en: r.process_en,
        difficulty: r.difficulty,
        quota_min: r.quota_min,
        video_count: Number(r.video_count ?? 0),
        duration_sec_total: Number(r.duration_sec_total ?? 0),
        distinct_recorders: Number(r.distinct_recorders ?? 0),
        uploaded_count: Number(r.uploaded_count ?? 0),
      })),
      count: rows.length,
    })
  } catch (err) {
    return handleApiError(err)
  }
}