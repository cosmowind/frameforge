// Admin 首页（dashboard）— v0.2 + payroll/stats/v2 表单入口
// v2 表单 4 入口（operators / locations / scenes / scene-applications）— 占位阶段，
// 事实层 docs/v2-forms-spec.md；表已落库 ff.ff_*
import Link from 'next/link'

const NAV = [
  {
    href: '/payroll',
    title: '💰 工资管理',
    desc: '按录制员 + 周期算工资；导出 CSV 给已劳动的人',
    highlight: true,
  },
  { href: '/stats', title: '📊 数据统计', desc: '按录制员/任务/难度/日期聚合', highlight: true },
  {
    href: '/admin/tables',
    title: '🗂 数据表浏览',
    desc: '查看 video / task / people / env 全字段，可勾选列 + 排序 + 搜索',
    highlight: true,
  },
  {
    href: '/admin/progress',
    title: '📊 开发进度',
    desc: '实时聚合 docs/features.md + git log 的进度仪表盘',
    highlight: true,
  },
  {
    href: '/admin/operators',
    title: '📋 操作员 (v2)',
    desc: 'v2 operators 占位 · ff.ff_operators · 字段见 v2-forms-spec §1',
    highlight: true,
  },
  {
    href: '/admin/locations',
    title: '📍 场所 (v2)',
    desc: 'v2 locations 占位 · ff.ff_locations · L1=27 / L2=228 选项',
    highlight: true,
  },
  {
    href: '/admin/scenes',
    title: '🎬 Scene 白名单 (v2)',
    desc: 'v2 scenes 占位 · ff.ff_scenes · 5 元组锁 + 配额管理',
    highlight: true,
  },
  {
    href: '/admin/scene-applications',
    title: '📝 Scene 申请池 (v2)',
    desc: 'v2 scene_applications 占位 · dr 未开通 scene 申请流程',
    highlight: true,
  },
  { href: '/device-types', title: '设备类型', desc: '管理 4 种 DeviceAdapter（D10 核心）' },
  { href: '/recorders', title: '录制员', desc: 'CRUD + 区域绑定' },
  { href: '/environments', title: '拍摄环境', desc: 'CRUD + difficulty 标记' },
  { href: '/products', title: '产品 / 工序', desc: '嵌套 CRUD' },
  { href: '/users', title: '账号', desc: 'Clerk 用户同步 + app_role 分配' },
  { href: '/regions', title: '区域', desc: '示例市 / 示例省等' },
  { href: '/audit', title: '审计日志', desc: 'who/when/source_device 追溯' },
]

export default function Page() {
  return (
    <div className="flex min-h-screen">
      <aside className="w-56 bg-slate-900 p-4 text-slate-100">
        <div className="text-lg font-bold">FrameForge Admin</div>
        <nav className="mt-4 space-y-1 text-sm">
          {NAV.map((n) => (
            <Link
              key={n.href}
              href={n.href}
              className={`block rounded px-2 py-1 hover:bg-slate-800 ${
                n.highlight ? 'text-emerald-400' : ''
              }`}
            >
              {n.title}
            </Link>
          ))}
        </nav>
      </aside>
      <main className="flex-1 p-6">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="mb-6 text-slate-600">
          FrameForge Admin · plan2 Phase 0 骨架 ·{' '}
          <span className="rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-800">
            工资 / 统计 已可访问（直查旧表 + lib/payroll.ts 单价规则）
          </span>
          {' · '}
          <span className="rounded bg-emerald-100 px-2 py-0.5 text-xs text-emerald-800">
            v2 表单 4 占位已就绪（v2-forms-spec.md 事实层）
          </span>
        </p>
        <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {NAV.map((n) => (
            <Link
              key={n.href}
              href={n.href}
              className={`block rounded border p-4 hover:border-slate-300 ${
                n.highlight ? 'border-emerald-200 bg-emerald-50' : 'border-slate-200 bg-white'
              }`}
            >
              <div className="font-medium">{n.title}</div>
              <div className="mt-1 text-sm text-slate-500">{n.desc}</div>
            </Link>
          ))}
        </section>
        <section className="mt-8 rounded border border-slate-200 bg-white p-4 text-sm">
          <h2 className="mb-2 font-semibold">数据源</h2>
          <ul className="list-disc space-y-1 pl-5 text-slate-600">
            <li>工资 / 统计 直查 <code>public.video_batch_config + public.videos + public.recorders</code></li>
            <li>设备类型 / 录制员 / 区域 / 审计 走 <code>ff.*</code> 镜像表（Phase 1 ETL 接入）</li>
            <li>
              <strong>v2 表单（4 张）</strong>：operators / locations / scenes / scene-applications
              写 <code>ff.ff_*</code>；表已落库（v2_frameforge_v2_forms.sql），字段定义见{' '}
              <code>docs/v2-forms-spec.md</code>
            </li>
            <li>Clerk 鉴权：自动 dev 模式（placeholder keys 时跳过），用户配置真 keys 后自动启用</li>
          </ul>
        </section>
      </main>
    </div>
  )
}