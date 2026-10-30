import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Card, Typography, Button, Space, Slider, Progress, Spin, message } from 'antd';
import { 
  PlayCircleOutlined, 
  PauseCircleOutlined, 
  SoundOutlined,
  FullscreenOutlined,
  LinkOutlined,
  LoadingOutlined,
  ReloadOutlined
} from '@ant-design/icons';
import { useAppStore } from '../store/useAppStore';
import VideoService from '../services/VideoService';
import MP4Box from 'mp4box';
import { FFmpeg } from '@ffmpeg/ffmpeg';
import { fetchFile, toBlobURL } from '@ffmpeg/util';

const { Text } = Typography;

interface TranscodeProgress {
  percentage: number;
  stage: 'loading' | 'transcoding' | 'complete' | 'error';
  message: string;
}

const VideoPlayer: React.FC = () => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isSynced, setIsSynced] = useState(true);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [playError, setPlayError] = useState(false);
  const [isTranscoding, setIsTranscoding] = useState(false);
  const [transcodeProgress, setTranscodeProgress] = useState<TranscodeProgress | null>(null);
  const [transcodedUrl, setTranscodedUrl] = useState<string | null>(null);

  const { 
    currentVideo, 
    segments, 
    selectedSegmentId,
    setVideoElement 
  } = useAppStore();

  // 初始化视频元素
  useEffect(() => {
    if (videoRef.current) {
      setVideoElement(videoRef.current);
    }
    return () => setVideoElement(null);
  }, [setVideoElement]);

  // 重置状态
  useEffect(() => {
    setPlayError(false);
    setTranscodedUrl(null);
    setTranscodeProgress(null);
    setIsTranscoding(false);
  }, [currentVideo?.filename]);

  // 监听视频事件
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handleTimeUpdate = () => setCurrentTime(video.currentTime);
    
    const handleLoadedMetadata = () => {
      setDuration(video.duration);
      console.log('视频元数据加载完成:', video.duration);
    };

    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);
    const handleEnded = () => setIsPlaying(false);
    
    const handleError = (e: Event) => {
      const video = e.target as HTMLVideoElement;
      console.error('视频播放错误:', video.error);
      setPlayError(true);
    };
    
    const handleCanPlay = () => {
      console.log('视频可以播放');
      setPlayError(false);
    };

    video.addEventListener('timeupdate', handleTimeUpdate);
    video.addEventListener('loadedmetadata', handleLoadedMetadata);
    video.addEventListener('play', handlePlay);
    video.addEventListener('pause', handlePause);
    video.addEventListener('ended', handleEnded);
    video.addEventListener('error', handleError);
    video.addEventListener('canplay', handleCanPlay);

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
    };
  }, [transcodedUrl]);

  // 检测视频编码
  const detectCodec = useCallback(async (file: File): Promise<string> => {
    return new Promise((resolve) => {
      const mp4boxFile = MP4Box.createFile();
      const reader = new FileReader();

      reader.onload = (e) => {
        const buffer = e.target?.result as ArrayBuffer;
        if (!buffer) {
          resolve('h264');
          return;
        }

        const mp4boxBuffer = buffer as unknown as { fileStart: number };
        mp4boxBuffer.fileStart = 0;

        mp4boxFile.onReady = (info) => {
          const videoTrack = info.videoTracks[0];
          if (videoTrack) {
            const codec = videoTrack.codec;
            if (codec.includes('hev1') || codec.includes('hvc1') || codec.includes('265')) {
              resolve('hevc');
            } else {
              resolve('h264');
            }
          } else {
            resolve('h264');
          }
        };

        mp4boxFile.onError = () => resolve('h264');
        mp4boxFile.appendBuffer(mp4boxBuffer as unknown as ArrayBuffer);
        mp4boxFile.flush();
      };

      reader.onerror = () => resolve('h264');
      reader.readAsArrayBuffer(file.slice(0, 1024 * 1024));
    });
  }, []);

  // 转码 HEVC 视频
  const transcodeVideo = useCallback(async (file: File) => {
    setIsTranscoding(true);
    setTranscodeProgress({
      percentage: 0,
      stage: 'loading',
      message: '正在加载转码组件...'
    });

    try {
      const ffmpeg = new FFmpeg();
      const baseURL = 'https://unpkg.com/@ffmpeg/core@0.12.6/dist/umd';
      
      await ffmpeg.load({
        coreURL: await toBlobURL(`${baseURL}/ffmpeg-core.js`, 'text/javascript'),
        wasmURL: await toBlobURL(`${baseURL}/ffmpeg-core.wasm`, 'application/wasm'),
      });

      setTranscodeProgress({
        percentage: 0,
        stage: 'transcoding',
        message: '正在转码...'
      });

      ffmpeg.on('progress', ({ progress }) => {
        setTranscodeProgress({
          percentage: Math.round(progress * 100),
          stage: 'transcoding',
          message: `正在转码... ${Math.round(progress * 100)}%`
        });
      });

      const inputData = await fetchFile(file);
      await ffmpeg.writeFile('input.mp4', inputData as unknown as Uint8Array);
      
      await ffmpeg.exec([
        '-i', 'input.mp4',
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-crf', '28',
        '-c:a', 'aac',
        '-y',
        'output.mp4',
      ]);

      const outputData = await ffmpeg.readFile('output.mp4');
      const blob = new Blob([outputData as BlobPart], { type: 'video/mp4' });
      const url = URL.createObjectURL(blob);

      setTranscodedUrl(url);
      setTranscodeProgress({
        percentage: 100,
        stage: 'complete',
        message: '转码完成'
      });
      message.success('HEVC 视频转码完成');
    } catch (error) {
      console.error('转码失败:', error);
      setTranscodeProgress({
        percentage: 0,
        stage: 'error',
        message: `转码失败: ${(error as Error).message}`
      });
      message.error('转码失败，请尝试其他视频');
    } finally {
      setIsTranscoding(false);
    }
  }, []);

  // 处理播放错误 - 检测是否需要转码
  const handlePlayError = useCallback(async () => {
    if (!currentVideo?.file) return;

    message.warning('视频播放失败，正在检测编码...');
    const codec = await detectCodec(currentVideo.file);
    
    if (codec === 'hevc') {
      message.info('检测到 HEVC 编码，需要转码后播放');
      await transcodeVideo(currentVideo.file);
    } else {
      message.error('视频播放失败，文件可能已损坏');
    }
  }, [currentVideo, detectCodec, transcodeVideo]);

  // 播放/暂停控制
  const togglePlay = () => {
    const video = videoRef.current;
    if (!video) return;

    if (isPlaying) {
      video.pause();
    } else {
      video.play().catch(() => {
        // 播放失败
      });
    }
  };

  // 跳转到指定时间
  const seekTo = (time: number) => {
    const video = videoRef.current;
    if (!video) return;

    video.currentTime = Math.max(0, Math.min(time, video.duration || 0));
    if (isSynced) {
      setIsSynced(false);
    }
  };

  const toggleSync = () => setIsSynced(!isSynced);

  const handleVolumeChange = (value: number) => {
    const video = videoRef.current;
    if (!video) return;
    const newVolume = value / 100;
    setVolume(newVolume);
    video.volume = newVolume;
  };

  const handlePlaybackRateChange = (value: number) => {
    const video = videoRef.current;
    if (!video) return;
    setPlaybackRate(value);
    video.playbackRate = value;
  };

  const toggleFullscreen = () => {
    const video = videoRef.current;
    if (!video) return;

    if (!isFullscreen) {
      video.requestFullscreen?.();
    } else {
      document.exitFullscreen?.();
    }
  };

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

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

  const videoUrl = transcodedUrl || currentVideo.url || '';

  return (
    <Card className="h-full flex flex-col">
      <div className="flex-1 relative bg-black rounded-lg overflow-hidden">
        {/* 转码进度 */}
        {isTranscoding && transcodeProgress && (
          <div className="absolute inset-0 flex items-center justify-center z-10 bg-black/90">
            <div className="text-center text-white p-6 max-w-md">
              {transcodeProgress.stage === 'loading' && (
                <>
                  <Spin indicator={<LoadingOutlined style={{ fontSize: 48 }} spin />} />
                  <Text className="text-white text-lg block mt-4">{transcodeProgress.message}</Text>
                </>
              )}
              {transcodeProgress.stage === 'transcoding' && (
                <>
                  <Text className="text-blue-400 text-lg block mb-4">正在转码 HEVC 视频</Text>
                  <Progress
                    percent={transcodeProgress.percentage}
                    status="active"
                    strokeColor={{ from: '#108ee9', to: '#87d068' }}
                  />
                  <Text className="text-gray-400 text-sm block mt-2">{transcodeProgress.message}</Text>
                  <Text className="text-gray-500 text-xs block mt-4">
                    使用 ultrafast 预设加速转码，请耐心等待...
                  </Text>
                </>
              )}
              {transcodeProgress.stage === 'error' && (
                <>
                  <Text className="text-red-400 text-lg block mb-2">转码失败</Text>
                  <Text className="text-white block mb-4">{transcodeProgress.message}</Text>
                </>
              )}
            </div>
          </div>
        )}

        {/* 播放错误提示 */}
        {playError && !isTranscoding && !transcodedUrl && (
          <div className="absolute inset-0 flex items-center justify-center z-10 bg-black/80">
            <div className="text-center text-white p-6">
              <Text className="text-yellow-400 text-lg block mb-4">视频播放失败</Text>
              <Button 
                type="primary" 
                icon={<ReloadOutlined />}
                onClick={handlePlayError}
              >
                检测编码并尝试修复
              </Button>
            </div>
          </div>
        )}

        {/* 转码完成标识 */}
        {transcodedUrl && (
          <div className="absolute top-4 right-4 bg-green-600/80 text-white px-3 py-2 rounded z-20">
            <Text className="text-white text-sm">已转码播放</Text>
          </div>
        )}
        
        <video
          ref={videoRef}
          src={videoUrl}
          className="w-full h-full object-contain"
          crossOrigin="anonymous"
        />
        
        <div className="absolute top-4 left-4 bg-black/50 text-white px-3 py-2 rounded">
          <Text className="text-white text-sm">
            {VideoService.formatDuration(currentTime)} / {VideoService.formatDuration(duration || currentVideo.duration)}
          </Text>
        </div>

        {selectedSegmentId && (
          <div className={`absolute ${transcodedUrl ? 'top-16' : 'top-4'} right-4 bg-primary/80 text-white px-3 py-2 rounded`}>
            <Text className="text-white text-sm">
              片段 {segments.find(s => s.id === selectedSegmentId)?.index}
            </Text>
          </div>
        )}
      </div>

      <div className="mt-4 space-y-3">
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
            >
              {isSynced ? '已同步' : '未同步'}
            </Button>

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
