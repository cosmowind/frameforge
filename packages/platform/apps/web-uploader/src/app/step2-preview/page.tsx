// Step 2：选 session + 预览（plan2 §2.1）
import Link from 'next/link'

export default function Step2PreviewPage() {
  return (
    <main className="mx-auto max-w-3xl p-4">
      <h1 className="text-2xl font-semibold mb-4">Step 2 · 选择 + 预览</h1>
      <p className="text-slate-600 mb-6">
        Phase 1 实现：选定 session → 调 DeviceAdapter.getPreviewHandle() → native 直接播放（DCIM/Generic AVI）或 worker 流式（HMD/MCAP）。
      </p>
      <div className="rounded border border-dashed border-slate-300 p-12 text-center text-slate-400">
        占位：Phase 1 填 video 标签 + Generic AVI 多 AVI 顺序切换
      </div>
      <Link href="/" className="mt-4 inline-block text-sm text-slate-500 hover:text-slate-900">
        ← 返回首页
      </Link>
    </main>
  )
}
