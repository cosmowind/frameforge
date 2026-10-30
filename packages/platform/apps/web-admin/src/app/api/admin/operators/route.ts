// /api/admin/operators — v2 ff_operators CRUD
// GET：拉全部 is_active=true（按用户要求：简单一次拉，前端过滤）
// POST：zod 解析 + business_key server-gen + dry-run（默认）→ ?dryRun=false 真写
// PATCH：?id=xxx + body 改写（is_active toggle / alias / name / hand_size）
// DELETE：?id=xxx 软删（is_active=false）
//   字段定义：docs/v2-forms-spec.md §1
//   zod schema：packages/shared/src/schemas/v2-forms.ts OperatorCreateSchema
import { NextRequest, NextResponse } from 'next/server'
import { z } from 'zod'
import { randomUUID } from 'node:crypto'
import { query } from '@/lib/db'
import { fail, handleApiError, ApiError } from '@/lib/api-error'
import { OperatorCreateSchema } from '@ff/shared/schemas'
import { HAND_OPTIONS, GENDER_OPTIONS, AGE_RANGE_OPTIONS } from '@ff/shared/constants/v2-options'

export const dynamic = 'force-dynamic'

interface OperatorRow {
  id: string
  business_key: string
  alias: string | null
  name: string | null
  hand: string | null
  hand_size_cm: number | null
  gender: string | null
  age_range: string | null
  job_role: string | null
  role_experience: string | null
  consented_to_recording: boolean
  is_active: boolean
  version: number
  created_at: string
  updated_at: string
}

// 业务键生成：op_<slug(alias)>_<8 hex>
function slug(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 24) || 'x'
}
function genBusinessKey(alias: string): string {
  const rand = randomUUID().replace(/-/g, '').slice(0, 8)
  return `op_${slug(alias)}_${rand}`
}

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

const PatchSchema = z
  .object({
    is_active: z.boolean().optional(),
    alias: z.string().min(1).max(64).optional(),
    name: z.string().min(1).max(64).optional(),
    hand: z.enum(HAND_OPTIONS).optional(),
    gender: z.enum(GENDER_OPTIONS).optional(),
    age_range: z.enum(AGE_RANGE_OPTIONS).optional(),
    job_role: z.string().min(1).max(64).optional(),
    role_experience: z.string().min(1).max(64).optional(),
    hand_size_cm: z.coerce.number().positive().max(50).optional(),
  })
  .strict()

export async function GET(req: NextRequest) {
  try {
    const showInactive = req.nextUrl.searchParams.get('includeInactive') === 'true'
    const sql = showInactive
      ? `SELECT * FROM ff_operators ORDER BY created_at DESC LIMIT 500`
      : `SELECT * FROM ff_operators WHERE is_active = true ORDER BY created_at DESC LIMIT 500`
    const rows = await query<OperatorRow>(sql)
    return NextResponse.json({ ok: true, data: { rows, total: rows.length } })
  } catch (err) {
    console.error('[operators GET]', err)
    return handleApiError(err)
  }
}

