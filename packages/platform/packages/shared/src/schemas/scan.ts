import { z } from 'zod'
import { DeviceTypeCodeSchema } from './device'

// 路径归一化 (P3)：forward slash + 绝对 + 无 ..
export const NormalizedPathSchema = z
  .string()
  .min(1)
  .refine((p) => !p.includes('..'), '路径不允许 ..')
  .refine((p) => !p.includes('\\'), '路径必须用 / 分隔 (P3)')

// 文件 hash 前 32 hex (16 字节)
export const FileHashSchema = z.string().regex(/^[0-9a-f]{32}$/, 'fileHash 须 32 位 hex')

// deviceId 12 hex (6 字节)
export const DeviceIdSchema = z.string().regex(/^[0-9a-f]{12}$/, 'deviceId 须 12 位 hex')

// Step 1 扫描请求
export const ScanReqSchema = z.object({
  deviceTypeCode: DeviceTypeCodeSchema,
  rootPath: NormalizedPathSchema,
  recursive: z.boolean().default(true),
})

// 视频单元（4 种设备共用的扫描结果）
export const VideoUnitSchema = z.object({
  sessionId: z.string().min(1),
  displayName: z.string(),
  filePaths: z.array(z.string()).min(1),
  estimatedSize: z.number().int().min(0),
  estimatedDuration: z.number().min(0),
  thumbnailPath: z.string().optional(),
})

export const ScanRespSchema = z.object({
  deviceTypeCode: DeviceTypeCodeSchema,
  units: z.array(VideoUnitSchema),
})

// Step 3 准备上传（设备特定 prepareForUpload 输出）
export const UploadFileRefSchema = z.object({
  preparedPath: z.string(), // 准备好的 MP4 路径
  fileHash: FileHashSchema,
  sizeBytes: z.number().int().min(0),
  durationSec: z.number().min(0).optional(),
  metadata: z.record(z.unknown()).optional(),
})

export type VideoUnit = z.infer<typeof VideoUnitSchema>
export type UploadFileRef = z.infer<typeof UploadFileRefSchema>
