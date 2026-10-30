// FrameForge schema 隔离：与旧 public.* 完全独立
// 数据库内物理命名：ff.ff_video_records（schema + ff_ 前缀）
import { pgSchema } from 'drizzle-orm/pg-core'

export const SCHEMA_NAME = process.env.DATABASE_SCHEMA ?? 'ff'
export const vumSchema = pgSchema(SCHEMA_NAME)
