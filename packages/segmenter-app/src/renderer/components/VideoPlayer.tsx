import React, { useRef, useEffect, useState } from 'react';
import { Card, Typography, Button, Space, Slider } from 'antd';
import { 
  PlayCircleOutlined, 
  PauseCircleOutlined, 
  SoundOutlined,
  FullscreenOutlined,
  LinkOutlined
} from '@ant-design/icons';
import { useAppStore } from '../store/useAppStore';
import VideoService from '../services/VideoService';

const { Text } = Typography;

const VideoPlayer: React.FC = () => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0); // 使用视频元素的实际时长
  const [volume, setVolume] = useState(1);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isSynced, setIsSynced] = useState(true);
  const [playbackRate, setPlaybackRate] = useState(1); // 播放速度
  const [videoError, setVideoError] = useState<string | null>(null);

  const { 
    currentVideo, 
    segments, 
    selectedSegmentId,
    setVideoElement,
    isProcessing,
    progress
  } = useAppStore();

  // 初始化视频元素
  useEffect(() => {
    if (videoRef.current) {
      setVideoElement(videoRef.current);
    }
    return () => setVideoElement(null);
  }, [setVideoElement]);

  // 监听视频时间更新
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handleTimeUpdate = () => {
      setCurrentTime(video.currentTime);
    };

    const handleLoadedMetadata = () => {
      setDuration(video.duration);
      console.log('视频实际时长:', video.duration);
      console.log('视频尺寸:', video.videoWidth, 'x', video.videoHeight);
    };

    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);
    const handleEnded = () => setIsPlaying(false);
    
    const handleError = (e: Event) => {
      const video = e.target as HTMLVideoElement;
      console.error('视频加载错误:', video.error);
      console.error('错误代码:', video.error?.code);
      console.error('错误信息:', video.error?.message);
      
      // 根据错误代码提供用户友好的错误信息
      let errorMsg = '视频加载失败';
      if (video.error) {
        switch (video.error.code) {
          case 1:
            errorMsg = '视频加载被中断';
            break;
          case 2:
            errorMsg = '网络错误，视频无法加载';
            break;
          case 3:
            errorMsg = '视频解码失败，可能是编码格式不支持 (HEVC/H.265)';
            break;
          case 4:
            errorMsg = '视频格式不支持或文件已损坏';
            break;
          default:
            errorMsg = `视频加载失败 (错误码: ${video.error.code})`;
        }
      }
      setVideoError(errorMsg);
    };
    
    const handleCanPlay = () => {
      console.log('视频可以播放');
      setVideoError(null); // 清除之前的错误
    };
    
    const handleStalled = () => {
      console.warn('视频加载停滞');
    };

    video.addEventListener('timeupdate', handleTimeUpdate);
    video.addEventListener('loadedmetadata', handleLoadedMetadata);
    video.addEventListener('play', handlePlay);
    video.addEventListener('pause', handlePause);
    video.addEventListener('ended', handleEnded);
    video.addEventListener('error', handleError);
    video.addEventListener('canplay', handleCanPlay);
    video.addEventListener('stalled', handleStalled);

    // 如果已经加载了元数据，立即设置时长
    if (video.duration && !isNaN(video.duration)) {
      setDuration(video.duration);
    }

    return () => {
      video.removeEventListener('timeupdate', handleTimeUpdate);
      video.removeEventListener('loadedmetadata', handleLoadedMetadata);
      video.removeEventListener('play', handlePlay);
      video.removeEventListener('pause', handlePause);
      video.removeEventListener('ended', handleEnded);
      video.removeEventListener('error', handleError);
      video.removeEventListener('canplay', handleCanPlay);
      video.removeEventListener('stalled', handleStalled);
    };
  }, []);

  // 播放/暂停控制
  const togglePlay = () => {
    const video = videoRef.current;
    if (!video) return;

    if (isPlaying) {
      video.pause();
    } else {
      video.play();
    }
  };

  // 跳转到指定时间
  const seekTo = (time: number) => {
    const video = videoRef.current;
    if (!video) return;

    video.currentTime = Math.max(0, Math.min(time, video.duration || 0));
    // 手动拖动进度条时解除同步
    if (isSynced) {
      setIsSynced(false);
    }
  };

  // 同步播放进度和时间轴
  const toggleSync = () => {
    setIsSynced(!isSynced);
  };

  // 音量控制
  const handleVolumeChange = (value: number) => {
    const video = videoRef.current;
    if (!video) return;

    const newVolume = value / 100;
    setVolume(newVolume);
    video.volume = newVolume;
  };

  // 播放速度控制
  const handlePlaybackRateChange = (value: number) => {
    const video = videoRef.current;
    if (!video) return;

    setPlaybackRate(value);
    video.playbackRate = value;
  };

  // 全屏控制
  const toggleFullscreen = () => {
    const video = videoRef.current;
    if (!video) return;

    if (!isFullscreen) {
      if (video.requestFullscreen) {
        video.requestFullscreen();
      }
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen();
      }
    }
  };

  // 监听全屏状态变化
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  // 跳转到选中片段
  const jumpToSelectedSegment = () => {
    if (!selectedSegmentId || !isSynced) return;
    
    const segment = segments.find(s => s.id === selectedSegmentId);
    if (segment) {
      seekTo(segment.startTime);
    }
  };

  useEffect(() => {
    if (isSynced) {
      jumpToSelectedSegment();
    }
  }, [selectedSegmentId, isSynced]);

  if (!currentVideo) {
    return (
      <Card className="h-full flex items-center justify-center">
        <Text type="secondary">请先加载视频文件</Text>
      </Card>
    );
  }

  return (
      <Card className="h-full flex flex-col">
      <div className="flex-1 relative bg-black rounded-lg overflow-hidden">
        {/* 预览生成期间不显示视频 */}
        {!isProcessing && (
          <video
            key={currentVideo.previewPath || currentVideo.path}
            ref={videoRef}
            src={(() => {
              const videoPath = currentVideo.previewPath || currentVideo.path;
              // 如果是 http/https URL，直接使用；否则添加 file:/// 前缀（Electron 环境）
              if (videoPath.startsWith('http://') || videoPath.startsWith('https://')) {
                return videoPath;
              }
              return `file:///${videoPath.replace(/\\/g, '/')}`;
            })()}
            className="w-full h-full object-contain"
            onLoadedMetadata={() => {
              // 视频加载完成后的处理
              console.log('视频元数据加载完成');
            }}
          />
        )}
        
        {/* 视频错误提示 */}
        {videoError && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/80">
            <div className="text-center text-white p-4">
              <div className="text-red-400 text-lg mb-2">⚠ {videoError}</div>
              <div className="text-gray-400 text-sm">
                当前视频编码: <span className="font-mono">{currentVideo.codec}</span>
                {currentVideo.codec === 'hevc' && (
                  <span className="block mt-1">
                    HEVC 编码需要转换，请等待预览文件生成完成
                  </span>
                )}
              </div>
            </div>
          </div>
        )}
        
        {/* 预览生成加载状态 */}
        {isProcessing && progress && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/80">
            <div className="text-center text-white p-6">
              <div className="text-yellow-400 text-xl mb-4">🎬 正在生成预览文件</div>
              <div className="w-64 bg-gray-700 rounded-full h-4 mb-2">
                <div 
                  className="bg-blue-500 h-4 rounded-full transition-all duration-300"
                  style={{ width: `${progress.percentage}%` }}
                />
              </div>
              <div className="text-gray-300 text-sm">{progress.percentage}%</div>
              <div className="text-gray-400 text-xs mt-2 max-w-xs">{progress.currentFile}</div>
            </div>
          </div>
        )}
        
        {/* 视频信息覆盖层 */}
        <div className="absolute top-4 left-4 bg-black/50 text-white px-3 py-2 rounded">
          <Text className="text-white text-sm">
            {VideoService.formatDuration(currentTime)} / {VideoService.formatDuration(duration || currentVideo.duration)}
          </Text>
        </div>

        {/* 选中片段指示器 */}
        {selectedSegmentId && (
          <div className="absolute top-4 right-4 bg-primary/80 text-white px-3 py-2 rounded">
            <Text className="text-white text-sm">
              片段 {segments.find(s => s.id === selectedSegmentId)?.index}
            </Text>
          </div>
        )}
      </div>

      {/* 视频控制栏 */}
      <div className="mt-4 space-y-3">
        {/* 进度条 */}
        <Slider
          min={0}
          max={duration || currentVideo.duration}
          step={0.1}
          value={currentTime}
          onChange={seekTo}
          tooltip={{
            formatter: (value) => VideoService.formatDuration(value || 0)
          }}
        />

        {/* 控制按钮 */}
        <div className="flex items-center justify-between">
          <Space>
            <Button
              type="text"
              size="large"
              icon={isPlaying ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
              onClick={togglePlay}
            />
            
            <div className="flex items-center space-x-2">
              <SoundOutlined />
              <Slider
                className="w-20"
                min={0}
                max={100}
                value={volume * 100}
                onChange={handleVolumeChange}
              />
            </div>

            <Button
              type={isSynced ? 'primary' : 'default'}
              size="small"
              icon={<LinkOutlined />}
              onClick={toggleSync}
              title={isSynced ? '播放进度已同步时间轴' : '播放进度未同步时间轴'}
            >
              {isSynced ? '已同步' : '未同步'}
            </Button>

            {/* 倍速控制 */}
            <div className="flex items-center space-x-2 ml-2">
              <Text className="text-sm text-gray-500">速度:</Text>
              <Slider
                className="w-24"
                min={0.5}
                max={4}
                step={0.25}
                value={playbackRate}
                onChange={handlePlaybackRateChange}
                tooltip={{
                  formatter: (value) => `${value}x`
                }}
              />
              <Text className="text-sm w-10">{playbackRate}x</Text>
            </div>
          </Space>

          <Space>
            <Text type="secondary" className="text-sm">
              {currentVideo.width} × {currentVideo.height}
            </Text>
            
            <Button
              type="text"
              icon={<FullscreenOutlined />}
              onClick={toggleFullscreen}
            />
          </Space>
        </div>
      </div>
    </Card>
  );
};

export default VideoPlayer;