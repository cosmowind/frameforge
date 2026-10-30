// GET /api/admin/stats/difficulty?from=&to=
// 聚合：按 difficulty (easy/medium/hard) 分组

import type { NextRequest } from 'next/server'
import { queryCrossSchema } from '@/lib/db'
import { handleApiError, ok } from '@/lib/api-error'

export interface DifficultyStatsRow {
  difficulty: string
  task_count: number
  video_count: number
  duration_sec_total: number
}

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url)
    const from = searchParams.get('from') ?? '1970-01-01'
    const to = searchParams.get('to') ?? '2999-12-31'

    const rows = await queryCrossSchema<DifficultyStatsRow>(
      `
      SELECT
        COALESCE(NULLIF(t.difficulty, ''), 'unknown') AS difficulty,
        COUNT(DISTINCT t.task_id)                AS task_count,
        COUNT(v.path)                            AS video_count,
        COALESCE(SUM(
          CASE WHEN v.duration_sec ~ '^[0-9]+$' THEN v.duration_sec::bigint ELSE 0 END
        ), 0)::bigint                             AS duration_sec_total
      FROM public.videos v
      INNER JOIN public.tasks t ON t.task_id = v.task_id
      WHERE v.scan_date BETWEEN $1 AND $2
        AND v.recorder_id <> ''
      GROUP BY COALESCE(NULLIF(t.difficulty, ''), 'unknown')
      ORDER BY difficulty
      `,
      [from, to],
    )

    return ok({
      from,
      to,
      rows: rows.map((r) => ({ ...r, duration_sec_total: Number(r.duration_sec_total ?? 0) })),
      count: rows.length,
    })
  } catch (err) {
    return handleApiError(err)
  }
}