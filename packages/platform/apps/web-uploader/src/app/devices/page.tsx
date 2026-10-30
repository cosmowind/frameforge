// Uploader /devices — 设备/环境登记
// 录制员选 1 种 device + env_id + recorder + 元信息 → 写 public.videos
// 流程：填表 → 「预览」→ 看到将写入字段 → 「确认提交」
'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'

interface DeviceOpt {
  code: string
  label: string
}
interface EnvOpt {
  env_id: string
  scene: string | null
  environment: string | null
}
interface RecorderOpt {
  id: string
  name: string
}

export default function DevicesPage() {
  const [devices, setDevices] = useState<DeviceOpt[]>([])
  const [envs, setEnvs] = useState<EnvOpt[]>([])
  const [recorders, setRecorders] = useState<RecorderOpt[]>([])
  const [err, setErr] = useState<string | null>(null)

  const [deviceCode, setDeviceCode] = useState('dji_gopro_dcim')
  const [path, setPath] = useState('')
  const [envId, setEnvId] = useState('')
  const [recorderId, setRecorderId] = useState('')
  const [folderName, setFolderName] = useState('')
  const [fileSize, setFileSize] = useState('')
  const [duration, setDuration] = useState('')
  const [fps, setFps] = useState('')
  const [frameCount, setFrameCount] = useState('')
  const [notes, setNotes] = useState('')

  const [dryRun, setDryRun] = useState<Record<string, unknown> | null>(null)
  const [result, setResult] = useState<Record<string, unknown> | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    fetch('/api/uploader/devices')
      .then((r) => r.json())
      .then((j) => {
        if (j.ok) {
          setDevices(j.data.devices)
          setEnvs(j.data.environments)
          setRecorders(j.data.recorders)
        } else setErr(j.error?.message ?? 'load failed')
      })
      .catch((e) => setErr((e as Error).message))
  }, [])

  const body = {
    deviceCode,
    path,
    envId,
    recorderId,
    folderName: folderName || undefined,
    fileSizeBytes: fileSize ? Number(fileSize) : undefined,
    durationSec: duration ? Number(duration) : undefined,
    fps: fps ? Number(fps) : undefined,
    frameCount: frameCount ? Number(frameCount) : undefined,
    notes: notes || undefined,
  }

  const runDry = async () => {
    setBusy(true); setErr(null); setDryRun(null); setResult(null)
    try {
      const r = await fetch('/api/uploader/devices', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      })
      const j = await r.json()
      if (!j.ok) throw new Error(j.error?.message ?? 'dry-run failed')
      setDryRun(j.data.willInsert)
    } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }

  const runCommit = async () => {
    setBusy(true); setErr(null)
    try {
      const r = await fetch('/api/uploader/devices?commit=true', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      })
      const j = await r.json()
      if (!j.ok) throw new Error(j.error?.message ?? 'commit failed')
      setResult(j.data)
    } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }

  return (
    <main className="mx-auto max-w-2xl p-4">
      <header className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold">📷 设备 / 环境登记</h1>
        <Link href="/" className="text-sm text-blue-600 underline">← 回到首页</Link>
      </header>
      <p className="mb-4 text-sm text-slate-600">
        录制员在接入前先登记：选设备类型 + 环境 + 自己的 ID + 视频元信息。<br />
        写入 <code className="font-mono">public.videos</code> 1 行（path 为主键，<code>ON CONFLICT DO NOTHING</code>）。
      </p>

      <section className="space-y-3 rounded border border-slate-200 bg-white p-4">
        <div>
          <label className="mb-1 block text-sm font-medium">设备类型 *</label>
          <select value={deviceCode} onChange={(e) => setDeviceCode(e.target.value)} className="w-full rounded border border-slate-300 px-2 py-1">
            {devices.map((d) => <option key={d.code} value={d.code}>{d.label}</option>)}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">视频路径（path）*</label>
          <input value={path} onChange={(e) => setPath(e.target.value)} placeholder="/media/0630/hmd/0630_xxx_session_00007" className="w-full rounded border border-slate-300 px-2 py-1 font-mono text-xs" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-sm font-medium">环境 env_id *</label>
            <select value={envId} onChange={(e) => setEnvId(e.target.value)} className="w-full rounded border border-slate-300 px-2 py-1">
              <option value="">（选）</option>
              {envs.map((e) => <option key={e.env_id} value={e.env_id}>{e.env_id} · {e.scene}/{e.environment}</option>)}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">录制员 recorder_id *</label>
            <select value={recorderId} onChange={(e) => setRecorderId(e.target.value)} className="w-full rounded border border-slate-300 px-2 py-1">
              <option value="">（选）</option>
              {recorders.map((c) => <option key={c.id} value={c.id}>{c.id} · {c.name}</option>)}
            </select>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-sm">folder_name（可选）</label>
            <input value={folderName} onChange={(e) => setFolderName(e.target.value)} className="w-full rounded border border-slate-300 px-2 py-1 text-xs" />
          </div>
          <div>
            <label className="mb-1 block text-sm">file_size_bytes（可选）</label>
            <input type="number" value={fileSize} onChange={(e) => setFileSize(e.target.value)} className="w-full rounded border border-slate-300 px-2 py-1 text-xs" />
          </div>
          <div>
            <label className="mb-1 block text-sm">duration_sec（可选）</label>
            <input type="number" value={duration} onChange={(e) => setDuration(e.target.value)} className="w-full rounded border border-slate-300 px-2 py-1 text-xs" />
          </div>
          <div>
            <label className="mb-1 block text-sm">fps（可选）</label>
            <input type="number" value={fps} onChange={(e) => setFps(e.target.value)} step="0.1" className="w-full rounded border border-slate-300 px-2 py-1 text-xs" />
          </div>
          <div>
            <label className="mb-1 block text-sm">frame_count（可选）</label>
            <input type="number" value={frameCount} onChange={(e) => setFrameCount(e.target.value)} className="w-full rounded border border-slate-300 px-2 py-1 text-xs" />
          </div>
        </div>
        <div>
          <label className="mb-1 block text-sm">notes（可选）</label>
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} className="w-full rounded border border-slate-300 px-2 py-1 text-xs" />
        </div>
      </section>

      <div className="mt-4 flex gap-2">
        <button onClick={runDry} disabled={busy || !path || !envId || !recorderId} className="rounded border border-slate-300 bg-slate-50 px-4 py-2 text-sm hover:bg-slate-100 disabled:opacity-40">
          {busy && !dryRun ? '预览中…' : '🔍 预览（不真写）'}
        </button>
        <button onClick={runCommit} disabled={busy || !dryRun || result !== null} className="rounded bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-40">
          {busy ? '提交中…' : '✓ 确认登记'}
        </button>
      </div>

      {err && <div className="mt-3 rounded border border-red-200 bg-red-50 p-2 text-sm text-red-800">错误：{err}</div>}

      {dryRun && (
        <section className="mt-3 rounded border border-blue-200 bg-blue-50 p-3 text-sm">
          <div className="mb-1 font-semibold text-blue-900">⚠ 预览：将写入 videos 1 行</div>
          <pre className="overflow-x-auto rounded bg-white p-2 font-mono text-xs">{JSON.stringify(dryRun, null, 2)}</pre>
        </section>
      )}
      {result && (
        <section className="mt-3 rounded border border-green-200 bg-green-50 p-3 text-sm text-green-900">
          ✅ 登记完成：path=<code className="font-mono">{String(result.path)}</code> · captureMode=<code className="font-mono">{String(result.captureMode)}</code>
        </section>
      )}

      <p className="mt-6 text-xs text-slate-500">
        录完 → 下一步：<Link href="/tasks" className="text-blue-600 underline">/tasks</Link> 选这个视频的任务
      </p>
    </main>
  )
}