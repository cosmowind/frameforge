// worker-backup: pg_dump + CSV 轮转（plan2 §6.6 backup 阶段触发 + Phase 3 worker-backup 完善）
import type { Processor } from 'bullmq'
import { QUEUE_NAMES, buildWorker } from '../queue/redis.js'
import { logger } from '@ff/shared/utils/logger'

export const processBackup: Processor = async (job) => {
  logger.info({ jobId: job.id, data: job.data }, 'backup starting')
  // Phase 1: pg_dump + CSV
  return { status: 'queued' }
}

export const backupWorker = buildWorker(QUEUE_NAMES.BACKUP, processBackup)
backupWorker.on('failed', (job, err) => {
  logger.error({ jobId: job?.id, err }, 'backup failed')
})
