'use client'
// /admin/operators — v2 ff_operators 实页（侧抽屉布局）
// 模式：list 始终可见 + 新建表单 = 右侧抽屉（480px）→ dry-run 预览 → Confirm 提交
// 行内「下架」按钮 → DELETE /api/admin/operators/[id]（软删 is_active=false）
// 事实层：docs/v2-forms-spec.md §1
// zod：packages/shared/src/schemas/v2-forms.ts OperatorCreateSchema
import Link from 'next/link'
import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  HAND_OPTIONS,
  GENDER_OPTIONS,
  AGE_RANGE_OPTIONS,
} from '@ff/shared/constants/v2-options'
import type { OperatorCreate, OperatorRow } from '@ff/shared/schemas'

// 表单 state 类型：consented_to_recording 用 boolean（用户编辑时可能是 false）
// 提交时 zod 强校验必须 true
type FormState = Omit<OperatorCreate, 'consented_to_recording'> & {
  consented_to_recording: boolean
}

type DryRun = {
  mode: 'dry-run'
  business_key: string
  payload: Record<string, unknown>
  sql_preview: string
}

type DrawerMode = 'closed' | 'form-fill' | 'form-dry-run'

export default function AdminOperatorsPage() {
  // 列表
  const [rows, setRows] = useState<OperatorRow[]>([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [showInactive, setShowInactive] = useState(false)

  // 抽屉
  const [drawer, setDrawer] = useState<DrawerMode>('closed')

  // 表单
  const [form, setForm] = useState<FormState>({
    alias: '',
    name: '',
    hand: 'right',
    gender: 'male',
    age_range: '25-30',
    job_role: '',
    role_experience: '',
    consented_to_recording: true,
    hand_size_cm: undefined,
  })
  const [dryRun, setDryRun] = useState<DryRun | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [submitErr, setSubmitErr] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  // 软删中的行 id
  const [deactivating, setDeactivating] = useState<string | null>(null)

  const loadList = useCallback(async () => {
    setLoading(true)
    setErr(null)
    try {
      const r = await fetch(
        `/api/admin/operators${showInactive ? '?includeInactive=true' : ''}`,
        { cache: 'no-store' },
      )
      const j = (await r.json()) as
        | { ok: true; data: { rows: OperatorRow[] } }
        | { ok: false; error: { message: string } }
      if (!j.ok) throw new Error(j.error.message)
      setRows(j.data.rows)
    } catch (e) {
      setErr((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [showInactive])

  useEffect(() => {
    loadList()
  }, [loadList])

  // 客户端搜索
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return rows
    return rows.filter(
      (r) =>
        (r.alias ?? '').toLowerCase().includes(q) ||
        (r.name ?? '').toLowerCase().includes(q) ||
        r.business_key.toLowerCase().includes(q) ||
        (r.job_role ?? '').toLowerCase().includes(q),
    )
  }, [rows, search])

  // 统计（让用户新建前知道已到第几个 op）
  const activeCount = useMemo(
    () => rows.filter((r) => r.is_active).length,
    [rows],
  )
  const lastAlias = useMemo(() => {
    const aliases = rows
      .map((r) => r.alias)
      .filter((a): a is string => !!a)
      .sort()
    return aliases[aliases.length - 1] ?? null
  }, [rows])

  // dry-run 提交
  const onDryRun = async () => {
    setSubmitting(true)
    setSubmitErr(null)
    try {
      const r = await fetch('/api/admin/operators?dryRun=true', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      const j = (await r.json()) as
        | { ok: true; data: DryRun }
        | { ok: false; error: { message: string; details?: unknown } }
      if (!j.ok) {
        const details = j.error.details ? `\n${JSON.stringify(j.error.details, null, 2)}` : ''
        throw new Error(j.error.message + details)
      }
      setDryRun(j.data)
      setDrawer('form-dry-run')
    } catch (e) {
      setSubmitErr((e as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  // commit
  const onCommit = async () => {
    if (!dryRun) return
    setSubmitting(true)
    setSubmitErr(null)
    try {
      const r = await fetch('/api/admin/operators?dryRun=false', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      const j = (await r.json()) as
        | { ok: true; data: { business_key: string; row: OperatorRow } }
        | { ok: false; error: { message: string } }
      if (!j.ok) throw new Error(j.error.message)
      setToast(`✅ 已创建：${j.data.business_key}`)
      setDrawer('closed')
      setDryRun(null)
      // 重置表单
      setForm({
        alias: '',
        name: '',
        hand: 'right',
        gender: 'male',
        age_range: '25-30',
        job_role: '',
        role_experience: '',
        consented_to_recording: true,
        hand_size_cm: undefined,
      })
      await loadList()
    } catch (e) {
      setSubmitErr((e as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  // 软删
  const onDeactivate = async (id: string, alias: string | null) => {
    if (!confirm(`确认下架「${alias ?? id}」？软删后 is_active=false，可在右上「显示已下架」里看到。`)) {
      return
    }
    setDeactivating(id)
    try {
      const r = await fetch(`/api/admin/operators?id=${encodeURIComponent(id)}`, {
        method: 'DELETE',
      })
      const j = (await r.json()) as
        | { ok: true; data: { row: { id: string; is_active: boolean } } }
        | { ok: false; error: { message: string } }
      if (!j.ok) throw new Error(j.error.message)
      setToast(`✅ 已下架：${alias ?? id}`)
      await loadList()
    } catch (e) {
      setToast(`❌ 下架失败：${(e as Error).message}`)
    } finally {
      setDeactivating(null)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* 头部 — 始终可见 */}
      <header className="border-b border-slate-200 bg-white px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold">📋 操作员 (v2)</h1>
            <p className="text-sm text-slate-500">
              数据源：<code className="font-mono">ff.ff_operators</code> · 事实层{' '}
              <code>docs/v2-forms-spec.md §1</code> · 写入走 dry-run → commit
            </p>
          </div>
          <Link
            href="/"
            className="rounded border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-100"
          >
            ← Admin 首页
          </Link>
        </div>
      </header>

      {toast && (
        <div className="mx-6 mt-4 flex items-center justify-between rounded border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
          <span>{toast}</span>
          <button onClick={() => setToast(null)} className="text-emerald-700 hover:text-emerald-900">
            ✕
          </button>
        </div>
      )}

      <main className="mx-auto max-w-[1400px] px-6 py-6">
        {err && (
          <div className="mb-4 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">
            ❌ {err}
          </div>
        )}

        <div className="flex gap-4">
          {/* ====== 左侧：list 始终可见 ====== */}
          <section className={drawer !== 'closed' ? 'flex-1 min-w-0' : 'flex-1'}>
            {/* 工具条 */}
            <div className="mb-3 flex flex-wrap items-center gap-2 rounded border border-slate-200 bg-white p-3 text-sm">
              <input
                type="text"
                placeholder="搜索 alias / name / business_key / job_role…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-72 rounded border border-slate-300 px-2 py-1"
              />
              <label className="flex items-center gap-1 text-xs text-slate-600">
                <input
                  type="checkbox"
                  checked={showInactive}
                  onChange={(e) => setShowInactive(e.target.checked)}
                />
                显示已下架
              </label>
              <span className="text-xs text-slate-500">
                {loading
                  ? '加载中…'
                  : `共 ${filtered.length} / ${rows.length} 行 · active ${activeCount}`}
              </span>
              {lastAlias && (
                <span className="text-xs text-slate-400">
                  上一 alias：<code className="font-mono">{lastAlias}</code>
                </span>
              )}
              <button
                onClick={() => {
                  setDrawer('form-fill')
                  setSubmitErr(null)
                  setDryRun(null)
                }}
                className="ml-auto rounded bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700"
              >
                + 新建操作员
              </button>
            </div>

            {/* 列表 */}
            <div className="overflow-x-auto rounded border border-slate-200 bg-white">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-3 py-2">business_key</th>
                    <th className="px-3 py-2">alias</th>
                    <th className="px-3 py-2">name</th>
                    <th className="px-3 py-2">hand</th>
                    <th className="px-3 py-2">gender / age</th>
                    <th className="px-3 py-2">job_role</th>
                    <th className="px-3 py-2">consent</th>
                    <th className="px-3 py-2">active</th>
                    <th className="px-3 py-2">created_at</th>
                    <th className="px-3 py-2 text-right">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {!loading && filtered.length === 0 && (
                    <tr>
                      <td colSpan={10} className="p-6 text-center text-slate-400">
                        无数据 — 点右上「+ 新建操作员」开始
                      </td>
                    </tr>
                  )}
                  {filtered.map((r, i) => (
                    <tr key={`${r.id}-${i}`} className="border-t border-slate-100">
                      <td className="px-3 py-1.5 font-mono text-xs font-semibold text-slate-900">
                        {r.business_key}
                      </td>
                      <td className="px-3 py-1.5 text-slate-700">{r.alias ?? '—'}</td>
                      <td className="px-3 py-1.5 text-slate-700">{r.name ?? '—'}</td>
                      <td className="px-3 py-1.5 text-slate-600">
                        {r.hand ?? '—'}
                        {r.hand_size_cm != null && (
                          <span className="ml-1 text-[10px] text-slate-400">
                            ({r.hand_size_cm}cm)
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-1.5 text-slate-600">
                        {r.gender ?? '—'} / {r.age_range ?? '—'}
                      </td>
                      <td className="px-3 py-1.5 text-slate-600">{r.job_role ?? '—'}</td>
                      <td className="px-3 py-1.5">
                        {r.consented_to_recording ? (
                          <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[11px] text-emerald-800">
                            ✓
                          </span>
                        ) : (
                          <span className="rounded bg-red-100 px-1.5 py-0.5 text-[11px] text-red-800">
                            ✗
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-1.5">
                        {r.is_active ? (
                          <span className="rounded bg-blue-100 px-1.5 py-0.5 text-[11px] text-blue-800">
                            active
                          </span>
                        ) : (
                          <span className="rounded bg-slate-200 px-1.5 py-0.5 text-[11px] text-slate-500">
                            inactive
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-1.5 font-mono text-[11px] text-slate-500">
                        {r.created_at.slice(0, 19).replace('T', ' ')}
                      </td>
                      <td className="px-3 py-1.5 text-right">
                        {r.is_active && (
                          <button
                            onClick={() => onDeactivate(r.id, r.alias ?? null)}
                            disabled={deactivating === r.id}
                            className="rounded border border-slate-300 px-2 py-0.5 text-[11px] text-slate-600 hover:bg-slate-50 disabled:opacity-50"
                            title="软删：is_active=false（数据保留）"
                          >
                            {deactivating === r.id ? '…' : '下架'}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* ====== 右侧：form 抽屉 ====== */}
          {drawer !== 'closed' && (
            <aside className="w-[480px] flex-shrink-0">
              <div className="sticky top-4 rounded border-2 border-emerald-400 bg-white p-5 shadow-lg">
                <div className="mb-4 flex items-center justify-between">
                  <h2 className="text-lg font-semibold text-emerald-900">
                    新建操作员 —{' '}
                    {drawer === 'form-dry-run' ? 'Step 2 · 预览' : 'Step 1 · 填字段'}
                  </h2>
                  <button
                    onClick={() => {
                      setDrawer('closed')
                      setSubmitErr(null)
                      setDryRun(null)
                    }}
                    className="text-sm text-slate-500 hover:text-slate-900"
                    title="关闭抽屉"
                  >
                    ✕
                  </button>
                </div>

                {submitErr && (
                  <div className="mb-3 whitespace-pre-wrap rounded border border-red-300 bg-red-50 px-3 py-2 text-xs text-red-800">
                    ❌ {submitErr}
                  </div>
                )}

                {drawer === 'form-dry-run' && dryRun ? (
                  <>
                    <div className="mb-3 rounded border border-amber-300 bg-amber-50 p-2 text-xs">
                      <strong>预览模式</strong> — 还没真写库。检查无误后点 <strong>Confirm 提交</strong>。
                    </div>
                    <dl className="mb-3 max-h-80 space-y-1 overflow-y-auto rounded border border-slate-200 bg-slate-50 p-2 text-xs">
                      <div className="flex justify-between border-b border-slate-200 pb-1">
                        <dt className="font-semibold text-slate-700">business_key（server-gen）</dt>
                        <dd className="font-mono text-emerald-700">{dryRun.business_key}</dd>
                      </div>
                      {Object.entries(dryRun.payload).map(([k, v]) => (
                        <div key={k} className="flex justify-between">
                          <dt className="text-slate-600">{k}</dt>
                          <dd className="font-mono text-[11px] text-slate-800">
                            {v === null || v === undefined ? '—' : String(v)}
                          </dd>
                        </div>
                      ))}
                    </dl>
                    <details className="mb-3 rounded border border-slate-200 bg-white p-1 text-[11px]">
                      <summary className="cursor-pointer font-semibold text-slate-700">
                        SQL 预览
                      </summary>
                      <pre className="mt-1 max-h-32 overflow-x-auto rounded bg-slate-900 p-2 font-mono text-[10px] text-slate-100">
                        {dryRun.sql_preview}
                      </pre>
                    </details>
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => setDrawer('form-fill')}
                        disabled={submitting}
                        className="rounded-md border border-slate-300 px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                      >
                        ← 修改
                      </button>
                      <button
                        onClick={onCommit}
                        disabled={submitting}
                        className="rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700 disabled:opacity-50"
                      >
                        {submitting ? '提交中…' : '✅ Confirm'}
                      </button>
                    </div>
                  </>
                ) : (
                  <form
                    onSubmit={(e) => {
                      e.preventDefault()
                      onDryRun()
                    }}
                    className="space-y-2.5"
                  >
                    <Field label="Alias *">
                      <input
                        required
                        value={form.alias}
                        onChange={(e) => setForm({ ...form, alias: e.target.value })}
                        placeholder="op01"
                        className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
                      />
                    </Field>
                    <Field label="Name *">
                      <input
                        required
                        value={form.name}
                        onChange={(e) => setForm({ ...form, name: e.target.value })}
                        placeholder="张三"
                        className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
                      />
                    </Field>
                    <div className="grid grid-cols-2 gap-2">
                      <Field label="Hand *">
                        <select
                          value={form.hand}
                          onChange={(e) =>
                            setForm({ ...form, hand: e.target.value as FormState['hand'] })
                          }
                          className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
                        >
                          {HAND_OPTIONS.map((h) => (
                            <option key={h} value={h}>
                              {h}
                            </option>
                          ))}
                        </select>
                      </Field>
                      <Field label="Hand size (cm)">
                        <input
                          type="number"
                          step="0.1"
                          value={form.hand_size_cm ?? ''}
                          onChange={(e) =>
                            setForm({
                              ...form,
                              hand_size_cm: e.target.value ? Number(e.target.value) : undefined,
                            })
                          }
                          className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
                        />
                      </Field>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <Field label="Gender *">
                        <select
                          value={form.gender}
                          onChange={(e) =>
                            setForm({
                              ...form,
                              gender: e.target.value as FormState['gender'],
                            })
                          }
                          className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
                        >
                          {GENDER_OPTIONS.map((g) => (
                            <option key={g} value={g}>
                              {g}
                            </option>
                          ))}
                        </select>
                      </Field>
                      <Field label="Age range *">
                        <select
                          value={form.age_range}
                          onChange={(e) =>
                            setForm({
                              ...form,
                              age_range: e.target.value as FormState['age_range'],
                            })
                          }
                          className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
                        >
                          {AGE_RANGE_OPTIONS.map((a) => (
                            <option key={a} value={a}>
                              {a}
                            </option>
                          ))}
                        </select>
                      </Field>
                    </div>
                    <Field label="Job / role *">
                      <input
                        required
                        value={form.job_role}
                        onChange={(e) => setForm({ ...form, job_role: e.target.value })}
                        placeholder="recorder"
                        className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
                      />
                    </Field>
                    <Field label="Role experience *">
                      <input
                        required
                        value={form.role_experience}
                        onChange={(e) => setForm({ ...form, role_experience: e.target.value })}
                        placeholder="1-3 years"
                        className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
                      />
                    </Field>

                    <div className="flex items-start gap-2 rounded border border-amber-200 bg-amber-50 p-2">
                      <input
                        id="consent"
                        type="checkbox"
                        checked={form.consented_to_recording}
                        onChange={(e) =>
                          setForm({ ...form, consented_to_recording: e.target.checked })
                        }
                        className="mt-0.5"
                      />
                      <label htmlFor="consent" className="text-[11px] text-amber-900">
                        <span className="text-red-500">*</span> Operator consented to recording
                        （合规硬要求；A 类 NOT NULL）
                      </label>
                    </div>

                    <div className="flex justify-end gap-2 border-t border-slate-100 pt-3">
                      <button
                        type="button"
                        onClick={() => {
                          setDrawer('closed')
                          setSubmitErr(null)
                        }}
                        className="rounded-md border border-slate-300 px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        disabled={submitting}
                        className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
                      >
                        {submitting ? '预览中…' : '→ Dry-run 预览'}
                      </button>
                    </div>
                  </form>
                )}
              </div>
            </aside>
          )}
        </div>
      </main>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-0.5 block text-[11px] font-medium text-slate-600">{label}</label>
      {children}
    </div>
  )
}
