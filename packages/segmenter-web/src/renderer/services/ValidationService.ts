import { VideoSegment, ValidationResult } from '../types';

export interface IValidationService {
  validateSegment(segment: VideoSegment): ValidationResult;
  validateAllSegments(segments: VideoSegment[]): ValidationResult;
  calculateDuration(startTime: number, endTime: number): number;
  isValidDuration(duration: number): boolean;
  getValidationWarnings(segment: VideoSegment): string[];
  canExecuteSegmentation(segments: VideoSegment[]): { canExecute: boolean; issues: string[] };
}

export class ValidationService implements IValidationService {
  // 验证规则常量
  private static readonly MIN_DURATION = 5; // 最小时长（秒）
  private static readonly MAX_DURATION = 25; // 最大时长（秒）
  private static readonly MIN_TIME = 0; // 最小时间值

  /**
   * 验证单个片段
   */
  validateSegment(segment: VideoSegment): ValidationResult {
    const warnings: string[] = [];
    const errors: string[] = [];

    // 基本时间值验证
    if (segment.startTime < ValidationService.MIN_TIME) {
      errors.push('开始时间不能为负数');
    }

    if (segment.endTime <= segment.startTime) {
      errors.push('结束时间必须大于开始时间');
    }

    // 时长计算验证
    const calculatedDuration = this.calculateDuration(segment.startTime, segment.endTime);
    if (Math.abs(segment.duration - calculatedDuration) > 0.01) {
      errors.push('片段时长计算不正确');
    }

    // 时长范围验证
    if (segment.duration < ValidationService.MIN_DURATION) {
      warnings.push(`片段时长过短（${segment.duration.toFixed(1)}秒 < ${ValidationService.MIN_DURATION}秒）`);
    }

    if (segment.duration > ValidationService.MAX_DURATION) {
      warnings.push(`片段时长过长（${segment.duration.toFixed(1)}秒 > ${ValidationService.MAX_DURATION}秒）`);
    }

    // 索引验证
    if (segment.index < 1) {
      errors.push('片段索引必须大于0');
    }

    // ID验证
    if (!segment.id || segment.id.trim() === '') {
      errors.push('片段ID不能为空');
    }

    return {
      isValid: errors.length === 0 && warnings.length === 0,
      warnings,
      errors,
    };
  }

  /**
   * 验证所有片段
   */
  validateAllSegments(segments: VideoSegment[]): ValidationResult {
    const allWarnings: string[] = [];
    const allErrors: string[] = [];

    // 验证每个片段
    segments.forEach((segment) => {
      const result = this.validateSegment(segment);
      
      // 添加片段标识到错误和警告信息
      result.errors.forEach(error => {
        allErrors.push(`片段${segment.index}: ${error}`);
      });
      
      result.warnings.forEach(warning => {
        allWarnings.push(`片段${segment.index}: ${warning}`);
      });
    });

    // 检查片段重叠
    const overlaps = this.checkSegmentOverlaps(segments);
    overlaps.forEach(overlap => {
      allErrors.push(overlap);
    });

    // 检查索引连续性
    const indexIssues = this.checkIndexContinuity(segments);
    indexIssues.forEach(issue => {
      allWarnings.push(issue);
    });

    // 检查ID唯一性
    const duplicateIds = this.checkIdUniqueness(segments);
    duplicateIds.forEach(duplicate => {
      allErrors.push(duplicate);
    });

    return {
      isValid: allErrors.length === 0 && allWarnings.length === 0,
      warnings: allWarnings,
      errors: allErrors,
    };
  }

  /**
   * 计算片段时长
   */
  calculateDuration(startTime: number, endTime: number): number {
    return Math.max(0, endTime - startTime);
  }

  /**
   * 检查时长是否有效
   */
  isValidDuration(duration: number): boolean {
    return duration >= ValidationService.MIN_DURATION && 
           duration <= ValidationService.MAX_DURATION;
  }

  /**
   * 获取片段的验证警告
   */
  getValidationWarnings(segment: VideoSegment): string[] {
    const warnings: string[] = [];

    if (segment.duration < ValidationService.MIN_DURATION) {
      warnings.push('时长过短');
    }

    if (segment.duration > ValidationService.MAX_DURATION) {
      warnings.push('时长过长');
    }

    // 检查时长是否接近边界值
    if (segment.duration >= ValidationService.MIN_DURATION && 
        segment.duration <= ValidationService.MIN_DURATION + 1) {
      warnings.push('时长接近最小值');
    }

    if (segment.duration >= ValidationService.MAX_DURATION - 1 && 
        segment.duration <= ValidationService.MAX_DURATION) {
      warnings.push('时长接近最大值');
    }

    return warnings;
  }

