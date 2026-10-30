// /admin/db — 数据库仪表盘（8 张表行数 + videos 字段填充率 + 最近备份 + 一键备份按钮）
import Link from 'next/link'
import { queryCrossSchema } from '@/lib/db'
import { listBackups } from '@/lib/backup'
import BackupButton from './BackupButton'

interface TableStats {
  table: string
  rows: number
  fill_rate?: Record<string, number>
}

interface AwaitedStats {
  tables: TableStats[]
  videos_total: number
  empty: { recorder_id: number; task_id: number; env_id: number; not_uploaded: number }
  backups: { name: string; size: number }[]
}

async function fetchStats() {
  // PG 没 libxml2，直接查 8 张固定表
  const tableNames = [
    'videos',
    'video_batch_config',
    'videos_backup_focused',
    'tasks',
    'recorders',
    'environments',
    'sd_cards',
    'app_config',
  ]
  const tables = (
    await Promise.all(
      tableNames.map(async (name) => {
        const r = await queryCrossSchema<{ n: string }>(
          `SELECT count(*)::int AS n FROM public.${name}`,
        )
        return { tablename: name, n: r[0]?.n ?? '0' }
      }),
    )
  ).sort((a, b) => Number(b.n) - Number(a.n))

  const v = await queryCrossSchema<{
    total: string
    empty_recorder: string
    empty_task: string
    empty_env: string
    not_uploaded: string
  }>(
    `SELECT
       count(*) AS total,
       count(*) FILTER (WHERE recorder_id = '' OR recorder_id IS NULL) AS empty_recorder,
       count(*) FILTER (WHERE task_id = '' OR task_id IS NULL) AS empty_task,
       count(*) FILTER (WHERE env_id = '' OR env_id IS NULL) AS empty_env,
       count(*) FILTER (WHERE uploaded IS NULL OR uploaded != 'Yes') AS not_uploaded
     FROM public.videos`,
  )
  const vRow = v[0]!
  const total = Number(vRow.total)

  const videos: TableStats = {
    table: 'videos',
    rows: total,
    fill_rate: {
      recorder_id: 1 - Number(vRow.empty_recorder) / Math.max(total, 1),
      task_id: 1 - Number(vRow.empty_task) / Math.max(total, 1),
      env_id: 1 - Number(vRow.empty_env) / Math.max(total, 1),
      uploaded: 1 - Number(vRow.not_uploaded) / Math.max(total, 1),
    },
  }
  const others = tables
    .filter((t) => t.tablename !== 'videos')
    .map((t) => ({ table: t.tablename, rows: Number(t.n) }))
  const backups = await listBackups()
  return {
    tables: [videos, ...others].sort((a, b) => b.rows - a.rows),
    videos_total: total,
    empty: {
      recorder_id: Number(vRow.empty_recorder),
      task_id: Number(vRow.empty_task),
      env_id: Number(vRow.empty_env),
      not_uploaded: Number(vRow.not_uploaded),
    },
    backups,
  }
}

export const dynamic = 'force-dynamic'

