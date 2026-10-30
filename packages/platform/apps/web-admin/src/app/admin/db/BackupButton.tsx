'use client'

import { useState, useTransition } from 'react'
import { useRouter } from 'next/navigation'

export default function BackupButton() {
  const router = useRouter()
  const [pending, startTransition] = useTransition()
  const [msg, setMsg] = useState<string | null>(null)

  const onClick = () => {
    setMsg(null)
    if (!confirm('⚠️ 触发一次 pg_dump 备份？\n\n耗时 1-10 秒，期间数据库不会被锁（--no-owner）。\n保留最近 10 份，旧备份会自动清理。')) {
      return
    }
    startTransition(async () => {
      try {
        const res = await fetch('/api/admin/db/backup', { method: 'POST' })
        const j = (await res.json()) as { ok: boolean; data?: { files: { name: string }[] }; error?: { message: string } }
        if (j.ok) {
          setMsg(`✅ 备份成功，新增 ${j.data?.files.length ?? 0} 个文件`)
          router.refresh()
        } else {
          setMsg(`❌ ${j.error?.message ?? 'unknown error'}`)
        }
      } catch (e) {
        setMsg(`❌ ${(e as Error).message}`)
      }
    })
  }

  return (
    <div className="flex items-center gap-3">
      <button
        type="button"
        onClick={onClick}
        disabled={pending}
        className="rounded bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700 disabled:bg-slate-300"
      >
        {pending ? '备份中…' : '⚡ 立即备份'}
      </button>
      {msg && <span className="text-xs text-slate-600">{msg}</span>}
    </div>
  )
}