// web-uploader 共享 db 客户端（直连远端 PG，schema ff）
// DATABASE_URL 必须从环境变量注入；.env 不入仓
import { Pool } from 'pg'

const DATABASE_URL =
  process.env.DATABASE_URL ?? 'postgresql://user:password@localhost:5432/ff'
if (!DATABASE_URL || DATABASE_URL.includes('user:password')) {
  // dev 默认从 .env 注入；这里只是占位
}
const SCHEMA = process.env.DATABASE_SCHEMA ?? 'ff'

declare global {
  // eslint-disable-next-line no-var
  var __ff_uploader_pool__: Pool | undefined
}

export const pool: Pool =
  global.__ff_uploader_pool__ ??
  new Pool({
    connectionString: DATABASE_URL,
    options: `-c search_path=${SCHEMA}`,
    max: 10,
    idleTimeoutMillis: 30_000,
  })

if (process.env.NODE_ENV !== 'production') global.__ff_uploader_pool__ = pool

export async function query<T = Record<string, unknown>>(
  text: string,
  params: unknown[] = [],
): Promise<T[]> {
  const res = await pool.query(text, params as unknown[])
  return res.rows as T[]
}

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