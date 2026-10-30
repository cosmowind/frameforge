// POST /api/uploader/devices
// 录制员端「设备/环境登记」：选 1 种 device_type + env_id + 视频元信息
// 写入 public.videos 1 行（path = 设备 path + 时间戳）
// 写入前必须 dry-run 预览（plan2 D1 写操作纪律）
import { NextRequest, NextResponse } from 'next/server'
import { z } from 'zod'
import { queryCrossSchema } from '@/lib/db'
import { fail, handleApiError, ApiError } from '@/lib/api-error'

const Body = z.object({
  deviceCode: z.enum(['dji_gopro_dcim', 'head_mounted_hmd', 'gopro_session_mcap', 'generic-avi_recording']),
  path: z.string().min(1).max(2000),
  envId: z.string().min(1).max(100),
  recorderId: z.string().min(1).max(100),
  folderName: z.string().max(500).optional(),
  fileSizeBytes: z.number().int().nonnegative().optional(),
  durationSec: z.number().nonnegative().optional(),
  fps: z.number().nonnegative().optional(),
  frameCount: z.number().int().nonnegative().optional(),
  notes: z.string().max(2000).optional(),
})

// device_code → capture_mode + file_type 映射（plan2 §2.3 Adapter）
const DEVICE_META: Record<string, { captureMode: string; fileType: string }> = {
  dji_gopro_dcim: { captureMode: 'single', fileType: 'mp4' },
  head_mounted_hmd: { captureMode: 'stereo', fileType: 'hmd' },
  gopro_session_mcap: { captureMode: 'depth', fileType: 'mcap' },
  generic-avi_recording: { captureMode: 'multi', fileType: 'avi' },
}

export const dynamic = 'force-dynamic'

export async function POST(req: NextRequest) {
  try {
    const json = await req.json().catch(() => null)
    const parsed = Body.safeParse(json)
    if (!parsed.success) throw new ApiError('VALIDATION', 'invalid body', 422, parsed.error.flatten())
    const b = parsed.data
    const url = req.nextUrl
    const commit = url.searchParams.get('commit') === 'true'

    // 验证 env_id 存在
    const envs = await queryCrossSchema<{ env_id: string }>(
      `SELECT env_id FROM public.environments WHERE env_id = $1 LIMIT 1`,
      [b.envId],
    )
    if (envs.length === 0) {
      throw new ApiError('FORBIDDEN', `env_id "${b.envId}" 不存在，请先在 /admin/tables 登记`, 422)
    }

    // 验证 recorder_id 存在
    const cs = await queryCrossSchema<{ id: string }>(
      `SELECT id FROM public.recorders WHERE id = $1 LIMIT 1`,
      [b.recorderId],
    )
    if (cs.length === 0) {
      throw new ApiError('FORBIDDEN', `recorder_id "${b.recorderId}" 不存在，请先在 /admin/tables 登记`, 422)
    }

    const meta = DEVICE_META[b.deviceCode]!
    const now = new Date().toISOString()

    // dry-run：返回将写入的字段
    if (!commit) {
      return NextResponse.json({
        ok: true,
        data: {
          mode: 'dry-run',
          willInsert: {
            path: b.path,
            recorder_id: b.recorderId,
            env_id: b.envId,
            device_id: b.deviceCode,
            file_type: meta.fileType,
            duration_sec: b.durationSec ? String(b.durationSec) : null,
            file_size_bytes: b.fileSizeBytes ?? null,
            fps: b.fps ?? null,
            frame_count: b.frameCount ?? null,
            folder_name: b.folderName ?? null,
            storage_provider: 'cos',
            scan_date: now,
            uploaded: 'No',
            extra_description: b.notes ?? null,
          },
        },
      })
    }

    // commit：真插入
    const result = await queryCrossSchema<{ path: string }>(
      `INSERT INTO public.videos
        (path, recorder_id, env_id, device_id, file_type, duration_sec,
         file_size_bytes, fps, frame_count, folder_name, storage_provider,
         scan_date, uploaded, extra_description)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
       ON CONFLICT (path) DO NOTHING
       RETURNING path`,
      [
        b.path,
        b.recorderId,
        b.envId,
        b.deviceCode,
        meta.fileType,
        b.durationSec ? String(b.durationSec) : null,
        b.fileSizeBytes ?? null,
        b.fps ?? null,
        b.frameCount ?? null,
        b.folderName ?? null,
        'cos',
        now,
        'No',
        b.notes ?? null,
      ],
    )
    const inserted = result.length > 0
    return NextResponse.json({
      ok: true,
      data: {
        mode: 'commit',
        inserted,
        path: b.path,
        captureMode: meta.captureMode,
        fileType: meta.fileType,
      },
    })
  } catch (err) {
    if (err instanceof ApiError) return fail(err.code, err.message, err.status, err.details)
    console.error('[uploader/devices] error:', err)
    return handleApiError(err)
  }
}

// GET /api/uploader/devices — 列出可选 env_id / device_code（前端填表用）
export async function GET() {
  try {
    const envs = await queryCrossSchema<{ env_id: string; scene: string; environment: string }>(
      `SELECT env_id, scene, environment FROM public.environments ORDER BY env_id LIMIT 200`,
    )
    const cs = await queryCrossSchema<{ id: string; name: string }>(
      `SELECT id, name FROM public.recorders ORDER BY id LIMIT 200`,
    )
    return NextResponse.json({
      ok: true,
      data: {
        devices: [
          { code: 'dji_gopro_dcim', label: '大疆 GoPro DCIM（单 mp4）' },
          { code: 'head_mounted_hmd', label: '头戴 HMD（hmd + json，stereo）' },
          { code: 'gopro_session_mcap', label: 'GoPro Session MCAP（mcap，depth）' },
          { code: 'generic-avi_recording', label: 'Generic AVI 录制（多 avi）' },
        ],
        environments: envs,
        recorders: cs,
      },
    })
  } catch (err) {
    console.error('[uploader/devices GET] error:', err)
    return handleApiError(err)
  }
}