// 备份触发（lib/backup.ts）
// 在 web-admin API 路由里调用：
//   POST /api/admin/db/backup → trigger()

import { spawn } from 'node:child_process'
import { promises as fs } from 'node:fs'
import path from 'node:path'
import { PATHS } from '@ff/shared/utils/paths'

const BACKUP_DIR = path.join(PATHS.RUNTIME, 'backups', 'manual')

async function ensureBackupDir(): Promise<string> {
  await fs.mkdir(BACKUP_DIR, { recursive: true })
  return BACKUP_DIR
}

export interface BackupResult {
  ok: boolean
  outDir: string
  files: { name: string; size: number }[]
  startedAt: string
  finishedAt: string
  durationMs: number
}

/** 触发完整备份（pg_dump 公共表 + ff schema + csv 导出） */
export async function triggerBackup(): Promise<BackupResult> {
  const startedAt = new Date()
  const outDir = await ensureBackupDir()
  const ts = formatTs(startedAt)

  // 调脚本
  await runShell('scripts/backup-videos.sh', [outDir])

  // 列出文件
  const files = await listBackups(outDir)

  const finishedAt = new Date()
  return {
    ok: true,
    outDir,
    files,
    startedAt: startedAt.toISOString(),
    finishedAt: finishedAt.toISOString(),
    durationMs: finishedAt.getTime() - startedAt.getTime(),
  }
}

/** 列出最近备份 */
export async function listBackups(dir: string = BACKUP_DIR, limit = 10): Promise<BackupResult['files']> {
  try {
    const entries = await fs.readdir(dir, { withFileTypes: true })
    const files = entries
      .filter((e) => e.isFile())
      .map(async (e) => {
        const stat = await fs.stat(path.join(dir, e.name))
        return { name: e.name, size: stat.size }
      })
    const resolved = await Promise.all(files)
    return resolved.sort((a, b) => b.name.localeCompare(a.name)).slice(0, limit)
  } catch {
    return []
  }
}

function formatTs(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`
}

function runShell(scriptRel: string, args: string[]): Promise<number> {
  return new Promise((resolve, reject) => {
    const cwd = process.cwd()
    const isWin = process.platform === 'win32'
    const cmd = isWin ? 'bash' : 'bash'
    const finalArgs = [scriptRel, ...args]
    const child = spawn(cmd, finalArgs, { cwd, stdio: 'inherit' })
    child.on('exit', (code) => (code === 0 ? resolve(code) : reject(new Error(`backup failed: ${code}`))))
    child.on('error', reject)
  })
}