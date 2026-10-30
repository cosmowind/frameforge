/**
 * Mock Electron API for browser development testing
 * 这个文件用于在没有 Electron 的情况下进行开发和调试
 */

// 检查是否在 Electron 环境中（如果 window.electronAPI 已存在，说明在 Electron 中）
const hasElectronAPI = typeof window !== 'undefined' && window.electronAPI !== undefined;

// 如果已经有 electronAPI，说明在 Electron 环境中，不需要注入 mock
if (hasElectronAPI) {
  console.log('[Dev] Running in Electron mode - using real Electron API');
} else {
  console.log('[Dev] Running in browser mode - using Mock Electron API');
  console.log('[Dev] You can test video playback with local file selection');

  // 存储 blob URL 用于清理
  let currentBlobUrl: string | null = null;

  // 创建隐藏的文件输入元素
  const createFileInput = (): HTMLInputElement => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'video/*,.mp4,.webm,.mov,.avi,.mkv';
    input.style.display = 'none';
    document.body.appendChild(input);
    return input;
  };

  // 清理之前的 blob URL
  const cleanupBlobUrl = () => {
    if (currentBlobUrl) {
      URL.revokeObjectURL(currentBlobUrl);
      currentBlobUrl = null;
    }
  };

  // Mock Electron API
  const mockElectronAPI = {
    // 文件操作
    selectVideoFile: async () => {
      console.log('[Mock] selectVideoFile called - opening file picker');
      cleanupBlobUrl();

      return new Promise<string | null>((resolve) => {
        const input = createFileInput();

        input.onchange = async () => {
          const file = input.files?.[0];
          if (!file) {
            console.log('[Mock] No file selected');
            document.body.removeChild(input);
            resolve(null);
            return;
          }

          console.log('[Mock] File selected:', file.name);

          // 创建 blob URL 供 video 元素使用
          currentBlobUrl = URL.createObjectURL(file);
          console.log('[Mock] Created blob URL:', currentBlobUrl);

          document.body.removeChild(input);
          // 返回 blob URL，这样 video 元素可以直接播放
          resolve(currentBlobUrl);
        };

        input.oncancel = () => {
          console.log('[Mock] File selection cancelled');
          document.body.removeChild(input);
          resolve(null);
        };

        // 触发文件选择对话框
        input.click();
      });
    },
    
    selectMetadataFile: async () => {
      console.log('[Mock] selectMetadataFile called');
      return null;
    },
    
    saveMetadataFile: async (data: string) => {
      console.log('[Mock] saveMetadataFile called with data:', data);
      return '/mock/path/metadata.json';
    },
    
    readFile: async (filePath: string) => {
      console.log('[Mock] readFile called for:', filePath);
      return '{}';
    },
    
    selectOutputDirectory: async () => {
      console.log('[Mock] selectOutputDirectory called');
      return '/mock/output';
    },
    
    // 视频处理
    extractVideoInfo: async (videoPath: string) => {
      console.log('[Mock] extractVideoInfo called for:', videoPath);

      // 如果是 blob URL，需要用 video 元素获取真实信息
      if (videoPath.startsWith('blob:')) {
        return new Promise((resolve) => {
          const video = document.createElement('video');
          video.preload = 'metadata';

          video.onloadedmetadata = () => {
            console.log('[Mock] Blob video metadata loaded:', video.duration, video.videoWidth, video.videoHeight);
            resolve({
              filename: 'local_video.mp4',
              path: videoPath,
              duration: video.duration,
              width: video.videoWidth,
              height: video.videoHeight,
              codec: 'h264', // 浏览器能播放说明是支持的编码
              bitrate: 0,
              size: 0
            });
            video.remove();
          };

          video.onerror = () => {
            console.error('[Mock] Failed to load blob video metadata');
            video.remove();
            resolve({
              filename: 'local_video.mp4',
              path: videoPath,
              duration: 0,
              width: 0,
              height: 0,
              codec: 'unknown',
              bitrate: 0,
              size: 0
            });
          };

          video.src = videoPath;
        });
      }

      // HTTP URL
      if (videoPath.startsWith('http')) {
        return {
          filename: 'online_video.mp4',
          path: videoPath,
          duration: 10,
          width: 320,
          height: 240,
          codec: 'h264',
          bitrate: 500000,
          size: 1000000
        };
      }

      // 其他情况返回默认值
      return {
        filename: 'video.mp4',
        path: videoPath,
        duration: 10,
        width: 1920,
        height: 1080,
        codec: 'h264',
        bitrate: 5000000,
        size: 10000000
      };
    },
    
    generatePreview: async (videoPath: string, duration: number) => {
      console.log('[Mock] generatePreview called - video is already playable');
      // 模拟异步操作
      await new Promise(resolve => setTimeout(resolve, 500));
      // H.264 编码不需要转换，直接返回原路径
      return videoPath;
    },
    
    checkSegmentsFile: async (videoPath: string) => {
      console.log('[Mock] checkSegmentsFile called');
      return null;
    },
    
    splitVideo: async (inputPath: string, segments: any[], outputDir: string, metadata?: any) => {
      console.log('[Mock] splitVideo called - video splitting is simulated');
      return {
        success: true,
        outputFiles: segments.map((s, i) => `${outputDir}/segment-${i}.mp4`),
        errors: [],
        outputFolder: outputDir
      };
    },
    
    // 进度监听
    onProgress: (callback: (progress: any) => void) => {
      console.log('[Mock] onProgress listener added');
    },
    
    removeProgressListener: () => {
      console.log('[Mock] onProgress listener removed');
    },
    
    onPreviewProgress: (callback: (percent: number) => void) => {
      console.log('[Mock] onPreviewProgress listener added');
      // 模拟快速完成
      setTimeout(() => callback(100), 100);
    },
    
    removePreviewProgressListener: () => {
      console.log('[Mock] onPreviewProgress listener removed');
    },
  };

  // 注入 Mock API 到 window 对象
  (window as any).electronAPI = mockElectronAPI;
}

export default {};
