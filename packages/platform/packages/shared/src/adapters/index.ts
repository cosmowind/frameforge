// DeviceAdapter 接口 + 4 设备类型共享定义（plan2 §5.3）
// 注：本文件仅声明接口与共享类型；具体实现见 packages/adapters/

import { z } from 'zod'
import { DEVICE_TYPE_CODES } from '../constants'
import { NormalizedPathSchema, VideoUnitSchema, UploadFileRefSchema } from '../schemas'
import type { UploadFileRef, VideoUnit } from '../schemas'

// 设备元数据
export const DeviceMetadataSchema = z.object({
  sessionFolderName: z.string().nullable().optional(),
  recordedAt: z.string().nullable().optional(), // ISO
  durationSec: z.number().nullable().optional(),
  resolution: z.string().nullable().optional(),
  codec: z.string().nullable().optional(),
  extra: z.record(z.unknown()).optional(),
})
export type DeviceMetadata = z.infer<typeof DeviceMetadataSchema>

// 预览句柄（native → file://, ffmpeg/hmd-decoder/mcap-extract → worker job id）
export const PreviewHandleSchema = z.object({
  kind: z.enum(['native', 'worker']),
  // native: 直接给 path
  fileUrl: z.string().optional(),
  // worker: 给任务 id，前端轮询/SSE 拿流
  jobId: z.string().optional(),
})
export type PreviewHandle = z.infer<typeof PreviewHandleSchema>

// DeviceAdapter 接口（前后端共享）
export interface DeviceAdapter {
  readonly code: string
  scan(rootPath: string): Promise<VideoUnit[]>
  parseMetadata(sessionPath: string): Promise<DeviceMetadata>
  getPreviewHandle(sessionPath: string): Promise<PreviewHandle>
  prepareForUpload(sessionPath: string, workDir: string): Promise<UploadFileRef>
}

// Adapter 注册表类型（前端 + 后端 runtime 通过 code 索引）
export type AdapterRegistry = Map<string, DeviceAdapter>

export type AnyDeviceCode = (typeof DEVICE_TYPE_CODES)[keyof typeof DEVICE_TYPE_CODES]

// Re-export 共享类型
export { DEVICE_TYPE_CODES }
export { NormalizedPathSchema, VideoUnitSchema, UploadFileRefSchema }
