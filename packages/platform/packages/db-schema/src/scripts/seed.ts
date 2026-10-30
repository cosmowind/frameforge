// 默认数据：默认 region + 默认 device_types（4 种）+ 默认 super admin（Clerk 通过 webhook 同步）
import pg from 'pg'
import { logger } from '@ff/shared/utils/logger'

const SCHEMA = process.env.DATABASE_SCHEMA ?? 'ff'

const DEFAULT_DEVICE_TYPES = [
  {
    code: 'dji-gopro-dcim',
    name_cn: 'DJI/GoPro (DCIM MP4)',
    name_en: 'DJI/GoPro (DCIM MP4)',
    root_subdir: 'DCIM',
    session_naming: 'file',
    file_extensions: ['.mp4'],
    preview_engine: 'native',
    upload_prep: 'direct',
  },
  {
    code: 'head-mounted-hmd',
    name_cn: '头环 (HMD 私有格式)',
    name_en: 'Head-Mounted HMD',
    root_subdir: 'hmd',
    session_naming: 'dir_session',
    file_extensions: ['.hmd', '.json'],
    preview_engine: 'hmd-decoder',
    upload_prep: 'extract-hmd',
  },
  {
    code: 'gopro-session-mcap',
    name_cn: 'GoPro Session (MCAP)',
    name_en: 'GoPro Session MCAP',
    root_subdir: 'data',
    session_naming: 'dir_session',
    file_extensions: ['.mcap', '.json'],
    preview_engine: 'mcap-extract',
    upload_prep: 'extract-mcap',
  },
  {
    code: 'generic-avi-recording',
    name_cn: 'Generic AVI (多 AVI)',
    name_en: 'Generic AVI AVI Recording',
    root_subdir: 'recordings',
    session_naming: 'dir_datetime',
    file_extensions: ['.avi', '.idx'],
    preview_engine: 'native',
    upload_prep: 'concat-avi',
  },
]

async function main(): Promise<void> {
  const client = new pg.Client({
    connectionString: process.env.DATABASE_URL,
    options: `-c search_path=${SCHEMA}`,
  })
  await client.connect()

  // 1) 默认 region
  await client.query(
    `INSERT INTO ff_regions (code, name, is_active) VALUES ('default', '示例市', true)
     ON CONFLICT (code) DO NOTHING`,
  )
  logger.info({ schema: SCHEMA }, 'ensured default region')

  // 2) 4 设备类型
  for (const dt of DEFAULT_DEVICE_TYPES) {
    await client.query(
      `INSERT INTO ff_device_types
        (code, name_cn, name_en, root_subdir, session_naming, file_extensions, preview_engine, upload_prep, is_active)
       VALUES ($1, $2, $3, $4, $5::ff.session_naming, $6::text[], $7::ff.preview_engine, $8::ff.upload_prep, true)
       ON CONFLICT (code) DO UPDATE SET
         name_cn = EXCLUDED.name_cn,
         root_subdir = EXCLUDED.root_subdir,
         session_naming = EXCLUDED.session_naming,
         preview_engine = EXCLUDED.preview_engine,
         upload_prep = EXCLUDED.upload_prep,
         updated_at = now()`,
      [
        dt.code,
        dt.name_cn,
        dt.name_en,
        dt.root_subdir,
        dt.session_naming,
        dt.file_extensions,
        dt.preview_engine,
        dt.upload_prep,
      ],
    )
  }
  logger.info({ count: DEFAULT_DEVICE_TYPES.length }, 'ensured 4 default device types')

  await client.end()
}

void main().catch((err) => {
  logger.error({ err }, 'seed failed')
  process.exit(1)
})
