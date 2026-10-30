// 4 张表的白名单 + 默认列（防 SQL 注入 + 默认显示配置）
// 数据源：public.*（业务真相）；写入只走 /api/ai/db/* 的 dry-run + commit
// 这里只读，不写。

export type TableKey = 'videos' | 'tasks' | 'recorders' | 'environments'

export interface TableConfig {
  key: TableKey
  label: string
  description: string
  /** 物理 schema.表名（pg_query 拼接时只接受白名单内组合） */
  physical: string
  /** 主键列，用于去重 / 高亮 */
  primaryKey: string
  /** 业务展示主键（更人类可读） */
  displayKey: string
  /** 人类默认显示列（顺序即是默认列序） */
  defaultColumns: string[]
  /** 默认排序（白名单列名） */
  defaultSort: { col: string; order: 'asc' | 'desc' }
}

export const TABLES: Record<TableKey, TableConfig> = {
  videos: {
    key: 'videos',
    label: '视频（videos）',
    description: '业务真相表 / 560 行 / 唯一主键 path',
    physical: 'public.videos',
    primaryKey: 'path',
    displayKey: 'path',
    defaultColumns: [
      'path',
      'recorder_id',
      'task_id',
      'env_id',
      'duration_sec',
      'file_type',
      'device_id',
      'uploaded',
      'score',
      'scan_date',
      'extra_description',
    ],
    defaultSort: { col: 'scan_date', order: 'desc' },
  },
  tasks: {
    key: 'tasks',
    label: '任务（tasks）',
    description: '工序字典 / 121 行',
    physical: 'public.tasks',
    primaryKey: 'task_id',
    displayKey: 'task_id',
    defaultColumns: [
      'task_id',
      'task',
      'process',
      'process_en',
      'product',
      'tool',
      'difficulty',
      'quota_min',
      'scene',
      'environment',
    ],
    defaultSort: { col: 'task_id', order: 'asc' },
  },
  recorders: {
    key: 'recorders',
    label: '录制员（recorders）',
    description: '录制员字典 / 14 行',
    physical: 'public.recorders',
    primaryKey: 'id',
    displayKey: 'id',
    defaultColumns: [
      'id',
      'name',
      'phone',
      'operator_job',
      'age_range',
      'gender',
      'handedness',
      'gloves',
      'workforce_type',
      'recording_experience_days',
      'notes',
    ],
    defaultSort: { col: 'id', order: 'asc' },
  },
  environments: {
    key: 'environments',
    label: '环境（environments）',
    description: '拍摄环境字典 / 19 行',
    physical: 'public.environments',
    primaryKey: 'env_id',
    displayKey: 'env_id',
    defaultColumns: [
      'env_id',
      'scene',
      'environment',
      'environment_description',
      'environment_description_en',
      'location_address',
      'facility_venue',
      'notes',
    ],
    defaultSort: { col: 'env_id', order: 'asc' },
  },
}

export const TABLE_KEYS: TableKey[] = ['videos', 'tasks', 'recorders', 'environments']
