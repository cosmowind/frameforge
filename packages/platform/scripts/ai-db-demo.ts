// scripts/ai-db-demo.ts
// 演示 AI 通过对话操作数据库的完整流程：
//   1) SELECT 看现状
//   2) DRY-RUN preview 要改什么
//   3) 用户确认
//   4) COMMIT 提交

import 'dotenv/config'
import { Pool } from 'pg'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import {
  assertSafeSql,
  dryRunUpdate,
  commitUpdate,
  dryRunBatchUpdate,
  commitBatchUpdate,
  DatabaseSafetyError,
} from '@ff/db-schema'

const DSN = process.env.DATABASE_URL
if (!DSN) {
  console.error('❌ DATABASE_URL not set. Copy apps/web-admin/.env to ./ and retry.')
  process.exit(1)
}

const pool = new Pool({ connectionString: DSN, options: '-c search_path=ff,public' })

async function main() {
  console.log('========== AI 数据库操作 Demo ==========')
  console.log('DSN:', DSN!.replace(/:[^:@/]+@/, ':***@'))
  console.log()

  // 1) SELECT 现状
  console.log('1) SELECT 看现状')
  const statusRow = (
    await pool.query(`
      SELECT
        count(*)::int AS total,
        count(*) FILTER (WHERE recorder_id = '' OR recorder_id IS NULL)::int AS empty_recorder,
        count(*) FILTER (WHERE uploaded != 'Yes' OR uploaded IS NULL)::int AS not_uploaded
      FROM public.videos
    `)
  ).rows[0] as { total: number; empty_recorder: number; not_uploaded: number }
  console.log(`   public.videos: 总 ${statusRow.total} 行 / 空 recorder ${statusRow.empty_recorder} / 未上传 ${statusRow.not_uploaded}`)
  console.log()

  // 2) 找一条未填的 path 作为 demo
  console.log('2) 取第一条未填的视频做演示')
  const target = (
    await pool.query(`
      SELECT path FROM public.videos
      WHERE recorder_id = '' OR recorder_id IS NULL
      LIMIT 1
    `)
  ).rows[0] as { path: string }
  console.log(`   target path: ${target.path.slice(-60)}`)
  console.log()

  // 3) DRY-RUN：演示要改 recorder_id / task_id / uploaded
  console.log('3) DRY-RUN preview')
  const dryRun = await dryRunUpdate(pool, {
    table: 'public.videos',
    where: { path: target.path },
    set: {
      recorder_id: 'op3',
      task_id: 'demo_task_001',
      uploaded: 'Yes',
    },
  })
  console.log(`   before: ${JSON.stringify(dryRun.before)}`)
  console.log(`   diffs:`)
  for (const d of dryRun.diffs) {
    console.log(`     ${d.field}: ${JSON.stringify(d.before)} → ${JSON.stringify(d.after)} (${d.changed ? 'CHANGED' : 'NO CHANGE'})`)
  }
  console.log()

  // 4) SQL 安全性检查（兜底）
  console.log('4) 安全 SQL 兜底检查')
  try {
    assertSafeSql('DROP TABLE public.videos')
    console.log('   ❌ DROP 未被拦截！')
  } catch (e) {
    console.log(`   ✅ DROP 被拦截：${(e as DatabaseSafetyError).message}`)
  }
  console.log()

  // 5) 询问用户是否执行
  console.log('5) 用户确认（demo 默认 yes）')
  const ok = process.argv.includes('--commit')
  if (!ok) {
    console.log('   ⏭️  跳过（用 --commit 真正执行）')
  } else {
    console.log('   执行 commitUpdate...')
    const r = await commitUpdate(pool, {
      table: 'public.videos',
      where: { path: target.path },
      set: {
        recorder_id: 'op3',
        task_id: 'demo_task_001',
        uploaded: 'Yes',
      },
    })
    console.log(`   ✅ 已更新 ${r.rowCount} 行`)
  }
  console.log()

  // 6) 整批 dry-run（演示场景：批量补 recorder_id）
  console.log('6) 整批 dry-run：批量给前 5 条空 recorder 的视频设 op3 + uploaded=Yes')
  const batchTargets = (
    await pool.query(`
      SELECT path FROM public.videos
      WHERE recorder_id = '' OR recorder_id IS NULL
      LIMIT 5
    `)
  ).rows as { path: string }[]
  const batchUpdates = batchTargets.map((t) => ({
    where: { path: t.path },
    set: { recorder_id: 'op3', uploaded: 'Yes' as const },
  }))
  const batchDryRun = await dryRunBatchUpdate(pool, 'public.videos', batchUpdates)
  console.log(`   ${batchDryRun.totalRows} 条 / ${batchDryRun.totalChanges} 字段变更`)
  for (const r of batchDryRun.results) {
    console.log(`   ${r.notFound ? '⚠️ ' : '  '}${r.path.slice(-50)}`)
  }
  console.log()

  await pool.end()
}

main().catch((err) => {
  console.error('❌ demo failed:', err)
  process.exit(1)
})