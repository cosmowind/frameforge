// Uploader /tasks — 任务登记
// 录制员先选 env_id（决定 scene 类）→ 看可登记的 task 列表 → 选 task → 写 videos.task_id
// 流程：选 video path + task → 预览 → 确认
'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'

interface TaskRow {
  task_id: string
  task: string
  process: string | null
  process_en: string | null
  product: string | null
  tool: string | null
  difficulty: string | null
  quota_min: string | null
  scene: string | null
  environment: string | null
}

interface EnvOpt { env_id: string; scene: string | null; environment: string | null }

export default function TasksPage() {
  const [envs, setEnvs] = useState<EnvOpt[]>([])
  const [path, setPath] = useState('')
  const [envId, setEnvId] = useState('')
  const [q, setQ] = useState('')
  const [tasks, setTasks] = useState<TaskRow[]>([])
  const [picked, setPicked] = useState('')
  const [dryRun, setDryRun] = useState<Record<string, unknown> | null>(null)
  const [result, setResult] = useState<Record<string, unknown> | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    fetch('/api/uploader/devices')
      .then((r) => r.json())
      .then((j) => { if (j.ok) setEnvs(j.data.environments) })
  }, [])

  useEffect(() => {
    const sp = new URLSearchParams({ envId, q, limit: '200' })
    fetch('/api/uploader/tasks?' + sp.toString())
      .then((r) => r.json())
      .then((j) => { if (j.ok) setTasks(j.data.tasks) })
  }, [envId, q])

  const submit = async (commit: boolean) => {
    setBusy(true); setErr(null); setDryRun(null); setResult(null)
    try {
      const r = await fetch('/api/uploader/tasks' + (commit ? '?commit=true' : ''), {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, taskId: picked }),
      })
      const j = await r.json()
      if (!j.ok) throw new Error(j.error?.message ?? 'failed')
      if (commit) setResult(j.data)
      else setDryRun(j.data.willUpdate)
    } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }

  return (
    <main className="mx-auto max-w-3xl p-4">
      <header className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold">📋 任务登记</h1>
        <Link href="/" className="text-sm text-blue-600 underline">← 回到首页</Link>
      </header>
      <p className="mb-4 text-sm text-slate-600">
        录完设备 → 选这个视频的 task_id（决定工序 / 工具 / 难度 / 配额）<br />
        写入 <code className="font-mono">public.videos.task_id</code>。
      </p>

      <section className="grid grid-cols-2 gap-3 rounded border border-slate-200 bg-white p-3 text-sm">
        <div>
          <label className="mb-1 block text-xs font-medium">视频 path *</label>
          <input value={path} onChange={(e) => setPath(e.target.value)} placeholder="/media/..." className="w-full rounded border border-slate-300 px-2 py-1 font-mono text-xs" />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium">环境 env_id（过滤）</label>
          <select value={envId} onChange={(e) => setEnvId(e.target.value)} className="w-full rounded border border-slate-300 px-2 py-1">
            <option value="">（所有）</option>
            {envs.map((e) => <option key={e.env_id} value={e.env_id}>{e.env_id} · {e.environment}</option>)}
          </select>
        </div>
        <div className="col-span-2">
          <label className="mb-1 block text-xs font-medium">搜索（task / process / product / tool）</label>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="水龙头 / 螺丝 / ..." className="w-full rounded border border-slate-300 px-2 py-1 text-xs" />
        </div>
      </section>

      <section className="mt-3 rounded border border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-3 py-2 text-xs text-slate-500">候选 task（{tasks.length}）</div>
        <ul className="max-h-80 overflow-y-auto divide-y divide-slate-100 text-xs">
          {tasks.length === 0 && <li className="p-3 text-slate-400">无匹配任务</li>}
          {tasks.map((t) => (
            <li key={t.task_id}
                onClick={() => setPicked(t.task_id)}
                className={`cursor-pointer p-2 hover:bg-blue-50 ${picked === t.task_id ? 'bg-blue-100' : ''}`}>
              <div className="flex items-baseline gap-2">
                <code className="font-mono text-[11px] text-slate-500">{t.task_id}</code>
                <span className="font-semibold">{t.task}</span>
                {t.difficulty && <span className="ml-auto rounded bg-amber-100 px-1.5 py-0.5 text-[10px] text-amber-800">难度 {t.difficulty}</span>}
              </div>
              <div className="mt-0.5 text-[11px] text-slate-500">
                {t.process} {t.process_en && `· ${t.process_en}`} · 工具 {t.tool} · 产品 {t.product} · 配额 {t.quota_min}min
              </div>
            </li>
          ))}
        </ul>
      </section>

      <div className="mt-3 flex gap-2">
        <button onClick={() => submit(false)} disabled={busy || !path || !picked} className="rounded border border-slate-300 bg-slate-50 px-4 py-2 text-sm hover:bg-slate-100 disabled:opacity-40">
          {busy && !dryRun ? '预览中…' : '🔍 预览'}
        </button>
        <button onClick={() => submit(true)} disabled={busy || !dryRun || result !== null} className="rounded bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-40">
          {busy ? '提交中…' : '✓ 确认登记 task_id'}
        </button>
      </div>

      {err && <div className="mt-3 rounded border border-red-200 bg-red-50 p-2 text-sm text-red-800">错误：{err}</div>}
      {dryRun && (
        <section className="mt-3 rounded border border-blue-200 bg-blue-50 p-3 text-sm">
          <div className="mb-1 font-semibold text-blue-900">⚠ 预览</div>
          <pre className="overflow-x-auto rounded bg-white p-2 font-mono text-xs">{JSON.stringify(dryRun, null, 2)}</pre>
        </section>
      )}
      {result && (
        <section className="mt-3 rounded border border-green-200 bg-green-50 p-3 text-sm text-green-900">
          ✅ 已写入 task_id=<code className="font-mono">{String(result.taskId)}</code>（{String(result.taskName)}）到 videos.path=<code className="font-mono">{String(result.path)}</code>
        </section>
      )}
    </main>
  )
}