'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'

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

interface Props {
  rows: UnfilledVideoRow[]
  total: number
  limit: number
  offset: number
  recorder: string
  task: string
  env_id: string
  recorders: RecorderOpt[]
  tasks: TaskOpt[]
  environments: EnvOpt[]
}

// localStorage 预填（plan2 §2.5 核心 UX）
const LS_KEY = 'ff.fill.last'
function readLast(): Record<string, string> {
  if (typeof window === 'undefined') return {}
  try {
    return JSON.parse(window.localStorage.getItem(LS_KEY) ?? '{}')
  } catch {
    return {}
  }
}
function writeLast(v: Record<string, string>) {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(LS_KEY, JSON.stringify(v))
}

export default function FillForm({
  rows,
  total,
  limit,
  offset,
  recorder,
  task,
  env_id,
  recorders,
  tasks,
  environments,
}: Props) {
  const router = useRouter()

  // 草稿：path -> { recorder_id, task_id, env_id, uploaded, score }
  const [draft, setDraft] = useState<Record<string, Partial<UnfilledVideoRow>>>({})
  const [batchRecorder, setBatchRecorder] = useState<string>('')
  const [batchTask, setBatchTask] = useState<string>('')
  const [batchEnv, setBatchEnv] = useState<string>('')
  const [batchUploaded, setBatchUploaded] = useState<'Yes' | 'No' | ''>('Yes')
  const [batchScore, setBatchScore] = useState<string>('')
  const [saving, setSaving] = useState(false)
  const [savedMsg, setSavedMsg] = useState<string | null>(null)

  const initialLast = readLast()
  const lastRecorder = initialLast.recorder_id ?? recorder
  const lastTask = initialLast.task_id ?? task
  const lastEnv = initialLast.env_id ?? env_id
  const lastUploaded = (initialLast.uploaded as 'Yes' | 'No' | undefined) ?? 'Yes'

  const setDraftCell = (path: string, key: keyof UnfilledVideoRow, value: string) => {
    setDraft((d) => ({ ...d, [path]: { ...d[path], [key]: value } }))
  }

  const applyBatch = () => {
    const next = { ...draft }
    for (const r of rows) {
      const cur = { ...(next[r.path] ?? {}) }
      if (batchRecorder) cur.recorder_id = batchRecorder
      if (batchTask) cur.task_id = batchTask
      if (batchEnv) cur.env_id = batchEnv
      if (batchUploaded) cur.uploaded = batchUploaded
      if (batchScore) cur.score = batchScore
      next[r.path] = cur
    }
    setDraft(next)
    writeLast({
      recorder_id: batchRecorder || lastRecorder,
      task_id: batchTask || lastTask,
      env_id: batchEnv || lastEnv,
      uploaded: batchUploaded || lastUploaded,
    })
  }

  const submit = async () => {
    const updates = Object.entries(draft)
      .map(([path, d]) => ({
        path,
        ...(d.recorder_id !== undefined ? { recorder_id: d.recorder_id } : {}),
        ...(d.task_id !== undefined ? { task_id: d.task_id } : {}),
        ...(d.env_id !== undefined ? { env_id: d.env_id } : {}),
        ...(d.uploaded !== undefined ? { uploaded: d.uploaded as 'Yes' | 'No' } : {}),
        ...(d.score !== undefined ? { score: d.score } : {}),
      }))
      .filter(
        (u) =>
          u.recorder_id !== undefined ||
          u.task_id !== undefined ||
          u.env_id !== undefined ||
          u.uploaded !== undefined ||
          u.score !== undefined,
      )
    if (updates.length === 0) {
      setSavedMsg('没有可保存的修改')
      return
    }
    setSaving(true)
    setSavedMsg(null)
    try {
      const res = await fetch('/api/admin/videos/batch-fill', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ updates }),
      })
      const j = (await res.json()) as {
        ok: boolean
        data?: { updated_count: number }
        error?: { message: string }
      }
      if (j.ok) {
        setSavedMsg(`✅ 成功更新 ${j.data?.updated_count ?? 0} 条`)
        setDraft({})
        router.refresh()
      } else {
        setSavedMsg(`❌ ${j.error?.message ?? 'unknown error'}`)
      }
    } catch (e) {
      setSavedMsg(`❌ ${(e as Error).message}`)
    } finally {
      setSaving(false)
    }
  }

  const dirtyCount = Object.keys(draft).length

  return (
    <div className="space-y-4">
      <section className="rounded border border-slate-200 bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold text-slate-700">
          🪄 批量预填（localStorage 会记忆）
        </h2>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          <Field label="录制员">
            <select
              value={batchRecorder || lastRecorder}
              onChange={(e) => setBatchRecorder(e.target.value)}
              className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
            >
              <option value="">— 选择 —</option>
              {recorders.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.id} {c.name ? `· ${c.name}` : ''}
                </option>
              ))}
            </select>
          </Field>
          <Field label="任务">
            <select
              value={batchTask || lastTask}
              onChange={(e) => setBatchTask(e.target.value)}
              className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
            >
              <option value="">— 选择 —</option>
              {tasks.map((t) => (
                <option key={t.task_id} value={t.task_id}>
                  {t.task_id} · {t.product ?? '?'}/{t.process ?? '?'}
                </option>
              ))}
            </select>
          </Field>
          <Field label="环境">
            <select
              value={batchEnv || lastEnv}
              onChange={(e) => setBatchEnv(e.target.value)}
              className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
            >
              <option value="">— 选择 —</option>
              {environments.map((e) => (
                <option key={e.env_id} value={e.env_id}>
                  {e.env_id} · {e.environment ?? '?'}
                </option>
              ))}
            </select>
          </Field>
          <Field label="上传">
            <select
              value={batchUploaded || lastUploaded}
              onChange={(e) => setBatchUploaded(e.target.value as 'Yes' | 'No' | '')}
              className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
            >
              <option value="">—</option>
              <option value="Yes">Yes</option>
              <option value="No">No</option>
            </select>
          </Field>
          <Field label="评分">
            <input
              type="text"
              value={batchScore}
              onChange={(e) => setBatchScore(e.target.value)}
              placeholder="如 95% / 4.5"
              className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
            />
          </Field>
        </div>
        <div className="mt-3 flex gap-2">
          <button
            type="button"
            onClick={applyBatch}
            className="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
          >
            应用到本页 {rows.length} 条
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={saving || dirtyCount === 0}
            className="rounded bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700 disabled:bg-slate-300"
          >
            {saving ? '保存中…' : `保存（${dirtyCount} 条有改动）`}
          </button>
          {savedMsg && (
            <span className="self-center text-sm text-slate-600">{savedMsg}</span>
          )}
        </div>
      </section>

      <section className="rounded border border-slate-200 bg-white">
        <header className="flex items-center justify-between border-b border-slate-100 px-4 py-3 text-sm">
          <div className="text-slate-600">
            第 {offset + 1} - {Math.min(offset + limit, total)} / 共 {total} 条
          </div>
          <div className="flex gap-1">
            <PageLink offset={Math.max(0, offset - limit)} limit={limit} recorder={recorder} task={task} env_id={env_id}>
              ← 上一页
            </PageLink>
            <PageLink offset={offset + limit} limit={limit} recorder={recorder} task={task} env_id={env_id}>
              下一页 →
            </PageLink>
          </div>
        </header>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="bg-slate-50 text-left uppercase text-slate-500">
              <tr>
                <th className="px-3 py-2">路径</th>
                <th className="px-3 py-2">日期</th>
                <th className="px-3 py-2">类型</th>
                <th className="px-3 py-2">缺失</th>
                <th className="px-3 py-2">录制员</th>
                <th className="px-3 py-2">任务</th>
                <th className="px-3 py-2">环境</th>
                <th className="px-3 py-2">上传</th>
                <th className="px-3 py-2">评分</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const d = draft[r.path] ?? {}
                const missing = new Set(r.missing)
                return (
                  <tr key={r.path} className="border-t border-slate-100 hover:bg-slate-50">
                    <td className="max-w-xs truncate px-3 py-2 font-mono text-slate-500" title={r.path}>
                      {r.path.split('/').slice(-2).join('/')}
                    </td>
                    <td className="px-3 py-2 text-slate-500">{r.scan_date ?? '—'}</td>
                    <td className="px-3 py-2 uppercase text-slate-500">{r.file_type ?? '?'}</td>
                    <td className="px-3 py-2">
                      <div className="flex flex-wrap gap-1">
                        {Array.from(missing).map((m) => (
                          <span
                            key={m}
                            className={`rounded px-1.5 py-0.5 text-xs ${
                              m === 'uploaded' ? 'bg-orange-100 text-orange-700' : 'bg-red-100 text-red-700'
                            }`}
                          >
                            {m}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-3 py-2">
                      <select
                        value={d.recorder_id ?? r.recorder_id ?? ''}
                        onChange={(e) => setDraftCell(r.path, 'recorder_id', e.target.value)}
                        className={`w-32 rounded border px-1 py-0.5 text-xs ${
                          missing.has('recorder') ? 'border-red-300 bg-red-50' : 'border-slate-200'
                        }`}
                      >
                        <option value="">—</option>
                        {recorders.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.id} {c.name?.slice(0, 4)}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-3 py-2">
                      <select
                        value={d.task_id ?? r.task_id ?? ''}
                        onChange={(e) => setDraftCell(r.path, 'task_id', e.target.value)}
                        className={`w-44 rounded border px-1 py-0.5 text-xs ${
                          missing.has('task') ? 'border-red-300 bg-red-50' : 'border-slate-200'
                        }`}
                      >
                        <option value="">—</option>
                        {tasks.map((t) => (
                          <option key={t.task_id} value={t.task_id}>
                            {t.task_id.slice(0, 12)} {t.product?.slice(0, 4)}/{t.process?.slice(0, 4)}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-3 py-2">
                      <select
                        value={d.env_id ?? r.env_id ?? ''}
                        onChange={(e) => setDraftCell(r.path, 'env_id', e.target.value)}
                        className={`w-32 rounded border px-1 py-0.5 text-xs ${
                          missing.has('env') ? 'border-red-300 bg-red-50' : 'border-slate-200'
                        }`}
                      >
                        <option value="">—</option>
                        {environments.map((env) => (
                          <option key={env.env_id} value={env.env_id}>
                            {env.env_id} {env.environment?.slice(0, 6)}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-3 py-2">
                      <select
                        value={d.uploaded ?? r.uploaded ?? ''}
                        onChange={(e) => setDraftCell(r.path, 'uploaded', e.target.value)}
                        className={`w-16 rounded border px-1 py-0.5 text-xs ${
                          missing.has('uploaded') ? 'border-orange-300 bg-orange-50' : 'border-slate-200'
                        }`}
                      >
                        <option value="">—</option>
                        <option value="Yes">Yes</option>
                        <option value="No">No</option>
                      </select>
                    </td>
                    <td className="px-3 py-2">
                      <input
                        type="text"
                        value={d.score ?? r.score ?? ''}
                        onChange={(e) => setDraftCell(r.path, 'score', e.target.value)}
                        className="w-14 rounded border border-slate-200 px-1 py-0.5 text-xs"
                        placeholder="—"
                      />
                    </td>
                  </tr>
                )
              })}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={9} className="px-3 py-8 text-center text-slate-400">
                    🎉 没有未填全的视频了！
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-xs text-slate-500">{label}</label>
      {children}
    </div>
  )
}

function PageLink({
  offset,
  limit,
  recorder,
  task,
  env_id,
  children,
}: {
  offset: number
  limit: number
  recorder: string
  task: string
  env_id: string
  children: React.ReactNode
}) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  if (recorder) params.set('recorder', recorder)
  if (task) params.set('task', task)
  if (env_id) params.set('env_id', env_id)
  return (
    <a
      href={`?${params.toString()}`}
      className="rounded border border-slate-300 px-2 py-1 hover:bg-slate-100"
    >
      {children}
    </a>
  )
}