// /stats — 统计聚合（recorders / tasks / dates / difficulty / regions）
import Link from 'next/link'
import { queryCrossSchema } from '@/lib/db'

interface DateStatsRow {
  scan_date: string
  video_count: number
  duration_sec_total: number
  distinct_recorders: number
  distinct_devices: number
}

interface RecorderStatsRow {
  recorder_id: string
  recorder_name: string | null
  video_count: number
  duration_min_total: number
  uploaded_count: number
}

interface TaskStatsRow {
  task_id: string
  product: string | null
  process: string | null
  difficulty: string | null
  video_count: number
  duration_sec_total: number
}

interface DifficultyStatsRow {
  difficulty: string
  video_count: number
  duration_sec_total: number
}

async function fetchStats(from: string, to: string) {
  const [dates, recorders, tasks, difficulties] = await Promise.all([
    queryCrossSchema<{
      scan_date: string
      video_count: string
      duration_sec_total: string
      distinct_recorders: string
      distinct_devices: string
    }>(
      `SELECT v.scan_date,
              COUNT(v.path) AS video_count,
              COALESCE(SUM(CASE WHEN v.duration_sec ~ '^[0-9]+$' THEN v.duration_sec::bigint ELSE 0 END),0)::bigint AS duration_sec_total,
              COUNT(DISTINCT v.recorder_id) AS distinct_recorders,
              COUNT(DISTINCT v.device_id) AS distinct_devices
       FROM public.videos v
       WHERE v.scan_date BETWEEN $1 AND $2
       GROUP BY v.scan_date ORDER BY v.scan_date DESC`,
      [from, to],
    ),
    queryCrossSchema<{
      recorder_id: string
      recorder_name: string | null
      video_count: string
      duration_sec_total: string
      uploaded_count: string
    }>(
      `SELECT c.id AS recorder_id, c.name AS recorder_name,
              COUNT(v.path) AS video_count,
              COALESCE(SUM(CASE WHEN v.duration_sec ~ '^[0-9]+$' THEN v.duration_sec::bigint ELSE 0 END),0)::bigint AS duration_sec_total,
              COUNT(*) FILTER (WHERE v.uploaded = 'Yes') AS uploaded_count
       FROM public.recorders c
       INNER JOIN public.videos v ON v.recorder_id = c.id
       WHERE v.scan_date BETWEEN $1 AND $2
       GROUP BY c.id
       ORDER BY video_count DESC, c.name`,
      [from, to],
    ),
    queryCrossSchema<{
      task_id: string
      product: string | null
      process: string | null
      difficulty: string | null
      video_count: string
      duration_sec_total: string
    }>(
      `SELECT t.task_id, t.product, t.process, t.difficulty,
              COUNT(v.path) AS video_count,
              COALESCE(SUM(CASE WHEN v.duration_sec ~ '^[0-9]+$' THEN v.duration_sec::bigint ELSE 0 END),0)::bigint AS duration_sec_total
       FROM public.tasks t
       INNER JOIN public.videos v ON v.task_id = t.task_id
       WHERE v.scan_date BETWEEN $1 AND $2 AND v.recorder_id <> ''
       GROUP BY t.task_id ORDER BY video_count DESC`,
      [from, to],
    ),
    queryCrossSchema<{
      difficulty: string
      video_count: string
      duration_sec_total: string
    }>(
      `SELECT COALESCE(NULLIF(t.difficulty,''),'unknown') AS difficulty,
              COUNT(v.path) AS video_count,
              COALESCE(SUM(CASE WHEN v.duration_sec ~ '^[0-9]+$' THEN v.duration_sec::bigint ELSE 0 END),0)::bigint AS duration_sec_total
       FROM public.videos v
       INNER JOIN public.tasks t ON t.task_id = v.task_id
       WHERE v.scan_date BETWEEN $1 AND $2 AND v.recorder_id <> ''
       GROUP BY 1 ORDER BY 1`,
      [from, to],
    ),
  ])

  return {
    dates: dates.map((d) => ({
      scan_date: d.scan_date,
      video_count: Number(d.video_count),
      duration_sec_total: Number(d.duration_sec_total),
      distinct_recorders: Number(d.distinct_recorders),
      distinct_devices: Number(d.distinct_devices),
    })),
    recorders: recorders.map((r) => ({
      recorder_id: r.recorder_id,
      recorder_name: r.recorder_name,
      video_count: Number(r.video_count),
      duration_min_total: Math.round(Number(r.duration_sec_total) / 60),
      uploaded_count: Number(r.uploaded_count),
    })),
    tasks: tasks.map((t) => ({
      task_id: t.task_id,
      product: t.product,
      process: t.process,
      difficulty: t.difficulty,
      video_count: Number(t.video_count),
      duration_sec_total: Number(t.duration_sec_total),
    })),
    difficulties: difficulties.map((d) => ({
      difficulty: d.difficulty,
      video_count: Number(d.video_count),
      duration_sec_total: Number(d.duration_sec_total),
    })),
  }
}

export const dynamic = 'force-dynamic'

