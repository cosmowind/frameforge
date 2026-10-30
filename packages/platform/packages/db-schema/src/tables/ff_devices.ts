// T7 — 设备指纹（plan2 详化字段）
import { uuid, text, boolean, timestamp, uniqueIndex, index } from 'drizzle-orm/pg-core'
import { vumSchema } from '../schema'

export const devices = vumSchema.table(
  'ff_devices',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    deviceId: text('device_id').notNull(), // 12 hex = 设备指纹
    fingerprintHash: text('fingerprint_hash').notNull(),
    platform: text('platform').notNull(),
    hostname: text('hostname'),
    cpuModel: text('cpu_model'),
    macAddresses: text('mac_addresses').array(),
    winMachineGuid: text('win_machine_guid'),
    salt: text('salt').notNull(),
    lastSeenAt: timestamp('last_seen_at', { withTimezone: true }),
    firstSeenAt: timestamp('first_seen_at', { withTimezone: true }).defaultNow().notNull(),
    isActive: boolean('is_active').notNull().default(true),
  },
  (t) => ({
    deviceIdIdx: uniqueIndex('ff_devices_device_id_idx').on(t.deviceId),
    fingerprintIdx: index('ff_devices_fingerprint_idx').on(t.fingerprintHash),
  }),
)

export type Device = typeof devices.$inferSelect
export type NewDevice = typeof devices.$inferInsert
