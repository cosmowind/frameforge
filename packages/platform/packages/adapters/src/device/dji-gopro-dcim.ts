// A. DjiGoproDcimAdapter（plan2 §5.4 — 最简单）
// scan: 列 DCIM/ 下所有 .mp4，按文件名排序
// parseMetadata: 从 MP4 容器读时长、分辨率
// getPreviewHandle: native → file:// URL
// prepareForUpload: 直接返回原 MP4 路径（无需处理）

import { promises as fs } from 'node:fs'
import path from 'node:path'
import type { DeviceAdapter, DeviceMetadata, PreviewHandle } from '@ff/shared/adapters'
import type { VideoUnit, UploadFileRef } from '@ff/shared/schemas'

export const DjiGoproDcimAdapter: DeviceAdapter = {
  code: 'dji-gopro-dcim',

  async scan(rootPath: string): Promise<VideoUnit[]> {
    const entries = await fs.readdir(rootPath, { withFileTypes: true }).catch(() => [])
    const mp4s = entries
      .filter((e) => e.isFile() && e.name.toLowerCase().endsWith('.mp4'))
      .map((e) => e.name)
      .sort()
    return mp4s.map((name) => {
      const filePath = path.posix.join(rootPath, name)
      return {
        sessionId: name.replace(/\.mp4$/i, ''),
        displayName: name,
        filePaths: [filePath],
        estimatedSize: 0,
        estimatedDuration: 0,
      }
    })
  },

  async parseMetadata(sessionPath: string): Promise<DeviceMetadata> {
    // Phase 1 由 worker 调 fluent-ffmpeg 读 metadata
    // 现在 Phase 0 占位
    return {
      sessionFolderName: path.posix.basename(sessionPath),
      durationSec: null,
      resolution: null,
      codec: null,
      extra: { adapter: 'dji-gopro-dcim' },
    }
  },

  async getPreviewHandle(sessionPath: string): Promise<PreviewHandle> {
    return { kind: 'native', fileUrl: `file://${sessionPath}` }
  },

  async prepareForUpload(sessionPath: string, _workDir: string): Promise<UploadFileRef> {
    const stat = await fs.stat(sessionPath)
    return {
      preparedPath: sessionPath, // MP4 直接传
      fileHash: '', // Phase 1 由 worker 计算
      sizeBytes: stat.size,
      metadata: { format: 'mp4' },
    }
  },
}
