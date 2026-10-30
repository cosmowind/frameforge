// 单价规则（可由 admin 在 ff.app_config 或环境变量覆盖）
// 默认：每视频 5 元基础 + 按 duration × difficulty 系数
// 后续接 ff.app_config 持久化
import type { DifficultyStatsRow } from '@/app/api/admin/stats/difficulty/route'

export interface RateConfig {
  base_per_video_cny: number       // 每视频基础
  per_minute_cny: Record<string, number>  // 按 difficulty
  upload_bonus_cny: number         // 已上传额外奖励
}

export const DEFAULT_RATES: RateConfig = {
  base_per_video_cny: 5,
  per_minute_cny: { easy: 0.1, medium: 0.2, hard: 0.3, unknown: 0.15 },
  upload_bonus_cny: 2,
}

export function calcPayrollForBatch(input: {
  duration_sec: number
  difficulty: string | null
  scored: boolean // 已评分=已确认工作（替代 uploaded 字段）
  rates?: RateConfig
}): { base: number; by_minutes: number; score_bonus: number; total: number } {
  const r = input.rates ?? DEFAULT_RATES
  const diff = (input.difficulty ?? 'unknown').toLowerCase()
  const perMin = r.per_minute_cny[diff] ?? r.per_minute_cny.unknown!

  const minutes = input.duration_sec / 60
  const base = r.base_per_video_cny
  const byMinutes = +(minutes * perMin).toFixed(2)
  const scoreBonus = input.scored ? r.upload_bonus_cny : 0
  const total = +(base + byMinutes + scoreBonus).toFixed(2)
  return { base, by_minutes: byMinutes, score_bonus: scoreBonus, total }
}