  /**
   * 检查是否可以执行分割
   */
  canExecuteSegmentation(segments: VideoSegment[]): { canExecute: boolean; issues: string[] } {
    const issues: string[] = [];

    // 检查是否有片段
    if (segments.length === 0) {
      issues.push('没有可分割的片段');
      return { canExecute: false, issues };
    }

    // 验证所有片段
    const validation = this.validateAllSegments(segments);
    
    // 严重错误阻止执行
    if (validation.errors.length > 0) {
      issues.push('存在严重错误，无法执行分割：');
      issues.push(...validation.errors);
      return { canExecute: false, issues };
    }

    // 警告不阻止执行，但需要提醒用户
    if (validation.warnings.length > 0) {
      issues.push('存在以下警告：');
      issues.push(...validation.warnings);
    }

    // 检查无效片段数量
    const invalidSegments = segments.filter(s => !s.isValid);
    if (invalidSegments.length > 0) {
      issues.push(`${invalidSegments.length}个片段不符合时长要求（5-25秒）`);
    }

    return { 
      canExecute: true, 
      issues: issues.length > 0 ? issues : ['所有片段验证通过，可以执行分割'] 
    };
  }

  /**
   * 检查片段重叠
   */
  private checkSegmentOverlaps(segments: VideoSegment[]): string[] {
    const overlaps: string[] = [];
    
    // 按开始时间排序
    const sortedSegments = [...segments].sort((a, b) => a.startTime - b.startTime);
    
    for (let i = 0; i < sortedSegments.length - 1; i++) {
      const current = sortedSegments[i];
      const next = sortedSegments[i + 1];
      
      if (current.endTime > next.startTime) {
        overlaps.push(
          `片段${current.index}和片段${next.index}存在时间重叠 ` +
          `(${current.endTime.toFixed(1)}s > ${next.startTime.toFixed(1)}s)`
        );
      }
    }
    
    return overlaps;
  }

  /**
   * 检查索引连续性
   */
  private checkIndexContinuity(segments: VideoSegment[]): string[] {
    const issues: string[] = [];
    
    if (segments.length === 0) return issues;
    
    // 按索引排序
    const sortedByIndex = [...segments].sort((a, b) => a.index - b.index);
    
    // 检查是否从1开始
    if (sortedByIndex[0].index !== 1) {
      issues.push('片段索引应该从1开始');
    }
    
    // 检查是否连续
    for (let i = 1; i < sortedByIndex.length; i++) {
      const expected = sortedByIndex[i - 1].index + 1;
      if (sortedByIndex[i].index !== expected) {
        issues.push(`片段索引不连续：期望${expected}，实际${sortedByIndex[i].index}`);
      }
    }
    
    return issues;
  }

  /**
   * 检查ID唯一性
   */
  private checkIdUniqueness(segments: VideoSegment[]): string[] {
    const issues: string[] = [];
    const idCounts = new Map<string, number>();
    
    segments.forEach(segment => {
      const count = idCounts.get(segment.id) || 0;
      idCounts.set(segment.id, count + 1);
    });
    
    idCounts.forEach((count, id) => {
      if (count > 1) {
        issues.push(`重复的片段ID: ${id} (出现${count}次)`);
      }
    });
    
    return issues;
  }

  /**
   * 获取验证统计信息
   */
  getValidationStats(segments: VideoSegment[]): {
    total: number;
    valid: number;
    invalid: number;
    warnings: number;
    totalDuration: number;
    averageDuration: number;
  } {
    const valid = segments.filter(s => s.isValid).length;
    const invalid = segments.length - valid;
    const warnings = segments.reduce((sum, s) => sum + s.warnings.length, 0);
    const totalDuration = segments.reduce((sum, s) => sum + s.duration, 0);
    const averageDuration = segments.length > 0 ? totalDuration / segments.length : 0;

    return {
      total: segments.length,
      valid,
      invalid,
      warnings,
      totalDuration,
      averageDuration,
    };
  }

  /**
   * 获取建议的修复操作
   */
  getSuggestions(segments: VideoSegment[]): string[] {
    const suggestions: string[] = [];
    
    const stats = this.getValidationStats(segments);
    
    if (stats.invalid > 0) {
      suggestions.push(`建议调整${stats.invalid}个无效片段的时长到5-25秒范围内`);
    }
    
    if (stats.averageDuration < 10) {
      suggestions.push('平均片段时长较短，考虑合并一些相邻片段');
    }
    
    if (stats.averageDuration > 20) {
      suggestions.push('平均片段时长较长，考虑分割一些长片段');
    }
    
    const overlaps = this.checkSegmentOverlaps(segments);
    if (overlaps.length > 0) {
      suggestions.push('存在片段重叠，请调整片段边界');
    }
    
    return suggestions;
  }
}

export default ValidationService;