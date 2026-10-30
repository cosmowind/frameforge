// 统一 API 响应（防 E14）
import { NextResponse } from 'next/server'

export function ok<T>(data: T, init?: ResponseInit) {
  return NextResponse.json({ ok: true, data }, init)
}

export function fail(code: string, message: string, status = 400, details?: Record<string, unknown>) {
  return NextResponse.json(
    {
      ok: false,
      error: { code, message, details },
    },
    { status },
  )
}

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number = 400,
    public details?: Record<string, unknown>,
  ) {
    super(message)
  }
}

export function handleApiError(err: unknown) {
  if (err instanceof ApiError) {
    return fail(err.code, err.message, err.status, err.details)
  }
  console.error('[api] unhandled', err)
  return fail('INTERNAL', 'internal server error', 500)
}