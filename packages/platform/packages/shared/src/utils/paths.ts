// 运行时路径常量（apps/backend, apps/web-uploader, apps/web-admin, apps/worker, packages/* 都可引用）
import path from 'node:path'

const RUNTIME_DIR = path.resolve(process.cwd(), 'runtime')

export const PATHS = {
  ROOT: process.cwd(),
  RUNTIME: RUNTIME_DIR,
  UPLOADS: path.join(RUNTIME_DIR, 'uploads'),
  BACKUPS: path.join(RUNTIME_DIR, 'backups'),
  LOGS: path.join(RUNTIME_DIR, 'logs'),
  CACHE: path.join(RUNTIME_DIR, 'cache'),
  DEBUG: path.join(RUNTIME_DIR, 'debug'),
  PULL: process.env.PULLER_LOCAL_ROOT ?? path.join(RUNTIME_DIR, 'pull'),
} as const

// P3 路径归一化
export function normalizePath(input: string): string {
  if (typeof input !== 'string' || input.length === 0) {
    throw new Error('path must be a non-empty string')
  }
  const replaced = input.replace(/\\/g, '/')
  if (replaced.includes('..')) {
    throw new Error(`path must not contain '..': ${input}`)
  }
  return path.posix.resolve(replaced)
}

/** 让相对路径在 Next.js server runtime 中能正确解析（不论 cwd） */
export function runtimePath(...parts: string[]): string {
  return path.resolve(process.cwd(), ...parts)
}
