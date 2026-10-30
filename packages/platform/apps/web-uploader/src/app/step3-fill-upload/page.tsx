// Step 3：填参 + 上传（plan2 §2.1 + §2.5 localStorage 预填）
import Link from 'next/link'

export default function Step3FillUploadPage() {
  return (
    <main className="mx-auto max-w-2xl p-4">
      <h1 className="text-2xl font-semibold mb-4">Step 3 · 填参 + 上传</h1>
      <p className="text-slate-600 mb-6">
        Phase 1 实现：录制员/环境/工序/任务描述 4 字段 — 上次值用 localStorage 预填 → 改即覆盖 → 提交走 Adapter.prepareForUpload() → 客户端直传 COS。
      </p>
      <div className="rounded border border-dashed border-slate-300 p-12 text-center text-slate-400">
        占位：Phase 1 填表单 + RHF + Zod + cos-js-sdk-v5 直传
      </div>
      <Link href="/" className="mt-4 inline-block text-sm text-slate-500 hover:text-slate-900">
        ← 返回首页
      </Link>
    </main>
  )
}
