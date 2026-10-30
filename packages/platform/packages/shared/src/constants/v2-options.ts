// v2 表单选项常量
// 来源：docs/前端调试参考/location0714.txt（2026-07-14 抓取）
// 单一来源：本文件即 ff_scenes/ff_locations 表的 L1/L2/L3 枚举全集
// 变更时机：DR 调整时同步改本文件 + zod schema

// L1 = Environment（27 选项）
export const ENV_L1_OPTIONS = [
  'Retail and Consumer Goods',
  'Fashion',
  'Repair Services',
  'Food and Beverage',
  'Home',
  'Construction and Hardware',
  'Food Processing',
  'Printing and Design',
  'Factory',
  'Hospitality',
  'Automotive and Transport',
  'Sports and Recreation',
  'Creative Workshops',
  'Administrative',
  'Education and Training',
  'Industrial Manufacturing',
  'Energy and Utilities',
  'Healthcare and Pharmacy',
  'Administrative & Office Services',
  'Cleaning and Sanitation',
  'Laboratory / Scientific',
  'Childcare and Caregiving',
  'Public Safety and Emergency Response',
  'Agriculture and Farming',
  'Beauty and Personal Care',
  'Entertainment and Events',
  'Other',
] as const
export type EnvL1 = (typeof ENV_L1_OPTIONS)[number]

// L2 = Venue（228 选项）— phase 1 先用文本；phase 2 改 select
// 暂留空数组提示，lineup 时从 location0714.txt 抽
export const VENUE_L2_OPTIONS: readonly string[] = [
  // 真实 228 选项从 docs/前端调试参考/location0714.txt 抽（agent 已抽）；
  // 首版只列前 20 个高频项做 L1→L2 cascade 演示，全量 phase 1.1 补
  'Home',
  'Office',
  'Grocery Store',
  'Supermarket',
  'Restaurant',
  'Coffee Shop',
  'Hotel',
  'Clothing Store',
  'Hardware Store',
  'Pharmacy',
  'Barber Shop',
  'Nail Salon',
  'Gym',
  'Library',
  'Convenience Store',
  'Bakery',
  'Flower Shop',
  'Pet Store',
  'Book Store',
  'Toy Store',
]

// L3 = Scene（1590 选项）— phase 2 接入，本期留空
export const SCENE_L3_OPTIONS: readonly string[] = []

// 业务必填：操作员 Hand / Gender / Age range
// 全部对齐 dr 官方（docs/前端调试参考/operator0714.txt + 官网抓的 2026-07-15 HTML 片段）
// 改值要同时改：v2-forms-spec.md §1.2 + zod schema + DB 数据 + 此文件
export const HAND_OPTIONS = ['left', 'right'] as const
export type Hand = (typeof HAND_OPTIONS)[number]

export const GENDER_OPTIONS = ['male', 'female', 'prefer_not_to_say'] as const
export type Gender = (typeof GENDER_OPTIONS)[number]

export const AGE_RANGE_OPTIONS = [
  '15-20',
  '20-25',
  '25-30',
  '30-35',
  '35-40',
  '40-45',
  '45-50',
  '50-55',
  '55-60',
  '60-65',
  '65-70',
  '70+',
] as const
export type AgeRange = (typeof AGE_RANGE_OPTIONS)[number]

// scenes 状态机
export const CAPTURE_MODE_OPTIONS = ['single', 'three_views', 'stereo'] as const
export type CaptureMode = (typeof CAPTURE_MODE_OPTIONS)[number]

export const SCENE_STATUS_OPTIONS = ['available', 'pending', 'retired'] as const
export type SceneStatus = (typeof SCENE_STATUS_OPTIONS)[number]

export const SCENE_ACCEPT_STATUS_OPTIONS = ['accepting', 'closed', 'filled'] as const
export type SceneAcceptStatus = (typeof SCENE_ACCEPT_STATUS_OPTIONS)[number]

export const SCENE_SOURCE_OPTIONS = ['manual', 'frameforge'] as const
export type SceneSource = (typeof SCENE_SOURCE_OPTIONS)[number]

// scene_applications 状态机
export const APPLICATION_STATUS_OPTIONS = [
  'draft',
  'submitted_to_dr',
  'approved',
  'rejected',
] as const
export type ApplicationStatus = (typeof APPLICATION_STATUS_OPTIONS)[number]

// video_uploads
export const SOURCE_FORMAT_OPTIONS = ['mp4', 'mcap', 'hmd'] as const
export type SourceFormat = (typeof SOURCE_FORMAT_OPTIONS)[number]

export const STORAGE_PROVIDER_OPTIONS = ['cos', 'aws_s3', 'tencent_cos'] as const
export type StorageProvider = (typeof STORAGE_PROVIDER_OPTIONS)[number]
