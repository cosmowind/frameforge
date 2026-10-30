'use client'
// /admin/progress 客户端：左侧 Phase 进度卡 + 右侧 commits
// 每 30s 拉一次 /api/dev/progress
import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'

interface CheckItem {
  text: string
  done: boolean
  inProgress: boolean
}

interface PhaseBlock {
  level: number
  heading: string
  items: CheckItem[]
}

interface Commit {
  sha: string
  shortSha: string
  subject: string
  date: string
}

interface ProgressData {
  features: {
    phases: PhaseBlock[]
    totals: { done: number; inProgress: number; pending: number; total: number }
  }
  status: {
    phases: PhaseBlock[]
    totals: { done: number; inProgress: number; pending: number; total: number }
  }
  commits: Commit[]
  generatedAt: string
}

const REFRESH_MS = 30_000

export default function ProgressClient() {
  const [data, setData] = useState<ProgressData | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null)

  const fetchProgress = useCallback(async () => {
    try {
      const r = await fetch('/api/dev/progress', { cache: 'no-store' })
      const j = (await r.json()) as { ok: boolean; data?: ProgressData; error?: { message: string } }
      if (!j.ok || !j.data) throw new Error(j.error?.message ?? 'fetch failed')
      setData(j.data)
      setLastRefresh(new Date())
      setErr(null)
    } catch (e) {
      setErr((e as Error).message)
    }
  }, [])

  useEffect(() => {
    fetchProgress()
    const t = setInterval(fetchProgress, REFRESH_MS)
    return () => clearInterval(t)
  }, [fetchProgress])

  // 聚合 features + status 的 totals
  const totals = data
    ? {
        done: data.features.totals.done + data.status.totals.done,
        inProgress: data.features.totals.inProgress + data.status.totals.inProgress,
        pending: data.features.totals.pending + data.status.totals.pending,
        total: data.features.totals.total + data.status.totals.total,
      }
    : { done: 0, inProgress: 0, pending: 0, total: 0 }
  const overallPct = totals.total > 0 ? Math.round((totals.done / totals.total) * 100) : 0

  // 合并 features + status 的 phases（去重 heading 优先级：features 在前）
  const mergedPhases: PhaseBlock[] = data
    ? (() => {
        const seen = new Set<string>()
        const out: PhaseBlock[] = []
        for (const p of [...data.features.phases, ...data.status.phases]) {
          const key = p.heading.toLowerCase()
          if (seen.has(key)) continue
          seen.add(key)
          out.push(p)
        }
        return out
      })()
    : []

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white px-6 py-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h1 className="text-2xl font-semibold">📊 开发进度</h1>
            <p className="text-sm text-slate-500">
              实时聚合 <span className="font-mono">docs/features.md</span> +{' '}
              <span className="font-mono">docs/project_status.md</span> checkbox +{' '}
              <span className="font-mono">git log</span>
              {lastRefresh && (
                <>
                  {' '}
                  · 上次刷新{' '}
                  <span className="font-mono">
                    {lastRefresh.toLocaleTimeString('zh-CN')}
                  </span>
                </>
              )}
            </p>
          </div>
          <div className="flex gap-2 text-sm">
            <button
              onClick={fetchProgress}
              className="rounded border border-slate-300 px-3 py-2 text-slate-700 hover:bg-slate-100"
            >
              🔄 立即刷新
            </button>
            <Link
              href="/admin/db"
              className="rounded border border-slate-300 px-3 py-2 text-slate-700 hover:bg-slate-100"
            >
              ← 数据库管理
            </Link>
          </div>
        </div>
      </header>

      {err && (
        <div className="m-6 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          错误：{err}
        </div>
      )}

      {data && (
        <main className="mx-auto max-w-[1500px] space-y-4 px-6 py-4">
          {/* 总进度条 */}
          <section className="rounded border border-slate-200 bg-white p-4 shadow-sm">
            <div className="mb-2 flex items-baseline justify-between">
              <h2 className="text-lg font-semibold">总进度</h2>
              <span className="text-sm text-slate-500">
                <span className="font-mono text-2xl font-semibold text-green-700">{overallPct}%</span>{' '}
                ({totals.done}/{totals.total})
              </span>
            </div>
            <div className="h-3 w-full overflow-hidden rounded bg-slate-100">
              <div className="flex h-full">
                <div
                  className="bg-green-500"
                  style={{ width: `${(totals.done / Math.max(1, totals.total)) * 100}%` }}
                  title={`已完成 ${totals.done}`}
                />
                <div
                  className="bg-yellow-400"
                  style={{ width: `${(totals.inProgress / Math.max(1, totals.total)) * 100}%` }}
                  title={`进行中 ${totals.inProgress}`}
                />
              </div>
            </div>
            <div className="mt-2 flex gap-4 text-xs text-slate-600">
              <span>
                <span className="inline-block h-2 w-2 rounded-full bg-green-500 align-middle" />{' '}
                已完成 <span className="font-mono">{totals.done}</span>
              </span>
              <span>
                <span className="inline-block h-2 w-2 rounded-full bg-yellow-400 align-middle" />{' '}
                进行中 <span className="font-mono">{totals.inProgress}</span>
              </span>
              <span>
                <span className="inline-block h-2 w-2 rounded-full bg-slate-300 align-middle" />{' '}
                待开始 <span className="font-mono">{totals.pending}</span>
              </span>
            </div>
          </section>

          <div className="grid gap-4 lg:grid-cols-3">
            {/* Phase 卡片 */}
            <section className="lg:col-span-2 space-y-3">
              <h2 className="text-lg font-semibold">各阶段进度</h2>
              {mergedPhases.length === 0 && (
                <div className="rounded border border-slate-200 bg-white p-4 text-sm text-slate-500">
                  暂无数据
                </div>
              )}
              {mergedPhases.map((p, idx) => {
                const total = p.items.length
                const done = p.items.filter((i) => i.done).length
                const inProg = p.items.filter((i) => i.inProgress && !i.done).length
                const pct = total > 0 ? Math.round((done / total) * 100) : 0
                // key = heading + idx（防同名 phase 撞 key）
                const key = `${p.heading}-${idx}`
                const allDone = done === total
                const anyInProg = inProg > 0
                return (
                  <div
                    key={key}
                    className={`rounded border bg-white p-4 shadow-sm ${
                      allDone
                        ? 'border-green-200 bg-green-50/30'
                        : anyInProg
                          ? 'border-yellow-200'
                          : 'border-slate-200'
                    }`}
                  >
                    <div className="mb-2 flex items-baseline justify-between">
                      <h3 className="text-base font-semibold text-slate-800">{p.heading}</h3>
                      <span className="text-xs text-slate-500">
                        <span className="font-mono">
                          {done}/{total}
                        </span>{' '}
                        · {pct}%
                      </span>
                    </div>
                    <div className="mb-2 h-2 w-full overflow-hidden rounded bg-slate-100">
                      <div className="flex h-full">
                        <div
                          className="bg-green-500"
                          style={{ width: `${(done / Math.max(1, total)) * 100}%` }}
                        />
                        <div
                          className="bg-yellow-400"
                          style={{ width: `${(inProg / Math.max(1, total)) * 100}%` }}
                        />
                      </div>
                    </div>
                    <details>
                      <summary className="cursor-pointer text-xs text-slate-500 hover:text-slate-700">
                        展开 {total} 项
                      </summary>
                      <ul className="mt-2 space-y-1 text-xs">
                        {p.items.map((it, i) => {
                          const itemKey = `${key}-${i}`
                          return (
                            <li
                              key={itemKey}
                              className={`flex items-start gap-2 ${
                                it.done
                                  ? 'text-slate-400 line-through'
                                  : it.inProgress
                                    ? 'text-yellow-700'
                                    : 'text-slate-600'
                              }`}
                            >
                              <span className="mt-0.5 inline-block h-3 w-3 flex-shrink-0 rounded border border-slate-300 text-center text-[10px] leading-[10px] text-white">
                                {it.done ? (
                                  <span className="block h-full w-full rounded bg-green-500">✓</span>
                                ) : it.inProgress ? (
                                  <span className="block h-full w-full rounded bg-yellow-400">~</span>
                                ) : null}
                              </span>
                              <span>{it.text}</span>
                            </li>
                          )
                        })}
                      </ul>
                    </details>
                  </div>
                )
              })}
            </section>

            {/* 最近 commits */}
            <section className="space-y-3">
              <h2 className="text-lg font-semibold">最近 commits</h2>
              <div className="rounded border border-slate-200 bg-white shadow-sm">
                <ul className="divide-y divide-slate-100">
                  {data.commits.length === 0 && (
                    <li className="p-4 text-xs text-slate-500">git log 为空</li>
                  )}
                  {data.commits.map((c, i) => (
                    <li key={`${c.sha}-${i}`} className="p-3 text-xs">
                      <div className="mb-1 flex items-baseline justify-between gap-2">
                        <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] text-slate-700">
                          {c.shortSha}
                        </code>
                        <time className="text-[11px] text-slate-400">
                          {new Date(c.date).toLocaleString('zh-CN', {
                            month: '2-digit',
                            day: '2-digit',
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </time>
                      </div>
                      <div className="text-slate-700">{c.subject}</div>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="rounded border border-slate-200 bg-slate-50 p-3 text-xs text-slate-500">
                💡 提示：勾选状态来源是仓库内 <span className="font-mono">docs/*.md</span>，每 30s 自动重拉一次。
                完成一项开发后，把{' '}
                <span className="font-mono">- [ ]</span> 改成{' '}
                <span className="font-mono">- [x]</span> 即可在本页看到绿色进度。
              </div>
            </section>
          </div>
        </main>
      )}

      {!data && !err && (
        <div className="p-12 text-center text-sm text-slate-500">加载中…</div>
      )}
    </div>
  )
}