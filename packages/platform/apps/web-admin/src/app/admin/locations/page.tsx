'use client'
// /admin/locations — v2 占位（绿框；v2-forms-spec 2.2 字段）
// 事实层：docs/v2-forms-spec.md 2. ff_locations
// 表已落库：ff.ff_locations
// L1=27 / L2=228 选项：来源 docs/前端调试参考/location0714.txt
// 下一步：地址搜索锁定接口（country_code + lat + lng 自动回填，业务不校验）
import Link from 'next/link'

const FIELDS = [
  { name: 'id',              type: 'uuid PK',          a: 'A', desc: 'gen_random_uuid()' },
  { name: 'business_key',    type: 'text UNIQUE',      a: 'A', desc: '场所简写' },
  { name: 'alias',           type: 'text',             a: 'B', desc: '「Alias *」' },
  { name: 'environment_l1',  type: 'text',             a: 'B', desc: '「Environment (L1) *」27 选项硬编码' },
  { name: 'venue_l2',        type: 'text',             a: 'B', desc: '「Venue (L2) *」228 选项硬编码' },
  { name: 'business_name',   type: 'text',             a: 'B', desc: '「Business name *」' },
  { name: 'business_type',   type: 'text',             a: 'B', desc: '「Business type *」' },
  { name: 'address_line1',   type: 'text',             a: 'B', desc: '「Address *」搜索+select 后回填' },
  { name: 'address_line2',   type: 'text',             a: 'N', desc: '二级地址' },
  { name: 'country_code',    type: 'text',             a: 'N', desc: '「Country *」降级：ff 录入端可空，未来地址搜索回填' },
  { name: 'city',            type: 'text',             a: 'B', desc: '「City *」' },
  { name: 'region_state',    type: 'text',             a: 'B', desc: '「Region / state *」' },
  { name: 'zip_postal',      type: 'text',             a: 'B', desc: '「Zip / postal *」' },
  { name: 'lat',             type: 'double precision', a: 'N', desc: '「GPS」地址锁定后回填' },
  { name: 'lng',             type: 'double precision', a: 'N', desc: '「GPS」地址锁定后回填' },
  { name: 'is_active',       type: 'boolean',          a: 'A', desc: 'R3 审计三件套' },
  { name: 'version',         type: 'integer',          a: 'A', desc: 'R3 乐观锁' },
  { name: 'created_at',      type: 'timestamptz',      a: 'A', desc: 'R3 审计时间' },
  { name: 'updated_at',      type: 'timestamptz',      a: 'A', desc: 'R3 审计时间' },
] as const

const A_BADGE: Record<string, string> = {
  A: 'bg-red-100 text-red-800',
  B: 'bg-amber-100 text-amber-800',
  N: 'bg-slate-100 text-slate-500',
}

export default function AdminLocationsPage() {
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold">📍 场所（v2 locations）</h1>
            <p className="text-sm text-slate-500">
              数据源：<code className="font-mono">ff.ff_locations</code> · 字段定义见{' '}
              <span
                className="text-blue-600 underline"
                title="本机仓库 docs/v2-forms-spec.md §2"
              >
                docs/v2-forms-spec.md §2
              </span>
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

      <main className="mx-auto max-w-[1100px] space-y-4 px-6 py-6">
        <div className="rounded border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
          🟩 <strong>占位阶段</strong> — 字段表已就位；L1+L2 下拉 + 地址搜索锁定接口尚待接。
          下一步会：① GET 拉现有行 → ② 新建表单 zod min(1) on alias/env_l1/venue_l2/business_name/business_type/address_line1/city/region_state/zip_postal
          → ③ 接入地址搜索回填 country_code + lat + lng。
        </div>

        <div className="rounded border-2 border-emerald-400 bg-white p-4">
          <h2 className="mb-3 text-lg font-semibold text-emerald-900">字段表（ff_locations）</h2>
          <div className="overflow-x-auto rounded border border-slate-200">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-3 py-2">列名</th>
                  <th className="px-3 py-2">类型</th>
                  <th className="px-3 py-2">类别</th>
                  <th className="px-3 py-2">说明</th>
                </tr>
              </thead>
              <tbody>
                {FIELDS.map((f) => (
                  <tr key={f.name} className="border-t border-slate-100">
                    <td className="px-3 py-1.5 font-mono text-xs font-semibold text-slate-900">
                      {f.name}
                    </td>
                    <td className="px-3 py-1.5 font-mono text-xs text-slate-600">{f.type}</td>
                    <td className="px-3 py-1.5">
                      <span className={`inline-block rounded px-2 py-0.5 text-[11px] font-semibold ${A_BADGE[f.a]}`}>
                        {f.a}
                      </span>
                    </td>
                    <td className="px-3 py-1.5 text-xs text-slate-600">{f.desc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="rounded border-2 border-dashed border-emerald-300 bg-white p-4 text-sm">
          <h2 className="mb-2 text-lg font-semibold text-emerald-900">表单入口（占位）</h2>
          <p className="text-slate-600">
            实际表单将按{' '}
            <code className="rounded bg-slate-100 px-1">
              Alias * / Environment (L1) * / Venue (L2) * / Business name * / Business type * /
              Address *（搜索+select） / Country / City * / Region / state * / Zip / postal *
            </code>{' '}
            排版。Country 标 * 但 v2 降级为 N（业务端不强制，地址搜索回填后再写入）。
          </p>
        </div>

        <div className="rounded border border-slate-200 bg-white p-3 text-xs text-slate-600">
          <h3 className="mb-1 font-semibold text-slate-700">索引</h3>
          <ul className="list-disc space-y-0.5 pl-5">
            <li><code className="font-mono">ff_locations(is_active)</code></li>
            <li><code className="font-mono">ff_locations(environment_l1, venue_l2) WHERE is_active</code></li>
            <li><code className="font-mono">ff_locations(country_code) WHERE is_active</code></li>
          </ul>
        </div>
      </main>
    </div>
  )
}
