// /admin/db/policy — 显示 docs/dev-process/database-policy.md 全文
import Link from 'next/link'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { runtimePath } from '@ff/shared/utils/paths'

async function loadPolicy(): Promise<string> {
  try {
    const p = runtimePath('docs', 'dev-process', 'database-policy.md')
    return await readFile(p, 'utf8')
  } catch {
    return '（policy 文档未找到）'
  }
}

export const dynamic = 'force-dynamic'

export default async function PolicyPage() {
  const md = await loadPolicy()

  // 简易 md → html（粗略：保留段落 + 列表）
  const html = md
    .split('\n\n')
    .map((block) => {
      if (block.startsWith('# ')) return `<h1 class="mt-6 text-2xl font-bold">${escape(block.slice(2))}</h1>`
      if (block.startsWith('## ')) return `<h2 class="mt-5 text-lg font-semibold">${escape(block.slice(3))}</h2>`
      if (block.startsWith('### ')) return `<h3 class="mt-4 text-base font-semibold">${escape(block.slice(4))}</h3>`
      if (block.startsWith('|')) return `<table class="my-3 w-full text-sm">${block.split('\n').map((row) => rowToHtml(row)).join('')}</table>`
      if (block.startsWith('- ')) {
        const items = block.split('\n').map((l) => `<li class="ml-4 list-disc">${escape(l.replace(/^- /, ''))}</li>`).join('')
        return `<ul>${items}</ul>`
      }
      return `<p class="my-2 text-sm leading-relaxed">${escape(block)}</p>`
    })
    .join('\n')

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold">数据库策略（policy）</h1>
            <p className="text-sm text-slate-500">AI + 管理员共同遵守</p>
          </div>
          <Link href="/admin/db" className="rounded border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-100">
            ← 数据库
          </Link>
        </div>
      </header>
      <main
        className="prose mx-auto max-w-4xl px-6 py-6"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  )
}

function escape(s: string) {
  return s.replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' })[c]!)
}

function rowToHtml(row: string) {
  const cells = row.split('|').slice(1, -1).map((c) => `<td class="border-b border-slate-200 px-2 py-1">${escape(c.trim())}</td>`).join('')
  return `<tr>${cells}</tr>`
}