import React from 'react';
import { Card, Typography, Button, Space, List, Tag } from 'antd';
import { 
  PlusOutlined, 
  DeleteOutlined, 
  ScissorOutlined,
  PlayCircleOutlined 
} from '@ant-design/icons';
import { useAppStore } from '../store/useAppStore';
import VideoService from '../services/VideoService';

const { Title, Text } = Typography;

const SegmentControls: React.FC = () => {
  const {
    currentVideo,
    segments,
    selectedSegmentId,
    videoElement,
    addSegment,
    deleteSegment,
    splitSegment,
    setSelectedSegmentId,
  } = useAppStore();

  // 添加新片段（基于当前播放时间）
  const handleAddSegment = () => {
    if (!videoElement || !currentVideo) return;

    const currentTime = videoElement.currentTime;
    const duration = Math.min(15, currentVideo.duration - currentTime); // 默认15秒或剩余时间
    const endTime = Math.min(currentTime + duration, currentVideo.duration);

    addSegment(currentTime, endTime);
  };

  // 删除选中片段
  const handleDeleteSegment = () => {
    if (selectedSegmentId) {
      deleteSegment(selectedSegmentId);
    }
  };

  // 分割选中片段
  const handleSplitSegment = () => {
    if (selectedSegmentId) {
      splitSegment(selectedSegmentId);
    }
  };

  // 跳转到片段开始时间
  const jumpToSegment = (segment: any) => {
    if (videoElement) {
      videoElement.currentTime = segment.startTime;
      setSelectedSegmentId(segment.id);
    }
  };

  // 播放片段
  const playSegment = (segment: any) => {
    if (!videoElement) return;

    videoElement.currentTime = segment.startTime;
    videoElement.play();
    
    // 设置播放结束时间
    const checkTime = () => {
      if (videoElement.currentTime >= segment.endTime) {
        videoElement.pause();
      } else {
        requestAnimationFrame(checkTime);
      }
    };
    
    requestAnimationFrame(checkTime);
  };

  return (
    <Card className="h-full flex flex-col">
      <div className="flex justify-between items-center mb-4 flex-shrink-0">
        <Title level={4} className="mb-0">片段控制</Title>
        
        <Space>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={handleAddSegment}
            disabled={!currentVideo}
          >
            添加片段
          </Button>
          
          <Button
            icon={<ScissorOutlined />}
            onClick={handleSplitSegment}
            disabled={!selectedSegmentId}
          >
            分割
          </Button>
          
          <Button
            danger
            icon={<DeleteOutlined />}
            onClick={handleDeleteSegment}
            disabled={!selectedSegmentId}
          >
            删除
          </Button>
        </Space>
      </div>

      {/* 片段列表 - 占用剩余空间并可滚动 */}
      <div className="flex-1 overflow-y-auto min-h-0">
        {segments.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <Text type="secondary">暂无片段，点击"添加片段"开始</Text>
          </div>
        ) : (
          <List
            size="small"
            dataSource={segments}
            renderItem={(segment) => (
              <List.Item
                className={`cursor-pointer transition-colors rounded p-2 ${
                  selectedSegmentId === segment.id
                    ? 'bg-primary/10 border-primary'
                    : 'hover:bg-gray-50'
                }`}
                onClick={() => setSelectedSegmentId(segment.id)}
                actions={[
                  <Button
                    key="jump"
                    type="text"
                    size="small"
                    onClick={(e) => {
                      e.stopPropagation();
                      jumpToSegment(segment);
                    }}
                  >
                    跳转
                  </Button>,
                  <Button
                    key="play"
                    type="text"
                    size="small"
                    icon={<PlayCircleOutlined />}
                    onClick={(e) => {
                      e.stopPropagation();
                      playSegment(segment);
                    }}
                  >
                    播放
                  </Button>
                ]}
              >
                <List.Item.Meta
                  title={
                    <div className="flex items-center space-x-2">
                      <Text strong>片段 {segment.index}</Text>
                      {!segment.isValid && (
                        <Tag color="warning">无效</Tag>
                      )}
                      {segment.warnings.length > 0 && (
                        <Tag color="orange">警告</Tag>
                      )}
                    </div>
                  }
                  description={
                    <div className="text-sm">
                      <div>
                        {VideoService.formatDuration(segment.startTime)} - {VideoService.formatDuration(segment.endTime)}
                      </div>
                      <div className="text-gray-500">
                        时长: {VideoService.formatDuration(segment.duration)}
                      </div>
                      {segment.warnings.length > 0 && (
                        <div className="text-orange-500 text-xs mt-1">
                          {segment.warnings.join(', ')}
                        </div>
                      )}
                    </div>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </div>
    </Card>
  );
};

export default SegmentControls;