// /admin/progress — 实时开发进度仪表盘
// 服务端组件：拉 /api/dev/progress，30s 自动刷新（客户端组件做）
import ProgressClient from './ProgressClient'

export const dynamic = 'force-dynamic'

export default function AdminProgressPage() {
  return <ProgressClient />
}