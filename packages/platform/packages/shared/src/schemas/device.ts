import { z } from 'zod'
import { DEVICE_TYPE_CODES } from '../constants'
import { UuidSchema } from './common'

// 4 设备 code（取自 DEVICE_TYPE_CODES）
export const DeviceTypeCodeSchema = z.enum([
  DEVICE_TYPE_CODES.DJI_GOPRO_DCIM,
  DEVICE_TYPE_CODES.HEAD_MOUNTED_HMD,
  DEVICE_TYPE_CODES.GOPRO_SESSION_MCAP,
  DEVICE_TYPE_CODES.GENERIC_AVI_RECORDING,
])

// 设备类型字典行
export const DeviceTypeSchema = z.object({
  id: UuidSchema,
  code: DeviceTypeCodeSchema,
  nameCn: z.string(),
  nameEn: z.string().nullable().optional(),
  rootSubdir: z.string(),
  sessionNaming: z.enum(['file', 'dir_session', 'dir_datetime']),
  fileExtensions: z.array(z.string()),
  previewEngine: z.enum(['native', 'ffmpeg', 'hmd-decoder', 'mcap-extract']),
  uploadPrep: z.enum(['direct', 'concat-avi', 'extract-hmd', 'extract-mcap']),
  isActive: z.boolean(),
})

export type DeviceType = z.infer<typeof DeviceTypeSchema>
