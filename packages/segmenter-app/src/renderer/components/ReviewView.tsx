import React from 'react';
import { Layout, Card, Typography } from 'antd';
import VideoPlayer from './VideoPlayer';
import Timeline from './Timeline';
import SegmentControls from './SegmentControls';
import { useAppStore } from '../store/useAppStore';

const { Content } = Layout;
const { Title } = Typography;

const ReviewView: React.FC = () => {
  const { currentVideo } = useAppStore();

  if (!currentVideo) {
    return (
      <div className="flex items-center justify-center h-full">
        <Card className="text-center">
          <Title level={3}>请先加载视频文件</Title>
        </Card>
      </div>
    );
  }

  return (
    <Layout className="h-full bg-transparent">
      <Content className="flex flex-col p-4 gap-2">
        {/* 视频播放器区域 */}
        <div className="flex-shrink-0">
          <VideoPlayer />
        </div>
        
        {/* 时间轴区域 - 固定高度 */}
        <div className="flex-shrink-0" style={{ height: '220px' }}>
          <Timeline />
        </div>
        
        {/* 片段控制区域 - 占据剩余空间 */}
        <div className="flex-1 min-h-0">
          <SegmentControls />
        </div>
      </Content>
    </Layout>
  );
};

export default ReviewView;
