// fetch 客户端（Phase 1 接 Clerk JWT，Phase 0 占位）
import { LOCALSTORAGE_KEYS } from '@ff/shared/constants'

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')
  if (init.body) headers.set('Content-Type', 'application/json')

  const res = await fetch(path, { ...init, headers })
  const data = (await res.json().catch(() => ({}))) as unknown
  if (!res.ok) {
    const err = data as { error?: { code: string; message: string } }
    throw new Error(err.error?.message ?? `HTTP ${res.status}`)
  }
  return data as T
}

export const UPLOADER_TOKEN_KEY = LOCALSTORAGE_KEYS.UPLOADER_TOKEN
