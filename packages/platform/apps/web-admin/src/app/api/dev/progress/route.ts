// /api/dev/progress
// 聚合 docs/features.md + docs/project_status.md 解析 checkbox + git log 最近 commits
// 只读，不碰 PG
import { NextResponse } from 'next/server'
import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import { promises as fs } from 'node:fs'
import path from 'node:path'

const execFileAsync = promisify(execFile)

// 仓库根解析：
// Next.js App Router 编译后，route.ts 的 __dirname 会被替换为 .next 编译目录，
// 不可靠。改用 cwd + 上溯找 docs/features.md 标记作为「定位仓库根」手段。
function findRepoRoot(): string {
  // 优先用环境变量
  if (process.env.FF_REPO_ROOT) return process.env.FF_REPO_ROOT
  // 从 cwd 上溯找 docs/features.md
  let cur = process.cwd()
  for (let i = 0; i < 8; i++) {
    try {
      const candidate = path.join(cur, 'docs/features.md')
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      require('node:fs').accessSync(candidate)
      return cur
    } catch {
      const parent = path.dirname(cur)
      if (parent === cur) break
      cur = parent
    }
  }
  // 兜底：cwd 的上 2 层（apps/web-admin → repo root）
  return path.resolve(process.cwd(), '../..')
}

const REPO_ROOT = findRepoRoot()

// 一个 checkbox 项
interface CheckItem {
  text: string
  done: boolean
  inProgress: boolean
}

// 一个 Phase（## 或 ### 段）
interface PhaseBlock {
  level: number
  heading: string
  items: CheckItem[]
}

// 文档解析结果
interface DocParseResult {
  phases: PhaseBlock[]
  totals: { done: number; inProgress: number; pending: number; total: number }
}

async function parseMarkdown(file: string): Promise<DocParseResult> {
  let raw = ''
  try {
    raw = await fs.readFile(file, 'utf8')
  } catch (e) {
    console.error('[parseMarkdown] readFile failed:', file, (e as Error).message)
    return { phases: [], totals: { done: 0, inProgress: 0, pending: 0, total: 0 } }
  }
  const lines = raw.split(/\r?\n/)

  const phases: PhaseBlock[] = []
  let cur: PhaseBlock | null = null
  const flatItems: CheckItem[] = []

  for (const line of lines) {
    // ## / ### heading
    const h = line.match(/^(#{2,6})\s+(.+?)\s*$/)
    if (h && h[1] !== undefined && h[2] !== undefined) {
      const heading = h[2].replace(/\s*—.*$/, '').replace(/\s*\(.*?\)\s*$/, '').trim()
      cur = { level: h[1].length, heading, items: [] }
      phases.push(cur)
      continue
    }
    // checkbox 行（任意缩进）
    const cb = line.match(/^\s*-\s+\[(x| )\]\s+(.*)$/i)
    if (cb && cur && cb[1] !== undefined && cb[2] !== undefined) {
      const done = cb[1].toLowerCase() === 'x'
      const text = cb[2].replace(/\*\*/g, '').trim()
      const inProgress = /进行中|进行|正在|active|in.progress/i.test(text)
      const item: CheckItem = { text, done, inProgress }
      cur.items.push(item)
      flatItems.push(item)
    }
  }

  // 只保留含 items 的 phase
  const phasesWithItems = phases.filter((p) => p.items.length > 0)
  const totals = {
    done: flatItems.filter((i) => i.done).length,
    inProgress: flatItems.filter((i) => i.inProgress && !i.done).length,
    pending: flatItems.filter((i) => !i.done).length,
    total: flatItems.length,
  }
  return { phases: phasesWithItems, totals }
}

interface Commit {
  sha: string
  shortSha: string
  subject: string
  date: string
}

async function getCommits(limit = 10): Promise<Commit[]> {
  try {
    const { stdout } = await execFileAsync(
      'git',
      [
        'log',
        `--pretty=format:%H|%h|%s|%ci`,
        `-n`,
        String(limit),
      ],
      { cwd: REPO_ROOT, maxBuffer: 1024 * 1024 },
    )
    return stdout
      .split('\n')
      .filter(Boolean)
      .map((l) => {
        const [sha, shortSha, subject, date] = l.split('|')
        return { sha: sha!, shortSha: shortSha!, subject: subject!, date: date! }
      })
  } catch {
    return []
  }
}

export const dynamic = 'force-dynamic'

export async function GET() {
  const featuresFile = path.join(REPO_ROOT, 'docs/features.md')
  const statusFile = path.join(REPO_ROOT, 'docs/project_status.md')

  const [features, status, commits] = await Promise.all([
    parseMarkdown(featuresFile).catch((e) => {
      console.error('parse features failed:', e)
      return { phases: [], totals: { done: 0, inProgress: 0, pending: 0, total: 0 } }
    }),
    parseMarkdown(statusFile).catch((e) => {
      console.error('parse status failed:', e)
      return { phases: [], totals: { done: 0, inProgress: 0, pending: 0, total: 0 } }
    }),
    getCommits(10),
  ])

  return NextResponse.json({
    ok: true,
    data: {
      features,
      status,
      commits,
      generatedAt: new Date().toISOString(),
    },
  })
}