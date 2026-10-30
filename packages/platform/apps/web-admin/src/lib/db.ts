// web-admin 共享 db 客户端（直连远端 PG，schema ff）
// DATABASE_URL 必须从环境变量注入；.env 不入仓
import { Pool } from 'pg'

const DATABASE_URL = process.env.DATABASE_URL
// `next build` evaluates route modules, so a missing DATABASE_URL must not
// fail the build -- only actual requests should.
const isBuildPhase = process.env.NEXT_PHASE === 'phase-production-build'
if (!DATABASE_URL && !isBuildPhase) {
  throw new Error('DATABASE_URL is required (set in apps/web-admin/.env)')
}
const SCHEMA = process.env.DATABASE_SCHEMA ?? 'ff'

// 全局缓存（Next.js dev 模式热重载友好）
declare global {
  // eslint-disable-next-line no-var
  var __ff_admin_pool__: Pool | undefined
}

export const pool: Pool =
  global.__ff_admin_pool__ ??
  new Pool({
    connectionString: DATABASE_URL,
    options: `-c search_path=${SCHEMA} -c client_encoding=UTF8`,
    max: 10,
    idleTimeoutMillis: 30_000,
  })

if (process.env.NODE_ENV !== 'production') global.__ff_admin_pool__ = pool

/** 跑 raw SQL（带参数），返回 row 数组 */
export async function query<T = Record<string, unknown>>(
  text: string,
  params: unknown[] = [],
): Promise<T[]> {
  const res = await pool.query(text, params as unknown[])
  return res.rows as T[]
}

/** 跑 SQL 但允许跨 schema（如查 public.videos）—— 不设 search_path */
export async function queryCrossSchema<T = Record<string, unknown>>(
  text: string,
  params: unknown[] = [],
): Promise<T[]> {
  const c = await pool.connect()
  try {
    await c.query(`SET search_path TO ${SCHEMA}, public`)
    const res = await c.query(text, params as unknown[])
    return res.rows as T[]
  } finally {
    c.release()
  }
}

export const SCHEMA_NAME = SCHEMA