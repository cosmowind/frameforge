'use client'
// /admin/scene-applications — v2 占位（绿框；v2-forms-spec 4.2 字段）
// 事实层：docs/v2-forms-spec.md 4. ff_scene_applications（dr 未开通 scene 申请池）
// 角色：培训员/录制员发现 dr 没开通某 scene → 在本表新建申请（draft → 提交 → dr 批了 → approved_scene_id 指向新建的 scenes 行）
// 表已落库：ff.ff_scene_applications
import Link from 'next/link'

const FIELDS = [
  { name: 'id',                    type: 'uuid PK',     a: 'A', desc: 'gen_random_uuid()' },
  { name: 'business_key',          type: 'text UNIQUE', a: 'A', desc: '业务键' },
  { name: 'alias',                 type: 'text',        a: 'B', desc: '申请内部编号' },
  { name: 'environment_l1',        type: 'text',        a: 'B', desc: '27 选项' },
  { name: 'venue_l2',              type: 'text',        a: 'B', desc: '228 选项' },
  { name: 'scene_l3',              type: 'text',        a: 'B', desc: '1590 选项（申请的）' },
  { name: 'deadline',              type: 'date',        a: 'N', desc: '申请场景不一定有截止' },
  { name: 'total_hours_quota',     type: 'double precision', a: 'N', desc: '同上' },
  { name: 'application_status',    type: 'text',        a: 'A', desc: 'S: draft/submitted_to_dr/approved/rejected（默认 draft）' },
  { name: 'applied_by_user_key',   type: 'text',        a: 'A', desc: 'dev cookie 占位；未来接 Clerk 字段类型不变' },
  { name: 'function_description',  type: 'text',        a: 'B', desc: '「场景职能」（与 scenes 区别字段）' },
  { name: 'dedup_against',         type: 'text',        a: 'B', desc: '「与现有 scene 对比」防重复' },
  { name: 'approved_scene_id',     type: 'uuid FK',     a: 'N', desc: '→ ff_scenes.id；dr 批了后回填；ON DELETE SET NULL' },
  { name: 'environment_photo_url', type: 'text',        a: 'N', desc: '申请附图（phase 2 接图床）' },
  { name: 'decided_at',            type: 'timestamptz', a: 'N', desc: '决策时间' },
  { name: 'is_active',             type: 'boolean',     a: 'A', desc: 'R3 审计三件套' },
  { name: 'version',               type: 'integer',     a: 'A', desc: 'R3 乐观锁' },
  { name: 'created_at',            type: 'timestamptz', a: 'A', desc: 'R3 审计时间' },
  { name: 'updated_at',            type: 'timestamptz', a: 'A', desc: 'R3 审计时间' },
] as const

const A_BADGE: Record<string, string> = {
  A: 'bg-red-100 text-red-800',
  B: 'bg-amber-100 text-amber-800',
  N: 'bg-slate-100 text-slate-500',
}

export default function AdminSceneApplicationsPage() {
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold">📝 Scene 申请池（v2 scene_applications）</h1>
            <p className="text-sm text-slate-500">
              数据源：<code className="font-mono">ff.ff_scene_applications</code> · 字段定义见{' '}
              <span className="text-blue-600 underline" title="本机仓库 docs/v2-forms-spec.md §4">
                docs/v2-forms-spec.md §4
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
          🟩 <strong>占位阶段</strong> — 字段表已就位；申请流（draft → submitted_to_dr → approved/rejected）尚待接。
          下一步会：① GET 拉现有行 → ② 新建申请 zod min(1) on alias/env_l1/venue_l2/scene_l3 →
          ③ 提交接口改 application_status='submitted_to_dr' → ④ dr webhook（未来）回写 approved_scene_id。
        </div>

        <div className="rounded border-2 border-emerald-400 bg-white p-4">
          <h2 className="mb-3 text-lg font-semibold text-emerald-900">字段表（ff_scene_applications）</h2>
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

        {/* 与 scenes 字段差异说明 */}
        <div className="rounded border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900">
          <h3 className="mb-1 font-semibold">与 ff_scenes 的字段差异（重要）</h3>
          <ul className="list-disc space-y-0.5 pl-5">
            <li>
              <strong>多 4 个申请态字段</strong>：function_description / dedup_against / approved_scene_id / decided_at
            </li>
            <li>
              <strong>无 capture_mode / project_code</strong> — 这两个由 dr 决定，dr 批了之后由 admin 在 ff_scenes 补
            </li>
          </ul>
        </div>

        <div className="rounded border border-slate-200 bg-white p-3 text-xs text-slate-600">
          <h3 className="mb-1 font-semibold text-slate-700">CHECK 约束</h3>
          <pre className="overflow-x-auto rounded bg-slate-900 p-2 font-mono text-[11px] text-slate-100">
{`application_status IN ('draft','submitted_to_dr','approved','rejected')`}
          </pre>
        </div>

        <div className="rounded border border-slate-200 bg-white p-3 text-xs text-slate-600">
          <h3 className="mb-1 font-semibold text-slate-700">索引</h3>
          <ul className="list-disc space-y-0.5 pl-5">
            <li><code className="font-mono">ff_scene_applications(application_status) WHERE is_active</code></li>
            <li><code className="font-mono">ff_scene_applications(applied_by_user_key) WHERE is_active</code></li>
          </ul>
        </div>
      </main>
    </div>
  )
}
