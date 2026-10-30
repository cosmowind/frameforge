// 单脚本 --stage up|down|status（L1 防 v1→v8 爆炸）
// Phase 0 模式：直接执行手写 SQL migration（11 个 enum + 15 张表）
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import pg from 'pg'
import { logger } from '@ff/shared/utils/logger'

const SCHEMA = process.env.DATABASE_SCHEMA ?? 'ff'

function parseStage(): string {
  const idx = process.argv.indexOf('--stage')
  if (idx === -1) return 'up'
  return process.argv[idx + 1] ?? 'up'
}

function findUpSql(): string {
  const here = fileURLToPath(import.meta.url)
  const fromUrl = new URL('./migrations/v0_initial_v2.sql', import.meta.url)
  const candidates = [fileURLToPath(fromUrl), join(here, '..', 'migrations', 'v0_initial_v2.sql')]
  for (const p of candidates) {
    try {
      return readFileSync(p, 'utf8')
    } catch {
      /* continue */
    }
  }
  throw new Error('no migration file found; expected packages/db-schema/src/migrations/v0_initial_v2.sql')
}

async function runUp(): Promise<void> {
  const sql = findUpSql()
  logger.info({ schema: SCHEMA, bytes: sql.length }, 'migrate up starting')

  const client = new pg.Client({
    connectionString: process.env.DATABASE_URL,
    options: `-c search_path=${SCHEMA}`,
  })
  await client.connect()

  await client.query(`CREATE SCHEMA IF NOT EXISTS "${SCHEMA}"`)
  await client.query(sql)

  const tables = await client.query(
    `SELECT count(*)::int AS n FROM pg_tables WHERE schemaname = $1`,
    [SCHEMA],
  )
  const enums = await client.query(
    `SELECT count(*)::int AS n FROM pg_type t JOIN pg_namespace n ON t.typnamespace=n.oid WHERE n.nspname=$1 AND typtype='e'`,
    [SCHEMA],
  )
  logger.info({ tables: tables.rows[0].n, enums: enums.rows[0].n }, 'migrate up verified')

  await client.end()
}

async function runStatus(): Promise<void> {
  const client = new pg.Client({ connectionString: process.env.DATABASE_URL })
  await client.connect()
  const r = await client.query(
    `SELECT tablename FROM pg_tables WHERE schemaname = $1 ORDER BY 1`,
    [SCHEMA],
  )
  // eslint-disable-next-line no-console
  console.log(`schema=${SCHEMA} tables=${r.rows.length}`)
  r.rows.forEach((row) => console.log(`  - ${row.tablename}`))
  await client.end()
}

async function main(): Promise<void> {
  const stage = parseStage()
  if (stage === 'up') await runUp()
  else if (stage === 'status') await runStatus()
  else if (stage === 'down') {
    logger.warn({ stage }, 'down 不实现；手动 DROP SCHEMA ff CASCADE 再重跑 up')
  } else {
    logger.error({ stage }, 'unknown stage; use up|down|status')
    process.exit(2)
  }
}

void main().catch((err) => {
  logger.error({ err }, 'migrate failed')
  process.exit(1)
})
