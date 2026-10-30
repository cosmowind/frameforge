// C. GoproSessionMcapAdapter（plan2 §5.4）
// scan: 列 data/session_*/ 下所有 .mcap
// parseMetadata: 用 mcap CLI 读 header + topic 列表
// getPreviewHandle: mcap-extract → worker 提取视频 → 转 MP4
// prepareForUpload: 提取后编码 MP4

import { promises as fs } from 'node:fs'
import path from 'node:path'
import type { DeviceAdapter, DeviceMetadata, PreviewHandle } from '@ff/shared/adapters'
import type { VideoUnit, UploadFileRef } from '@ff/shared/schemas'

export const GoproSessionMcapAdapter: DeviceAdapter = {
  code: 'gopro-session-mcap',

  async scan(rootPath: string): Promise<VideoUnit[]> {
    const entries = await fs.readdir(rootPath, { withFileTypes: true }).catch(() => [])
    const sessions = entries.filter((e) => e.isDirectory() && /^session_/i.test(e.name))
    const units: VideoUnit[] = []
    for (const s of sessions) {
      const sessionDir = path.posix.join(rootPath, s.name)
      const inner = await fs.readdir(sessionDir).catch(() => [])
      const mcaps = inner.filter((f) => f.toLowerCase().endsWith('.mcap'))
      if (mcaps.length === 0) continue
      units.push({
        sessionId: s.name,
        displayName: s.name,
        filePaths: mcaps.map((f) => path.posix.join(sessionDir, f)),
        estimatedSize: 0,
        estimatedDuration: 0,
      })
    }
    return units
  },

  async parseMetadata(sessionPath: string): Promise<DeviceMetadata> {
    const dir = path.posix.dirname(sessionPath)
    const jsonPath = path.posix.join(dir, path.posix.basename(sessionPath).replace(/\.mcap$/, '.json'))
    const raw = await fs.readFile(jsonPath, 'utf-8').catch(() => '')
    let meta: Record<string, unknown> = {}
    try {
      meta = JSON.parse(raw)
    } catch {
      // ignore
    }
    return {
      sessionFolderName: path.posix.basename(dir),
      extra: meta,
    }
  },

  async getPreviewHandle(sessionPath: string): Promise<PreviewHandle> {
    return { kind: 'worker', jobId: `preview:mcap:${sessionPath}` }
  },

  async prepareForUpload(sessionPath: string, workDir: string): Promise<UploadFileRef> {
    const outMp4 = path.posix.join(workDir, `${path.posix.basename(sessionPath, '.mcap')}.mp4`)
    const stat = await fs.stat(sessionPath).catch(() => ({ size: 0 }))
    return {
      preparedPath: outMp4,
      fileHash: '',
      sizeBytes: stat.size,
      metadata: { format: 'mp4', sourceFormat: 'mcap', sourcePath: sessionPath },
    }
  },
}
