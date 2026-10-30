import { vumSchema } from './schema'

// 11 个 PG enum（plan2 §3.4）
export const appRoleEnum = vumSchema.enum('app_role', ['uploader', 'admin'])
export const sessionNamingEnum = vumSchema.enum('session_naming', [
  'file',
  'dir_session',
  'dir_datetime',
])
export const previewEngineEnum = vumSchema.enum('preview_engine', [
  'native',
  'ffmpeg',
  'hmd-decoder',
  'mcap-extract',
])
export const uploadPrepEnum = vumSchema.enum('upload_prep', [
  'direct',
  'concat-avi',
  'extract-hmd',
  'extract-mcap',
])
export const lifecycleStateEnum = vumSchema.enum('lifecycle_state', [
  'SCANNED',
  'PREVIEWING',
  'PREVIEWED',
  'META_FILLED',
  'UPLOADING',
  'UPLOADED',
  'LOCAL_DELETED',
  'ARCHIVED',
  'FAILED',
  'RETRYING',
])
export const uploadTargetEnum = vumSchema.enum('upload_target', ['partner', 'backup', 'quark'])
export const uploadAdapterEnum = vumSchema.enum('upload_adapter', [
  'cos-direct',
  'scf-cross-bucket',
  'api',
  'playwright',
  'quark-rclone',
  'local-puller',
])
export const uploadStatusEnum = vumSchema.enum('upload_status', [
  'pending',
  'success',
  'failed',
  'retrying',
])
export const cosStorageClassEnum = vumSchema.enum('cos_storage_class', [
  'standard',
  'ia',
  'archive',
  'deep_archive',
])
export const scfTriggerEnum = vumSchema.enum('scf_trigger', ['cos-put', 'http', 'timer'])
export const runStatusEnum = vumSchema.enum('run_status', ['running', 'success', 'failed'])
