import { z } from 'zod'
import { APP_ROLES, LIFECYCLE_STATES, UPLOAD_TARGETS, UPLOAD_STATUSES, UPLOAD_ADAPTERS } from '../constants'

export const AppRoleSchema = z.enum(APP_ROLES)

export const LifecycleStateSchema = z.enum(LIFECYCLE_STATES)

export const UploadTargetSchema = z.enum(UPLOAD_TARGETS)

export const UploadStatusSchema = z.enum(UPLOAD_STATUSES)

export const UploadAdapterSchema = z.enum(UPLOAD_ADAPTERS)

export const UuidSchema = z.string().uuid()

export const BusinessKeySchema = z
  .string()
  .min(1)
  .max(64)
  .regex(/^[a-z][a-z0-9_-]*$/, 'businessKey 须以小写字母开头，仅含 a-z/0-9/_/-')

export const VersionSchema = z.number().int().min(0)

export const IsoDateTimeSchema = z.string().datetime({ offset: true })

export const PageQuerySchema = z.object({
  page: z.coerce.number().int().min(1).default(1),
  pageSize: z.coerce.number().int().min(1).max(200).default(20),
})
