// Worker 启动校验（fail-fast 防 E11）
import 'dotenv/config'
import { z } from 'zod'

const EnvSchema = z.object({
  NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
  WORKER_PORT: z.coerce.number().int().positive().default(3010),

  // 数据库（ff schema）
  DATABASE_URL: z.string().url(),
  DATABASE_SCHEMA: z.string().default('ff'),

  // Redis (BullMQ)
  REDIS_URL: z.string().url(),
  BULLMQ_PREFIX: z.string().default('ff'),

  // 腾讯云 COS
  COS_REGION: z.string().optional(),
  COS_BUCKET: z.string().optional(),
  COS_SECRET_ID: z.string().optional(),
  COS_SECRET_KEY: z.string().optional(),
  COS_TEMP_KEY_DURATION_SEC: z.coerce.number().int().default(3600),

  // ffmpeg
  FFMPEG_PATH: z.string().default('/usr/bin/ffmpeg'),

  // 设备 decoder（私有格式）
  HMD_DECODER_PATH: z.string().optional(),
  MCAP_EXTRACTOR_PATH: z.string().optional(),

  // Puller（L2 本地硬盘）
  PULLER_LOCAL_ROOT: z.string().optional(),
  PULLER_BANDWIDTH_MBPS: z.coerce.number().int().default(20),

  // 夸克网盘 L3
  QUARK_REMOTE_DIR: z.string().optional(),
  QUARK_RCLONE_BWLIMIT: z.string().default('10M'),

  // Worker 并发
  WORKER_DEVICE_SCAN_CONCURRENCY: z.coerce.number().int().min(1).default(4),
  WORKER_PREVIEW_CONCURRENCY: z.coerce.number().int().min(1).default(2),
  WORKER_PULLER_CONCURRENCY: z.coerce.number().int().min(1).default(1),
  WORKER_BACKUP_CONCURRENCY: z.coerce.number().int().min(1).default(1),
})

const parsed = EnvSchema.safeParse(process.env)
if (!parsed.success) {
  console.error('[worker env] invalid', JSON.stringify(parsed.error.format(), null, 2))
  process.exit(1)
}

export const env = parsed.data
export type Env = z.infer<typeof EnvSchema>
