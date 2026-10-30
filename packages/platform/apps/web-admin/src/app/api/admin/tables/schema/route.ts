// GET /api/admin/tables/schema
// 返回 4 张白名单表的列元信息（列名 / 类型 / 可空 / 默认值）
// 数据源：information_schema.columns（只读），白名单表名
import { NextResponse } from 'next/server'
import { queryCrossSchema } from '@/lib/db'
import { TABLES, TABLE_KEYS, type TableKey } from '@/lib/table-config'

interface ColMeta {
  table_name: string
  column_name: string
  data_type: string
  is_nullable: 'YES' | 'NO'
  column_default: string | null
  ordinal_position: number
}

export const dynamic = 'force-dynamic'

export async function GET() {
  // 走参数化查询；表名是白名单常量 TABLE_KEYS（前端不会传入）
  const rows = await queryCrossSchema<ColMeta>(
    `SELECT table_name, column_name, data_type, is_nullable, column_default, ordinal_position
     FROM information_schema.columns
     WHERE table_schema = 'public'
       AND table_name = ANY($1)
     ORDER BY table_name, ordinal_position`,
    [TABLE_KEYS],
  )

  // 按表分组
  const grouped: Record<TableKey, Array<Omit<ColMeta, 'table_name'>>> = {
    videos: [],
    tasks: [],
    recorders: [],
    environments: [],
  }
  for (const r of rows) {
    const key = r.table_name as TableKey
    if (key in grouped) {
      const { table_name, ...rest } = r
      void table_name
      grouped[key].push(rest)
    }
  }

  return NextResponse.json({
    ok: true,
    data: {
      tables: TABLE_KEYS.map((k) => ({
        ...TABLES[k],
        columns: grouped[k],
      })),
    },
  })
}
