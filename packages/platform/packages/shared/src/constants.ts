// 全局常量：前后端共享
// 注意：版本号随 @ff/shared 改动 +1

export const APP_VERSION = '0.2.0'

// 4 设备 code（ff_device_types 表对应 row 的 code 列）
export const DEVICE_TYPE_CODES = {
  DJI_GOPRO_DCIM: 'dji-gopro-dcim',
  HEAD_MOUNTED_HMD: 'head-mounted-hmd',
  GOPRO_SESSION_MCAP: 'gopro-session-mcap',
  GENERIC_AVI_RECORDING: 'generic-avi-recording',
} as const

// 业务主键前缀
export const BUSINESS_KEY_PREFIX = {
  RECORDER: 'rec',
  ENVIRONMENT: 'env',
  PRODUCT: 'prod',
  PROCESS: 'proc',
} as const

// localStorage 预填键（前端用）
export const LOCALSTORAGE_KEYS = {
  LAST_FORM: 'ff.lastForm',
  DEVICE_TOKEN: 'ff.deviceToken',
  UPLOADER_TOKEN: 'ff.uploader.token',
  ADMIN_TOKEN: 'ff.admin.token',
} as const

// 业务 quotas（按 plan1 B1/B2 沿用）
export const QUOTA_DEFAULTS = {
  OPERATOR_X_TASK_X_ENV_DAILY_HARD: 8,
  OPERATOR_X_TASK_X_ENV_DAILY_MED: 5,
  OPERATOR_X_TASK_X_ENV_DAILY_EASY: 3,
} as const

// 生命周期状态
export const LIFECYCLE_STATES = [
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
] as const

// 上传目标 / 适配器
export const UPLOAD_TARGETS = ['partner', 'backup', 'quark'] as const
export const UPLOAD_ADAPTERS = [
  'cos-direct',
  'scf-cross-bucket',
  'api',
  'playwright',
  'quark-rclone',
  'local-puller',
] as const
export const UPLOAD_STATUSES = ['pending', 'success', 'failed', 'retrying'] as const

// 路由（Clerk + 两端隔离）
export const ROUTES = {
  UPLOADER_HOME: '/',
  UPLOADER_STEP1: '/step1-scan',
  UPLOADER_STEP2: '/step2-preview',
  UPLOADER_STEP3: '/step3-fill-upload',
  UPLOADER_LIBRARY: '/library',
  ADMIN_HOME: '/',
  ADMIN_DEVICES: '/device-types',
  ADMIN_RECORDERS: '/recorders',
  ADMIN_ENVIRONMENTS: '/environments',
  ADMIN_PRODUCTS: '/products',
  ADMIN_USERS: '/users',
  ADMIN_REGIONS: '/regions',
  ADMIN_AUDIT: '/audit',
  SIGN_IN: '/sign-in',
  SIGN_UP: '/sign-up',
} as const

// App role
export const APP_ROLES = ['uploader', 'admin'] as const
