import { VideoSegment, SplitResult, ProgressInfo } from '../types';

// 检测是否在 Electron 环境中
const isElectron = () => {
  return typeof window !== 'undefined' && 
         (window as any).electronAPI?.isElectron === true;
};

export class FFmpegService {
  private loaded: boolean = false;

  /**
   * 加载 FFmpeg（Electron 环境下直接使用系统 FFmpeg）
   */
  async load(): Promise<void> {
    if (isElectron()) {
      // Electron 环境下不需要加载 WASM
      this.loaded = true;
      console.log('使用系统原生 FFmpeg');
      return;
    }

    // Web 环境下需要加载 WASM（但当前不支持）
    throw new Error('Web 环境暂不支持视频分割，请使用 Electron 版本');
  }

  /**
   * 分割视频
   */
  async splitVideo(
    file: File | string,
    segments: VideoSegment[],
    _onProgress?: (progress: ProgressInfo) => void
  ): Promise<SplitResult> {
    if (!isElectron()) {
      return {
        success: false,
        outputFiles: [],
        errors: ['请使用 Electron 版本进行视频分割'],
      };
    }

    try {
      await this.load();

      const electronAPI = (window as any).electronAPI;
      
      // 获取视频文件路径
      let inputPath: string;
      if (typeof file === 'string') {
        inputPath = file;
      } else {
        // 从 File 对象获取路径（Electron 中 File 对象有 path 属性）
        inputPath = (file as any).path;
      }

      if (!inputPath) {
        return {
          success: false,
          outputFiles: [],
          errors: ['无法获取视频文件路径'],
        };
      }

      // 获取输出目录（视频所在目录）
      const outputDir = inputPath.substring(0, inputPath.lastIndexOf('\\') || inputPath.lastIndexOf('/'));

      console.log('调用 Electron 分割视频:', { inputPath, segments: segments.length, outputDir });

      // 调用 Electron 主进程进行分割
      const result = await electronAPI.splitVideo(inputPath, segments, outputDir);

      return result;
    } catch (error) {
      console.error('视频分割失败:', error);
      return {
        success: false,
        outputFiles: [],
        errors: [(error as Error).message],
      };
    }
  }

  /**
   * 格式化时间为 HH:MM:SS.mmm
   */
  formatTime(seconds: number): string {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toFixed(3).padStart(6, '0')}`;
  }

  /**
   * 检查是否已加载
   */
  isLoaded(): boolean {
    return this.loaded;
  }

  /**
   * 终止 FFmpeg
   */
  terminate(): void {
    this.loaded = false;
  }
}

// 创建单例
export const ffmpegService = new FFmpegService();
export default ffmpegService;
