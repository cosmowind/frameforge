// Redis 客户端 + BullMQ Queue 工厂（plan2 §6.2 SCF/Cron/Puller 共用 BullMQ）
import { Queue, Worker, type Processor } from 'bullmq'
import IORedis from 'ioredis'
import { env } from '../config/env.js'

// re-exported so job modules can import the env with the queue helpers
export { env }

export const redis = new IORedis(env.REDIS_URL, {
  maxRetriesPerRequest: null, // BullMQ 要求
  enableReadyCheck: true,
})

redis.on('error', (err) => {
  console.error('[worker redis] error', err)
})

// 统一 queue 选项
const defaultJobOptions = {
  attempts: 5,
  backoff: { type: 'exponential', delay: 1000 },
  removeOnComplete: { count: 1000, age: 24 * 3600 },
  removeOnFail: { count: 5000, age: 7 * 24 * 3600 },
}

// 队列定义（与 plan2 §8 架构图：device-scan / preview / pull / backup 各一个）
export const QUEUE_NAMES = {
  DEVICE_SCAN: 'ff:device-scan',
  PREVIEW: 'ff:preview',
  PULL: 'ff:pull',
  BACKUP: 'ff:backup',
} as const

export const buildQueue = (name: string) =>
  new Queue(name, {
    connection: redis,
    prefix: env.BULLMQ_PREFIX,
    defaultJobOptions,
  })

export const buildWorker = (name: string, processor: Processor) =>
  new Worker(name, processor, {
    connection: redis,
    prefix: env.BULLMQ_PREFIX,
    concurrency: env[`WORKER_${name.toUpperCase().replace('FrameForge:', '')}_CONCURRENCY` as never] as number,
  })

export const queues = {
  deviceScan: buildQueue(QUEUE_NAMES.DEVICE_SCAN),
  preview: buildQueue(QUEUE_NAMES.PREVIEW),
  pull: buildQueue(QUEUE_NAMES.PULL),
  backup: buildQueue(QUEUE_NAMES.BACKUP),
}
