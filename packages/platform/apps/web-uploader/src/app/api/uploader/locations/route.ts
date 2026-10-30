// POST /api/uploader/locations — v2-forms-spec §2 快速新建场所
// 占位阶段：501 not implemented；下一步会 zod min(1) + dry-run → commit
import { fail } from '@/lib/api-error'

export const dynamic = 'force-dynamic'

export async function POST() {
  return fail('NOT_IMPLEMENTED', 'POST /api/uploader/locations 占位：v2-forms-spec §2 写入未实现', 501, {
    next: 'zod min(1) on alias/env_l1/venue_l2/business_name/business_type/address_line1/city/region_state/zip_postal',
    spec: 'docs/v2-forms-spec.md §2.3',
  })
}
