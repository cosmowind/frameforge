// B. HeadMountedHmdAdapter（plan2 §5.4 — 最复杂）
// scan: 列 hmd/session_*/ 下所有 .hmd 文件
// parseMetadata: 读 .json 元数据（姿态 + 传感器时间戳）
// getPreviewHandle: hmd-decoder → worker 异步转 MP4
// prepareForUpload: worker 端调 HMD decoder → 提取视频 + 编码 MP4

import { promises as fs } from 'node:fs'
import path from 'node:path'
import type { DeviceAdapter, DeviceMetadata, PreviewHandle } from '@ff/shared/adapters'
import type { VideoUnit, UploadFileRef } from '@ff/shared/schemas'

export const HeadMountedHmdAdapter: DeviceAdapter = {
  code: 'head-mounted-hmd',

  async scan(rootPath: string): Promise<VideoUnit[]> {
    const entries = await fs.readdir(rootPath, { withFileTypes: true }).catch(() => [])
    const sessions = entries.filter((e) => e.isDirectory() && /^session_/i.test(e.name))
    const units: VideoUnit[] = []
    for (const s of sessions) {
      const sessionDir = path.posix.join(rootPath, s.name)
      const inner = await fs.readdir(sessionDir).catch(() => [])
      const hmds = inner.filter((f) => f.toLowerCase().endsWith('.hmd'))
      if (hmds.length === 0) continue
      units.push({
        sessionId: s.name,
        displayName: s.name,
        filePaths: hmds.map((f) => path.posix.join(sessionDir, f)),
        estimatedSize: 0,
        estimatedDuration: 0,
      })
    }
    return units
  },

  async parseMetadata(sessionPath: string): Promise<DeviceMetadata> {
    // 解析同目录下的 .json
    const dir = path.posix.dirname(sessionPath)
    const jsonPath = path.posix.join(dir, path.posix.basename(sessionPath).replace(/\.hmd$/, '.json'))
    const raw = await fs.readFile(jsonPath, 'utf-8').catch(() => '')
    let meta: Record<string, unknown> = {}
    try {
      meta = JSON.parse(raw)
    } catch {
      // ignore
    }
    return {
      sessionFolderName: path.posix.basename(dir),
      recordedAt: typeof meta.timestamp === 'string' ? meta.timestamp : null,
      durationSec: typeof meta.durationSec === 'number' ? meta.durationSec : null,
      extra: meta,
    }
  },

  async getPreviewHandle(sessionPath: string): Promise<PreviewHandle> {
    // HMD 不能浏览器直接播，需 worker 转码
    return { kind: 'worker', jobId: `preview:${sessionPath}` }
  },

  async prepareForUpload(sessionPath: string, workDir: string): Promise<UploadFileRef> {
    // Phase 1 接 HMD decoder 提取为 MP4
    const outMp4 = path.posix.join(workDir, `${path.posix.basename(sessionPath, '.hmd')}.mp4`)
    const stat = await fs.stat(sessionPath).catch(() => ({ size: 0 }))
    return {
      preparedPath: outMp4,
      fileHash: '',
      sizeBytes: stat.size,
      metadata: { format: 'mp4', sourceFormat: 'hmd', sourcePath: sessionPath },
    }
  },
}
