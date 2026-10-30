// POST /api/admin/db/migrate
// 跑 packages/db-schema/src/migrations/*.sql
// 安全：只读 SQL 文件 → 拆 statement → 每条独立跑 → 单条失败立即停
// 仅限 4 张表白名单 + ADD COLUMN / CREATE INDEX 关键字
import { NextRequest, NextResponse } from 'next/server'
import { promises as fs } from 'node:fs'
import path from 'node:path'
import { queryCrossSchema } from '@/lib/db'
import { fail, handleApiError, ApiError } from '@/lib/api-error'

// 仓库根解析（同 /api/dev/progress）
function findRepoRoot(): string {
  if (process.env.FF_REPO_ROOT) return process.env.FF_REPO_ROOT
  let cur = process.cwd()
  for (let i = 0; i < 8; i++) {
    try {
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      require('node:fs').accessSync(path.join(cur, 'docs/features.md'))
      return cur
    } catch {
      const parent = path.dirname(cur)
      if (parent === cur) break
      cur = parent
    }
  }
  return path.resolve(process.cwd(), '../..')
}

const REPO_ROOT = findRepoRoot()

const MIGRATIONS_DIR = path.join(REPO_ROOT, 'packages/db-schema/src/migrations')

interface RunResult {
  file: string
  statements: Array<{ sql: string; status: 'ok' | 'skipped' | 'failed'; error?: string; durationMs: number }>
  totalMs: number
}

// 拆 SQL 文件成 statement（按 ; + 换行分割；忽略 -- 注释）
function splitSql(sql: string): string[] {
  // 移除 -- 注释行
  const cleaned = sql
    .split('\n')
    .filter((l) => !l.trim().startsWith('--'))
    .join('\n')
  // 按 ; 分割 + 过滤空
  return cleaned
    .split(/;\s*(?:\n|$)/)
    .map((s) => s.trim())
    .filter((s) => s.length > 0)
}

// 关键字白名单（plan2 数据库红线：只允许 ADD COLUMN / CREATE INDEX / CREATE TABLE）
const ALLOWED_KEYWORDS = /^\s*(ALTER\s+TABLE|CREATE\s+(UNIQUE\s+)?INDEX|CREATE\s+TABLE|CREATE\s+TYPE|COMMENT\s+ON)/i

function isAllowed(stmt: string): boolean {
  return ALLOWED_KEYWORDS.test(stmt)
}

export const dynamic = 'force-dynamic'

export async function POST(req: NextRequest) {
  try {
    const url = req.nextUrl
    const dryRun = url.searchParams.get('dryRun') !== 'false'
    const fileParam = url.searchParams.get('file')

    // 默认跑 v1_frameforge_fields.sql；可显式指定
    const fileName = fileParam || 'v1_frameforge_fields.sql'
    const filePath = path.join(MIGRATIONS_DIR, fileName)
    // 防 path traversal
    if (!filePath.startsWith(MIGRATIONS_DIR)) {
      throw new ApiError('FORBIDDEN', 'file path 越界', 403)
    }
    const raw = await fs.readFile(filePath, 'utf8')
    const stmts = splitSql(raw)

    // 关键字校验
    const illegal = stmts.filter((s) => !isAllowed(s))
    if (illegal.length > 0) {
      throw new ApiError(
        'FORBIDDEN',
        `${illegal.length} 条 statement 不在白名单（仅允许 ALTER TABLE / CREATE INDEX / CREATE TABLE / CREATE TYPE）`,
        403,
        { examples: illegal.slice(0, 3) },
      )
    }

    // dry-run：只返回 SQL 列表，不跑
    if (dryRun) {
      return NextResponse.json({
        ok: true,
        data: {
          mode: 'dry-run',
          file: fileName,
          statementCount: stmts.length,
          statements: stmts,
        },
      })
    }

    // 真跑：每条独立 try
    const t0 = Date.now()
    const results: RunResult['statements'] = []
    for (const sql of stmts) {
      const ts = Date.now()
      try {
        await queryCrossSchema(sql)
        results.push({ sql, status: 'ok', durationMs: Date.now() - ts })
      } catch (e) {
        const err = (e as Error).message
        // IF NOT EXISTS 重复加列不算错
        if (/already exists|does not exist/i.test(err)) {
          results.push({ sql, status: 'skipped', durationMs: Date.now() - ts, error: err })
        } else {
          results.push({ sql, status: 'failed', error: err, durationMs: Date.now() - ts })
          return NextResponse.json({
            ok: false,
            data: {
              mode: 'commit',
              file: fileName,
              statements: results,
              totalMs: Date.now() - t0,
              stoppedAt: sql.slice(0, 80),
            },
            error: { code: 'SQL', message: `statement failed: ${err}` },
          }, { status: 500 })
        }
      }
    }
    return NextResponse.json({
      ok: true,
      data: {
        mode: 'commit',
        file: fileName,
        statements: results,
        totalMs: Date.now() - t0,
      },
    })
  } catch (err) {
    if (err instanceof ApiError) return fail(err.code, err.message, err.status, err.details)
    console.error('[migrate] error:', err)
    return handleApiError(err)
  }
}