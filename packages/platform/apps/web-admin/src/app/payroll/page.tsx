// /payroll — 工资管理主页（plan2 Phase 1 优先开发：给已劳动的人开工资）
import Link from 'next/link'
import { queryCrossSchema } from '@/lib/db'
import { calcPayrollForBatch, DEFAULT_RATES } from '@/lib/payroll'

interface RecorderSummary {
  recorder_id: string
  recorder_name: string | null
  video_count: number
  duration_sec_total: number
  uploaded_count: number
  total_cny: number
  by_difficulty_cny: Record<string, number>
}

interface PayrollResponse {
  from: string
  to: string
  rates: {
    base_per_video_cny: number
    per_minute_cny: Record<string, number>
    upload_bonus_cny: number
  }
  recorder_summary: RecorderSummary[]
  grand_total_cny: number
}

// 直接调 SQL（RSC 同进程内最快，避免 self-fetch 端口问题）
async function fetchPayroll(from: string, to: string): Promise<PayrollResponse> {
  const videoRows = await queryCrossSchema<{
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
    `SELECT v.scan_date, v.recorder_id, c.name AS recorder_name, v.task_id,
            t.product AS task_product, t.process AS task_process, t.difficulty,
            v.duration_sec, v.uploaded
     FROM public.videos v
     LEFT JOIN public.recorders c ON c.id = v.recorder_id
     LEFT JOIN public.tasks t ON t.task_id = v.task_id
     WHERE v.scan_date BETWEEN $1 AND $2 AND v.recorder_id <> ''
     ORDER BY v.scan_date DESC, v.recorder_id NULLS LAST`,
    [from, to],
  )

  const byRecorder = new Map<string, RecorderSummary>()
  let grand_total_cny = 0
  for (const r of videoRows) {
    const durSec = Number(/^[0-9]+$/.test(r.duration_sec ?? '') ? r.duration_sec : 0)
    const uploaded = (r.uploaded ?? '').toLowerCase() === 'yes'
    const calc = calcPayrollForBatch({ duration_sec: durSec, difficulty: r.difficulty, scored: uploaded })
    const key = r.recorder_id
    const cur =
      byRecorder.get(key) ??
      ({
        recorder_id: r.recorder_id,
        recorder_name: r.recorder_name,
        video_count: 0,
        duration_sec_total: 0,
        uploaded_count: 0,
        total_cny: 0,
        by_difficulty_cny: {},
      } satisfies RecorderSummary)
    cur.video_count += 1
    cur.duration_sec_total += durSec
    if (uploaded) cur.uploaded_count += 1
    cur.total_cny = +(cur.total_cny + calc.total).toFixed(2)
    const diff = (r.difficulty ?? 'unknown').toLowerCase()
    cur.by_difficulty_cny[diff] = +((cur.by_difficulty_cny[diff] ?? 0) + calc.total).toFixed(2)
    byRecorder.set(key, cur)
    grand_total_cny = +(grand_total_cny + calc.total).toFixed(2)
  }
  const recorder_summary = Array.from(byRecorder.values()).sort((a, b) => b.total_cny - a.total_cny)

  return {
    from,
    to,
    rates: DEFAULT_RATES,
    recorder_summary,
    grand_total_cny,
  }
}

export const dynamic = 'force-dynamic'

interface PageProps {
  searchParams: Promise<{ from?: string; to?: string }>
}

