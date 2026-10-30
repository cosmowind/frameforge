// 占位（Phase 0 dev 模式无 Clerk）
import Link from 'next/link'

export default function Page() {
  return (
    <main className="grid min-h-screen place-items-center">
      <div className="rounded border border-slate-200 bg-white p-8 text-center">
        <h1 className="text-xl font-semibold">注册</h1>
        <p className="mt-2 text-sm text-slate-500">
          Phase 0 dev 模式：无 Clerk 注册
        </p>
        <Link
          href="/"
          className="mt-6 inline-block rounded bg-blue-600 px-4 py-2 text-sm text-white"
        >
          进入首页
        </Link>
      </div>
    </main>
  )
}