export default async function DbAdminPage() {
  let data: AwaitedStats | null = null
  let err: string | null = null
  try {
    data = await fetchStats()
  } catch (e) {
    err = (e as Error).message
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold">数据库管理</h1>
            <p className="text-sm text-slate-500">
              数据库健康 + 备份 + 填充率；详细红线看{' '}
              <Link href="/admin/db/policy" className="text-blue-600 underline">
                数据库策略
              </Link>
            </p>
          </div>
          <div className="flex gap-2 text-sm">
            <Link href="/payroll" className="rounded border border-slate-300 px-3 py-2 text-slate-700 hover:bg-slate-100">
              工资
            </Link>
            <Link href="/stats" className="rounded border border-slate-300 px-3 py-2 text-slate-700 hover:bg-slate-100">
              统计
            </Link>
            <Link
              href="/admin/tables"
              className="rounded border border-emerald-300 bg-emerald-50 px-3 py-2 text-emerald-800 hover:bg-emerald-100"
            >
              🗂 数据表
            </Link>
            <Link
              href="/admin/progress"
              className="rounded border border-blue-300 bg-blue-50 px-3 py-2 text-blue-800 hover:bg-blue-100"
            >
              📊 开发进度
            </Link>
            <Link href="/" className="rounded border border-slate-300 px-3 py-2 text-slate-700 hover:bg-slate-100">
              ← 后台
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-6 space-y-6">
        {err && (
          <div className="rounded border border-red-200 bg-red-50 p-4 text-red-800">错误：{err}</div>
        )}

        {data && (
          <>
            <section className="grid grid-cols-4 gap-4">
              <Card label="总视频数" value={String(data.videos_total)} accent="blue" />
              <Card
                label="空 recorder_id"
                value={String(data.empty.recorder_id)}
                accent={data.empty.recorder_id > 0 ? 'red' : 'emerald'}
              />
              <Card
                label="空 task_id"
                value={String(data.empty.task_id)}
                accent={data.empty.task_id > 0 ? 'red' : 'emerald'}
              />
              <Card
                label="未上传"
                value={String(data.empty.not_uploaded)}
                accent={data.empty.not_uploaded > 0 ? 'amber' : 'emerald'}
              />
            </section>

            <section className="rounded border border-slate-200 bg-white">
              <header className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
                <h2 className="text-sm font-semibold text-slate-700">public.* 表行数</h2>
              </header>
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-4 py-2">表</th>
                    <th className="px-4 py-2 text-right">行数</th>
                    <th className="px-4 py-2">填充率（仅 videos）</th>
                  </tr>
                </thead>
                <tbody>
                  {data.tables.map((t) => (
                    <tr key={t.table} className="border-t border-slate-100">
                      <td className="px-4 py-2 font-mono">{t.table}</td>
                      <td className="px-4 py-2 text-right font-mono">{t.rows.toLocaleString()}</td>
                      <td className="px-4 py-2 text-xs text-slate-600">
                        {t.fill_rate ? (
                          <div className="flex flex-wrap gap-2">
                            {Object.entries(t.fill_rate).map(([k, v]) => (
                              <span
                                key={k}
                                className={`rounded px-1.5 py-0.5 ${
                                  (v as number) >= 0.8
                                    ? 'bg-emerald-100 text-emerald-800'
                                    : (v as number) >= 0.5
                                    ? 'bg-amber-100 text-amber-800'
                                    : 'bg-red-100 text-red-800'
                                }`}
                              >
                                {k}: {((v as number) * 100).toFixed(0)}%
                              </span>
                            ))}
                          </div>
                        ) : (
                          '—'
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>

            <section className="rounded border border-slate-200 bg-white">
              <header className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
                <h2 className="text-sm font-semibold text-slate-700">最近备份</h2>
                <BackupButton />
              </header>
              <div className="p-4">
                {data.backups.length === 0 ? (
                  <div className="rounded border border-dashed border-slate-200 p-6 text-center text-sm text-slate-400">
                    暂无备份。点「立即备份」开始。
                  </div>
                ) : (
                  <ul className="space-y-1 text-sm">
                    {data.backups.map((b) => (
                      <li key={b.name} className="flex justify-between font-mono text-xs">
                        <span>{b.name}</span>
                        <span className="text-slate-500">{(b.size / 1024).toFixed(1)} KB</span>
                      </li>
                    ))}
                  </ul>
                )}
                <p className="mt-3 text-xs text-slate-400">
                  默认保留最近 10 份。回滚命令：<code>psql $DATABASE_URL &lt; runtime/backups/manual/all-*.sql.gz | gunzip</code>
                </p>
              </div>
            </section>

            <section className="rounded border border-amber-300 bg-amber-50 p-4 text-sm">
              <h3 className="mb-1 font-semibold text-amber-900">⚠️ 数据库红线（AI 与管理员共同遵守）</h3>
              <ul className="list-disc space-y-1 pl-5 text-amber-900">
                <li>禁止 DROP / TRUNCATE public.* — 业务唯一真相</li>
                <li>所有 UPDATE 必须带 WHERE（防误全表更新）</li>
                <li>改 schema 前必先备份（用上面「立即备份」按钮）</li>
                <li>AI 写操作必须 dry-run 先返回 diff，用户确认才提交</li>
                <li>完整规范：<Link href="/admin/db/policy" className="underline">/admin/db/policy</Link></li>
              </ul>
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
  accent: 'red' | 'amber' | 'emerald' | 'blue'
}) {
  const colors = {
    red: 'border-red-200 bg-red-50 text-red-800',
    amber: 'border-amber-200 bg-amber-50 text-amber-800',
    emerald: 'border-emerald-200 bg-emerald-50 text-emerald-800',
    blue: 'border-blue-200 bg-blue-50 text-blue-800',
  } as const
  return (
    <div className={`rounded border p-4 ${colors[accent]}`}>
      <div className="text-xs uppercase">{label}</div>
      <div className="mt-1 text-2xl font-bold">{value}</div>
    </div>
  )
}