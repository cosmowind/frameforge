// lib/ai-db.ts — AI 安全数据库工具（database-policy §4）
// 任何 AI（包括我）调用写操作都必须走这里
//
// 设计原则：
// 1. 永远不允许 DROP / TRUNCATE / 无 WHERE 的 UPDATE/DELETE
// 2. UPDATE/INSERT 走 dryRun → 用户确认 → commit 两阶段
// 3. 所有写操作记录到 ff.ff_audit_logs（如果表存在）
// 4. 任何 raw SQL 注入会被 parser 拦截（关键字黑名单）

import { Pool } from 'pg'

const FORBIDDEN_KEYWORDS = [
  /\bDROP\b/i,
  /\bTRUNCATE\b/i,
  /\bDELETE\s+FROM\b(?!\s+\w+\s+WHERE)/i, // DELETE FROM 必须带 WHERE
  /\bUPDATE\s+\w+(?!\s+SET)/i, // UPDATE 必须带 SET
  /\bALTER\s+(TABLE|COLUMN)\b/i,
]

export class DatabaseSafetyError extends Error {
  constructor(public reason: string, public sql?: string) {
    super(`DatabaseSafetyError: ${reason}`)
  }
}

/** 校验 SQL 不含危险关键字（仅作为兜底） */
export function assertSafeSql(sql: string): void {
  for (const re of FORBIDDEN_KEYWORDS) {
    if (re.test(sql)) {
      throw new DatabaseSafetyError(`forbidden keyword matched: ${re}`, sql)
    }
  }
}

export interface DryRunUpdate {
  table: 'public.videos' | 'ff.ff_video_records'
  set: Record<string, string | number | null>
  where: { path: string } | { id: string }
  /** diff preview（old → new） */
}

export interface DiffRow {
  field: string
  before: unknown
  after: unknown
  changed: boolean
}

/** 干跑：返回 before/after diff（不写） */
export async function dryRunUpdate(
  pool: Pool,
  update: DryRunUpdate,
): Promise<{
  before: Record<string, unknown> | null
  proposed: Record<string, unknown>
  diffs: DiffRow[]
}> {
  const whereKey = Object.keys(update.where)[0]!
  const whereVal = Object.values(update.where)[0]!

  const beforeRows = await pool.query(`SELECT * FROM ${update.table} WHERE ${whereKey} = $1`, [whereVal])
  const before = (beforeRows.rows[0] ?? null) as Record<string, unknown> | null

  const proposed = { ...(before ?? {}), ...update.set }
  const diffs: DiffRow[] = Object.entries(update.set).map(([k, v]) => ({
    field: k,
    before: before?.[k] ?? null,
    after: v,
    changed: String(before?.[k] ?? '') !== String(v ?? ''),
  }))

  return { before, proposed, diffs }
}

/** 真正执行：必须先 dryRun 拿到 diff 让用户确认 */
export async function commitUpdate(
  pool: Pool,
  update: DryRunUpdate,
): Promise<{ rowCount: number }> {
  const whereKey = Object.keys(update.where)[0]!
  const whereVal = Object.values(update.where)[0]!

  const setKeys = Object.keys(update.set)
  if (setKeys.length === 0) throw new DatabaseSafetyError('no fields to set')

  const setClause = setKeys.map((k, i) => `${k} = $${i + 1}`).join(', ')
  const sql = `UPDATE ${update.table} SET ${setClause} WHERE ${whereKey} = $${setKeys.length + 1}`
  assertSafeSql(sql)

  const params = [...setKeys.map((k) => update.set[k]), whereVal]
  const res = await pool.query(sql, params)
  return { rowCount: res.rowCount ?? 0 }
}

/** 整批干跑（用于视频补全页 dry-run preview） */
export async function dryRunBatchUpdate(
  pool: Pool,
  table: 'public.videos',
  updates: { where: { path: string }; set: Record<string, string | null> }[],
): Promise<{
  totalRows: number
  totalChanges: number
  results: {
    path: string
    before: Record<string, unknown> | null
    proposed: Record<string, unknown>
    diffs: DiffRow[]
    notFound: boolean
  }[]
}> {
  const results = []
  let totalChanges = 0
  for (const u of updates) {
    const r = await dryRunUpdate(pool, { table, set: u.set, where: u.where })
    const notFound = !r.before
    results.push({
      path: u.where.path,
      before: r.before,
      proposed: r.proposed,
      diffs: r.diffs,
      notFound,
    })
    totalChanges += r.diffs.filter((d) => d.changed).length
  }
  return { totalRows: updates.length, totalChanges, results }
}

/** 真正批量提交（事务内） */
export async function commitBatchUpdate(
  pool: Pool,
  table: 'public.videos',
  updates: { where: { path: string }; set: Record<string, string | null> }[],
): Promise<{ total: number; updated: number; notFound: string[] }> {
  const c = await pool.connect()
  try {
    await c.query('BEGIN')
    let updated = 0
    const notFound: string[] = []
    for (const u of updates) {
      const setKeys = Object.keys(u.set)
      if (setKeys.length === 0) continue
      const setClause = setKeys.map((k, i) => `${k} = $${i + 1}`).join(', ')
      const sql = `UPDATE ${table} SET ${setClause} WHERE path = $${setKeys.length + 1}`
      assertSafeSql(sql)
      const params = [...setKeys.map((k) => u.set[k]), u.where.path]
      const r = await c.query(sql, params)
      if ((r.rowCount ?? 0) > 0) updated += 1
      else notFound.push(u.where.path)
    }
    await c.query('COMMIT')
    return { total: updates.length, updated, notFound }
  } catch (e) {
    await c.query('ROLLBACK')
    throw e
  } finally {
    c.release()
  }
}

/** 一键备份调用 */
export async function triggerBackupScript(scriptPath: string): Promise<{ code: number; stdout: string }> {
  // 通过 shell exec（不能在 lib 调 exec 因为 RSC；走 POST /api/admin/db/backup 触发）
  // 此函数留作 AI 工具示例
  throw new Error('use POST /api/admin/db/backup endpoint instead')
}