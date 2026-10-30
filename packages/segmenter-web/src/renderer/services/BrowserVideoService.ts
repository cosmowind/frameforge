import { VideoInfo } from '../types';
import BrowserFileService from './BrowserFileService';

export class BrowserVideoService {
  /**
   * 从视频文件提取信息（不检测编码，直接返回）
   */
  static async extractVideoInfo(file: File): Promise<VideoInfo> {
    // 验证文件是否为 MP4 格式
    if (!this.isMP4File(file)) {
      throw new Error('只支持MP4格式的视频文件');
    }

    return new Promise((resolve) => {
      const video = document.createElement('video');
      const url = URL.createObjectURL(file);

      video.onloadedmetadata = () => {
        const videoInfo: VideoInfo = {
          filename: file.name,
          path: '',
          duration: video.duration,
          width: video.videoWidth,
          height: video.videoHeight,
          codec: 'unknown', // 先不检测，播放时再判断
          bitrate: 0,
          size: file.size,
          file: file,
          url: url,
        };
        resolve(videoInfo);
      };

      video.onerror = () => {
        URL.revokeObjectURL(url);
        // 加载失败也返回视频信息，让用户可以尝试播放
        const videoInfo: VideoInfo = {
          filename: file.name,
          path: '',
          duration: 0,
          width: 0,
          height: 0,
          codec: 'unknown',
          bitrate: 0,
          size: file.size,
          file: file,
          url: url,
        };
        resolve(videoInfo);
      };

      video.src = url;
    });
  }

  /**
   * 验证文件是否为MP4格式
   */
  static isMP4File(file: File): boolean {
    return file.type === 'video/mp4' || file.name.toLowerCase().endsWith('.mp4');
  }

  /**
   * 格式化文件大小
   */
  static formatFileSize(bytes: number): string {
    return BrowserFileService.formatFileSize(bytes);
  }

  /**
   * 格式化视频时长
   */
  static formatDuration(seconds: number): string {
    return BrowserFileService.formatDuration(seconds);
  }

  /**
   * 验证视频文件大小和时长
   */
  static validateVideo(videoInfo: VideoInfo): { isValid: boolean; warnings: string[] } {
    const warnings: string[] = [];
    
    const minSize = 500 * 1024 * 1024;
    const maxSize = 5 * 1024 * 1024 * 1024;
    
    if (videoInfo.size && videoInfo.size < minSize) {
      warnings.push('视频文件较小，可能质量不佳');
    }
    
    if (videoInfo.size && videoInfo.size > maxSize) {
      warnings.push('视频文件过大，处理可能较慢');
    }
    
    if (videoInfo.duration < 30) {
      warnings.push('视频时长较短，分割片段可能有限');
    }
    
    if (videoInfo.duration > 300) {
      warnings.push('视频时长较长，建议分段处理');
    }
    
    return {
      isValid: warnings.length === 0,
      warnings
    };
  }
}

export default BrowserVideoService;
