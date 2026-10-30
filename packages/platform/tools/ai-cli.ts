// tools/ai-cli.ts
// 给 AI agent / 用户命令行用的 DB 操作工具
// 用法：
//   tsx tools/ai-cli.ts query "<SQL>"
//   tsx tools/ai-cli.ts dry-run '<json updates 数组>'
//   tsx tools/ai-cli.ts commit '<json updates 数组>' --yes
//
// 示例：
//   tsx tools/ai-cli.ts query "SELECT count(*) FROM public.videos"
//   tsx tools/ai-cli.ts dry-run '[{"where":{"path":"D:/sp/..."},"set":{"recorder_id":"op3"}}]'

import 'dotenv/config'

const BASE = process.env.WEB_ADMIN_BASE_URL ?? 'http://localhost:3002'

async function call(path: string, body: unknown): Promise<unknown> {
  const r = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const j = (await r.json()) as { ok: boolean; data?: unknown; error?: { message: string } }
  if (!j.ok) {
    console.error('❌', j.error?.message)
    process.exit(1)
  }
  return j.data
}

async function main() {
  const cmd = process.argv[2]
  const arg = process.argv[3]

  if (!cmd || cmd === 'help') {
    console.log(`用法：
  tsx tools/ai-cli.ts query "<SQL>"
  tsx tools/ai-cli.ts dry-run '<updates JSON 数组>'
  tsx tools/ai-cli.ts commit '<updates JSON 数组>' --yes
  tsx tools/ai-cli.ts health
`)
    return
  }

  if (cmd === 'health') {
    const r = await fetch(`${BASE}/api/admin/db/health`)
    console.log(JSON.stringify(await r.json(), null, 2))
    return
  }

  if (cmd === 'query') {
    if (!arg) {
      console.error('❌ query 需要 SQL 参数')
      process.exit(1)
    }
    const r = await call('/api/ai/db/query', { sql: arg })
    console.log(JSON.stringify(r, null, 2))
    return
  }

  if (cmd === 'dry-run' || cmd === 'commit') {
    if (!arg) {
      console.error(`❌ ${cmd} 需要 updates JSON`)
      process.exit(1)
    }
    let updates
    try {
      updates = JSON.parse(arg)
    } catch (e) {
      console.error('❌ JSON 解析失败:', (e as Error).message)
      process.exit(1)
    }
    const path = cmd === 'dry-run' ? '/api/ai/db/dry-run' : '/api/ai/db/commit'
    const body: { table: string; updates: unknown; confirm?: boolean } = {
      table: 'public.videos',
      updates,
    }
    if (cmd === 'commit') {
      if (!process.argv.includes('--yes')) {
        console.error('❌ commit 必须带 --yes 确认')
        process.exit(1)
      }
      body.confirm = true
    }
    const r = await call(path, body)
    console.log(JSON.stringify(r, null, 2))
    return
  }

  console.error(`❌ 未知命令: ${cmd}`)
  process.exit(1)
}

main().catch((err) => {
  console.error('❌', err)
  process.exit(1)
})