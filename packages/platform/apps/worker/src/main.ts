// Worker 入口：注册 4 个 BullMQ consumer + HTTP /health
import http from 'node:http'
import { env } from './config/env.js'
import { logger } from '@ff/shared/utils/logger'
import { redis, queues, deviceScanWorker, previewWorker, pullWorker, backupWorker } from './jobs/index.js'

async function main() {
  logger.info(
    {
      app: 'ff-worker',
      version: '0.2.0',
      bullmqPrefix: env.BULLMQ_PREFIX,
      queues: Object.keys(queues),
    },
    'worker starting',
  )

  // BullMQ worker 启动即开始消费；保留所有 worker 引用防止 GC
  void deviceScanWorker
  void previewWorker
  void pullWorker
  void backupWorker

  const server = http.createServer((req, res) => {
    if (req.url === '/health' || req.url === '/healthz') {
      res.writeHead(200, { 'Content-Type': 'application/json' })
      res.end(
        JSON.stringify({
          app: 'ff-worker',
          status: 'ok',
          redis: redis.status,
          workers: ['device-scan', 'preview', 'pull', 'backup'],
        }),
      )
      return
    }
    res.writeHead(404).end()
  })

  server.listen(env.WORKER_PORT, () => {
    logger.info({ port: env.WORKER_PORT }, 'worker listening')
  })

  const shutdown = async (signal: string) => {
    logger.info({ signal }, 'worker shutting down')
    await Promise.all([
      deviceScanWorker.close(),
      previewWorker.close(),
      pullWorker.close(),
      backupWorker.close(),
      redis.quit(),
    ])
    server.close()
    process.exit(0)
  }
  process.on('SIGINT', () => void shutdown('SIGINT'))
  process.on('SIGTERM', () => void shutdown('SIGTERM'))
}

void main().catch((err) => {
  logger.error({ err }, 'worker failed to start')
  process.exit(1)
})
