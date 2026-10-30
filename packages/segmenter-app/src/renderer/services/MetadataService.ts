import { SegmentMetadata, VideoSegment } from '../types';
import { getFileNameWithoutExtension } from '../utils';

export interface IMetadataService {
  saveMetadata(metadata: SegmentMetadata, filePath?: string): Promise<string>;
  loadMetadata(filePath?: string): Promise<SegmentMetadata>;
  validateMetadata(metadata: unknown): metadata is SegmentMetadata;
  exportReviewReport(metadata: SegmentMetadata): Promise<string>;
}

export class MetadataService implements IMetadataService {
  private static readonly METADATA_VERSION = '1.0.0';

  /**
   * 保存元数据到JSON文件
   */
  async saveMetadata(metadata: SegmentMetadata, filePath?: string): Promise<string> {
    if (!window.electronAPI) {
      throw new Error('Electron API 不可用');
    }

    try {
      // 更新修改时间
      const updatedMetadata = {
        ...metadata,
        modifiedAt: new Date(),
      };

      const jsonString = JSON.stringify(updatedMetadata, null, 2);
      const savedPath = await window.electronAPI.saveMetadataFile(jsonString);
      
      if (!savedPath) {
        throw new Error('用户取消保存操作');
      }

      return savedPath;
    } catch (error) {
      console.error('保存元数据失败:', error);
      throw new Error('保存元数据文件失败：' + (error as Error).message);
    }
  }

  /**
   * 从JSON文件加载元数据
   */
  async loadMetadata(filePath?: string): Promise<SegmentMetadata> {
    if (!window.electronAPI) {
      throw new Error('Electron API 不可用');
    }

    try {
      let selectedPath = filePath;
      if (!selectedPath) {
        selectedPath = await window.electronAPI.selectMetadataFile();
        if (!selectedPath) {
          throw new Error('用户取消选择操作');
        }
      }

      // 读取文件内容
      const jsonString = await window.electronAPI.readFile(selectedPath);
      
      // 解析并验证元数据
      const metadata = MetadataService.parseMetadata(jsonString);
      
      return metadata;
    } catch (error) {
      console.error('加载元数据失败:', error);
      if (error instanceof Error) {
        throw error;
      }
      throw new Error('加载元数据文件失败');
    }
  }

  /**
   * 验证元数据格式是否正确
   */
  validateMetadata(metadata: unknown): metadata is SegmentMetadata {
    if (!metadata || typeof metadata !== 'object') {
      return false;
    }

    const meta = metadata as any;

    // 检查必需字段
    if (
      typeof meta.version !== 'string' ||
      typeof meta.sourceVideoName !== 'string' ||
      typeof meta.sourceVideoDuration !== 'number' ||
      !Array.isArray(meta.segments)
    ) {
      return false;
    }

    // 检查日期字段
    if (meta.createdAt && !(meta.createdAt instanceof Date) && typeof meta.createdAt !== 'string') {
      return false;
    }

    if (meta.modifiedAt && !(meta.modifiedAt instanceof Date) && typeof meta.modifiedAt !== 'string') {
      return false;
    }

    // 检查片段数组
    for (const segment of meta.segments) {
      if (!this.validateSegment(segment)) {
        return false;
      }
    }

    return true;
  }

  /**
   * 验证单个片段格式
   */
  private validateSegment(segment: unknown): segment is VideoSegment {
    if (!segment || typeof segment !== 'object') {
      return false;
    }

    const seg = segment as any;

    return (
      typeof seg.id === 'string' &&
      typeof seg.startTime === 'number' &&
      typeof seg.endTime === 'number' &&
      typeof seg.duration === 'number' &&
      typeof seg.index === 'number' &&
      typeof seg.isValid === 'boolean' &&
      Array.isArray(seg.warnings) &&
      seg.startTime >= 0 &&
      seg.endTime > seg.startTime &&
      seg.duration === seg.endTime - seg.startTime
    );
  }

  /**
   * 导出审核报告
   */
  async exportReviewReport(metadata: SegmentMetadata): Promise<string> {
    const problemSegments = metadata.segments.filter(
      segment => segment.annotation?.hasIssue || !segment.isValid
    );

    const report = {
      reportVersion: '1.0.0',
      generatedAt: new Date(),
      sourceVideo: metadata.sourceVideoName,
      totalSegments: metadata.segments.length,
      problemSegments: problemSegments.length,
      segments: problemSegments.map(segment => ({
        index: segment.index,
        startTime: segment.startTime,
        endTime: segment.endTime,
        duration: segment.duration,
        isValid: segment.isValid,
        warnings: segment.warnings,
        annotation: segment.annotation,
      })),
    };

    const jsonString = JSON.stringify(report, null, 2);
    
    if (!window.electronAPI) {
      throw new Error('Electron API 不可用');
    }

    const savedPath = await window.electronAPI.saveMetadataFile(jsonString);
    if (!savedPath) {
      throw new Error('用户取消保存操作');
    }

    return savedPath;
  }

  /**
   * 创建新的元数据对象
   */
  static createMetadata(
    sourceVideoName: string,
    sourceVideoDuration: number,
    segments: VideoSegment[] = []
  ): SegmentMetadata {
    return {
      version: MetadataService.METADATA_VERSION,
      sourceVideoName,
      sourceVideoDuration,
      createdAt: new Date(),
      modifiedAt: new Date(),
      segments: [...segments],
    };
  }

  /**
   * 根据视频文件名生成默认的元数据文件名
   */
  static generateMetadataFileName(videoFileName: string): string {
    const nameWithoutExt = getFileNameWithoutExtension(videoFileName);
    return `${nameWithoutExt}-metadata.json`;
  }

  /**
   * 检查元数据文件是否与视频文件匹配
   */
  static isMetadataMatchingVideo(metadataFileName: string, videoFileName: string): boolean {
    const videoNameWithoutExt = getFileNameWithoutExtension(videoFileName);
    const expectedMetadataName = `${videoNameWithoutExt}-metadata.json`;
    return metadataFileName.toLowerCase() === expectedMetadataName.toLowerCase();
  }

  /**
   * 解析JSON字符串为元数据对象
   */
  static parseMetadata(jsonString: string): SegmentMetadata {
    try {
      const parsed = JSON.parse(jsonString);
      
      // 转换日期字符串为Date对象
      if (parsed.createdAt && typeof parsed.createdAt === 'string') {
        parsed.createdAt = new Date(parsed.createdAt);
      }
      if (parsed.modifiedAt && typeof parsed.modifiedAt === 'string') {
        parsed.modifiedAt = new Date(parsed.modifiedAt);
      }

      const service = new MetadataService();
      if (!service.validateMetadata(parsed)) {
        throw new Error('元数据格式不正确');
      }

      return parsed as SegmentMetadata;
    } catch (error) {
      if (error instanceof SyntaxError) {
        throw new Error('JSON格式错误：' + error.message);
      }
      throw error;
    }
  }
}

export default MetadataService;