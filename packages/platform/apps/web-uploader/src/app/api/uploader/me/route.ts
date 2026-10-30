// /api/uploader/me — 录制员端身份
// dev 模式：读 cookie `ff_dev_recorder` 或 header `x-dev-recorder`
// 生产模式：Clerk webhook 同步 ff_users（plan2 §5）后，前端用 Clerk 拿 userId
import { NextRequest, NextResponse } from 'next/server'
import { z } from 'zod'
import { queryCrossSchema } from '@/lib/db'
import { fail, handleApiError, ApiError } from '@/lib/api-error'

const PostBody = z.object({ recorderId: z.string().min(1).max(100) })

function parseCookieRecorder(req: NextRequest): string | null {
  const cookieHeader = req.headers.get('cookie') ?? ''
  for (const part of cookieHeader.split(';')) {
    const [k, v] = part.trim().split('=')
    if (k === 'ff_dev_recorder' && v) return decodeURIComponent(v)
  }
  return req.headers.get('x-dev-recorder')
}

export const dynamic = 'force-dynamic'

export async function GET(req: NextRequest) {
  try {
    const recorderId = parseCookieRecorder(req)
    if (!recorderId) {
      return NextResponse.json({
        ok: true,
        data: { signedIn: false, recorderId: null, message: '未登录' },
      })
    }
    const cs = await queryCrossSchema<{ id: string; name: string; phone: string | null; operator_job: string | null }>(
      `SELECT id, name, phone, operator_job FROM public.recorders WHERE id = $1 LIMIT 1`,
      [recorderId],
    )
    return NextResponse.json({
      ok: true,
      data: {
        signedIn: true,
        recorderId,
        recorder: cs[0] ?? null,
      },
    })
  } catch (err) {
    console.error('[uploader/me GET] error:', err)
    return handleApiError(err)
  }
}

export async function POST(req: NextRequest) {
  try {
    const json = await req.json().catch(() => null)
    const parsed = PostBody.safeParse(json)
    if (!parsed.success) throw new ApiError('VALIDATION', 'invalid body', 422, parsed.error.flatten())

    const cs = await queryCrossSchema<{ id: string; name: string }>(
      `SELECT id, name FROM public.recorders WHERE id = $1 LIMIT 1`,
      [parsed.data.recorderId],
    )
    if (cs.length === 0) {
      throw new ApiError('FORBIDDEN', `recorder_id "${parsed.data.recorderId}" 不存在，请先在 /admin/tables 登记`, 422)
    }

    return NextResponse.json({
      ok: true,
      data: {
        recorderId: cs[0]!.id,
        recorderName: cs[0]!.name,
        devMode: true,
        message: 'dev 模式：已设置 ff_dev_recorder cookie（生产模式待 Clerk 接入）',
      },
    })
  } catch (err) {
    if (err instanceof ApiError) return fail(err.code, err.message, err.status, err.details)
    console.error('[uploader/me POST] error:', err)
    return handleApiError(err)
  }
}