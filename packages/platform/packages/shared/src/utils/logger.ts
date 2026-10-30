// 结构化 JSON 日志（Pino）
import { pino, type LoggerOptions } from 'pino'

const opts: LoggerOptions = {
  level: process.env.NODE_ENV === 'production' ? 'info' : 'debug',
  base: { app: 'ff', version: process.env.APP_VERSION ?? '0.2.0' },
}

export const logger = pino(opts)
export type Logger = typeof logger
