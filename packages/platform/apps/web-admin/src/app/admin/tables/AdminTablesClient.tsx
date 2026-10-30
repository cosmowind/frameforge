'use client'
// /admin/tables 客户端：4 表 tabs + 列勾选 + 搜索 + 排序 + 分页 + 批量编辑
// 服务端预拉 schema（columns 元信息 + 默认列），数据按需 fetch
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import BulkEditDrawer from './BulkEditDrawer'
import type {
  TableConfig,
  TableKey,
} from '@/lib/table-config'

interface ColumnMeta {
  column_name: string
  data_type: string
  is_nullable: 'YES' | 'NO'
  column_default: string | null
}

interface SchemaResponse {
  tables: Array<TableConfig & { columns: ColumnMeta[] }>
}

interface DataResponse {
  table: TableKey
  primaryKey: string
  rows: Array<Record<string, unknown>>
  total: number
  limit: number
  offset: number
  sort: string
  order: 'asc' | 'desc'
}

const PAGE_SIZE_OPTIONS = [50, 100, 200, 500]

export default function AdminTablesClient({
  initial,
}: {
  initial: SchemaResponse
}) {
  const tables = initial.tables
  const [activeKey, setActiveKey] = useState<TableKey>('videos')
  const active = tables.find((t) => t.key === activeKey)!

  // 列显隐：每张表独立状态；初始用默认列
  const [visibleCols, setVisibleCols] = useState<Record<TableKey, string[]>>(() => {
    const m = {} as Record<TableKey, string[]>
    for (const t of tables) m[t.key] = [...t.defaultColumns]
    return m
  })
  // 列顺序：每张表独立（默认 = schema ordinal_position 顺序）
  const [orderedCols, setOrderedCols] = useState<Record<TableKey, string[]>>(() => {
    const m = {} as Record<TableKey, string[]>
    for (const t of tables) m[t.key] = t.columns.map((c) => c.column_name)
    return m
  })

  const [showColPicker, setShowColPicker] = useState(false)
  const [search, setSearch] = useState('')
  const [pageSize, setPageSize] = useState(100)
  const [page, setPage] = useState(0)
  const [sort, setSort] = useState<{ col: string; order: 'asc' | 'desc' }>({
    col: active.defaultSort.col,
    order: active.defaultSort.order,
  })
  const [data, setData] = useState<DataResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  // 批量编辑：选中行 pk + 抽屉显隐
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [showBulk, setShowBulk] = useState(false)
  // 切 tab / fetch 成功 / 列显隐时清空选中
  const resetSelection = useCallback(() => {
    setSelected(new Set())
    setShowBulk(false)
  }, [])
  // 切 activeKey 时清选中（防跨表遗留）
  useEffect(() => {
    resetSelection()
  }, [activeKey, resetSelection])

  // 切换表时重置排序 + 页码
  useEffect(() => {
    setSort({ col: active.defaultSort.col, order: active.defaultSort.order })
    setPage(0)
    setSearch('')
  }, [activeKey, active.defaultSort.col, active.defaultSort.order])

  // 全局单调递增的 key 后缀（每次 fetch data 都 +1）
  // React 19 strict mode dev 双渲染 + Next.js 16 HMR 偶尔会让同一次 fetch 的两个 <tr> 看到一样的 key
  // 用单调计数器保证两次 render 之间的 key 永不重复
  const renderEpochRef = useRef(0)
  const [dataEpoch, setDataEpoch] = useState(0)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setErr(null)
    try {
      const url = new URL('/api/admin/tables/data', window.location.origin)
      url.searchParams.set('table', activeKey)
      url.searchParams.set('limit', String(pageSize))
      url.searchParams.set('offset', String(page * pageSize))
      url.searchParams.set('sort', sort.col)
      url.searchParams.set('order', sort.order)
      if (search.trim()) url.searchParams.set('q', search.trim())
      const r = await fetch(url.toString())
      const j = (await r.json()) as { ok: boolean; data?: DataResponse; error?: { message: string } }
      if (!j.ok || !j.data) throw new Error(j.error?.message ?? 'fetch failed')
      // 每次拿到新数据都让 epoch +1，确保 React 看到的 key 永不重复
      renderEpochRef.current += 1
      setDataEpoch(renderEpochRef.current)
      setData(j.data)
      // 拿到新数据后清选中（防止切页/排序后 pk 漂移）
      setSelected(new Set())
    } catch (e) {
      setErr((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [activeKey, pageSize, page, sort, search])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // 搜索用 debounce
  const [searchInput, setSearchInput] = useState('')
  useEffect(() => {
    const t = setTimeout(() => setSearch(searchInput), 300)
    return () => clearTimeout(t)
  }, [searchInput])

  // 切换 tab 时把页码归 0 + 立即清空旧 data（避免旧 tab 的行用新 tab 的列渲染出现 undefined 单元格）
  useEffect(() => {
    setPage(0)
    setData(null)
    setErr(null)
    setSearchInput('')
    setSearch('')
    // 重置 epoch，让新 tab 从 0 开始
    renderEpochRef.current += 1
    setDataEpoch(renderEpochRef.current)
  }, [activeKey])

  const visibleSet = useMemo(() => new Set(visibleCols[activeKey]), [visibleCols, activeKey])
  const ordered = useMemo(
    () => orderedCols[activeKey].filter((c) => visibleSet.has(c)),
    [orderedCols, visibleCols, activeKey],
  )

  const toggleCol = (col: string) => {
    setVisibleCols((prev) => {
      const cur = new Set(prev[activeKey])
      if (cur.has(col)) cur.delete(col)
      else cur.add(col)
      // 至少保留 1 列
      if (cur.size === 0) return prev
      return { ...prev, [activeKey]: [...cur] }
    })
  }

  const moveCol = (col: string, dir: -1 | 1) => {
    setOrderedCols((prev) => {
      const arr = [...prev[activeKey]]
      const i = arr.indexOf(col)
      if (i < 0) return prev
      const j = i + dir
      if (j < 0 || j >= arr.length) return prev
      const a = arr[i]!
      const b = arr[j]!
      arr[i] = b
      arr[j] = a
      return { ...prev, [activeKey]: arr }
    })
  }

  const onHeaderClick = (col: string) => {
    setSort((s) =>
      s.col === col ? { col, order: s.order === 'asc' ? 'desc' : 'asc' } : { col, order: 'asc' },
    )
    setPage(0)
  }

  const total = data?.total ?? 0
  const maxPage = Math.max(0, Math.ceil(total / pageSize) - 1)

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold">数据表浏览</h1>
            <p className="text-sm text-slate-500">
              查看 4 张业务表（videos / tasks / recorders / environments），可勾选字段、排序、搜索；
              修改请走 <Link href="/library/fill" className="text-blue-600 underline">/library/fill</Link> 或
              AI 数据库工具（<Link href="/admin/db" className="text-blue-600 underline">/admin/db</Link>）
            </p>
          </div>
          <div className="flex gap-2 text-sm">
            <Link
              href="/admin/db"
              className="rounded border border-slate-300 px-3 py-2 text-slate-700 hover:bg-slate-100"
            >
              ← 数据库管理
            </Link>
          </div>
        </div>
      </header>

      <nav className="border-b border-slate-200 bg-white px-6">
        <div className="flex gap-1">
          {tables.map((t) => (
            <button
              key={t.key}
              onClick={() => setActiveKey(t.key)}
              className={`-mb-px border-b-2 px-4 py-3 text-sm ${
                t.key === activeKey
                  ? 'border-blue-500 font-semibold text-blue-700'
                  : 'border-transparent text-slate-600 hover:text-slate-900'
              }`}
            >
              {t.label}
              <span className="ml-2 text-xs text-slate-400">{t.description}</span>
            </button>
          ))}
        </div>
      </nav>

      <main className="mx-auto max-w-[1500px] space-y-4 px-6 py-4">
        <div className="flex flex-wrap items-center gap-2 rounded border border-slate-200 bg-white p-3 text-sm">
          <input
            type="text"
            placeholder="搜索（跨所有列模糊匹配）…"
            value={searchInput}
            onChange={(e) => {
              setSearchInput(e.target.value)
              setPage(0)
            }}
            className="w-72 rounded border border-slate-300 px-2 py-1"
          />
          <span className="text-xs text-slate-500">
            排序：<span className="font-mono">{sort.col}</span> {sort.order === 'asc' ? '↑' : '↓'}
          </span>
          <label className="ml-auto flex items-center gap-1 text-xs">
            每页
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value))
                setPage(0)
              }}
              className="rounded border border-slate-300 px-1 py-0.5"
            >
              {PAGE_SIZE_OPTIONS.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <button
            onClick={() => setShowColPicker((v) => !v)}
            className="rounded border border-slate-300 bg-slate-50 px-2 py-1 text-xs hover:bg-slate-100"
          >
            ⚙ 列设置（{visibleCols[activeKey].length}/{orderedCols[activeKey].length}）
          </button>
        </div>

        {showColPicker && (
          <div className="rounded border border-slate-200 bg-white p-3 text-sm shadow">
            <div className="mb-2 font-medium text-slate-700">列显隐 + 顺序</div>
            <ul className="max-h-80 space-y-1 overflow-y-auto">
              {orderedCols[activeKey].map((c, i) => (
                <li key={c} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={visibleSet.has(c)}
                    onChange={() => toggleCol(c)}
                  />
                  <span className="font-mono text-xs">{c}</span>
                  <span className="ml-auto flex gap-1 text-xs">
                    <button
                      onClick={() => moveCol(c, -1)}
                      disabled={i === 0}
                      className="rounded border border-slate-200 px-1.5 hover:bg-slate-50 disabled:opacity-30"
                    >
                      ←
                    </button>
                    <button
                      onClick={() => moveCol(c, 1)}
                      disabled={i === orderedCols[activeKey].length - 1}
                      className="rounded border border-slate-200 px-1.5 hover:bg-slate-50 disabled:opacity-30"
                    >
                      →
                    </button>
                  </span>
                </li>
              ))}
            </ul>
            <div className="mt-2 flex justify-end gap-2 text-xs">
              <button
                onClick={() => {
                  setVisibleCols((prev) => ({
                    ...prev,
                    [activeKey]: orderedCols[activeKey],
                  }))
                }}
                className="rounded border border-slate-300 px-2 py-1 hover:bg-slate-50"
              >
                全选
              </button>
              <button
                onClick={() => {
                  setVisibleCols((prev) => ({
                    ...prev,
                    [activeKey]: [active.primaryKey],
                  }))
                }}
                className="rounded border border-slate-300 px-2 py-1 hover:bg-slate-50"
              >
                只看主键
              </button>
              <button
                onClick={() => setShowColPicker(false)}
                className="rounded bg-slate-900 px-2 py-1 text-white"
              >
                完成
              </button>
            </div>
          </div>
        )}

        {err && (
          <div className="rounded border border-red-200 bg-red-50 p-3 text-red-800">错误：{err}</div>
        )}

        {/* 批量编辑选中条：仅 videos tab 显示 */}
        {active.key === 'videos' && selected.size > 0 && (
          <div className="flex items-center justify-between rounded border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
            <div>
              已选 <span className="font-mono font-semibold">{selected.size}</span> 行
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setSelected(new Set())}
                className="rounded border border-emerald-300 bg-white px-2 py-1 text-xs hover:bg-emerald-100"
              >
                取消选择
              </button>
              <button
                onClick={() => setShowBulk(true)}
                className="rounded bg-emerald-600 px-3 py-1 text-xs font-semibold text-white hover:bg-emerald-700"
              >
                ✏ 批量编辑
              </button>
            </div>
          </div>
        )}

        <div className="overflow-x-auto rounded border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr>
                {active.key === 'videos' && (
                  <th className="w-8 px-3 py-2">
                    <input
                      type="checkbox"
                      checked={
                        !!data &&
                        data.rows.length > 0 &&
                        data.rows.every((r) => selected.has(String(r[active.primaryKey] ?? '')))
                      }
                      onChange={(e) => {
                        if (!data) return
                        if (e.target.checked) {
                          const next = new Set(selected)
                          for (const r of data.rows) next.add(String(r[active.primaryKey] ?? ''))
                          setSelected(next)
                        } else {
                          setSelected(new Set())
                        }
                      }}
                      title="全选当前页"
                    />
                  </th>
                )}
                {ordered.map((c) => (
                  <th
                    key={c}
                    onClick={() => onHeaderClick(c)}
                    className="cursor-pointer select-none whitespace-nowrap px-3 py-2 hover:bg-slate-100"
                    title="点击切换排序"
                  >
                    <span className="font-mono">{c}</span>
                    {sort.col === c && (
                      <span className="ml-1 text-blue-600">{sort.order === 'asc' ? '↑' : '↓'}</span>
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody key={`${activeKey}-tbody`}>
              {loading && !data && (
                <tr key={`${activeKey}-loading`}>
                  <td colSpan={ordered.length || 1} className="p-6 text-center text-slate-400">
                    加载中…
                  </td>
                </tr>
              )}
              {!loading && data?.rows.length === 0 && (
                <tr key={`${activeKey}-empty`}>
                  <td colSpan={ordered.length || 1} className="p-6 text-center text-slate-400">
                    无数据
                  </td>
                </tr>
              )}
              {data?.rows.map((row, i) => {
                // key 策略：用 render epoch + 行 index 双重兜底
                // React 19 dev 双渲染 + Next.js HMR 偶尔会让同一次 fetch 的两个 <tr> 看到
                // 一样的 primaryKey-派生 key。epoch 每次 fetch 都 +1，绝不重复；
                // index 在单次 render 内绝对唯一。两层保险。
                const keyPart = `e${dataEpoch}-${activeKey}-r${i}`
                const pkVal = String(row[active.primaryKey] ?? '')
                return (
                <tr key={keyPart} className="border-t border-slate-100">
                  {active.key === 'videos' && (
                    <td className="w-8 px-3 py-1.5">
                      <input
                        type="checkbox"
                        checked={selected.has(pkVal)}
                        onChange={(e) => {
                          const next = new Set(selected)
                          if (e.target.checked) next.add(pkVal)
                          else next.delete(pkVal)
                          setSelected(next)
                        }}
                      />
                    </td>
                  )}
                  {ordered.map((c) => {
                    const v = row[c]
                    const isPk = c === active.primaryKey
                    return (
                      <td
                        key={c}
                        className={`whitespace-nowrap px-3 py-1.5 font-mono text-xs ${
                          isPk ? 'font-semibold text-slate-900' : 'text-slate-600'
                        } ${v === '' || v === null ? 'text-slate-300' : ''}`}
                        title={String(v ?? '')}
                      >
                        {v === null || v === ''
                          ? '—'
                          : typeof v === 'object'
                            ? JSON.stringify(v)
                            : String(v)}
                      </td>
                    )
                  })}
                </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between text-xs text-slate-600">
          <div>
            {data ? (
              <>
                第 <span className="font-mono">{page * pageSize + 1}</span>–
                <span className="font-mono">
                  {Math.min((page + 1) * pageSize, total)}
                </span>{' '}
                行 / 共 <span className="font-mono">{total}</span> 行
                {search && ` （已过滤 "${search}"）`}
              </>
            ) : (
              '—'
            )}
          </div>
          <div className="flex gap-1">
            <button
              onClick={() => setPage(0)}
              disabled={page === 0}
              className="rounded border border-slate-300 px-2 py-1 hover:bg-slate-50 disabled:opacity-30"
            >
              « 首页
            </button>
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="rounded border border-slate-300 px-2 py-1 hover:bg-slate-50 disabled:opacity-30"
            >
              ‹ 上一页
            </button>
            <span className="px-2 py-1">
              <span className="font-mono">{page + 1}</span> / <span className="font-mono">{maxPage + 1}</span>
            </span>
            <button
              onClick={() => setPage((p) => Math.min(maxPage, p + 1))}
              disabled={page >= maxPage}
              className="rounded border border-slate-300 px-2 py-1 hover:bg-slate-50 disabled:opacity-30"
            >
              下一页 ›
            </button>
            <button
              onClick={() => setPage(maxPage)}
              disabled={page >= maxPage}
              className="rounded border border-slate-300 px-2 py-1 hover:bg-slate-50 disabled:opacity-30"
            >
              末页 »
            </button>
          </div>
        </div>
      </main>

      {showBulk && (
        <BulkEditDrawer
          table={active.key}
          primaryKey={active.primaryKey}
          selectedPks={Array.from(selected)}
          onClose={() => setShowBulk(false)}
          onSuccess={() => {
            // 提交后清选中 + 强制刷新当前页
            setSelected(new Set())
            setShowBulk(false)
            fetchData()
          }}
        />
      )}
    </div>
  )
}