export default async function StatsPage({
  searchParams,
}: {
  searchParams: Promise<{ from?: string; to?: string }>
}) {
  const params = await searchParams
  const today = new Date().toISOString().slice(0, 10)
  const monthStart = today.slice(0, 8) + '01'
  const from = params.from ?? monthStart
  const to = params.to ?? today

  let err: string | null = null
  let dates: DateStatsRow[] = []
  let recorders: RecorderStatsRow[] = []
  let tasks: TaskStatsRow[] = []
  let difficulties: DifficultyStatsRow[] = []
  try {
    const data = await fetchStats(from, to)
    dates = data.dates
    recorders = data.recorders
    tasks = data.tasks
    difficulties = data.difficulties
  } catch (e) {
    err = (e as Error).message
  }

  const totals = {
    videos: recorders.reduce((s, r) => s + Number(r.video_count ?? 0), 0),
    minutes: recorders.reduce((s, r) => s + Number(r.duration_min_total ?? 0), 0),
    distinctDays: dates.length,
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold">数据统计</h1>
            <p className="text-sm text-slate-500">
              范围 <code className="rounded bg-slate-100 px-1">{from}</code> →{' '}
              <code className="rounded bg-slate-100 px-1">{to}</code>
            </p>
          </div>
          <div className="flex gap-2 text-sm">
            <Link
              href="/payroll"
              className="rounded border border-slate-300 px-3 py-2 text-slate-700 hover:bg-slate-100"
            >
              ← 工资
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

      <main className="mx-auto max-w-6xl px-6 py-6 space-y-6">
        {err && (
          <div className="rounded border border-red-200 bg-red-50 p-4 text-red-800">错误：{err}</div>
        )}

        {err == null && (
          <>
            <section className="grid grid-cols-3 gap-4">
              <StatCard label="总视频数" value={totals.videos.toLocaleString()} />
              <StatCard label="总时长" value={`${totals.minutes.toLocaleString()} 分`} />
              <StatCard label="接入天数" value={String(totals.distinctDays)} />
            </section>

            <Section title="每日接入量">
              {dates.length === 0 ? (
                <Empty msg="该周期无视频" />
              ) : (
                <BarChart
                  data={dates.slice(0, 30).map((d) => ({
                    label: d.scan_date,
                    value: d.video_count,
                  }))}
                />
              )}
            </Section>

            <Section title="录制员工作量 Top 10">
              <Table
                head={['录制员', 'ID', '视频数', '已上传', '总时长']}
                rows={recorders.slice(0, 10).map((r) => [
                  r.recorder_name ?? '—',
                  r.recorder_id,
                  String(r.video_count),
                  String(r.uploaded_count),
                  `${r.duration_min_total} 分`,
                ])}
              />
            </Section>

            <Section title="按难度分布">
              <Table
                head={['难度', '视频数', '总时长（秒）']}
                rows={difficulties.map((d) => [
                  d.difficulty,
                  String(d.video_count),
                  String(d.duration_sec_total),
                ])}
              />
            </Section>

            <Section title="任务 Top 10（按视频数）">
              <Table
                head={['Task ID', 'Product', 'Process', '难度', '视频', '分钟']}
                rows={tasks.slice(0, 10).map((t) => [
                  t.task_id,
                  t.product ?? '—',
                  t.process ?? '—',
                  t.difficulty ?? '—',
                  String(t.video_count),
                  Math.round(t.duration_sec_total / 60).toString(),
                ])}
              />
            </Section>
          </>
        )}
      </main>
    </div>
  )
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-slate-200 bg-white p-4">
      <div className="text-xs uppercase text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-bold">{value}</div>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded border border-slate-200 bg-white">
      <h2 className="border-b border-slate-100 px-4 py-3 text-sm font-semibold text-slate-700">
        {title}
      </h2>
      <div className="p-4">{children}</div>
    </section>
  )
}

function Table({ head, rows }: { head: string[]; rows: string[][] }) {
  if (rows.length === 0) return <Empty msg="无数据" />
  return (
    <table className="w-full text-sm">
      <thead className="text-left text-xs uppercase text-slate-500">
        <tr>
          {head.map((h, i) => (
            <th key={i} className="px-3 py-2">
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i} className="border-t border-slate-100">
            {r.map((c, j) => (
              <td key={j} className="px-3 py-2 text-slate-700">
                {c}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function Empty({ msg }: { msg: string }) {
  return <div className="rounded border border-dashed border-slate-200 p-8 text-center text-slate-400">{msg}</div>
}

function BarChart({ data }: { data: { label: string; value: number }[] }) {
  const max = Math.max(...data.map((d) => d.value), 1)
  return (
    <div className="space-y-1">
      {data.map((d) => (
        <div key={d.label} className="flex items-center gap-3 text-xs">
          <span className="w-24 shrink-0 truncate text-slate-500" title={d.label}>
            {d.label}
          </span>
          <div className="h-5 rounded bg-blue-500" style={{ width: `${(d.value / max) * 100}%` }} />
          <span className="font-mono text-slate-700">{d.value}</span>
        </div>
      ))}
    </div>
  )
}