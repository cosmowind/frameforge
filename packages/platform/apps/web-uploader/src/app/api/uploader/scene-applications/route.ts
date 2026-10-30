// POST /api/uploader/scene-applications — v2-forms-spec §4 快速申请新 scene
// 占位阶段：501 not implemented；下一步会 zod min(1) + dry-run → commit
import { fail } from '@/lib/api-error'

export const dynamic = 'force-dynamic'

export async function POST() {
  return fail(
    'NOT_IMPLEMENTED',
    'POST /api/uploader/scene-applications 占位：v2-forms-spec §4 写入未实现',
    501,
    {
      next: 'zod min(1) on alias/env_l1/venue_l2/scene_l3 → 写 application_status=draft',
      spec: 'docs/v2-forms-spec.md §4.2',
    },
  )
}
