import { contextBridge, ipcRenderer } from 'electron';

// 暴露安全的 API 给渲染进程
contextBridge.exposeInMainWorld('electronAPI', {
  // 文件操作
  selectVideoFile: () => ipcRenderer.invoke('select-video-file'),
  selectMetadataFile: () => ipcRenderer.invoke('select-metadata-file'),
  saveMetadataFile: (data: string) => ipcRenderer.invoke('save-metadata-file', data),
  readFile: (filePath: string) => ipcRenderer.invoke('read-file', filePath),
  selectOutputDirectory: () => ipcRenderer.invoke('select-output-directory'),

  // 视频处理
  extractVideoInfo: (path: string) => ipcRenderer.invoke('extract-video-info', path),
  generatePreview: (videoPath: string, duration: number) => ipcRenderer.invoke('generate-preview', videoPath, duration),
  checkSegmentsFile: (videoPath: string) => ipcRenderer.invoke('check-segments-file', videoPath),
  splitVideo: (inputPath: string, segments: any[], outputDir: string, metadata?: any) =>
    ipcRenderer.invoke('split-video', inputPath, segments, outputDir, metadata),

  // 进度监听
  onProgress: (callback: (progress: any) => void) => {
    ipcRenderer.on('split-progress', (_event, progress) => callback(progress));
  },
  removeProgressListener: () => {
    ipcRenderer.removeAllListeners('split-progress');
  },
  onPreviewProgress: (callback: (percent: number) => void) => {
    ipcRenderer.on('preview-progress', (_event, percent) => callback(percent));
  },
  removePreviewProgressListener: () => {
    ipcRenderer.removeAllListeners('preview-progress');
  },
});

export {};
