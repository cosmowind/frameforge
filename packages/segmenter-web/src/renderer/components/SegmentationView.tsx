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
  const [videoScale, setVideoScale] = React.useState(100);
  const [videoPlayerHeight, setVideoPlayerHeight] = React.useState(0);
  const videoContainerRef = React.useRef<HTMLDivElement>(null);
  
  const { 
    currentVideo, 
    isRulesPanelVisible,
  } = useAppStore();

  // 监听视频播放器的实际高度
  React.useEffect(() => {
    const updateHeight = () => {
      if (videoContainerRef.current) {
        const card = videoContainerRef.current.querySelector('.ant-card');
        if (card) {
          setVideoPlayerHeight(card.scrollHeight);
        }
      }
    };
    
    // 延迟获取高度，等待视频加载
    const timer = setTimeout(updateHeight, 200);
    window.addEventListener('resize', updateHeight);
    
    return () => {
      clearTimeout(timer);
      window.removeEventListener('resize', updateHeight);
    };
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

  // 计算视频容器实际占用的高度（考虑缩放）
  const scaledVideoHeight = videoPlayerHeight * (videoScale / 100);

  return (
    <Layout className="h-full bg-transparent">
      {/* 主内容区域 - 可滚动 */}
      <Content className="overflow-auto">
        <div className="p-4">
          {/* 视频播放器区域 */}
          <div 
            ref={videoContainerRef}
            className="mb-4"
            style={{
              height: `${scaledVideoHeight}px`,
              minHeight: '200px',
              position: 'relative',
            }}
          >
            <div 
              style={{ 
                transform: `scale(${videoScale / 100})`, 
                transformOrigin: 'top center',
                width: '100%',
                height: videoPlayerHeight ? `${videoPlayerHeight}px` : 'auto',
              }}
            >
              <VideoPlayer />
            </div>
          </div>
          
          {/* 时间轴区域 - 紧跟在视频下方 */}
          <div className="mb-4" style={{ height: '180px' }}>
            <Timeline />
          </div>
          
          {/* 片段控制区域 - 在时间轴下方 */}
          <div>
            <SegmentControls />
          </div>
        </div>
      </Content>
      
      {/* 规则面板侧边栏 */}
      {isRulesPanelVisible && (
        <Sider 
          width={320} 
          className="bg-white/90 backdrop-blur-sm border-l border-gray-200 flex flex-col"
          style={{ height: '100%', overflow: 'auto' }}
        >
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
          
          <div className="flex-1 overflow-hidden">
            <RulesPanel />
          </div>
        </Sider>
      )}
    </Layout>
  );
};

export default SegmentationView;
