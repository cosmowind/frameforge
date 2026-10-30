'use client'
// /admin/scenes — v2 占位（绿框；v2-forms-spec 3.2 字段）
// 事实层：docs/v2-forms-spec.md 3. ff_scenes（dr 已开通 scene 白名单）
// 关键作用：Playwright 上传按钮锁（env/venue/scene/project/captureMode 5 元组）
// 表已落库：ff.ff_scenes
import Link from 'next/link'

const FIELDS = [
  { name: 'id',                    type: 'uuid PK',     a: 'A', desc: 'gen_random_uuid()' },
  { name: 'business_key',          type: 'text UNIQUE', a: 'A', desc: '合成键（如 summit02_grocery_supershelf）' },
  { name: 'alias',                 type: 'text',        a: 'B', desc: 'admin 内部简写' },
  { name: 'project_code',          type: 'text',        a: 'B', desc: '「Summit-02」项目编号' },
  { name: 'capture_mode',          type: 'text',        a: 'B', desc: '「双目」= single/three_views/stereo' },
  { name: 'environment_l1',        type: 'text',        a: 'B', desc: '27 选项' },
  { name: 'venue_l2',              type: 'text',        a: 'B', desc: '228 选项' },
  { name: 'scene_l3',              type: 'text',        a: 'B', desc: '1590 选项' },
  { name: 'deadline',              type: 'date',        a: 'B', desc: '「2026-07-31」任务截止' },
  { name: 'accept_status',         type: 'text',        a: 'A', desc: 'S: accepting/closed/filled（默认 accepting）' },
  { name: 'total_hours_quota',     type: 'double precision', a: 'B', desc: '「共 80 小时」' },
  { name: 'used_hours',            type: 'double precision', a: 'A', desc: '「剩余 76.9 小时」worker 累计写' },
  { name: 'source',                type: 'text',        a: 'A', desc: 'S: manual/frameforge（v2 全部 manual）' },
  { name: 'status',                type: 'text',        a: 'A', desc: 'S: available/pending/retired（默认 available）' },
  { name: 'environment_photo_url', type: 'text',        a: 'N', desc: 'phase 2 接图床，先留空' },
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

export default function AdminScenesPage() {
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold">🎬 Scene 白名单（v2 scenes）</h1>
            <p className="text-sm text-slate-500">
              数据源：<code className="font-mono">ff.ff_scenes</code> · 字段定义见{' '}
              <span className="text-blue-600 underline" title="本机仓库 docs/v2-forms-spec.md §3">
                docs/v2-forms-spec.md §3
              </span>
              {' '}·{' '}
              <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[11px] text-amber-800">
                5 元组锁：env_l1 + venue_l2 + scene_l3 + project_code + capture_mode
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
          🟩 <strong>占位阶段</strong> — 字段表已就位；scene 录入表单 + 配额统计仪表盘尚待接。
          下一步会：① GET 拉现有行 → ② 新建表单 zod min(1) on alias/project_code/capture_mode/env_l1/venue_l2/scene_l3/deadline/accept_status/total_hours_quota
          → ③ 守门员约束在 video_uploads.scene_id 落库时校验。
        </div>

        <div className="rounded border-2 border-emerald-400 bg-white p-4">
          <h2 className="mb-3 text-lg font-semibold text-emerald-900">字段表（ff_scenes）</h2>
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

        {/* CHECK 约束 */}
        <div className="rounded border border-slate-200 bg-white p-3 text-xs text-slate-600">
          <h3 className="mb-1 font-semibold text-slate-700">CHECK 约束</h3>
          <pre className="overflow-x-auto rounded bg-slate-900 p-2 font-mono text-[11px] text-slate-100">
{`accept_status IN ('accepting','closed','filled')
status        IN ('available','pending','retired')
capture_mode  IS NULL OR capture_mode IN ('single','three_views','stereo')
source        IN ('manual','frameforge')
used_hours    >= 0
              AND (total_hours_quota IS NULL OR used_hours <= total_hours_quota)`}
          </pre>
        </div>

        <div className="rounded border border-slate-200 bg-white p-3 text-xs text-slate-600">
          <h3 className="mb-1 font-semibold text-slate-700">守门员约束（业务层）</h3>
          <ol className="list-decimal space-y-0.5 pl-5">
            <li>
              <code className="font-mono">video_uploads.scene_id</code> 只能选{' '}
              <code className="font-mono">status='available' AND accept_status='accepting' AND used_hours &lt; total_hours_quota</code> 的行
            </li>
            <li>
              <code className="font-mono">source='manual'</code> 的行可随时建；<code className="font-mono">source='frameforge'</code> 的行 v2 不接 DR API
            </li>
            <li>
              <code className="font-mono">environment_photo_url</code> 接受 <code>cos://bucket/key</code> 或 <code>https://</code>，phase 2 才校验
            </li>
          </ol>
        </div>

        <div className="rounded border border-slate-200 bg-white p-3 text-xs text-slate-600">
          <h3 className="mb-1 font-semibold text-slate-700">索引</h3>
          <ul className="list-disc space-y-0.5 pl-5">
            <li><code className="font-mono">ff_scenes(project_code)</code></li>
            <li><code className="font-mono">ff_scenes(status) WHERE is_active</code></li>
            <li><code className="font-mono">ff_scenes(accept_status) WHERE is_active</code></li>
            <li><code className="font-mono">ff_scenes(environment_l1, venue_l2, scene_l3)</code> — 5 元组锁</li>
          </ul>
        </div>
      </main>
    </div>
  )
}
