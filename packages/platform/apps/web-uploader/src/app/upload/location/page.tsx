'use client'
// /upload/location — 快速新建场所（modal 子路由；v2-forms-spec §2）
// 占位阶段：表单字段按 zod min(1) 列出 + L1/L2 用文本框占位（27+228 真实选项 phase 2 接入）
import Link from 'next/link'
import { useState } from 'react'

export default function QuickNewLocationPage() {
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null)

  const onSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setSubmitting(true)
    setResult(null)
    const fd = new FormData(e.currentTarget)
    const payload = Object.fromEntries(fd.entries())
    try {
      const r = await fetch('/api/uploader/locations', {
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
        <h1 className="text-2xl font-semibold">📍 快速新建场所</h1>
        <Link
          href="/upload"
          className="rounded border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-100"
        >
          ← 返回 /upload
        </Link>
      </header>

      <div className="mb-4 rounded border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
        🟩 <strong>占位阶段</strong> — 字段表已就位；POST /api/uploader/locations 暂返 501 not implemented。
        L1=27 / L2=228 真实下拉选项 phase 2 接入（先存文本）；地址搜索锁定接口（country + lat + lng 回填）phase 2 接入。
        下一步会：① zod min(1) on alias/env_l1/venue_l2/business_name/business_type/address_line1/city/region_state/zip_postal
        → ② 写入走 dry-run → commit → ③ 回写 /upload 的地点下拉。
      </div>

      <form
        onSubmit={onSubmit}
        className="rounded border-2 border-emerald-400 bg-white p-6 shadow-sm"
      >
        <h2 className="mb-4 text-lg font-semibold text-emerald-900">ff_locations（v2-forms-spec §2）</h2>

        <div className="mb-3">
          <label className="mb-1 block text-[11px] font-medium text-slate-600">Alias *</label>
          <input
            name="alias"
            placeholder="loc01"
            className="w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
          />
        </div>

        <div className="mb-3 grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-[11px] font-medium text-slate-600">Environment (L1) *</label>
            <input
              name="environment_l1"
              placeholder="Retail and Consumer Goods"
              className="w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
            />
            <p className="mt-0.5 text-[10px] text-slate-400">27 选项硬编码（phase 2 改 select）</p>
          </div>
          <div>
            <label className="mb-1 block text-[11px] font-medium text-slate-600">Venue (L2) *</label>
            <input
              name="venue_l2"
              placeholder="Grocery Store"
              className="w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
            />
            <p className="mt-0.5 text-[10px] text-slate-400">228 选项硬编码（phase 2 改 select）</p>
          </div>
        </div>

        <div className="mb-3 grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-[11px] font-medium text-slate-600">Business name *</label>
            <input
              name="business_name"
              className="w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-[11px] font-medium text-slate-600">Business type *</label>
            <input
              name="business_type"
              className="w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
            />
          </div>
        </div>

        <div className="mb-3">
          <label className="mb-1 block text-[11px] font-medium text-slate-600">Address *（搜索锁定 phase 2）</label>
          <input
            name="address_line1"
            placeholder="Search an address…"
            className="w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
          />
        </div>

        <div className="mb-3 grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-[11px] font-medium text-slate-600">Country（v2 降级 N 类）</label>
            <input
              name="country_code"
              placeholder="CN"
              className="w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-[11px] font-medium text-slate-600">City *</label>
            <input
              name="city"
              className="w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
            />
          </div>
        </div>

        <div className="mb-4 grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-[11px] font-medium text-slate-600">Region / state *</label>
            <input
              name="region_state"
              className="w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-[11px] font-medium text-slate-600">Zip / postal *</label>
            <input
              name="zip_postal"
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
