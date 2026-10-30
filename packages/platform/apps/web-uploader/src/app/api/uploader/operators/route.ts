// POST /api/uploader/operators — v2-forms-spec §1 快速新建操作员
// 占位阶段：501 not implemented；下一步会 zod min(1) + dry-run → commit
import { fail } from '@/lib/api-error'

export const dynamic = 'force-dynamic'

export async function POST() {
  return fail('NOT_IMPLEMENTED', 'POST /api/uploader/operators 占位：v2-forms-spec §1 写入未实现', 501, {
    next: 'zod min(1) on alias/name/hand/gender/age_range/job_role/role_experience + consented_to_recording=true',
    spec: 'docs/v2-forms-spec.md §1.3',
  })
}
