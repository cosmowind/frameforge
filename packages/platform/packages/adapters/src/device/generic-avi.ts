// D. Generic AVIRecordingAdapter（plan2 §5.4 — 多 AVI）
// scan: 列 recordings/<date>_<timestamp>/ 下所有 .avi + .idx
// parseMetadata: 读 N 个 AVI 时长合并
// getPreviewHandle: native（前端 JS 控制 <video> 顺序切换）
// prepareForUpload: worker ffmpeg -f concat list.txt -c copy out.mp4

import { promises as fs } from 'node:fs'
import path from 'node:path'
import type { DeviceAdapter, DeviceMetadata, PreviewHandle } from '@ff/shared/adapters'
import type { VideoUnit, UploadFileRef } from '@ff/shared/schemas'

export const Generic AVIRecordingAdapter: DeviceAdapter = {
  code: 'generic-avi-recording',

  async scan(rootPath: string): Promise<VideoUnit[]> {
    const entries = await fs.readdir(rootPath, { withFileTypes: true }).catch(() => [])
    const sessions = entries.filter((e) => e.isDirectory() && /^\d{4}-\d{2}-\d{2}_/.test(e.name))
    const units: VideoUnit[] = []
    for (const s of sessions) {
      const sessionDir = path.posix.join(rootPath, s.name)
      const inner = await fs.readdir(sessionDir).catch(() => [])
      // 按 part 编号排序
      const avis = inner
        .filter((f) => f.toLowerCase().endsWith('.avi'))
        .sort()
      if (avis.length === 0) continue
      units.push({
        sessionId: s.name,
        displayName: s.name,
        filePaths: avis.map((f) => path.posix.join(sessionDir, f)),
        estimatedSize: 0,
        estimatedDuration: 0,
        // 标记多 part
        thumbnailPath: undefined,
      })
    }
    return units
  },

  async parseMetadata(sessionPath: string): Promise<DeviceMetadata> {
    // Phase 1 由 worker 用 ffmpeg 读 N 个 AVI 的 metadata 后合并
    return {
      sessionFolderName: path.posix.basename(path.posix.dirname(sessionPath)),
      extra: { multiPart: true, sourcePath: sessionPath },
    }
  },

  async getPreviewHandle(sessionPath: string): Promise<PreviewHandle> {
    // 多 AVI 顺序播放：返回首个 AVI 路径，前端 JS 控制
    return { kind: 'native', fileUrl: `file://${sessionPath}` }
  },

  async prepareForUpload(sessionPath: string, workDir: string): Promise<UploadFileRef> {
    // Phase 1：worker 端用 ffmpeg concat 输出单 MP4
    const outMp4 = path.posix.join(workDir, `${path.posix.basename(path.posix.dirname(sessionPath))}.mp4`)
    return {
      preparedPath: outMp4,
      fileHash: '',
      sizeBytes: 0,
      metadata: { format: 'mp4', sourceFormat: 'avi', multiPart: true },
    }
  },
}
