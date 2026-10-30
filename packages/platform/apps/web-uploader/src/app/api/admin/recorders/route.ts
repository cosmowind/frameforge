// GET /api/admin/recorders — 列所有 recorder (供 fill 页面下拉用)
// GET /api/admin/tasks
// GET /api/admin/environments

import { queryCrossSchema } from '@/lib/db'
import { handleApiError, ok } from '@/lib/api-error'

export async function GET() {
  try {
    const [recorders, tasks, environments] = await Promise.all([
      queryCrossSchema<{ id: string; name: string | null; operator_job: string | null }>(
        `SELECT id, name, operator_job FROM public.recorders ORDER BY id`,
      ),
      queryCrossSchema<{
        task_id: string
        product: string | null
        task: string | null
        process: string | null
        difficulty: string | null
      }>(
        `SELECT task_id, product, task, process, difficulty FROM public.tasks ORDER BY task_id`,
      ),
      queryCrossSchema<{
        env_id: string
        scene: string | null
        location_address: string | null
        environment: string | null
      }>(
        `SELECT env_id, scene, location_address, environment FROM public.environments ORDER BY env_id`,
      ),
    ])
    return ok({ recorders, tasks, environments })
  } catch (err) {
    return handleApiError(err)
  }
}