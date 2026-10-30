import { VideoInfo } from '../types';
import BrowserVideoService from './BrowserVideoService';
import BrowserFileService from './BrowserFileService';

export class VideoService {
  /**
   * 选择视频文件
   */
  static async selectVideoFile(): Promise<File | null> {
    return await BrowserFileService.selectVideoFile();
  }

  /**
   * 提取视频信息
   */
  static async extractVideoInfo(file: File): Promise<VideoInfo> {
    try {
      return await BrowserVideoService.extractVideoInfo(file);
    } catch (error) {
      console.error('提取视频信息失败:', error);
      throw new Error('无法读取视频文件信息，请确保文件未损坏');
    }
  }

  /**
   * 验证文件是否为MP4格式
   */
  static isMP4File(file: File): boolean {
    return BrowserVideoService.isMP4File(file);
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
    return BrowserVideoService.validateVideo(videoInfo);
  }
}

export default VideoService;