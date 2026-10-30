// 核心数据模型接口

export interface SegmentPoint {
  id: string;
  time: number; // 秒
  type: 'start' | 'end';
}

export interface SegmentAnnotation {
  hasIssue: boolean;
  note: string;
  reviewedBy?: string;
  reviewedAt?: Date;
}

export interface VideoSegment {
  id: string;
  startTime: number;
  endTime: number;
  duration: number;
  index: number;
  isValid: boolean;
  warnings: string[];
  annotation?: SegmentAnnotation;
}

export interface SegmentMetadata {
  version: string;
  sourceVideoName: string;
  sourceVideoDuration: number;
  createdAt: Date;
  modifiedAt: Date;
  segments: VideoSegment[];
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
  file?: File; // 浏览器环境下的文件对象
  url?: string; // 浏览器环境下的 Object URL
}

export interface ValidationResult {
  isValid: boolean;
  warnings: string[];
  errors: string[];
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

// Timeline 组件相关接口
export interface TimelineProps {
  videoDuration: number;
  segments: VideoSegment[];
  currentTime: number;
  onSegmentCreate: (time: number) => void;
  onSegmentUpdate: (segmentId: string, startTime: number, endTime: number) => void;
  onSegmentDelete: (segmentId: string) => void;
  onSegmentSplit: (segmentId: string) => void;
  onTimeChange: (time: number) => void;
}

export interface TimelineState {
  scale: number; // 缩放级别
  scrollPosition: number;
  selectedSegmentId: string | null;
  isDragging: boolean;
  dragTarget: 'start' | 'end' | null;
}

// 工具选择器相关接口
export type ToolType = 'segmentation' | 'rotation';

export interface ToolOption {
  key: ToolType;
  label: string;
  icon: React.ReactNode;
  description: string;
}

// 视频旋转相关接口
export type RotationAngle = 0 | 90 | 180 | 270;

export interface RotationConfig {
  angle: RotationAngle;
  clockwise: boolean;
}

export interface RotateResult {
  success: boolean;
  outputFile?: string;
  error?: string;
}