export default async function PayrollPage({ searchParams }: PageProps) {
  const params = await searchParams
  const today = new Date().toISOString().slice(0, 10)
  const monthStart = today.slice(0, 8) + '01'
  const from = params.from ?? monthStart
  const to = params.to ?? today

  let data: PayrollResponse | null = null
  let err: string | null = null
  try {
    data = await fetchPayroll(from, to)
  } catch (e) {
    err = (e as Error).message
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold">工资管理</h1>
            <p className="text-sm text-slate-500">
              范围 <code className="rounded bg-slate-100 px-1">{from}</code> →{' '}
              <code className="rounded bg-slate-100 px-1">{to}</code>
            </p>
          </div>
          <div className="flex gap-2 text-sm">
            <Link
              href={`/api/admin/payroll/export.csv?from=${from}&to=${to}`}
              className="rounded bg-emerald-600 px-3 py-2 font-medium text-white hover:bg-emerald-700"
              prefetch={false}
            >
              导出 CSV
            </Link>
            <Link
              href="/stats"
              className="rounded border border-slate-300 px-3 py-2 text-slate-700 hover:bg-slate-100"
            >
              统计 →
            </Link>
            <Link
              href="/"
              className="rounded border border-slate-300 px-3 py-2 text-slate-700 hover:bg-slate-100"
            >
              ← 后台
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-6">
        {err && (
          <div className="rounded border border-red-200 bg-red-50 p-4 text-red-800">
            错误：{err}
          </div>
        )}

        {data && (
          <>
            <section className="mb-6 grid grid-cols-3 gap-4">
              <Card label="总工资" value={`¥ ${data.grand_total_cny.toFixed(2)}`} accent="emerald" />
              <Card label="有数据的录制员" value={String(data.recorder_summary.length)} accent="blue" />
              <Card
                label="视频总数"
                value={String(data.recorder_summary.reduce((s, r) => s + r.video_count, 0))}
                accent="slate"
              />
            </section>

            <section className="mb-6 rounded border border-slate-200 bg-white p-4">
              <h2 className="mb-2 text-sm font-semibold text-slate-700">当前单价规则</h2>
              <div className="grid grid-cols-2 gap-2 text-sm text-slate-600 md:grid-cols-4">
                <div>
                  基础：<code>¥ {data.rates.base_per_video_cny}</code> / 视频
                </div>
                {Object.entries(data.rates.per_minute_cny).map(([k, v]) => (
                  <div key={k}>
                    {k}：<code>¥ {v}</code> / 分钟
                  </div>
                ))}
                <div>
                  已上传奖励：<code>¥ {data.rates.upload_bonus_cny}</code>
                </div>
              </div>
              <p className="mt-2 text-xs text-slate-400">
                改 lib/payroll.ts 的 DEFAULT_RATES 可调单价。
              </p>
            </section>

            <section className="rounded border border-slate-200 bg-white">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-4 py-3">录制员</th>
                    <th className="px-4 py-3">工号</th>
                    <th className="px-4 py-3 text-right">视频数</th>
                    <th className="px-4 py-3 text-right">已上传</th>
                    <th className="px-4 py-3 text-right">总时长</th>
                    <th className="px-4 py-3 text-right">应付 (¥)</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recorder_summary.map((r) => (
                    <tr key={r.recorder_id} className="border-t border-slate-100">
                      <td className="px-4 py-3 font-medium">{r.recorder_name ?? '—'}</td>
                      <td className="px-4 py-3 text-slate-500">{r.recorder_id}</td>
                      <td className="px-4 py-3 text-right">{r.video_count}</td>
                      <td className="px-4 py-3 text-right">{r.uploaded_count}</td>
                      <td className="px-4 py-3 text-right">
                        {Math.round(r.duration_sec_total / 60)} 分
                      </td>
                      <td className="px-4 py-3 text-right font-mono font-semibold text-emerald-700">
                        {r.total_cny.toFixed(2)}
                      </td>
                    </tr>
                  ))}
                  {data.recorder_summary.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-slate-400">
                        该周期无数据。试试扩大日期范围。
                      </td>
                    </tr>
                  )}
                </tbody>
                {data.recorder_summary.length > 0 && (
                  <tfoot>
                    <tr className="border-t-2 border-slate-300 bg-slate-50 font-semibold">
                      <td className="px-4 py-3" colSpan={5}>
                        合计
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-emerald-700">
                        ¥ {data.grand_total_cny.toFixed(2)}
                      </td>
                    </tr>
                  </tfoot>
                )}
              </table>
            </section>
          </>
        )}
      </main>
    </div>
  )
}

function Card({
  label,
  value,
  accent,
}: {
  label: string
  value: string
  accent: 'emerald' | 'blue' | 'slate'
}) {
  const colors = {
    emerald: 'border-emerald-200 bg-emerald-50 text-emerald-800',
    blue: 'border-blue-200 bg-blue-50 text-blue-800',
    slate: 'border-slate-200 bg-white text-slate-800',
  } as const
  return (
    <div className={`rounded border p-4 ${colors[accent]}`}>
      <div className="text-xs uppercase">{label}</div>
      <div className="mt-1 text-2xl font-bold">{value}</div>
    </div>
  )
}