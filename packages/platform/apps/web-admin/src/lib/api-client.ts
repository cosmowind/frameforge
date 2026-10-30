// 共享 fetch client（仅 admin 后端使用，dev 模式无 Clerk 不带 token）
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

export interface ApiOk<T> {
  ok: true
  data: T
}
export interface ApiErr {
  ok: false
  error: { code: string; message: string }
}
export type ApiResponse<T> = ApiOk<T> | ApiErr