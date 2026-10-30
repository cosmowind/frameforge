import { create } from 'zustand';
import { VideoInfo, VideoSegment, SegmentMetadata, ProgressInfo, SplitResult } from '../types';
import SegmentManager from '../services/SegmentManager';
import VideoService from '../services/VideoService';
import MetadataService from '../services/MetadataService';

interface AppState {
  // 视频相关
  currentVideo: VideoInfo | null;
  videoElement: HTMLVideoElement | null;
  
  // 片段相关
  segments: VideoSegment[];
  selectedSegmentId: string | null;
  segmentManager: SegmentManager;
  
  // 历史记录（用于撤销）
  history: VideoSegment[][];
  historyIndex: number;
  
  // 元数据
  metadata: SegmentMetadata | null;
  metadataPath: string | null;
  
  // UI状态
  currentView: 'segmentation' | 'review';
  isRulesPanelVisible: boolean;
  isProcessing: boolean;
  progress: ProgressInfo | null;
  
  // 操作方法
  setCurrentVideo: (video: VideoInfo | null) => void;
  setVideoElement: (element: HTMLVideoElement | null) => void;
  setSegments: (segments: VideoSegment[]) => void;
  setSelectedSegmentId: (id: string | null) => void;
  setMetadata: (metadata: SegmentMetadata | null) => void;
  setMetadataPath: (path: string | null) => void;
  setCurrentView: (view: 'segmentation' | 'review') => void;
  toggleRulesPanel: () => void;
  setProcessing: (processing: boolean) => void;
  setProgress: (progress: ProgressInfo | null) => void;
  
  // 历史记录操作
  undo: () => void;
  canUndo: () => boolean;
  saveHistory: () => void;
  
  // 异步操作（将在后续任务中实现）
  loadVideo: (path?: string) => Promise<string | null>;
  loadMetadata: (path?: string) => Promise<void>;
  saveMetadata: (path?: string) => Promise<string>;
  addSegment: (startTime: number, endTime: number) => void;
  updateSegment: (id: string, updates: Partial<VideoSegment>) => void;
  deleteSegment: (id: string) => void;
  splitSegment: (id: string) => void;
  executeSegmentation: (outputDir?: string) => Promise<SplitResult>;
}

