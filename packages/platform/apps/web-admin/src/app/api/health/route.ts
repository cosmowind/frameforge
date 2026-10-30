// GET /api/health
import { NextResponse } from 'next/server'
import { pool } from '@/lib/db'

export async function GET() {
  let dbStatus = 'down'
  try {
    await pool.query('SELECT 1')
    dbStatus = 'ok'
  } catch (err) {
    console.error('[health] db error', err)
  }
  return NextResponse.json({
    app: 'web-admin',
    version: '0.2.0',
    db: dbStatus,
    status: 'ok',
  })
}