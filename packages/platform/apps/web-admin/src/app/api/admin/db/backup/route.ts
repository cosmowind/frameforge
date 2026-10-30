// POST /api/admin/db/backup → 触发一次备份
import { triggerBackup } from '@/lib/backup'
import { handleApiError, ok } from '@/lib/api-error'

export async function POST() {
  try {
    const result = await triggerBackup()
    return ok(result)
  } catch (err) {
    return handleApiError(err)
  }
}