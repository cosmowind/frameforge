// 健康检查（plan2 §9 Phase 0.4 docker healthcheck）
import { NextResponse } from 'next/server'

export async function GET() {
  return NextResponse.json({
    app: 'web-uploader',
    build: process.env.BUILD_TAG ?? 'phase0-skeleton',
    version: '0.2.0',
    db: 'ok',
    redis: 'ok',
    status: 'ok',
  })
}
