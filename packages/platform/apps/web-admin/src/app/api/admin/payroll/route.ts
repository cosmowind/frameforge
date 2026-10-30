// GET /api/admin/payroll?from=&to=&recorder_id=&difficulty=
// 工资计算：按 recorder + period 聚合
// 数据源：public.videos（有 recorder_id 关联）+ public.recorders + public.tasks
// 单价规则：见 src/lib/payroll.ts（DEFAULT_RATES）

import type { NextRequest } from 'next/server'
import { queryCrossSchema } from '@/lib/db'
import { handleApiError, ok } from '@/lib/api-error'
import { calcPayrollForBatch, DEFAULT_RATES, type RateConfig } from '@/lib/payroll'

export interface PayrollVideoRow {
  video_path: string
  scan_date: string | null
  recorder_id: string
  recorder_name: string | null
  task_id: string
  task_product: string | null
  task_process: string | null
  difficulty: string | null
  duration_sec: number
  uploaded: boolean
  base_cny: number
  by_minutes_cny: number
  upload_bonus_cny: number
  total_cny: number
}

export interface PayrollRecorderSummary {
  recorder_id: string
  recorder_name: string | null
  video_count: number
  duration_sec_total: number
  uploaded_count: number
  total_cny: number
  by_difficulty_cny: Record<string, number>
}

export interface PayrollResponse {
  from: string
  to: string
  rates: RateConfig
  video_rows: PayrollVideoRow[]
  recorder_summary: PayrollRecorderSummary[]
  grand_total_cny: number
}

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url)
    const from = searchParams.get('from') ?? '1970-01-01'
    const to = searchParams.get('to') ?? '2999-12-31'
    const recorderFilter = searchParams.get('recorder_id')
    const diffFilter = searchParams.get('difficulty')

    const videoRows = await queryCrossSchema<{
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
        v.path                AS video_path,
        v.scan_date           AS scan_date,
        v.recorder_id        AS recorder_id,
        c.name                AS recorder_name,
        v.task_id             AS task_id,
        t.product             AS task_product,
        t.process             AS task_process,
        t.difficulty          AS difficulty,
        v.duration_sec        AS duration_sec,
        v.uploaded            AS uploaded
      FROM public.videos v
      LEFT JOIN public.recorders c ON c.id = v.recorder_id
      LEFT JOIN public.tasks t ON t.task_id = v.task_id
      WHERE v.scan_date BETWEEN $1 AND $2
        AND v.recorder_id <> ''
        AND ($3::text IS NULL OR v.recorder_id = $3)
        AND ($4::text IS NULL OR COALESCE(t.difficulty,'') = $4)
      ORDER BY v.scan_date DESC, v.recorder_id NULLS LAST
      `,
      [from, to, recorderFilter, diffFilter],
    )

    const video_rows: PayrollVideoRow[] = videoRows.map((r) => {
      const durSec = Number(/^[0-9]+$/.test(r.duration_sec ?? '') ? r.duration_sec : 0)
      const uploaded = (r.uploaded ?? '').toLowerCase() === 'yes'
      const calc = calcPayrollForBatch({
        duration_sec: durSec,
        difficulty: r.difficulty,
        scored: uploaded,
      })
      return {
        video_path: r.video_path,
        scan_date: r.scan_date,
        recorder_id: r.recorder_id,
        recorder_name: r.recorder_name,
        task_id: r.task_id,
        task_product: r.task_product,
        task_process: r.task_process,
        difficulty: r.difficulty,
        duration_sec: durSec,
        uploaded,
        base_cny: calc.base,
        by_minutes_cny: calc.by_minutes,
        upload_bonus_cny: calc.score_bonus,
        total_cny: calc.total,
      }
    })

    const byRecorder = new Map<string, PayrollRecorderSummary>()
    for (const row of video_rows) {
      const key = row.recorder_id ?? '__null__'
      const cur =
        byRecorder.get(key) ??
        ({
          recorder_id: row.recorder_id,
          recorder_name: row.recorder_name,
          video_count: 0,
          duration_sec_total: 0,
          uploaded_count: 0,
          total_cny: 0,
          by_difficulty_cny: {},
        } satisfies PayrollRecorderSummary)
      cur.video_count += 1
      cur.duration_sec_total += row.duration_sec
      if (row.uploaded) cur.uploaded_count += 1
      cur.total_cny = +(cur.total_cny + row.total_cny).toFixed(2)
      const diff = (row.difficulty ?? 'unknown').toLowerCase()
      cur.by_difficulty_cny[diff] = +((cur.by_difficulty_cny[diff] ?? 0) + row.total_cny).toFixed(2)
      byRecorder.set(key, cur)
    }
    const recorder_summary = Array.from(byRecorder.values()).sort(
      (a, b) => b.total_cny - a.total_cny,
    )

    const grand_total_cny = +recorder_summary.reduce((s, r) => s + r.total_cny, 0).toFixed(2)

    const payload: PayrollResponse = {
      from,
      to,
      rates: DEFAULT_RATES,
      video_rows,
      recorder_summary,
      grand_total_cny,
    }
    return ok(payload)
  } catch (err) {
    return handleApiError(err)
  }
}