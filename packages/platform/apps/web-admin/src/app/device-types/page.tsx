// 设备类型管理（plan2 §9 Phase 2.3 — 但 Phase 0 占位）
import Link from 'next/link'

export default function Page() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-semibold mb-4">设备类型</h1>
      <p className="text-slate-600 mb-6">
        ff_device_types 表的 CRUD（Phase 1 接 Adapter registry 加新设备时配合）
      </p>
      <div className="rounded border border-dashed border-slate-300 p-12 text-center text-slate-400">
        占位：Phase 1 填表格 CRUD
      </div>
      <Link href="/" className="mt-4 inline-block text-sm text-slate-500 hover:text-slate-900">
        ← 返回 Dashboard
      </Link>
    </div>
  )
}
