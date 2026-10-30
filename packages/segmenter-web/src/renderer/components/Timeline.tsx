import React, { useRef, useState, useEffect } from 'react';
import { Card, Button, Space, Tooltip, Slider } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { useAppStore } from '../store/useAppStore';
import VideoService from '../services/VideoService';

const Timeline: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  const [isDragging, setIsDragging] = useState(false);
  const [dragTarget, setDragTarget] = useState<{ segmentId: string; edge: 'start' | 'end' } | null>(null);
  const [currentTime, setCurrentTime] = useState(0); // 添加本地状态来跟踪播放时间
  const [videoDuration, setVideoDuration] = useState(0); // 视频实际时长

  const {
    currentVideo,
    segments,
    selectedSegmentId,
    videoElement,
    setSelectedSegmentId,
    updateSegment,
    addSegment,
  } = useAppStore();

  // 监听视频播放进度更新和时长
  useEffect(() => {
    if (!videoElement) return;

    const handleTimeUpdate = () => {
      setCurrentTime(videoElement.currentTime);
    };

    const handleLoadedMetadata = () => {
      setVideoDuration(videoElement.duration);
      console.log('Timeline: 视频实际时长', videoElement.duration);
    };

    videoElement.addEventListener('timeupdate', handleTimeUpdate);
    videoElement.addEventListener('loadedmetadata', handleLoadedMetadata);

    // 如果已经加载了元数据，立即设置时长
    if (videoElement.duration && !isNaN(videoElement.duration)) {
      setVideoDuration(videoElement.duration);
    }

    return () => {
      videoElement.removeEventListener('timeupdate', handleTimeUpdate);
      videoElement.removeEventListener('loadedmetadata', handleLoadedMetadata);
    };
  }, [videoElement]);

  // 添加键盘监听 - 按 'A' 键添加片段
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'a' || e.key === 'A') {
        if (!videoElement) return;
        
        const duration = videoDuration || (currentVideo?.duration || 0);
        // 在当前播放位置添加片段
        const currentTime = videoElement.currentTime;
        const segmentDuration = Math.min(15, duration - currentTime);
        addSegment(currentTime, currentTime + segmentDuration);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [videoElement, videoDuration, currentVideo, addSegment]);

  // 绘制时间轴
  useEffect(() => {
    if (!canvasRef.current || !currentVideo) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // 使用视频元素的实际时长，如果没有则使用 currentVideo.duration
    const duration = videoDuration || currentVideo.duration;

    // 设置canvas尺寸（根据缩放调整宽度）
    const container = containerRef.current;
    if (container) {
      const baseWidth = container.clientWidth;
      canvas.width = baseWidth * scale; // 根据缩放比例调整宽度
      canvas.height = 120;
    }

    // 清空画布
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // 绘制背景
    ctx.fillStyle = '#f5f5f5';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // 绘制时间刻度
    drawTimeScale(ctx, canvas.width, duration);

    // 绘制片段
    segments.forEach(segment => {
      drawSegment(ctx, segment, canvas.width, duration);
    });

    // 绘制当前播放位置
    drawPlayhead(ctx, currentTime, canvas.width, duration);
  }, [currentVideo, segments, selectedSegmentId, currentTime, scale, videoDuration]);

  // 绘制时间刻度
  const drawTimeScale = (ctx: CanvasRenderingContext2D, width: number, duration: number) => {
    const interval = Math.ceil(duration / 10);
    ctx.strokeStyle = '#d9d9d9';
    ctx.fillStyle = '#666';
    ctx.font = '10px sans-serif';

    for (let i = 0; i <= duration; i += interval) {
      const x = (i / duration) * width;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, 10);
      ctx.stroke();

      ctx.fillText(VideoService.formatDuration(i), x - 15, 25);
    }
  };

  // 绘制片段
  const drawSegment = (
    ctx: CanvasRenderingContext2D,
    segment: any,
    width: number,
    duration: number
  ) => {
    const startX = (segment.startTime / duration) * width;
    const endX = (segment.endTime / duration) * width;
    const segmentWidth = endX - startX;

    // 片段背景
    const isSelected = segment.id === selectedSegmentId;
    ctx.fillStyle = isSelected
      ? 'rgba(99, 102, 241, 0.3)'
      : segment.isValid
      ? 'rgba(99, 102, 241, 0.2)'
      : 'rgba(245, 158, 11, 0.2)';

    ctx.fillRect(startX, 30, segmentWidth, 60);

    // 片段边框
    ctx.strokeStyle = isSelected
      ? '#6366F1'
      : segment.isValid
      ? '#818CF8'
      : '#F59E0B';
    ctx.lineWidth = isSelected ? 2 : 1;
    ctx.strokeRect(startX, 30, segmentWidth, 60);

    // 片段信息
    ctx.fillStyle = '#333';
    ctx.font = 'bold 12px sans-serif';
    const text = `片段 ${segment.index}`;
    const textWidth = ctx.measureText(text).width;
    if (segmentWidth > textWidth + 10) {
      ctx.fillText(text, startX + (segmentWidth - textWidth) / 2, 55);
      
      // 时长信息
      ctx.font = '10px sans-serif';
      const durationText = VideoService.formatDuration(segment.duration);
      const durationWidth = ctx.measureText(durationText).width;
      ctx.fillText(durationText, startX + (segmentWidth - durationWidth) / 2, 70);
    }

    // 拖动手柄
    ctx.fillStyle = isSelected ? '#6366F1' : '#999';
    ctx.beginPath();
    ctx.arc(startX, 60, 6, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.arc(endX, 60, 6, 0, Math.PI * 2);
    ctx.fill();
  };

  // 绘制播放头
  const drawPlayhead = (
    ctx: CanvasRenderingContext2D,
    currentTime: number,
    width: number,
    duration: number
  ) => {
    const x = (currentTime / duration) * width;
    ctx.strokeStyle = '#ff4d4f';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, 120);
    ctx.stroke();

    // 播放头三角形
    ctx.fillStyle = '#ff4d4f';
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x - 5, 10);
    ctx.lineTo(x + 5, 10);
    ctx.closePath();
    ctx.fill();
  };

  // 处理鼠标点击 - 只选择片段，不添加新片段
  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!canvasRef.current || !currentVideo) return;

    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const duration = videoDuration || currentVideo.duration;

    // 检查是否点击了片段
    const clickedSegment = segments.find(segment => {
      const startX = (segment.startTime / duration) * canvas.width;
      const endX = (segment.endTime / duration) * canvas.width;
      return x >= startX && x <= endX;
    });

    if (clickedSegment) {
      setSelectedSegmentId(clickedSegment.id);
      if (videoElement) {
        videoElement.currentTime = clickedSegment.startTime;
      }
    } else {
      // 点击空白处取消选择
      setSelectedSegmentId(null);
    }
  };

  // 处理鼠标按下（开始拖动）
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!canvasRef.current || !currentVideo) return;

    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const duration = videoDuration || currentVideo.duration;

    // 检查是否点击了片段边缘（增加检测范围到15px）
    for (const segment of segments) {
      const startX = (segment.startTime / duration) * canvas.width;
      const endX = (segment.endTime / duration) * canvas.width;

      if (Math.abs(x - startX) < 15) {
        setIsDragging(true);
        setDragTarget({ segmentId: segment.id, edge: 'start' });
        setSelectedSegmentId(segment.id);
        e.stopPropagation(); // 阻止事件冒泡
        return;
      }

      if (Math.abs(x - endX) < 15) {
        setIsDragging(true);
        setDragTarget({ segmentId: segment.id, edge: 'end' });
        setSelectedSegmentId(segment.id);
        e.stopPropagation(); // 阻止事件冒泡
        return;
      }
    }
  };

  // 处理鼠标移动（拖动中）
  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDragging || !dragTarget || !canvasRef.current || !currentVideo) return;

    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const duration = videoDuration || currentVideo.duration;
    const time = Math.max(0, Math.min((x / canvas.width) * duration, duration));

    const segment = segments.find(s => s.id === dragTarget.segmentId);
    if (!segment) return;

    if (dragTarget.edge === 'start') {
      if (time < segment.endTime - 1) {
        updateSegment(segment.id, { startTime: time });
      }
    } else {
      if (time > segment.startTime + 1) {
        updateSegment(segment.id, { endTime: time });
      }
    }
  };

  // 处理鼠标释放（结束拖动）
  const handleMouseUp = () => {
    setIsDragging(false);
    setDragTarget(null);
  };

  // 添加片段按钮处理
  const handleAddSegment = () => {
    if (!videoElement) return;
    
    const duration = videoDuration || (currentVideo?.duration || 0);
    // 在当前播放位置添加片段
    const currentTime = videoElement.currentTime;
    const segmentDuration = Math.min(15, duration - currentTime);
    addSegment(currentTime, currentTime + segmentDuration);
  };

  if (!currentVideo) {
    return null;
  }

  return (
    <Card className="h-full">
      <div className="flex justify-between items-center mb-2">
        <Space>
          <Tooltip title="在当前播放位置添加片段 (快捷键: A)">
            <Button 
              size="small" 
              icon={<PlusOutlined />}
              onClick={handleAddSegment}
              type="primary"
            >
              添加片段 (A)
            </Button>
          </Tooltip>
          <span className="text-sm text-gray-500">拖动边缘调整片段</span>
        </Space>

        <Space>
          <span className="text-sm text-gray-500">时间轴缩放:</span>
          <Slider
            className="w-32"
            min={0.1}
            max={10}
            step={0.1}
            value={scale}
            onChange={setScale}
            tooltip={{
              formatter: (value) => `${value}x`
            }}
          />
          <span className="text-sm w-12">{scale.toFixed(1)}x</span>
        </Space>
      </div>

      <div 
        ref={scrollContainerRef}
        className="relative overflow-x-auto overflow-y-hidden border border-gray-200 rounded"
        style={{ maxHeight: '140px' }}
      >
        <div ref={containerRef} style={{ width: '100%', display: 'inline-block' }}>
          <canvas
            ref={canvasRef}
            className="cursor-crosshair"
            onClick={handleCanvasClick}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            style={{ display: 'block' }}
          />
        </div>
      </div>
      
      {/* 横向滚动提示 */}
      {scale > 1 && (
        <div className="text-xs text-gray-400 text-center mt-1">
          ← 左右滚动查看完整时间轴 →
        </div>
      )}
    </Card>
  );
};

export default Timeline;