import React, { useState } from 'react';
import { 
  Layout, 
  Card, 
  Typography, 
  Button, 
  Space, 
  Select, 
  message, 
  Spin, 
  Progress,
  Radio,
  Divider
} from 'antd';
import { 
  RotateRightOutlined, 
  RotateLeftOutlined, 
  ExportOutlined,
  PlayCircleOutlined
} from '@ant-design/icons';
import VideoPlayer from './VideoPlayer';
import { useAppStore } from '../store/useAppStore';
import { RotationAngle } from '../types';

const { Content } = Layout;
const { Title, Text } = Typography;

const VideoRotationView: React.FC = () => {
  const { currentVideo, isProcessing, progress, rotateVideo } = useAppStore();
  const [rotationAngle, setRotationAngle] = useState<RotationAngle>(90);
  const [clockwise, setClockwise] = useState(true);
  const [isRotating, setIsRotating] = useState(false);
  const [rotateProgress, setRotateProgress] = useState(0);

  const rotationOptions = [
    { label: '90°', value: 90 },
    { label: '180°', value: 180 },
    { label: '270°', value: 270 },
  ];

  const handleRotate = async () => {
    if (!currentVideo?.file && !currentVideo?.path) {
      message.error('请先加载视频文件');
      return;
    }

    setIsRotating(true);
    setRotateProgress(0);

    try {
      // 模拟进度更新
      const progressInterval = setInterval(() => {
        setRotateProgress(prev => {
          if (prev >= 90) {
            clearInterval(progressInterval);
            return 90;
          }
          return prev + 10;
        });
      }, 200);

      const result = await rotateVideo(rotationAngle, clockwise);

      clearInterval(progressInterval);
      setRotateProgress(100);

      if (result.success) {
        message.success(`视频旋转成功！输出文件: ${result.outputFile}`);
      } else {
        message.error(`视频旋转失败: ${result.error}`);
      }
    } catch (error) {
      console.error('旋转视频失败:', error);
      message.error('旋转视频失败: ' + (error as Error).message);
    } finally {
      setIsRotating(false);
      setRotateProgress(0);
    }
  };

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
      <Content className="flex flex-col p-4 gap-4">
        {/* 视频播放器区域 */}
        <div className="flex-shrink-0">
          <VideoPlayer />
        </div>
        
        {/* 旋转控制区域 */}
        <Card title="视频旋转设置" className="flex-shrink-0">
          <div className="space-y-4">
            {/* 旋转角度选择 */}
            <div>
              <Text strong className="block mb-2">旋转角度</Text>
              <Radio.Group
                value={rotationAngle}
                onChange={(e) => setRotationAngle(e.target.value)}
                optionType="button"
                buttonStyle="solid"
              >
                {rotationOptions.map((option) => (
                  <Radio.Button key={option.value} value={option.value}>
                    {option.label}
                  </Radio.Button>
                ))}
              </Radio.Group>
            </div>

            {/* 旋转方向 */}
            <div>
              <Text strong className="block mb-2">旋转方向</Text>
              <Radio.Group
                value={clockwise}
                onChange={(e) => setClockwise(e.target.value)}
              >
                <Radio value={true}>顺时针</Radio>
                <Radio value={false}>逆时针</Radio>
              </Radio.Group>
            </div>

            {/* 视频信息 */}
            <div className="bg-gray-50 p-3 rounded">
              <Text strong className="block mb-2">当前视频信息</Text>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <Text type="secondary">文件名: </Text>
                  <Text>{currentVideo.filename}</Text>
                </div>
                <div>
                  <Text type="secondary">分辨率: </Text>
                  <Text>{currentVideo.width} × {currentVideo.height}</Text>
                </div>
                <div>
                  <Text type="secondary">时长: </Text>
                  <Text>{Math.round(currentVideo.duration)}秒</Text>
                </div>
                <div>
                  <Text type="secondary">编码: </Text>
                  <Text>{currentVideo.codec}</Text>
                </div>
              </div>
            </div>

            {/* 旋转说明 */}
            <div className="bg-blue-50 p-3 rounded">
              <Text type="secondary" className="text-sm">
                <strong>说明:</strong> 旋转后的视频将自动调整尺寸，不会出现黑边。
                例如：1920×1080 的视频旋转90°后将变为 1080×1920。
              </Text>
            </div>

            {/* 旋转按钮 */}
            <div className="flex justify-center">
              <Button
                type="primary"
                size="large"
                icon={<RotateRightOutlined />}
                onClick={handleRotate}
                loading={isRotating}
                disabled={!currentVideo}
                className="w-48"
              >
                {isRotating ? '旋转中...' : '旋转并导出'}
              </Button>
            </div>

            {/* 进度显示 */}
            {isRotating && (
              <div className="mt-4">
                <Progress
                  percent={rotateProgress}
                  status="active"
                  strokeColor={{ from: '#108ee9', to: '#87d068' }}
                />
                <Text className="text-sm text-gray-500 block mt-1">
                  正在旋转视频，请稍候...
                </Text>
              </div>
            )}
          </div>
        </Card>
      </Content>
    </Layout>
  );
};

export default VideoRotationView;