'use client'
// BulkEditDrawer — 批量编辑抽屉
// 流程：dry-run 预览 → 用户确认 → ?commit=true 真改
// 写权限：仅 videos 4 字段（与 /api/admin/tables/bulk 同步）
import { useState } from 'react'

interface BulkField {
  key: string
  label: string
  type: 'text' | 'boolean'
}

const BULK_FIELDS: BulkField[] = [
  { key: 'recorder_id', label: '录制员 ID', type: 'text' },
  { key: 'task_id', label: '任务 ID', type: 'text' },
  { key: 'env_id', label: '环境 ID', type: 'text' },
  { key: 'uploaded', label: '已上传', type: 'boolean' },
]

interface DryRunResult {
  mode: 'dry-run'
  affected: number
  sampleBefore: Array<Record<string, unknown>>
  sql: string
  requestedPks: number
}

interface CommitResult {
  mode: 'commit'
  affected: number
  changed: number
  requestedPks: number
}

type BulkResult = DryRunResult | CommitResult

export default function BulkEditDrawer({
  table,
  primaryKey,
  selectedPks,
  onClose,
  onSuccess,
}: {
  table: string
  primaryKey: string
  selectedPks: string[]
  onClose: () => void
  onSuccess: () => void
}) {
  const [field, setField] = useState<string>('recorder_id')
  const [textValue, setTextValue] = useState('')
  const [boolValue, setBoolValue] = useState(true)
  const [dryRun, setDryRun] = useState<DryRunResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [done, setDone] = useState<CommitResult | null>(null)

  const currentField = BULK_FIELDS.find((f) => f.key === field)!
  const isText = currentField.type === 'text'

  const payload = {
    table,
    pks: selectedPks,
    updates: isText
      ? { [field]: textValue }
      : { [field]: boolValue },
  }

  const runDryRun = async () => {
    setBusy(true)
    setErr(null)
    try {
      const r = await fetch('/api/admin/tables/bulk', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const j = (await r.json()) as { ok: boolean; data?: BulkResult; error?: { message: string } }
      if (!j.ok || !j.data) throw new Error(j.error?.message ?? 'dry-run failed')
      setDryRun(j.data as DryRunResult)
    } catch (e) {
      setErr((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const runCommit = async () => {
    setBusy(true)
    setErr(null)
    try {
      const r = await fetch('/api/admin/tables/bulk?commit=true', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const j = (await r.json()) as { ok: boolean; data?: BulkResult; error?: { message: string } }
      if (!j.ok || !j.data) throw new Error(j.error?.message ?? 'commit failed')
      setDone(j.data as CommitResult)
      onSuccess()
    } catch (e) {
      setErr((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-stretch justify-end bg-black/30">
      <div className="flex w-full max-w-xl flex-col bg-white shadow-2xl">
        <header className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <div>
            <h2 className="text-lg font-semibold">批量编辑</h2>
            <p className="text-xs text-slate-500">
              <span className="font-mono">{table}</span> · 选中{' '}
              <span className="font-mono">{selectedPks.length}</span> 行 · 主键{' '}
              <span className="font-mono">{primaryKey}</span>
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded border border-slate-300 px-3 py-1 text-sm hover:bg-slate-50"
          >
            ✕ 关闭
          </button>
        </header>

        <main className="flex-1 space-y-4 overflow-y-auto p-5 text-sm">
          {/* 字段选择 */}
          <div>
            <label className="mb-1 block text-xs text-slate-600">要改的字段</label>
            <select
              value={field}
              onChange={(e) => {
                setField(e.target.value)
                setDryRun(null)
                setDone(null)
              }}
              className="w-full rounded border border-slate-300 px-2 py-1"
            >
              {BULK_FIELDS.map((f) => (
                <option key={f.key} value={f.key}>
                  {f.label} ({f.key})
                </option>
              ))}
            </select>
          </div>

          {/* 值输入 */}
          <div>
            <label className="mb-1 block text-xs text-slate-600">新值</label>
            {isText ? (
              <input
                type="text"
                value={textValue}
                onChange={(e) => {
                  setTextValue(e.target.value)
                  setDryRun(null)
                }}
                placeholder="留空表示置 NULL"
                className="w-full rounded border border-slate-300 px-2 py-1 font-mono"
              />
            ) : (
              <div className="flex gap-3">
                <label className="flex items-center gap-1">
                  <input
                    type="radio"
                    checked={boolValue === true}
                    onChange={() => {
                      setBoolValue(true)
                      setDryRun(null)
                    }}
                  />
                  true
                </label>
                <label className="flex items-center gap-1">
                  <input
                    type="radio"
                    checked={boolValue === false}
                    onChange={() => {
                      setBoolValue(false)
                      setDryRun(null)
                    }}
                  />
                  false
                </label>
              </div>
            )}
          </div>

          <button
            onClick={runDryRun}
            disabled={busy}
            className="w-full rounded border border-slate-300 bg-slate-50 px-3 py-2 hover:bg-slate-100 disabled:opacity-50"
          >
            {busy && !dryRun ? '预览中…' : '🔍 预览（不真改）'}
          </button>

          {err && (
            <div className="rounded border border-red-200 bg-red-50 p-2 text-xs text-red-800">
              {err}
            </div>
          )}

          {dryRun && (
            <section className="rounded border border-blue-200 bg-blue-50 p-3">
              <div className="mb-2 text-xs font-semibold text-blue-900">
                ⚠ 预览（不会真改数据库）
              </div>
              <div className="space-y-1 text-xs text-blue-900">
                <div>
                  <span className="text-slate-600">匹配行数：</span>
                  <span className="font-mono font-semibold">{dryRun.affected}</span> / {dryRun.requestedPks}
                </div>
                <div>
                  <span className="text-slate-600">将执行 SQL：</span>
                  <pre className="mt-1 overflow-x-auto rounded bg-white p-2 font-mono text-[10px]">
                    {dryRun.sql}
                  </pre>
                </div>
                {dryRun.sampleBefore.length > 0 && (
                  <div>
                    <span className="text-slate-600">BEFORE 抽样（前 3 行）：</span>
                    <pre className="mt-1 overflow-x-auto rounded bg-white p-2 font-mono text-[10px]">
                      {JSON.stringify(dryRun.sampleBefore, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            </section>
          )}

          {done && (
            <section className="rounded border border-green-200 bg-green-50 p-3 text-xs text-green-900">
              ✅ 提交完成：实际更新 <span className="font-mono">{done.changed}</span> / {done.affected} 行
            </section>
          )}
        </main>

        <footer className="flex items-center justify-between gap-2 border-t border-slate-200 px-5 py-3 text-sm">
          <button
            onClick={onClose}
            className="rounded border border-slate-300 px-3 py-1.5 text-slate-700 hover:bg-slate-50"
          >
            取消
          </button>
          <button
            onClick={runCommit}
            disabled={busy || !dryRun || done !== null || dryRun.affected === 0}
            className="rounded bg-red-600 px-4 py-1.5 font-semibold text-white hover:bg-red-700 disabled:opacity-40"
            title={!dryRun ? '请先预览' : dryRun.affected === 0 ? '无匹配行' : '确认后写入数据库'}
          >
            {busy ? '提交中…' : '✓ 确认提交'}
          </button>
        </footer>
      </div>
    </div>
  )
}