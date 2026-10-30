// GET /api/admin/tables/data?table=videos&limit=100&offset=0&sort=scan_date&order=desc&q=op3
// 白名单表 + 白名单列 + 参数化 LIMIT/OFFSET；杜绝 SQL 注入
import { NextRequest, NextResponse } from 'next/server'
import { z } from 'zod'
import { queryCrossSchema } from '@/lib/db'
import { TABLES, TABLE_KEYS, type TableKey } from '@/lib/table-config'
import { fail, handleApiError, ApiError } from '@/lib/api-error'

const TableKeySchema = z.enum(TABLE_KEYS as [TableKey, ...TableKey[]])
const OrderSchema = z.enum(['asc', 'desc'])

const Q = z.object({
  table: TableKeySchema,
  limit: z.coerce.number().int().min(1).max(500).default(100),
  offset: z.coerce.number().int().min(0).default(0),
  sort: z.string().min(1).max(64).optional(),
  order: OrderSchema.default('desc'),
  q: z.string().max(200).optional(),
})

export const dynamic = 'force-dynamic'

export async function GET(req: NextRequest) {
  try {
    const sp = req.nextUrl.searchParams
    const parsed = Q.safeParse({
      table: sp.get('table') ?? undefined,
      limit: sp.get('limit') ?? undefined,
      offset: sp.get('offset') ?? undefined,
      sort: sp.get('sort') ?? undefined,
      order: sp.get('order') ?? undefined,
      q: sp.get('q') ?? undefined,
    })
    if (!parsed.success) throw new ApiError('VALIDATION', 'invalid query', 422, parsed.error.flatten())
    const { table, limit, offset, order } = parsed.data
    const cfg = TABLES[table]

    // 白名单列名（用表实际列，避免 order by 注入）
    const allColRows = await queryCrossSchema<{ column_name: string }>(
      `SELECT column_name FROM information_schema.columns
       WHERE table_schema = 'public' AND table_name = $1
       ORDER BY ordinal_position`,
      [table],
    )
    const allowedCols = new Set(allColRows.map((r) => r.column_name))
    if (!allowedCols.has(cfg.primaryKey)) {
      throw new ApiError('SCHEMA', `table ${table} missing pk ${cfg.primaryKey}`, 500)
    }

    const sortCol = parsed.data.sort && allowedCols.has(parsed.data.sort) ? parsed.data.sort : cfg.defaultSort.col
    // 必须白名单列 + 必须不是 ORDER BY 注入；column name 来自白名单，安全
    const sortExpr = `"${sortCol}"`

    // q：跨所有列 ILIKE（timestamp / numeric 等先 ::text 强转）
    const allCols = allColRows.map((r) => r.column_name)
    const q = parsed.data.q?.trim()
    const where: string[] = []
    const params: unknown[] = []
    if (q && q.length > 0) {
      const ors: string[] = []
      for (const c of allCols) {
        params.push(`%${q}%`)
        ors.push(`"${c}"::text ILIKE $${params.length}`)
      }
      where.push(`(${ors.join(' OR ')})`)
    }
    const whereSql = where.length > 0 ? `WHERE ${where.join(' AND ')}` : ''

    // COUNT(*) 一次（让前端知道总数/分页）
    const countSql = `SELECT count(*)::bigint AS n FROM ${cfg.physical} ${whereSql}`
    const countRows = await queryCrossSchema<{ n: string }>(countSql, params)
    const total = Number(countRows[0]?.n ?? 0)

    params.push(limit)
    const limitIdx = params.length
    params.push(offset)
    const offsetIdx = params.length
    const dataSql = `SELECT * FROM ${cfg.physical} ${whereSql}
                     ORDER BY ${sortExpr} ${order === 'asc' ? 'ASC' : 'DESC'}
                     LIMIT $${limitIdx} OFFSET $${offsetIdx}`
    const rows = await queryCrossSchema<Record<string, unknown>>(dataSql, params)

    return NextResponse.json({
      ok: true,
      data: {
        table,
        primaryKey: cfg.primaryKey,
        rows,
        total,
        limit,
        offset,
        sort: sortCol,
        order,
      },
    })
  } catch (err) {
    if (err instanceof ApiError) return fail(err.code, err.message, err.status, err.details)
    console.error('[tables/data] error:', err)
    return handleApiError(err)
  }
}
