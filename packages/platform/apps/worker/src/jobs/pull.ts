// worker-pull: 从 COS CDN 回源拉到本地硬盘（plan2 L2）
import type { Processor } from 'bullmq'
import { promises as fs } from 'node:fs'
import path from 'node:path'
import { spawn } from 'node:child_process'
import { QUEUE_NAMES, buildWorker, env } from '../queue/redis.js'
import { logger } from '@ff/shared/utils/logger'

export const processPull: Processor = async (job) => {
  const { cosKey, cosBucket, cosRegion, fileHash } = job.data as {
    cosKey: string
    cosBucket: string
    cosRegion: string
    fileHash: string
  }
  logger.info({ jobId: job.id, cosKey }, 'pull starting')

  if (!env.PULLER_LOCAL_ROOT) {
    throw new Error('PULLER_LOCAL_ROOT not set')
  }
  const localPath = path.join(env.PULLER_LOCAL_ROOT, fileHash)
  if (
    await fs
      .stat(localPath)
      .then((s) => s.isFile())
      .catch(() => false)
  ) {
    logger.info({ fileHash }, 'pull: already exists, skip')
    return { skipped: true, localPath }
  }
  await fs.mkdir(path.dirname(localPath), { recursive: true })

  // Phase 1: 用 rclone / awscli sync COS → 本地
  // Phase 0 占位：仅返回占位
  return {
    pulled: false,
    placeholder: true,
    cosKey,
    cosBucket,
    cosRegion,
    localPath,
  }
}

export const pullWorker = buildWorker(QUEUE_NAMES.PULL, processPull)
pullWorker.on('failed', (job, err) => {
  logger.error({ jobId: job?.id, err }, 'pull failed')
})

// 防止 unused 警告
void spawn