export async function POST(req: NextRequest) {
  try {
    const url = req.nextUrl
    const dryRun = url.searchParams.get('dryRun') !== 'false' // 默认 true

    // 1. 解析 body
    const body = (await req.json().catch(() => ({}))) as unknown
    const parsed = OperatorCreateSchema.safeParse(body)
    if (!parsed.success) {
      throw new ApiError('VALIDATION', 'zod 校验失败', 422, parsed.error.flatten())
    }
    const input = parsed.data

    // 2. 生成 business_key（查重 + 失败重试 3 次）
    let businessKey = genBusinessKey(input.alias)
    for (let i = 0; i < 3; i++) {
      const exists = await query<{ id: string }>(
        `SELECT id FROM ff_operators WHERE business_key = $1`,
        [businessKey],
      )
      if (exists.length === 0) break
      businessKey = genBusinessKey(input.alias)
    }

    // 3. 拼装 row（null 处理 N 类）
    const row = {
      business_key: businessKey,
      alias: input.alias,
      name: input.name,
      hand: input.hand,
      hand_size_cm: input.hand_size_cm ?? null,
      gender: input.gender,
      age_range: input.age_range,
      job_role: input.job_role,
      role_experience: input.role_experience,
      consented_to_recording: input.consented_to_recording,
    }

    // 4. SQL 预览（dry-run 用）
    const cols = Object.keys(row)
    const placeholders = cols.map((_, i) => `$${i + 1}`).join(', ')
    const values = cols.map((k) => (row as Record<string, unknown>)[k])
    const sqlPreview = `INSERT INTO "ff"."ff_operators" (${cols.map((c) => `"${c}"`).join(', ')}) VALUES (${placeholders}) RETURNING *`

    if (dryRun) {
      return NextResponse.json({
        ok: true,
        data: {
          mode: 'dry-run',
          business_key: businessKey,
          payload: row,
          sql_preview: sqlPreview,
          next: `?dryRun=false 真写；或前端点 Confirm 触发 commit`,
        },
      })
    }

    // 5. 真写
    const inserted = await query<OperatorRow>(
      `INSERT INTO ff_operators (${cols.map((c) => `"${c}"`).join(', ')})
       VALUES (${placeholders}) RETURNING *`,
      values,
    )
    const created = inserted[0]
    if (!created) {
      throw new ApiError('INTERNAL', 'insert returned no row', 500)
    }
    return NextResponse.json({
      ok: true,
      data: {
        mode: 'commit',
        business_key: businessKey,
        row: created,
      },
    })
  } catch (err) {
    if (err instanceof ApiError) return fail(err.code, err.message, err.status, err.details)
    console.error('[operators POST]', err)
    return handleApiError(err)
  }
}

// PATCH /api/admin/operators?id=xxx — 改写
export async function PATCH(req: NextRequest) {
  try {
    const id = req.nextUrl.searchParams.get('id')
    if (!id || !UUID_RE.test(id)) {
      throw new ApiError('VALIDATION', '缺少 ?id=xxx（须为 uuid）', 422)
    }
    const body = (await req.json().catch(() => ({}))) as unknown
    const parsed = PatchSchema.safeParse(body)
    if (!parsed.success) {
      throw new ApiError('VALIDATION', 'zod 校验失败', 422, parsed.error.flatten())
    }
    const patch = parsed.data
    if (Object.keys(patch).length === 0) {
      throw new ApiError('VALIDATION', 'patch 至少 1 个字段', 422)
    }

    // 拼 SET
    const sets: string[] = []
    const vals: unknown[] = []
    let i = 1
    for (const [k, v] of Object.entries(patch)) {
      sets.push(`"${k}" = $${i}`)
      vals.push(v)
      i++
    }
    sets.push(`"version" = "version" + 1`)
    sets.push(`"updated_at" = now()`)
    vals.push(id)
    const idIdx = i
    // is_active 不在 patch 里时默认更新 active 行
    const targetActive = patch.is_active === undefined ? true : patch.is_active
    vals.push(targetActive)

    const rows = await query<OperatorRow>(
      `UPDATE ff_operators SET ${sets.join(', ')}
       WHERE id = $${idIdx} AND is_active = $${idIdx + 1} RETURNING *`,
      vals,
    )
    if (rows.length === 0) {
      throw new ApiError('NOT_FOUND', `operator ${id} 不存在或 is_active=${!targetActive}`, 404)
    }
    return NextResponse.json({ ok: true, data: { row: rows[0] } })
  } catch (err) {
    if (err instanceof ApiError) return fail(err.code, err.message, err.status, err.details)
    console.error('[operators PATCH]', err)
    return handleApiError(err)
  }
}

// DELETE /api/admin/operators?id=xxx — 软删（is_active=false）
export async function DELETE(req: NextRequest) {
  try {
    const id = req.nextUrl.searchParams.get('id')
    if (!id || !UUID_RE.test(id)) {
      throw new ApiError('VALIDATION', '缺少 ?id=xxx（须为 uuid）', 422)
    }
    const rows = await query<OperatorRow>(
      `UPDATE ff_operators SET is_active = false, version = version + 1, updated_at = now()
       WHERE id = $1 AND is_active = true RETURNING id, is_active, version`,
      [id],
    )
    if (rows.length === 0) {
      throw new ApiError('NOT_FOUND', `operator ${id} 不存在或已下架`, 404)
    }
    return NextResponse.json({ ok: true, data: { row: rows[0] } })
  } catch (err) {
    if (err instanceof ApiError) return fail(err.code, err.message, err.status, err.details)
    console.error('[operators DELETE]', err)
    return handleApiError(err)
  }
}
