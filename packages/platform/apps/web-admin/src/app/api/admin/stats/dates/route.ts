// GET /api/admin/stats/dates?from=&to=
// 聚合：每天的视频/时长/批次数（用于趋势图）

import type { NextRequest } from 'next/server'
import { queryCrossSchema } from '@/lib/db'
import { handleApiError, ok } from '@/lib/api-error'

export interface DateStatsRow {
  scan_date: string
  video_count: number
  batch_count: number
  duration_sec_total: number
  distinct_recorders: number
  distinct_devices: number
}

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url)
    const from = searchParams.get('from') ?? '1970-01-01'
    const to = searchParams.get('to') ?? '2999-12-31'

    const rows = await queryCrossSchema<DateStatsRow>(
      `
      SELECT
        v.scan_date,
        COUNT(DISTINCT v.path)                  AS video_count,
        COUNT(DISTINCT vbc.id)                  AS batch_count,
        COALESCE(SUM(
          CASE WHEN v.duration_sec ~ '^[0-9]+$' THEN v.duration_sec::bigint ELSE 0 END
        ), 0)::bigint                            AS duration_sec_total,
        COUNT(DISTINCT v.recorder_id)          AS distinct_recorders,
        COUNT(DISTINCT v.device_id)             AS distinct_devices
      FROM public.videos v
      LEFT JOIN public.video_batch_config vbc
        ON vbc.task_id = v.task_id AND vbc.recorder_id = v.recorder_id
      WHERE v.scan_date BETWEEN $1 AND $2
      GROUP BY v.scan_date
      ORDER BY v.scan_date DESC
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