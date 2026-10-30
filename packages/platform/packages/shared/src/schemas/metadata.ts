import { z } from 'zod'
import { UuidSchema } from './common'

// 录制员（plan2 D2 业务主键稳定）
export const RecorderCreateSchema = z.object({
  businessKey: z.string().min(1).max(64),
  nameCn: z.string().min(1).max(64),
  nameEn: z.string().max(64).optional(),
  regionId: UuidSchema,
  phone: z.string().regex(/^[+\d\s-]{6,32}$/u).optional(),
  remark: z.string().max(500).optional(),
})

export const RecorderUpdateSchema = RecorderCreateSchema.partial()

// 环境
export const EnvironmentCreateSchema = z.object({
  businessKey: z.string().min(1).max(64),
  nameCn: z.string().min(1).max(64),
  nameEn: z.string().max(64).optional(),
  regionId: UuidSchema,
  envType: z.enum(['workshop', 'outdoor', 'lab', 'other']).default('other'),
  difficulty: z.enum(['easy', 'medium', 'hard']).default('medium'),
  remark: z.string().max(500).optional(),
})

export const EnvironmentUpdateSchema = EnvironmentCreateSchema.partial()

// 产品
export const ProductCreateSchema = z.object({
  businessKey: z.string().min(1).max(64),
  nameCn: z.string().min(1).max(128),
  nameEn: z.string().max(128).optional(),
  regionId: UuidSchema,
  imageUrl: z.string().url().optional(),
})

export const ProductUpdateSchema = ProductCreateSchema.partial()

// 工序
export const ProcessCreateSchema = z.object({
  businessKey: z.string().min(1).max(64),
  productId: UuidSchema,
  nameCn: z.string().min(1).max(128),
  nameEn: z.string().max(128).optional(),
  sequence: z.number().int().min(0).default(0),
})

export const ProcessUpdateSchema = ProcessCreateSchema.partial()

// Clerk webhook payload（admin 加账号时）
export const ClerkWebhookUserSchema = z.object({
  id: z.string(),
  email_addresses: z.array(z.object({ id: z.string(), email_address: z.string().email() })),
  first_name: z.string().nullable().optional(),
  last_name: z.string().nullable().optional(),
  public_metadata: z.record(z.unknown()).optional(),
})

export type RecorderCreate = z.infer<typeof RecorderCreateSchema>
export type EnvironmentCreate = z.infer<typeof EnvironmentCreateSchema>
export type ProductCreate = z.infer<typeof ProductCreateSchema>
export type ProcessCreate = z.infer<typeof ProcessCreateSchema>
