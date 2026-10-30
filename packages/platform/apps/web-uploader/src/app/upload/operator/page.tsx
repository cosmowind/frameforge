'use client'
// /upload/operator — 快速新建操作员（modal 子路由；v2-forms-spec §1）
// 占位阶段：表单字段按 zod min(1) 列出 + 提交按钮（POST /api/uploader/operators 暂返 501）
import Link from 'next/link'
import { useState } from 'react'

const B_FIELDS = [
  { name: 'alias', label: 'Alias *', placeholder: 'op01' },
  { name: 'name', label: 'Name *', placeholder: '张三' },
  { name: 'hand', label: 'Hand *', placeholder: 'left / right / both' },
  { name: 'gender', label: 'Gender *', placeholder: 'male / female / other' },
  { name: 'age_range', label: 'Age range *', placeholder: '20-29' },
  { name: 'job_role', label: 'Job / role *', placeholder: 'recorder' },
  { name: 'role_experience', label: 'Role experience *', placeholder: '1-3 years' },
] as const

export default function QuickNewOperatorPage() {
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null)

  const onSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setSubmitting(true)
    setResult(null)
    const fd = new FormData(e.currentTarget)
    const payload = Object.fromEntries(fd.entries())
    try {
      const r = await fetch('/api/uploader/operators', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const j = (await r.json().catch(() => ({}))) as { ok?: boolean; error?: { message: string } }
      if (!r.ok) throw new Error(j.error?.message ?? `HTTP ${r.status}`)
      setResult({ ok: true, message: '已提交（占位阶段未真写）' })
    } catch (err) {
      setResult({ ok: false, message: (err as Error).message })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="mx-auto max-w-2xl p-4">
      <header className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">📋 快速新建操作员</h1>
        <Link
          href="/upload"
          className="rounded border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-100"
        >
          ← 返回 /upload
        </Link>
      </header>

      <div className="mb-4 rounded border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
        🟩 <strong>占位阶段</strong> — 字段表已就位；POST /api/uploader/operators 暂返 501 not implemented。
        下一步会：① zod min(1) on alias/name/hand/gender/age_range/job_role/role_experience + consent=true
        → ② 写入走 dry-run → commit → ③ 回写 /upload 的操作员下拉。
      </div>

      <form
        onSubmit={onSubmit}
        className="rounded border-2 border-emerald-400 bg-white p-6 shadow-sm"
      >
        <h2 className="mb-4 text-lg font-semibold text-emerald-900">ff_operators（v2-forms-spec §1）</h2>

        {B_FIELDS.map((f) => (
          <div key={f.name} className="mb-3">
            <label className="mb-1 block text-[11px] font-medium text-slate-600">{f.label}</label>
            <input
              name={f.name}
              placeholder={f.placeholder}
              className="w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
            />
          </div>
        ))}

        <div className="mb-3">
          <label className="mb-1 block text-[11px] font-medium text-slate-600">Hand size (cm)</label>
          <input
            name="hand_size_cm"
            type="number"
            step="0.1"
            className="w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
          />
        </div>

        <div className="mb-3">
          <label className="mb-1 block text-[11px] font-medium text-slate-600">Email</label>
          <input
            name="email"
            type="email"
            className="w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
          />
        </div>

        <div className="mb-4 flex items-start gap-2">
          <input
            id="consent"
            name="consented_to_recording"
            type="checkbox"
            value="true"
            required
            className="mt-0.5"
          />
          <label htmlFor="consent" className="text-[12px] text-slate-700">
            <span className="text-red-500">*</span> Operator consented to recording
            （合规硬要求；schema NOT NULL）
          </label>
        </div>

        {result && (
          <div
            className={`mb-3 rounded border px-3 py-2 text-sm ${
              result.ok
                ? 'border-emerald-300 bg-emerald-50 text-emerald-900'
                : 'border-red-300 bg-red-50 text-red-800'
            }`}
          >
            {result.ok ? '✅' : '❌'} {result.message}
          </div>
        )}

        <div className="flex justify-end gap-2">
          <Link
            href="/upload"
            className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Cancel
          </Link>
          <button
            type="submit"
            disabled={submitting}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {submitting ? '提交中…' : 'Save changes'}
          </button>
        </div>
      </form>
    </main>
  )
}
