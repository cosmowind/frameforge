// /admin/tables — 4 表浏览器（videos / tasks / recorders / environments）
// 数据源：public.*（业务真相）；只读，不写。
// 配置 + 排序 + 列显存在客户端 useState；URL 不持久（避免分享 URL 攻击面）
import { queryCrossSchema } from '@/lib/db'
import { TABLES, TABLE_KEYS, type TableKey } from '@/lib/table-config'
import AdminTablesClient from './AdminTablesClient'

export const dynamic = 'force-dynamic'

interface ColMeta {
  table_name: string
  column_name: string
  data_type: string
  is_nullable: 'YES' | 'NO'
  column_default: string | null
  ordinal_position: number
}

async function loadSchema() {
  const rows = await queryCrossSchema<ColMeta>(
    `SELECT table_name, column_name, data_type, is_nullable, column_default, ordinal_position
     FROM information_schema.columns
     WHERE table_schema = 'public'
       AND table_name = ANY($1)
     ORDER BY table_name, ordinal_position`,
    [TABLE_KEYS],
  )
  const grouped: Record<TableKey, ColMeta[]> = {
    videos: [],
    tasks: [],
    recorders: [],
    environments: [],
  }
  for (const r of rows) {
    const k = r.table_name as TableKey
    if (k in grouped) grouped[k].push(r)
  }
  return TABLE_KEYS.map((k) => ({
    ...TABLES[k],
    columns: grouped[k],
  }))
}

export default async function AdminTablesPage() {
  let tables: Awaited<ReturnType<typeof loadSchema>> = []
  let err: string | null = null
  try {
    tables = await loadSchema()
  } catch (e) {
    err = (e as Error).message
  }
  if (err) {
    return (
      <div className="p-6">
        <div className="rounded border border-red-200 bg-red-50 p-4 text-red-800">
          加载表结构失败：{err}
        </div>
      </div>
    )
  }
  return <AdminTablesClient initial={{ tables }} />
}
