// GET /api/admin/payroll/export.csv?from=&to=
// CSV 导出：每行 = 1 个视频的工资
// 列：scan_date, video_path, recorder_id, recorder_name, task_id, task_product, task_process,
//     difficulty, duration_sec, uploaded, base_cny, by_minutes_cny, upload_bonus_cny, total_cny

import type { NextRequest } from 'next/server'
import { queryCrossSchema } from '@/lib/db'
import { calcPayrollForBatch } from '@/lib/payroll'

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url)
    const from = searchParams.get('from') ?? '1970-01-01'
    const to = searchParams.get('to') ?? '2999-12-31'

    const rows = await queryCrossSchema<{
      video_path: string
      scan_date: string | null
      recorder_id: string
      recorder_name: string | null
      task_id: string
      task_product: string | null
      task_process: string | null
      difficulty: string | null
      duration_sec: string | null
      uploaded: string | null
    }>(
      `
      SELECT
        v.path AS video_path,
        v.scan_date, v.recorder_id, c.name AS recorder_name,
        v.task_id, t.product AS task_product, t.process AS task_process, t.difficulty,
        v.duration_sec, v.uploaded
      FROM public.videos v
      LEFT JOIN public.recorders c ON c.id = v.recorder_id
      LEFT JOIN public.tasks t ON t.task_id = v.task_id
      WHERE v.scan_date BETWEEN $1 AND $2
        AND v.recorder_id <> ''
      ORDER BY v.scan_date DESC, v.recorder_id NULLS LAST
      `,
      [from, to],
    )

    const head = [
      'scan_date',
      'video_path',
      'recorder_id',
      'recorder_name',
      'task_id',
      'task_product',
      'task_process',
      'difficulty',
      'duration_sec',
      'uploaded',
      'base_cny',
      'by_minutes_cny',
      'upload_bonus_cny',
      'total_cny',
    ]
    const escape = (v: unknown) => {
      const s = v == null ? '' : String(v)
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
    }
    const lines = [head.join(',')]
    for (const r of rows) {
      const durSec = Number(/^[0-9]+$/.test(r.duration_sec ?? '') ? r.duration_sec : 0)
      const uploaded = (r.uploaded ?? '').toLowerCase() === 'yes'
      const calc = calcPayrollForBatch({
        duration_sec: durSec,
        difficulty: r.difficulty,
        scored: uploaded,
      })
      lines.push(
        [
          r.scan_date,
          r.video_path,
          r.recorder_id,
          r.recorder_name,
          r.task_id,
          r.task_product,
          r.task_process,
          r.difficulty,
          durSec,
          r.uploaded,
          calc.base,
          calc.by_minutes,
          calc.score_bonus,
          calc.total,
        ]
          .map(escape)
          .join(','),
      )
    }
    const csv = '﻿' + lines.join('\n')
    return new Response(csv, {
      status: 200,
      headers: {
        'Content-Type': 'text/csv; charset=utf-8',
        'Content-Disposition': `attachment; filename="payroll-${from}-to-${to}.csv"`,
      },
    })
  } catch (err) {
    return new Response(`error: ${(err as Error).message}`, { status: 500 })
  }
}