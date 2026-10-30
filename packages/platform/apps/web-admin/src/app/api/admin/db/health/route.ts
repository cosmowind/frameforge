// GET /api/admin/db/health
// 返回 public.* 8 表行数 + 关键填充率 + 最近备份

import { queryCrossSchema } from '@/lib/db'
import { listBackups } from '@/lib/backup'
import { handleApiError, ok } from '@/lib/api-error'

export interface TableStats {
  table: string
  rows: number
  fill_rate?: Record<string, number> // recorder_id 等字段填充率
}

export interface DbHealth {
  tables: TableStats[]
  videos_unfilled: number
  videos_total: number
  recent_backups: { name: string; size: number }[]
  db_connected: boolean
}

export async function GET() {
  try {
    // PG 没 libxml，不能用 query_to_xml。直接查 8 张固定表
    const tableNames = [
      'videos',
      'video_batch_config',
      'videos_backup_focused',
      'tasks',
      'recorders',
      'environments',
      'sd_cards',
      'app_config',
    ]
    const tables = await Promise.all(
      tableNames.map(async (name) => {
        const r = await queryCrossSchema<{ n: string }>(
          `SELECT count(*)::int AS n FROM public.${name}`,
        )
        return { tablename: name, n: r[0]?.n ?? '0' }
      }),
    )

    const v = await queryCrossSchema<{
      total: string
      empty_recorder: string
      empty_task: string
      empty_env: string
      not_uploaded: string
    }>(
      `SELECT
         count(*) AS total,
         count(*) FILTER (WHERE recorder_id = '' OR recorder_id IS NULL) AS empty_recorder,
         count(*) FILTER (WHERE task_id = '' OR task_id IS NULL) AS empty_task,
         count(*) FILTER (WHERE env_id = '' OR env_id IS NULL) AS empty_env,
         count(*) FILTER (WHERE uploaded IS NULL OR uploaded != 'Yes') AS not_uploaded
       FROM public.videos`,
    )

    const vRow = v[0]!
    const total = Number(vRow.total)
    const backups = await listBackups()

    const videos: TableStats = {
      table: 'videos',
      rows: total,
      fill_rate: {
        recorder_id: 1 - Number(vRow.empty_recorder) / Math.max(total, 1),
        task_id: 1 - Number(vRow.empty_task) / Math.max(total, 1),
        env_id: 1 - Number(vRow.empty_env) / Math.max(total, 1),
        uploaded: 1 - Number(vRow.not_uploaded) / Math.max(total, 1),
      },
    }

    const others = tables
      .filter((t) => t.tablename !== 'videos')
      .map((t) => ({ table: t.tablename, rows: Number(t.n) }))

    const payload: DbHealth = {
      db_connected: true,
      tables: [videos, ...others].sort((a, b) => b.rows - a.rows),
      videos_total: total,
      videos_unfilled: Number(vRow.empty_recorder) + Number(vRow.empty_task) + Number(vRow.empty_env),
      recent_backups: backups,
    }
    return ok(payload)
  } catch (err) {
    return handleApiError(err)
  }
}