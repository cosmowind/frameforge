// T10 — 文件资源索引（三层存储）
import { uuid, text, bigint, integer, timestamp, jsonb, uniqueIndex, index } from 'drizzle-orm/pg-core'
import { ffSchema } from '../schema'
import { cosStorageClassEnum } from '../enums'
import { videoRecords } from './ff_video_records'

export const fileAssets = ffSchema.table(
  'ff_file_assets',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    videoRecordId: uuid('video_record_id')
      .notNull()
      .references(() => videoRecords.id, { onDelete: 'cascade' }),
    fileHash: text('file_hash').notNull(),
    fileSizeBytes: bigint('file_size_bytes', { mode: 'number' }).notNull(),

    // === L1 COS ===
    cosKey: text('cos_key'),
    cosBucket: text('cos_bucket'),
    cosRegion: text('cos_region'),
    cosStorageClass: cosStorageClassEnum('cos_storage_class').notNull().default('standard'),
    cosUploadedAt: timestamp('cos_uploaded_at', { withTimezone: true }),

    // === L1 客户 COS（SCF 同步）===
    clientCosKey: text('client_cos_key'),
    clientCosUploadedAt: timestamp('client_cos_uploaded_at', { withTimezone: true }),
    clientCosEtag: text('client_cos_etag'),

    // === L2 本地硬盘（Puller）===
    localPath: text('local_path'),
    localPulledAt: timestamp('local_pulled_at', { withTimezone: true }),
    localPullAttempts: integer('local_pull_attempts').notNull().default(0),
    localSizeBytes: bigint('local_size_bytes', { mode: 'number' }),
    localChecksum: text('local_checksum'),

    // === L3 夸克网盘 ===
    quarkBackupAt: timestamp('quark_backup_at', { withTimezone: true }),
    quarkBackupSizeBytes: bigint('quark_backup_size_bytes', { mode: 'number' }),
    quarkBackupPath: text('quark_backup_path'),

    // === 生命周期转换时间点 ===
    transitionToIaAt: timestamp('transition_to_ia_at', { withTimezone: true }),
    transitionToArchiveAt: timestamp('transition_to_archive_at', { withTimezone: true }),
    transitionToDeepAt: timestamp('transition_to_deep_at', { withTimezone: true }),

    extra: jsonb('extra').$type<Record<string, unknown>>(),
    createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull(),
  },
  (t) => ({
    videoIdx: uniqueIndex('ff_file_assets_video_idx').on(t.videoRecordId),
    hashIdx: uniqueIndex('ff_file_assets_hash_idx').on(t.fileHash),
    cosClassIdx: index('ff_file_assets_cos_class_idx').on(t.cosStorageClass, t.cosUploadedAt),
    localPullIdx: index('ff_file_assets_local_pull_idx').on(t.localPulledAt),
    quarkIdx: index('ff_file_assets_quark_idx').on(t.quarkBackupAt),
  }),
)

export type FileAsset = typeof fileAssets.$inferSelect
export type NewFileAsset = typeof fileAssets.$inferInsert
