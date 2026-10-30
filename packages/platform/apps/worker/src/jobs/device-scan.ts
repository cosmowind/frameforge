// worker-device-scan: 调度各 DeviceAdapter.scan() 写入 ff_video_records (SCANNED)
import type { Processor } from 'bullmq'
import { drizzle } from 'drizzle-orm/node-postgres'
import pg from 'pg'
import { ffSchema } from '@ff/db-schema'
import { videoRecords } from '@ff/db-schema/tables/ff_video_records'
import { deviceTypes } from '@ff/db-schema/tables/ff_device_types'
import { eq } from 'drizzle-orm'
import { QUEUE_NAMES, buildWorker, env } from '../queue/redis.js'
import { buildAdapterRegistry } from '@ff/adapters'
import { logger } from '@ff/shared/utils/logger'

const SCHEMA = env.DATABASE_SCHEMA

const pool = new pg.Pool({
  connectionString: env.DATABASE_URL,
  options: `-c search_path=${SCHEMA}`,
})
export const db = drizzle(pool, { schema: { videoRecords, deviceTypes } })

export const processDeviceScan: Processor = async (job) => {
  const { deviceTypeCode, rootPath } = job.data as { deviceTypeCode: string; rootPath: string }
  logger.info({ jobId: job.id, deviceTypeCode, rootPath }, 'device-scan starting')

  const adapter = buildAdapterRegistry().get(deviceTypeCode)
  if (!adapter) {
    throw new Error(`unknown device type code: ${deviceTypeCode}`)
  }

  const units = await adapter.scan(rootPath)
  const dt = await db.select().from(deviceTypes).where(eq(deviceTypes.code, deviceTypeCode)).limit(1)
  if (dt.length === 0) {
    throw new Error(`device_type not seeded: ${deviceTypeCode}`)
  }
  const deviceTypeId = dt[0]!.id

  // Phase 1: 写 ff_video_records；现在 Phase 0 占位
  // 等待 Phase 1 实现：hash 计算 + file_size 提取 + file_size_bytes

  return {
    scanned: units.length,
    deviceTypeId,
    units: units.map((u) => ({ sessionId: u.sessionId, displayName: u.displayName })),
  }
}

export const deviceScanWorker = buildWorker(QUEUE_NAMES.DEVICE_SCAN, processDeviceScan)

deviceScanWorker.on('failed', (job, err) => {
  logger.error({ jobId: job?.id, err }, 'device-scan failed')
})
