export interface ElectronAPI {
  selectVideoFile: () => Promise<string | null>;
  selectMetadataFile: () => Promise<string | null>;
  saveMetadataFile: (data: string) => Promise<string | null>;
  readFile: (filePath: string) => Promise<string>;
  selectOutputDirectory: () => Promise<string | null>;
  extractVideoInfo: (path: string) => Promise<VideoInfo>;
  generatePreview: (videoPath: string, duration: number) => Promise<string>;
  checkSegmentsFile: (videoPath: string) => Promise<string | null>;
  splitVideo: (
    inputPath: string,
    segments: any[],
    outputDir: string,
    metadata?: any
  ) => Promise<SplitResult>;
  onProgress: (callback: (progress: ProgressInfo) => void) => void;
  removeProgressListener: () => void;
  onPreviewProgress: (callback: (percent: number) => void) => void;
  removePreviewProgressListener: () => void;
}

export interface VideoInfo {
  filename: string;
  path: string;
  duration: number;
  width: number;
  height: number;
  codec: string;
  bitrate: number;
  size?: number; // 文件大小（字节）
  previewPath?: string; // H.264 预览文件路径（用于不支持的编码如 HEVC）
}

export interface ProgressInfo {
  currentSegment: number;
  totalSegments: number;
  percentage: number;
  currentFile: string;
}

export interface SplitResult {
  success: boolean;
  outputFiles: string[];
  errors: string[];
  outputFolder?: string;
}

declare global {
  interface Window {
    electronAPI: ElectronAPI;
  }
}
