// Uploader /login — 录制员登录（关联 Clerk ↔ recorder）
// dev 模式（clerk placeholder）：从 recorders 列表直接选
// 生产模式：Clerk SignIn → 查 ff_users.recorder_id
'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'

interface RecorderOpt { id: string; name: string }

export default function LoginPage() {
  const [me, setMe] = useState<Record<string, unknown> | null>(null)
  const [recorders, setRecorders] = useState<RecorderOpt[]>([])
  const [picked, setPicked] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [result, setResult] = useState<Record<string, unknown> | null>(null)
  const [busy, setBusy] = useState(false)

  const refresh = async () => {
    setErr(null)
    try {
      const r = await fetch('/api/uploader/me')
      const j = await r.json()
      if (j.ok) setMe(j.data)
    } catch (e) { setErr((e as Error).message) }
  }
  useEffect(() => { refresh() }, [])

  useEffect(() => {
    fetch('/api/uploader/devices')
      .then((r) => r.json())
      .then((j) => { if (j.ok) setRecorders(j.data.recorders) })
  }, [])

  const submit = async () => {
    setBusy(true); setErr(null); setResult(null)
    try {
      const r = await fetch('/api/uploader/me', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ recorderId: picked }),
      })
      const j = await r.json()
      if (!j.ok) throw new Error(j.error?.message ?? 'login failed')
      setResult(j.data)
      // dev 模式：写 cookie 让 GET /api/uploader/me 后续能识别
      if (j.data.devMode) {
        document.cookie = `ff_dev_recorder=${picked}; path=/; max-age=86400`
      }
      await refresh()
    } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }

  const meRecorder = (me?.recorder as { id: string; name: string } | null) ?? null
  const loggedIn = !!meRecorder

  return (
    <main className="mx-auto max-w-2xl p-4">
      <header className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold">👤 录制员登录</h1>
        <Link href="/" className="text-sm text-blue-600 underline">← 回到首页</Link>
      </header>

      {loggedIn ? (
        <section className="rounded border border-green-200 bg-green-50 p-4">
          <div className="font-semibold text-green-900">✅ 已登录</div>
          <div className="mt-1 text-sm text-green-800">
            录制员：<code className="font-mono">{meRecorder!.id}</code> · {meRecorder!.name}
          </div>
          <div className="mt-3 flex gap-2">
            <Link href="/devices" className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white">→ 去登记设备</Link>
            <button onClick={() => { document.cookie = 'ff_dev_recorder=; path=/; max-age=0'; setMe(null); }} className="rounded border border-slate-300 px-3 py-1.5 text-sm">登出</button>
          </div>
        </section>
      ) : (
        <section className="rounded border border-slate-200 bg-white p-4">
          <p className="mb-3 text-sm text-slate-600">
            dev 模式：直接选你的 recorder_id（生产模式走 Clerk SignIn）。
            录制员数据来自 <code className="font-mono">public.recorders</code>。
          </p>
          <label className="mb-1 block text-sm font-medium">选你的 ID</label>
          <select value={picked} onChange={(e) => setPicked(e.target.value)} className="w-full rounded border border-slate-300 px-2 py-1">
            <option value="">（选）</option>
            {recorders.map((c) => <option key={c.id} value={c.id}>{c.id} · {c.name}</option>)}
          </select>
          <div className="mt-3 text-xs text-slate-500">
            找不到？管理员去 <Link href="http://localhost:3002/admin/tables" className="text-blue-600 underline">/admin/tables</Link> 登记。
          </div>
          <button onClick={submit} disabled={busy || !picked} className="mt-3 rounded bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-40">
            {busy ? '登录中…' : '登录'}
          </button>
        </section>
      )}

      {err && <div className="mt-3 rounded border border-red-200 bg-red-50 p-2 text-sm text-red-800">错误：{err}</div>}
      {result && !loggedIn && (
        <section className="mt-3 rounded border border-blue-200 bg-blue-50 p-2 text-sm">{JSON.stringify(result)}</section>
      )}

      <p className="mt-6 text-xs text-slate-500">
        登录后 → <Link href="/devices" className="text-blue-600 underline">/devices</Link> · <Link href="/tasks" className="text-blue-600 underline">/tasks</Link>
      </p>
    </main>
  )
}