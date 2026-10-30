// Jobs barrel（便于 main.ts 与测试统一引用）
export { redis, queues, QUEUE_NAMES, buildQueue, buildWorker } from '../queue/redis.js'
export { deviceScanWorker, processDeviceScan } from './device-scan.js'
export { previewWorker, processPreview } from './preview.js'
export { pullWorker, processPull } from './pull.js'
export { backupWorker, processBackup } from './backup.js'
