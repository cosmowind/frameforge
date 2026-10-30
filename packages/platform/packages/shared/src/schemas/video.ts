import { z } from 'zod'
import { UuidSchema, BusinessKeySchema, VersionSchema, IsoDateTimeSchema, LifecycleStateSchema } from './common'

// 视频主表行
export const VideoRecordSchema = z.object({
  id: UuidSchema,
  deviceTypeId: UuidSchema,
  sessionFolderName: z.string().nullable().optional(),
  recorderKey: z.string(),
  environmentKey: z.string(),
  processId: UuidSchema,
  fileHash: z.string(),
  originalPath: z.string(),
  originalFilename: z.string(),
  renamedFilename: z.string(),
  fileSizeBytes: z.number().int().min(0),
  originalFormat: z.enum(['mp4', 'hmd', 'mcap', 'avi']),
  deviceSpecificMetadata: z.record(z.unknown()).nullable().optional(),
  isMultiPart: z.boolean(),
  partCount: z.number().int().min(1),
  scanDate: IsoDateTimeSchema,
  recordedAt: IsoDateTimeSchema.nullable().optional(),
  durationSec: z.number().int().nullable().optional(),
  resolution: z.string().nullable().optional(),
  codec: z.string().nullable().optional(),
  taskDescription: z.string(),
  isWearingGloves: z.boolean().nullable().optional(),
  score: z.number().int().min(1).max(5).nullable().optional(),
  lifecycleState: LifecycleStateSchema,
  sourceDevice: z.string(),
  version: VersionSchema,
  regionId: UuidSchema,
})

export type VideoRecord = z.infer<typeof VideoRecordSchema>
