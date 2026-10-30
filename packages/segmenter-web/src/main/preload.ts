import { contextBridge, ipcRenderer } from 'electron';

// 暴露 API 给渲染进程
contextBridge.exposeInMainWorld('electronAPI', {
  // 文件操作
  selectVideoFile: () => ipcRenderer.invoke('select-video-file'),
  selectMetadataFile: () => ipcRenderer.invoke('select-metadata-file'),
  selectOutputDirectory: () => ipcRenderer.invoke('select-output-directory'),
  saveMetadataFile: (data: string) => ipcRenderer.invoke('save-metadata-file', data),
  readFile: (filePath: string) => ipcRenderer.invoke('read-file', filePath),
  
  // 视频操作
  extractVideoInfo: (videoPath: string) => ipcRenderer.invoke('extract-video-info', videoPath),
  checkSegmentsFile: (videoPath: string) => ipcRenderer.invoke('check-segments-file', videoPath),
  splitVideo: (inputPath: string, segments: any[], outputDir: string, metadata?: any) => 
    ipcRenderer.invoke('split-video', inputPath, segments, outputDir, metadata),
  rotateVideo: (inputPath: string, angle: number, clockwise: boolean) => 
    ipcRenderer.invoke('rotate-video', inputPath, angle, clockwise),
  
  // 进度监听
  onSplitProgress: (callback: (progress: any) => void) => {
    ipcRenderer.on('split-progress', (_, progress) => callback(progress));
  },
  
  // 环境信息
  isElectron: true,
  platform: process.platform,
});
