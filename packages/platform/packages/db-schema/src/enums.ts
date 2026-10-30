import { ffSchema } from './schema'

// 11 个 PG enum（plan2 §3.4）
export const appRoleEnum = ffSchema.enum('app_role', ['uploader', 'admin'])
export const sessionNamingEnum = ffSchema.enum('session_naming', [
  'file',
  'dir_session',
  'dir_datetime',
])
export const previewEngineEnum = ffSchema.enum('preview_engine', [
  'native',
  'ffmpeg',
  'hmd-decoder',
  'mcap-extract',
])
export const uploadPrepEnum = ffSchema.enum('upload_prep', [
  'direct',
  'concat-avi',
  'extract-hmd',
  'extract-mcap',
])
export const lifecycleStateEnum = ffSchema.enum('lifecycle_state', [
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
export const uploadTargetEnum = ffSchema.enum('upload_target', ['partner', 'backup', 'quark'])
export const uploadAdapterEnum = ffSchema.enum('upload_adapter', [
  'cos-direct',
  'scf-cross-bucket',
  'api',
  'playwright',
  'quark-rclone',
  'local-puller',
])
export const uploadStatusEnum = ffSchema.enum('upload_status', [
  'pending',
  'success',
  'failed',
  'retrying',
])
export const cosStorageClassEnum = ffSchema.enum('cos_storage_class', [
  'standard',
  'ia',
  'archive',
  'deep_archive',
])
export const scfTriggerEnum = ffSchema.enum('scf_trigger', ['cos-put', 'http', 'timer'])
export const runStatusEnum = ffSchema.enum('run_status', ['running', 'success', 'failed'])
