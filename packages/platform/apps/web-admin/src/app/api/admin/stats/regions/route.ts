// GET /api/admin/stats/regions?from=&to=
// 聚合：按 region (sd_cards.region + city)

import type { NextRequest } from 'next/server'
import { queryCrossSchema } from '@/lib/db'
import { handleApiError, ok } from '@/lib/api-error'

export interface RegionStatsRow {
  region: string
  city: string | null
  device_count: number
  video_count: number
  duration_sec_total: number
}

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url)
    const from = searchParams.get('from') ?? '1970-01-01'
    const to = searchParams.get('to') ?? '2999-12-31'

    const rows = await queryCrossSchema<RegionStatsRow>(
      `
      SELECT
        COALESCE(NULLIF(sd.region, ''), 'unknown') AS region,
        sd.city,
        COUNT(DISTINCT sd.device_id)              AS device_count,
        COUNT(DISTINCT v.path)                    AS video_count,
        COALESCE(SUM(
          CASE WHEN v.duration_sec ~ '^[0-9]+$' THEN v.duration_sec::bigint ELSE 0 END
        ), 0)::bigint                              AS duration_sec_total
      FROM public.sd_cards sd
      LEFT JOIN public.videos v
        ON v.device_id = sd.device_id
        AND (v.scan_date >= $1 AND v.scan_date <= $2)
      GROUP BY sd.region, sd.city
      ORDER BY video_count DESC, region
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