export const useAppStore = create<AppState>((set, get) => ({
  // 初始状态
  currentVideo: null,
  videoElement: null,
  segments: [],
  selectedSegmentId: null,
  segmentManager: new SegmentManager(),
  history: [],
  historyIndex: -1,
  metadata: null,
  metadataPath: null,
  currentView: 'segmentation',
  isRulesPanelVisible: true,
  isProcessing: false,
  progress: null,
  
  // 同步操作
  setCurrentVideo: (video) => set({ currentVideo: video }),
  setVideoElement: (element) => set({ videoElement: element }),
  setSegments: (segments) => set({ segments }),
  setSelectedSegmentId: (id) => set({ selectedSegmentId: id }),
  setMetadata: (metadata) => set({ metadata }),
  setMetadataPath: (path) => set({ metadataPath: path }),
  setCurrentView: (view) => set({ currentView: view }),
  toggleRulesPanel: () => set((state) => ({ isRulesPanelVisible: !state.isRulesPanelVisible })),
  setProcessing: (processing) => set({ isProcessing: processing }),
  setProgress: (progress) => set({ progress }),
  
  // 历史记录操作
  saveHistory: () => {
    const { segments, history, historyIndex } = get();
    // 保存当前状态到历史记录
    const newHistory = history.slice(0, historyIndex + 1);
    newHistory.push(JSON.parse(JSON.stringify(segments)));
    // 限制历史记录数量为50
    if (newHistory.length > 50) {
      newHistory.shift();
    } else {
      set({ historyIndex: historyIndex + 1 });
    }
    set({ history: newHistory });
  },
  
  undo: () => {
    const { history, historyIndex, segmentManager } = get();
    if (historyIndex > 0) {
      const previousSegments = history[historyIndex - 1];
      segmentManager.setSegments(previousSegments);
      set({ 
        segments: segmentManager.getSegmentsSnapshot(),
        historyIndex: historyIndex - 1 
      });
    }
  },
  
  canUndo: () => {
    const { historyIndex } = get();
    return historyIndex > 0;
  },
  
  // 异步操作的实现
  loadVideo: async (path?: string) => {
    try {
      set({ isProcessing: true });
      
      let selectedPath = path;
      if (!selectedPath) {
        const result = await VideoService.selectVideoFile();
        if (!result) {
          return null; // 用户取消选择
        }
        selectedPath = result;
      }
      
      // 提取视频信息
      const videoInfo = await VideoService.extractVideoInfo(selectedPath);

      // 验证视频
      const validation = VideoService.validateVideo(videoInfo);
      if (validation.warnings.length > 0) {
        console.warn('视频验证警告:', validation.warnings);
      }

      // 检测不支持的编码，生成 H.264 预览文件
      const unsupportedCodecs = ['hevc', 'h265', 'mpeg2video', 'vc1'];
      if (unsupportedCodecs.includes(videoInfo.codec)) {
        console.log(`检测到不支持的编码: ${videoInfo.codec}，正在生成 H.264 预览文件...`);
        console.log('这可能需要一些时间，请耐心等待...');

        // 监听预览生成进度
        window.electronAPI.onPreviewProgress((percent: number) => {
          set({
            progress: {
              currentSegment: 1,
              totalSegments: 1,
              percentage: percent,
              currentFile: `正在转换视频: ${percent}%`,
            },
          });
        });

        try {
          console.log('开始生成预览文件，原始视频路径:', videoInfo.path);
          const previewPath = await window.electronAPI.generatePreview(videoInfo.path, videoInfo.duration);
          
          if (previewPath && previewPath.length > 0) {
            videoInfo.previewPath = previewPath;
            console.log('预览文件生成成功:', previewPath);
          } else {
            console.warn('预览文件路径为空，将使用原始视频文件');
          }
        } catch (error) {
          console.error('生成预览文件失败:', error);
          console.warn('视频可能无法正常播放，建议使用 H.264 或 H.265 编码的视频');
          // 预览生成失败不影响继续操作，但添加警告
          videoInfo.previewPath = undefined;
        } finally {
          window.electronAPI.removePreviewProgressListener();
          set({ progress: null });
        }
      } else {
        console.log(`视频编码: ${videoInfo.codec}，无需生成预览文件`);
      }

      // 更新状态
      set({
        currentVideo: videoInfo,
        segments: [], // 清空现有片段
        selectedSegmentId: null,
        metadata: null // 清空元数据
      });
      
      // 重置SegmentManager
      const { segmentManager } = get();
      segmentManager.setSegments([]);
      
      console.log('视频加载成功:', videoInfo);
      return selectedPath; // 返回视频路径
    } catch (error) {
      console.error('加载视频失败:', error);
      // 这里可以添加错误提示
      throw error;
    } finally {
      set({ isProcessing: false });
    }
  },
  
  loadMetadata: async (path?: string) => {
    try {
      set({ isProcessing: true });
      
      const metadataService = new MetadataService();
      const metadata = await metadataService.loadMetadata(path);
      
      // 验证元数据
      if (!metadataService.validateMetadata(metadata)) {
        throw new Error('元数据格式不正确');
      }
      
      // 更新状态
      const { segmentManager } = get();
      segmentManager.setSegments(metadata.segments);
      
      set({ 
        metadata,
        segments: segmentManager.getSegmentsSnapshot(),
        selectedSegmentId: null,
      });
      
      console.log('元数据加载成功:', metadata);
    } catch (error) {
      console.error('加载元数据失败:', error);
      throw error;
    } finally {
      set({ isProcessing: false });
    }
  },
  
  saveMetadata: async (path?: string) => {
    try {
      set({ isProcessing: true });
      
      const { currentVideo, segments } = get();
      if (!currentVideo) {
        throw new Error('请先加载视频文件');
      }
      
      // 创建或更新元数据
      let metadata = get().metadata;
      if (!metadata) {
        metadata = MetadataService.createMetadata(
          currentVideo.filename,
          currentVideo.duration,
          segments
        );
      } else {
        metadata = {
          ...metadata,
          segments: [...segments],
          modifiedAt: new Date(),
        };
      }
      
      const metadataService = new MetadataService();
      const savedPath = await metadataService.saveMetadata(metadata, path);
      
      // 更新状态
      set({ 
        metadata,
        metadataPath: savedPath,
      });
      
      console.log('元数据保存成功:', savedPath);
      return savedPath;
    } catch (error) {
      console.error('保存元数据失败:', error);
      throw error;
    } finally {
      set({ isProcessing: false });
    }
  },
  
  addSegment: (startTime: number, endTime: number) => {
    const state = get();
    state.saveHistory(); // 保存历史记录
    state.segmentManager.createSegment(startTime, endTime);
    const updatedSegments = state.segmentManager.getSegmentsSnapshot();
    set({ segments: updatedSegments });
  },
  
  updateSegment: (id: string, updates: Partial<VideoSegment>) => {
    const state = get();
    state.saveHistory(); // 保存历史记录
    state.segmentManager.updateSegment(id, updates);
    const updatedSegments = state.segmentManager.getSegmentsSnapshot();
    set({ segments: updatedSegments });
  },
  
  deleteSegment: (id: string) => {
    const state = get();
    state.saveHistory(); // 保存历史记录
    state.segmentManager.deleteSegment(id);
    const updatedSegments = state.segmentManager.getSegmentsSnapshot();
    set({ segments: updatedSegments });
    
    // 如果删除的是当前选中的片段，清除选中状态
    if (state.selectedSegmentId === id) {
      set({ selectedSegmentId: null });
    }
  },
  
  splitSegment: (id: string) => {
    const state = get();
    state.saveHistory(); // 保存历史记录
    state.segmentManager.splitSegment(id);
    const updatedSegments = state.segmentManager.getSegmentsSnapshot();
    set({ segments: updatedSegments });
    
    // 选中第一个新片段（分割后的第一个）
    const splitSegment = updatedSegments.find(s => s.id !== id);
    if (splitSegment) {
      set({ selectedSegmentId: splitSegment.id });
    }
  },
  
  executeSegmentation: async (outputDir?: string) => {
    try {
      set({ isProcessing: true, progress: null });
      
      const { currentVideo, segments, segmentManager, metadata } = get();
      
      if (!currentVideo) {
        throw new Error('请先加载视频文件');
      }
      
      if (segments.length === 0) {
        throw new Error('没有可分割的片段');
      }
      
      // 检查是否可以执行分割
      const validation = segmentManager.canExecuteSegmentation();
      if (!validation.canExecute) {
        throw new Error('存在验证错误，无法执行分割：\n' + validation.issues.join('\n'));
      }
      
      // 选择输出目录
      let selectedDir = outputDir;
      if (!selectedDir && window.electronAPI) {
        const result = await window.electronAPI.selectOutputDirectory();
        if (!result) {
          throw new Error('用户取消选择输出目录');
        }
        selectedDir = result;
      }
      
      if (!selectedDir) {
        throw new Error('未选择输出目录');
      }
      
      // 创建或更新元数据
      let metadataToSave = metadata;
      if (!metadataToSave) {
        metadataToSave = MetadataService.createMetadata(
          currentVideo.filename,
          currentVideo.duration,
          segments
        );
      } else {
        metadataToSave = {
          ...metadataToSave,
          segments: [...segments],
          modifiedAt: new Date(),
        };
      }
      
      // 设置进度监听
      if (window.electronAPI) {
        window.electronAPI.onProgress((progress) => {
          set({ progress });
        });
      }
      
      // 执行分割，传递元数据
      const result = await window.electronAPI.splitVideo(
        currentVideo.path,
        segments,
        selectedDir,
        metadataToSave
      );
      
      // 清除进度监听
      if (window.electronAPI) {
        window.electronAPI.removeProgressListener();
      }
      
      if (!result.success) {
        throw new Error('视频分割失败：\n' + result.errors.join('\n'));
      }
      
      // 更新元数据状态
      set({ metadata: metadataToSave });
      
      console.log('视频分割成功:', result.outputFiles);
      return result;
    } catch (error) {
      console.error('执行分割失败:', error);
      throw error;
    } finally {
      set({ isProcessing: false, progress: null });
    }
  },
}));