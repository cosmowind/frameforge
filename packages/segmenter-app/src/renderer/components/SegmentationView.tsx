import React from 'react';
import { Layout, Card, Typography, Slider } from 'antd';
import VideoPlayer from './VideoPlayer';
import Timeline from './Timeline';
import SegmentControls from './SegmentControls';
import RulesPanel from './RulesPanel';
import { useAppStore } from '../store/useAppStore';

const { Content, Sider } = Layout;
const { Title } = Typography;

const SegmentationView: React.FC = () => {
  const [videoScale, setVideoScale] = React.useState(100); // 默认100%大小
  const videoContainerRef = React.useRef<HTMLDivElement>(null);
  const [videoNaturalHeight, setVideoNaturalHeight] = React.useState(0);
  
  const { 
    currentVideo, 
    isRulesPanelVisible,
  } = useAppStore();

  // 监听视频播放器的实际高度
  React.useEffect(() => {
    if (videoContainerRef.current) {
      const updateHeight = () => {
        const videoPlayerCard = videoContainerRef.current?.querySelector('.ant-card');
        if (videoPlayerCard) {
          setVideoNaturalHeight(videoPlayerCard.clientHeight);
        }
      };
      
      // 初始化时获取高度
      setTimeout(updateHeight, 100);
      
      // 监听窗口大小变化
      window.addEventListener('resize', updateHeight);
      return () => window.removeEventListener('resize', updateHeight);
    }
  }, [currentVideo]);

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
        {/* 视频播放器区域 - 使用 transform scale 缩放，并调整容器高度 */}
        <div 
          className="flex-shrink-0"
          style={{
            height: videoNaturalHeight ? `${videoNaturalHeight * (videoScale / 100)}px` : 'auto',
            minHeight: '200px',
            overflow: 'visible'
          }}
        >
          <div 
            ref={videoContainerRef}
            style={{ 
              transform: `scale(${videoScale / 100})`, 
              transformOrigin: 'top center',
              width: '100%'
            }}
          >
            <VideoPlayer />
          </div>
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
      
      {/* 规则面板侧边栏 - 带视频缩放控制 */}
      {isRulesPanelVisible && (
        <Sider 
          width={320} 
          className="bg-white/90 backdrop-blur-sm border-l border-gray-200 flex flex-col"
          style={{ height: '100%' }}
        >
          {/* 视频缩放控制 */}
          <div className="p-4 border-b border-gray-200">
            <div className="text-sm font-medium mb-2">视频缩放</div>
            <div className="flex items-center gap-2">
              <Slider
                min={50}
                max={150}
                value={videoScale}
                onChange={setVideoScale}
                className="flex-1"
                tooltip={{ formatter: (value) => `${value}%` }}
              />
              <span className="text-xs text-gray-500 w-12">{videoScale}%</span>
            </div>
          </div>
          
          {/* 规则面板内容 */}
          <div className="flex-1 overflow-hidden">
            <RulesPanel />
          </div>
        </Sider>
      )}
    </Layout>
  );
};

export default SegmentationView;