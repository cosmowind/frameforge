import { VideoSegment, ValidationResult } from '../types';
import ValidationService from './ValidationService';

export interface ISegmentManager {
  createSegment(startTime: number, endTime: number): VideoSegment;
  updateSegment(segmentId: string, updates: Partial<VideoSegment>): void;
  deleteSegment(segmentId: string): void;
  splitSegment(segmentId: string): [VideoSegment, VideoSegment];
  validateSegment(segment: VideoSegment): ValidationResult;
  getAllSegments(): VideoSegment[];
  getSegmentById(id: string): VideoSegment | null;
}

class SegmentManager implements ISegmentManager {
  private segments: VideoSegment[] = [];
  private nextIndex = 1;
  private validationService: ValidationService;

  constructor(initialSegments: VideoSegment[] = []) {
    this.segments = [...initialSegments];
    this.validationService = new ValidationService();
    this.updateIndices();
  }

  createSegment(startTime: number, endTime: number): VideoSegment {
    const id = `segment-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const duration = this.validationService.calculateDuration(startTime, endTime);
    
    const segment: VideoSegment = {
      id,
      startTime,
      endTime,
      duration,
      index: this.nextIndex++,
      isValid: this.validationService.isValidDuration(duration),
      warnings: this.validationService.getValidationWarnings({
        id,
        startTime,
        endTime,
        duration,
        index: this.nextIndex - 1,
        isValid: false, // 临时值，下面会更新
        warnings: [],
      }),
    };

    // 更新isValid状态
    segment.isValid = this.validationService.isValidDuration(duration) && segment.warnings.length === 0;

    this.segments.push(segment);
    this.sortSegmentsByTime();
    this.updateIndices();
    
    return segment;
  }

  updateSegment(segmentId: string, updates: Partial<VideoSegment>): void {
    const segmentIndex = this.segments.findIndex(s => s.id === segmentId);
    if (segmentIndex === -1) {
      throw new Error(`Segment with id ${segmentId} not found`);
    }

    const segment = this.segments[segmentIndex];
    const updatedSegment = { ...segment, ...updates };
    
    // 重新计算时长和验证状态
    if (updates.startTime !== undefined || updates.endTime !== undefined) {
      updatedSegment.duration = this.validationService.calculateDuration(
        updatedSegment.startTime, 
        updatedSegment.endTime
      );
      updatedSegment.warnings = this.validationService.getValidationWarnings(updatedSegment);
      updatedSegment.isValid = this.validationService.isValidDuration(updatedSegment.duration) && 
                              updatedSegment.warnings.length === 0;
    }

    this.segments[segmentIndex] = updatedSegment;
    this.sortSegmentsByTime();
    this.updateIndices();
  }

  deleteSegment(segmentId: string): void {
    const initialLength = this.segments.length;
    this.segments = this.segments.filter(s => s.id !== segmentId);
    
    if (this.segments.length === initialLength) {
      throw new Error(`Segment with id ${segmentId} not found`);
    }
    
    this.updateIndices();
  }

  splitSegment(segmentId: string): [VideoSegment, VideoSegment] {
    const segment = this.getSegmentById(segmentId);
    if (!segment) {
      throw new Error(`Segment with id ${segmentId} not found`);
    }

    const midTime = (segment.startTime + segment.endTime) / 2;
    
    // 创建两个新片段
    const firstSegment = this.createSegment(segment.startTime, midTime);
    const secondSegment = this.createSegment(midTime, segment.endTime);
    
    // 删除原片段
    this.deleteSegment(segmentId);
    
    return [firstSegment, secondSegment];
  }

  validateSegment(segment: VideoSegment): ValidationResult {
    return this.validationService.validateSegment(segment);
  }

  getAllSegments(): VideoSegment[] {
    return [...this.segments];
  }

  getSegmentById(id: string): VideoSegment | null {
    return this.segments.find(s => s.id === id) || null;
  }

  // 私有辅助方法
  private sortSegmentsByTime(): void {
    this.segments.sort((a, b) => a.startTime - b.startTime);
  }

  private updateIndices(): void {
    this.segments.forEach((segment, index) => {
      segment.index = index + 1;
    });
    this.nextIndex = this.segments.length + 1;
  }

  // 获取当前片段数组的副本（用于状态管理）
  getSegmentsSnapshot(): VideoSegment[] {
    return this.getAllSegments();
  }

  // 设置新的片段数组（用于从外部更新）
  setSegments(segments: VideoSegment[]): void {
    this.segments = [...segments];
    this.sortSegmentsByTime();
    this.updateIndices();
  }

  // 验证所有片段
  validateAllSegments(): ValidationResult {
    return this.validationService.validateAllSegments(this.segments);
  }

  // 检查是否可以执行分割
  canExecuteSegmentation(): { canExecute: boolean; issues: string[] } {
    return this.validationService.canExecuteSegmentation(this.segments);
  }

  // 获取验证统计信息
  getValidationStats() {
    return this.validationService.getValidationStats(this.segments);
  }

  // 获取修复建议
  getSuggestions(): string[] {
    return this.validationService.getSuggestions(this.segments);
  }
}

export default SegmentManager;