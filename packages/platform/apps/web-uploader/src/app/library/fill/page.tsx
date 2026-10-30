// /library/fill — 视频信息补全（plan2 优先开发：让录制员填那些未填的视频元数据）
import Link from 'next/link'
import { queryCrossSchema } from '@/lib/db'
import FillForm from './FillForm'

interface UnfilledVideoRow {
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
  missing: ('recorder' | 'task' | 'env' | 'uploaded')[]
}

interface RecorderOpt {
  id: string
  name: string | null
  operator_job: string | null
}
interface TaskOpt {
  task_id: string
  product: string | null
  task: string | null
  process: string | null
  difficulty: string | null
}
interface EnvOpt {
  env_id: string
  scene: string | null
  location_address: string | null
  environment: string | null
}

export const dynamic = 'force-dynamic'

interface PageProps {
  searchParams: Promise<{ limit?: string; offset?: string; recorder?: string; task?: string; env_id?: string }>
}

async function fetchUnfilled(opts: {
  limit: number
  offset: number
  recorder?: string
  task?: string
  env_id?: string
}) {
  const where: string[] = [
    `(v.recorder_id IS NULL OR v.recorder_id = '' OR v.task_id IS NULL OR v.task_id = '' OR v.env_id IS NULL OR v.env_id = '' OR v.uploaded IS NULL OR v.uploaded != 'Yes')`,
  ]
  const params: unknown[] = []
  if (opts.recorder) {
    params.push(opts.recorder)
    where.push(`v.recorder_id = $${params.length}`)
  }
  if (opts.task) {
    params.push(opts.task)
    where.push(`v.task_id = $${params.length}`)
  }
  if (opts.env_id) {
    params.push(opts.env_id)
    where.push(`v.env_id = $${params.length}`)
  }
  params.push(opts.limit)
  const li = params.length
  params.push(opts.offset)
  const oi = params.length
  const rows = await queryCrossSchema<Omit<UnfilledVideoRow, 'missing'>>(
    `SELECT
       v.path, v.scan_date, v.duration_sec, v.file_type, v.device_id,
       NULLIF(v.recorder_id, '') AS recorder_id, c.name AS recorder_name,
       NULLIF(v.task_id, '') AS task_id, t.product AS task_product,
       t.process AS task_process, t.difficulty,
       NULLIF(v.env_id, '') AS env_id, e.environment AS env_name,
       v.uploaded, v.score
     FROM public.videos v
     LEFT JOIN public.recorders c ON c.id = v.recorder_id
     LEFT JOIN public.tasks t ON t.task_id = v.task_id
     LEFT JOIN public.environments e ON e.env_id = v.env_id
     WHERE ${where.join(' AND ')}
     ORDER BY v.scan_date DESC NULLS LAST, v.path ASC
     LIMIT $${li} OFFSET $${oi}`,
    params,
  )
  const totalRow = await queryCrossSchema<{ count: string }>(
    `SELECT COUNT(*) AS count FROM public.videos v WHERE ${where
      .filter((w) => !/LIMIT|OFFSET/.test(w))
      .join(' AND ')}`,
    params.slice(0, params.length - 2),
  )

  const normalized: UnfilledVideoRow[] = rows.map((r) => {
    const missing: UnfilledVideoRow['missing'] = []
    if (!r.recorder_id) missing.push('recorder')
    if (!r.task_id) missing.push('task')
    if (!r.env_id) missing.push('env')
    if ((r.uploaded ?? '').toLowerCase() !== 'yes') missing.push('uploaded')
    return { ...r, missing }
  })
  return { rows: normalized, total: Number(totalRow[0]?.count ?? 0) }
}

async function fetchOptions() {
  const [recorders, tasks, environments] = await Promise.all([
    queryCrossSchema<RecorderOpt>(
      `SELECT id, name, operator_job FROM public.recorders ORDER BY id`,
    ),
    queryCrossSchema<TaskOpt>(
      `SELECT task_id, product, task, process, difficulty FROM public.tasks ORDER BY task_id`,
    ),
    queryCrossSchema<EnvOpt>(
      `SELECT env_id, scene, location_address, environment FROM public.environments ORDER BY env_id`,
    ),
  ])
  return { recorders, tasks, environments }
}

export default async function FillPage({ searchParams }: PageProps) {
  const params = await searchParams
  const limit = Math.min(Number(params.limit ?? 50), 200)
  const offset = Math.max(Number(params.offset ?? 0), 0)
  const recorder = params.recorder
  const task = params.task
  const env_id = params.env_id

  let data: { rows: UnfilledVideoRow[]; total: number } | null = null
  let opts: { recorders: RecorderOpt[]; tasks: TaskOpt[]; environments: EnvOpt[] } | null = null
  let err: string | null = null
  try {
    ;[data, opts] = await Promise.all([
      fetchUnfilled({ limit, offset, recorder, task, env_id }),
      fetchOptions(),
    ])
  } catch (e) {
    err = (e as Error).message
  }

  return (
    <main className="mx-auto max-w-7xl p-4">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-3">
        <div>
          <h1 className="text-2xl font-semibold">视频信息补全</h1>
          <p className="text-sm text-slate-500">
            {data ? `共 ${data.total} 条未填全视频` : '加载中…'} · plan2 优先开发
          </p>
        </div>
        <div className="flex gap-2 text-sm">
          <Link href="/library" className="rounded border border-slate-300 px-3 py-2 text-slate-700 hover:bg-slate-100">
            ← 视频库
          </Link>
          <Link href="/" className="rounded border border-slate-300 px-3 py-2 text-slate-700 hover:bg-slate-100">
            ← 首页
          </Link>
        </div>
      </header>

      {err && (
        <div className="rounded border border-red-200 bg-red-50 p-4 text-red-800">
          错误：{err}
          <p className="mt-1 text-xs">
            先在 ff 根跑 <code>pnpm install</code> + 启动 web-uploader（pnpm dev）。
          </p>
        </div>
      )}

      {data && opts && (
        <FillForm
          rows={data.rows}
          total={data.total}
          limit={limit}
          offset={offset}
          recorder={recorder ?? ''}
          task={task ?? ''}
          env_id={env_id ?? ''}
          recorders={opts.recorders}
          tasks={opts.tasks}
          environments={opts.environments}
        />
      )}
    </main>
  )
}