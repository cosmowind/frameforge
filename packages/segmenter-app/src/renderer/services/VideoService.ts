import { VideoInfo } from '../types';

export class VideoService {
  /**
   * 选择视频文件
   */
  static async selectVideoFile(): Promise<string | null> {
    if (!window.electronAPI) {
      throw new Error('Electron API 不可用');
    }
    
    return await window.electronAPI.selectVideoFile();
  }

  /**
   * 提取视频信息
   */
  static async extractVideoInfo(videoPath: string): Promise<VideoInfo> {
    if (!window.electronAPI) {
      throw new Error('Electron API 不可用');
    }
    
    // 首先验证文件是否为MP4格式
    if (!this.isMP4File(videoPath)) {
      throw new Error('只支持MP4格式的视频文件');
    }
    
    try {
      const videoInfo = await window.electronAPI.extractVideoInfo(videoPath);
      return videoInfo;
    } catch (error) {
      console.error('提取视频信息失败:', error);
      throw new Error('无法读取视频文件信息，请确保文件未损坏');
    }
  }

  /**
   * 验证文件是否为MP4格式
   */
  static isMP4File(filePath: string): boolean {
    return filePath.toLowerCase().endsWith('.mp4');
  }

  /**
   * 格式化文件大小
   */
  static formatFileSize(bytes: number): string {
    const sizes = ['B', 'KB', 'MB', 'GB'];
    if (bytes === 0) return '0 B';
    
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
  }

  /**
   * 格式化视频时长
   */
  static formatDuration(seconds: number): string {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hours > 0) {
      return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
  }

  /**
   * 验证视频文件大小和时长
   */
  static validateVideo(videoInfo: VideoInfo): { isValid: boolean; warnings: string[] } {
    const warnings: string[] = [];
    
    // 检查文件大小（500MB - 5GB）
    const minSize = 500 * 1024 * 1024; // 500MB
    const maxSize = 5 * 1024 * 1024 * 1024; // 5GB
    
    if (videoInfo.size && videoInfo.size < minSize) {
      warnings.push('视频文件较小，可能质量不佳');
    }
    
    if (videoInfo.size && videoInfo.size > maxSize) {
      warnings.push('视频文件过大，处理可能较慢');
    }
    
    // 检查时长（30秒 - 5分钟）
    if (videoInfo.duration < 30) {
      warnings.push('视频时长较短，分割片段可能有限');
    }
    
    if (videoInfo.duration > 300) { // 5分钟
      warnings.push('视频时长较长，建议分段处理');
    }
    
    return {
      isValid: warnings.length === 0,
      warnings
    };
  }
}

export default VideoService;