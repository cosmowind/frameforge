// POST /api/admin/tables/bulk
// 批量更新白名单表的行（默认 dry-run 预览；?commit=true 才真改）
// 安全：表白名单 + 字段白名单（每张表独立可写字段）+ WHERE pk = ANY($1)
// 只读 public.* —— 不写 public.videos 以外的字典表
import { NextRequest, NextResponse } from 'next/server'
import { z } from 'zod'
import { queryCrossSchema, pool } from '@/lib/db'
import { TABLES, TABLE_KEYS, type TableKey } from '@/lib/table-config'
import { fail, handleApiError, ApiError } from '@/lib/api-error'

const TableKeySchema = z.enum(TABLE_KEYS as [TableKey, ...TableKey[]])

// 每张表允许被批量改的字段（写权限白名单 — 防误改字典表的所有列）
const WRITABLE_FIELDS: Record<TableKey, string[]> = {
  // 业务表：可改关联字段 + 上传标志
  videos: ['recorder_id', 'task_id', 'env_id', 'uploaded'],
  // 字典表：不允许批量改（必须在专用 CRUD 页面编辑）
  tasks: [],
  recorders: [],
  environments: [],
}

const Body = z.object({
  table: TableKeySchema,
  pks: z.array(z.string().min(1).max(500)).min(1).max(500), // 单次最多 500 行
  updates: z.record(z.string(), z.union([z.string(), z.number(), z.boolean(), z.null()])).refine(
    (u) => Object.keys(u).length > 0 && Object.keys(u).length <= 10,
    'updates 字段数 1-10',
  ),
})

export const dynamic = 'force-dynamic'

export async function POST(req: NextRequest) {
  try {
    const url = req.nextUrl
    const commit = url.searchParams.get('commit') === 'true'

    const json = await req.json().catch(() => null)
    const parsed = Body.safeParse(json)
    if (!parsed.success) throw new ApiError('VALIDATION', 'invalid body', 422, parsed.error.flatten())

    const { table, pks, updates } = parsed.data
    const cfg = TABLES[table]

    // 字段白名单二次校验
    const allowedFields = WRITABLE_FIELDS[table]
    if (allowedFields.length === 0) {
      throw new ApiError('FORBIDDEN', `表 ${table} 不允许批量编辑（请用专用 CRUD 页面）`, 403)
    }
    const updateKeys = Object.keys(updates)
    const illegal = updateKeys.filter((k) => !allowedFields.includes(k))
    if (illegal.length > 0) {
      throw new ApiError(
        'FORBIDDEN',
        `字段 [${illegal.join(', ')}] 不在白名单 [${allowedFields.join(', ')}]`,
        403,
      )
    }

    // 真实列名校验（information_schema）
    const colRows = await queryCrossSchema<{ column_name: string }>(
      `SELECT column_name FROM information_schema.columns
       WHERE table_schema = 'public' AND table_name = $1`,
      [table],
    )
    const realCols = new Set(colRows.map((r) => r.column_name))
    for (const k of updateKeys) {
      if (!realCols.has(k)) {
        throw new ApiError('SCHEMA', `字段 ${k} 在表 ${table} 中不存在`, 422)
      }
    }
    if (!realCols.has(cfg.primaryKey)) {
      throw new ApiError('SCHEMA', `表 ${table} 缺主键 ${cfg.primaryKey}`, 500)
    }

    // 构造 SET 子句（白名单内列名 + 参数化值）
    const setClauses: string[] = []
    const params: unknown[] = []
    for (const [k, v] of Object.entries(updates)) {
      params.push(v)
      setClauses.push(`"${k}" = $${params.length}`)
    }

    // WHERE pk = ANY($N)
    params.push(pks)
    const pkParamIdx = params.length
    const whereSql = `"${cfg.primaryKey}" = ANY($${pkParamIdx}::text[])`

    // 预估受影响行数（SELECT count(*) WHERE pk IN ...）
    // 注意：params 必须和 SQL 占位符数量一致
    // 简化：countSql / sampleSql 用独立 $1::text[]，避免 SET 字段污染占位符编号
    const pkWhere = `"${cfg.primaryKey}" = ANY($1::text[])`
    const countSql = `SELECT count(*)::int AS n FROM ${cfg.physical} WHERE ${pkWhere}`
    const matched = await queryCrossSchema<{ n: number }>(countSql, [pks])
    const affected = matched[0]?.n ?? 0

    // dry-run：返回 SQL 预览 + 抽样 3 行 BEFORE
    if (!commit) {
      // 抽样 3 行 BEFORE（仅在 dry-run 模式取）
      const sampleWhere = `"${cfg.primaryKey}" = ANY($1::text[])`
      const sampleSql = `SELECT * FROM ${cfg.physical} WHERE ${sampleWhere} LIMIT 3`
      const sample = await queryCrossSchema<Record<string, unknown>>(sampleSql, [pks])
      const updateSql = `UPDATE ${cfg.physical} SET ${setClauses.join(', ')} WHERE ${whereSql}`
      return NextResponse.json({
        ok: true,
        data: {
          mode: 'dry-run',
          table,
          primaryKey: cfg.primaryKey,
          requestedPks: pks.length,
          affected,
          sampleBefore: sample,
          sql: updateSql,
          paramsCount: params.length,
        },
      })
    }

    // commit：真改
    if (affected === 0) {
      throw new ApiError('NO_MATCH', '没有任何主键匹配现有行', 404)
    }
    const updateSql = `UPDATE ${cfg.physical} SET ${setClauses.join(', ')} WHERE ${whereSql}`
    const result = await queryCrossSchema<{ count: number }>(updateSql, params)
    const changed = result.length > 0 ? Number(result[0]?.count ?? 0) : 0

    return NextResponse.json({
      ok: true,
      data: {
        mode: 'commit',
        table,
        primaryKey: cfg.primaryKey,
        requestedPks: pks.length,
        affected,
        changed,
      },
    })
  } catch (err) {
    if (err instanceof ApiError) return fail(err.code, err.message, err.status, err.details)
    console.error('[tables/bulk] error:', err)
    return handleApiError(err)
  }
}