// POST /api/ai/db/query — 给 AI agent 用的安全 SELECT 端点
// body: { sql: string, params?: unknown[] }
// 拒绝：非 SELECT / 含 DROP / 含 ALTER / 含 TRUNCATE / 写操作
import type { NextRequest } from 'next/server'
import { Pool } from 'pg'
import { z } from 'zod'
import { ok, fail, ApiError, handleApiError } from '@/lib/api-error'

const Body = z.object({
  sql: z.string().min(1).max(10_000),
  params: z.array(z.unknown()).optional(),
})

const FORBIDDEN = [
  /\bDROP\b/i,
  /\bTRUNCATE\b/i,
  /\bDELETE\b/i,
  /\bUPDATE\b/i,
  /\bINSERT\b/i,
  /\bALTER\b/i,
  /\bCREATE\b/i,
  /\bGRANT\b/i,
  /\bREVOKE\b/i,
  /\bCOPY\b/i,
  /\bpg_read_server_files\b/i,
  /\bpg_write_server_files\b/i,
  /\blo_export\b/i,
  /\bdo\b/i,
]

function assertSelectOnly(sql: string) {
  const trimmed = sql.trim().replace(/;\s*$/, '')
  if (!/^(\s*)(--[^\n]*\n)*\s*SELECT\b/i.test(trimmed)) {
    throw new ApiError('NOT_SELECT', 'SQL 必须以 SELECT 开头', 400)
  }
  for (const re of FORBIDDEN) {
    if (re.test(trimmed)) {
      throw new ApiError('FORBIDDEN_KEYWORD', `SQL 含禁用关键字：${re}`, 400)
    }
  }
  // 拒绝多语句
  if (trimmed.includes(';')) throw new ApiError('MULTI_STMT', '不允许多语句', 400)
}

let _pool: Pool | null = null
function pool(): Pool {
  if (_pool) return _pool
  _pool = new Pool({
    connectionString: process.env.DATABASE_URL!,
    options: `-c search_path=${process.env.DATABASE_SCHEMA ?? 'ff'},public`,
    max: 5,
  })
  return _pool
}

export async function POST(req: NextRequest) {
  try {
    const json = await req.json()
    const parsed = Body.safeParse(json)
    if (!parsed.success) throw new ApiError('VALIDATION', 'invalid body', 422, parsed.error.flatten())
    assertSelectOnly(parsed.data.sql)
    const res = await pool().query(parsed.data.sql, (parsed.data.params ?? []) as unknown[])
    return ok({ rows: res.rows, rowCount: res.rowCount ?? 0 })
  } catch (err) {
    if (err instanceof ApiError) return fail(err.code, err.message, err.status, err.details)
    return handleApiError(err)
  }
}