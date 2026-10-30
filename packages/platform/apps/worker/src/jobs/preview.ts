// worker-preview: 调度 ffmpeg / hmd-decoder / mcap-extract 转码为可播放 MP4
import type { Processor } from 'bullmq'
import { QUEUE_NAMES, buildWorker } from '../queue/redis.js'
import { logger } from '@ff/shared/utils/logger'

export const processPreview: Processor = async (job) => {
  const { sessionPath, deviceTypeCode } = job.data as { sessionPath: string; deviceTypeCode: string }
  logger.info({ jobId: job.id, sessionPath, deviceTypeCode }, 'preview starting')
  // Phase 1: 接 ffmpeg/HMD/MCAP 实现
  // Phase 0 占位：返回任务接收
  return { status: 'queued', sessionPath, deviceTypeCode }
}

export const previewWorker = buildWorker(QUEUE_NAMES.PREVIEW, processPreview)
previewWorker.on('failed', (job, err) => {
  logger.error({ jobId: job?.id, err }, 'preview failed')
})
