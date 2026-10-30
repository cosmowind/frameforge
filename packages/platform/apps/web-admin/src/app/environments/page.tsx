import Link from 'next/link'

export default function Page() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-semibold mb-4">拍摄环境</h1>
      <p className="text-slate-600 mb-6">ff_environments CRUD（envType/difficulty）</p>
      <div className="rounded border border-dashed border-slate-300 p-12 text-center text-slate-400">
        占位：Phase 1 填表格
      </div>
      <Link href="/" className="mt-4 inline-block text-sm text-slate-500 hover:text-slate-900">
        ← 返回 Dashboard
      </Link>
    </div>
  )
}
