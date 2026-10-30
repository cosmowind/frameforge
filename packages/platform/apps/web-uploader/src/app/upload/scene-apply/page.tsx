'use client'
// /upload/scene-apply — 快速申请新 scene（modal 子路由；v2-forms-spec §4）
// 占位阶段：表单字段按 zod min(1) 列出 + 提交按钮（POST /api/uploader/scene-applications 暂返 501）
// 角色：录制员发现 dr 没开通某 scene → 在此新建申请
import Link from 'next/link'
import { useState } from 'react'

export default function QuickSceneApplyPage() {
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null)

  const onSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setSubmitting(true)
    setResult(null)
    const fd = new FormData(e.currentTarget)
    const payload = Object.fromEntries(fd.entries())
    try {
      const r = await fetch('/api/uploader/scene-applications', {
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
        <h1 className="text-2xl font-semibold">📝 快速申请新 scene</h1>
        <Link
          href="/upload"
          className="rounded border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-100"
        >
          ← 返回 /upload
        </Link>
      </header>

      <div className="mb-4 rounded border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
        🟩 <strong>占位阶段</strong> — 字段表已就位；POST /api/uploader/scene-applications 暂返 501 not implemented。
        下一步会：① zod min(1) on alias/env_l1/venue_l2/scene_l3 →
        ② 写入 ff_scene_applications(application_status='draft') → ③ 后续由 admin 改 submitted_to_dr → dr webhook 回写 approved_scene_id。
      </div>

      <form
        onSubmit={onSubmit}
        className="rounded border-2 border-emerald-400 bg-white p-6 shadow-sm"
      >
        <h2 className="mb-4 text-lg font-semibold text-emerald-900">
          ff_scene_applications（v2-forms-spec §4）
        </h2>

        <div className="mb-3">
          <label className="mb-1 block text-[11px] font-medium text-slate-600">Alias *</label>
          <input
            name="alias"
            placeholder="apply01"
            className="w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
          />
        </div>

        <div className="mb-3 grid grid-cols-3 gap-3">
          <div>
            <label className="mb-1 block text-[11px] font-medium text-slate-600">Environment (L1) *</label>
            <input
              name="environment_l1"
              placeholder="Retail and Consumer Goods"
              className="w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-[11px] font-medium text-slate-600">Venue (L2) *</label>
            <input
              name="venue_l2"
              placeholder="Grocery Store"
              className="w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-[11px] font-medium text-slate-600">Scene (L3) *</label>
            <input
              name="scene_l3"
              placeholder="Supermarket Shelf"
              className="w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
            />
            <p className="mt-0.5 text-[10px] text-slate-400">1590 选项（phase 2 改 select）</p>
          </div>
        </div>

        <div className="mb-3">
          <label className="mb-1 block text-[11px] font-medium text-slate-600">场景职能（function_description）</label>
          <textarea
            name="function_description"
            rows={2}
            className="w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
          />
        </div>

        <div className="mb-3">
          <label className="mb-1 block text-[11px] font-medium text-slate-600">
            与现有 scene 对比（dedup_against）
          </label>
          <textarea
            name="dedup_against"
            rows={2}
            placeholder="已查过 ff_scenes 表，没有重复"
            className="w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
          />
        </div>

        <div className="mb-4 grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-[11px] font-medium text-slate-600">Deadline (N 类)</label>
            <input
              name="deadline"
              type="date"
              className="w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-[11px] font-medium text-slate-600">
              Total hours quota (N 类)
            </label>
            <input
              name="total_hours_quota"
              type="number"
              step="0.1"
              className="w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
            />
          </div>
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
