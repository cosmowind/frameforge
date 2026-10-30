import React, { useMemo, useState } from 'react';
import { 
  ConfigProvider, 
  Button, 
  Space, 
  Card, 
  Typography, 
  message, 
  Spin, 
  Tabs,
  FloatButton
} from 'antd';
import { 
  PlayCircleOutlined, 
  FolderOpenOutlined, 
  SaveOutlined, 
  FileTextOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  WarningOutlined,
  ScissorOutlined,
  EyeOutlined,
  EyeInvisibleOutlined
} from '@ant-design/icons';
import zhCN from 'antd/locale/zh_CN';
import { useAppStore } from './store/useAppStore';
import VideoService from './services/VideoService';
import SegmentationView from './components/SegmentationView';
import ReviewView from './components/ReviewView';
import VideoRotationView from './components/VideoRotationView';
import ToolSelector from './components/ToolSelector';
import { ToolType } from './types';

const { Title, Text } = Typography;
const { TabPane } = Tabs;

const App: React.FC = () => {
  const {
    currentVideo,
    segments,
    isProcessing,
    progress,
    isRulesPanelVisible,
    loadVideo,
    loadMetadata,
    saveMetadata,
    executeSegmentation,
    toggleRulesPanel,
    undo,
    canUndo,
  } = useAppStore();

  const [activeTool, setActiveTool] = useState<ToolType>('segmentation');

  // 添加键盘快捷键监听
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl+Z 撤销
      if (e.ctrlKey && e.key === 'z' && !e.shiftKey) {
        e.preventDefault();
        if (canUndo()) {
          undo();
          message.success('已撤销上次操作');
        } else {
          message.info('没有可撤销的操作');
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [undo, canUndo]);

  // 计算验证统计信息
  const validationStats = useMemo(() => {
    const valid = segments.filter(s => s.isValid).length;
    const invalid = segments.length - valid;
    const totalWarnings = segments.reduce((sum, s) => sum + s.warnings.length, 0);
    const totalDuration = segments.reduce((sum, s) => sum + s.duration, 0);
    const averageDuration = segments.length > 0 ? totalDuration / segments.length : 0;

    return {
      total: segments.length,
      valid,
      invalid,
      warnings: totalWarnings,
      totalDuration,
      averageDuration,
    };
  }, [segments]);

  const handleLoadVideo = async () => {
    try {
      const videoFile = await loadVideo(); // 获取加载的视频文件
      if (!videoFile) return;
      
      message.success('视频加载成功！');
    } catch (error) {
      message.error('视频加载失败：' + (error as Error).message);
    }
  };

  const handleLoadMetadata = async () => {
    try {
      await loadMetadata();
      message.success('元数据加载成功！');
    } catch (error) {
      message.error('元数据加载失败：' + (error as Error).message);
    }
  };

  const handleSaveMetadata = async () => {
    try {
      const savedPath = await saveMetadata();
      message.success(`元数据保存成功：${savedPath}`);
    } catch (error) {
      message.error('元数据保存失败：' + (error as Error).message);
    }
  };

  const handleExecuteSegmentation = async () => {
    try {
      const result = await executeSegmentation();
      if (result.success) {
        message.success(`视频分割成功！生成了${result.outputFiles.length}个文件`);
      }
    } catch (error) {
      message.error('视频分割失败：' + (error as Error).message);
    }
  };

  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: '#6366F1',
          borderRadius: 8,
          colorBgContainer: '#FFFFFF',
        },
      }}
    >
      <div className="w-full h-screen flex flex-col">
        {/* 顶部工具栏 */}
        <div className="bg-white border-b border-gray-200 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Title level={3} className="mb-0">视频工具箱</Title>
              {currentVideo && (
                <ToolSelector
                  activeTool={activeTool}
                  onToolChange={setActiveTool}
                  disabled={isProcessing}
                />
              )}
            </div>
            
            <Space>
              {!currentVideo ? (
                <Button 
                  type="primary" 
                  icon={<FolderOpenOutlined />}
                  onClick={handleLoadVideo}
                  loading={isProcessing}
                  size="large"
                >
                  选择视频文件
                </Button>
              ) : (
                <>
                  {activeTool === 'segmentation' && (
                    <>
                      <Button 
                        type="primary"
                        icon={<ScissorOutlined />}
                        onClick={handleExecuteSegmentation}
                        disabled={segments.length === 0 || isProcessing}
                        loading={isProcessing}
                      >
                        执行分割
                      </Button>
                      <Button 
                        icon={<SaveOutlined />}
                        onClick={handleSaveMetadata}
                        disabled={segments.length === 0}
                      >
                        保存元数据
                      </Button>
                      <Button 
                        icon={<FileTextOutlined />}
                        onClick={handleLoadMetadata}
                      >
                        加载元数据
                      </Button>
                    </>
                  )}
                  <Button 
                    onClick={handleLoadVideo}
                    loading={isProcessing}
                  >
                    重新选择
                  </Button>
                </>
              )}
            </Space>
          </div>

          {/* 视频信息栏 */}
          {currentVideo && (
            <div className="mt-4 flex items-center justify-between bg-gray-50 p-3 rounded">
              <div className="flex items-center space-x-6">
                <div>
                  <Text strong>文件: </Text>
                  <Text>{currentVideo.filename}</Text>
                </div>
                <div>
                  <Text strong>时长: </Text>
                  <Text>{VideoService.formatDuration(currentVideo.duration)}</Text>
                </div>
                <div>
                  <Text strong>分辨率: </Text>
                  <Text>{currentVideo.width} × {currentVideo.height}</Text>
                </div>
              </div>
              
              <div className="flex items-center space-x-4">
                <div className="flex items-center space-x-2">
                  <CheckCircleOutlined className="text-green-500" />
                  <Text>{validationStats.valid}</Text>
                </div>
                <div className="flex items-center space-x-2">
                  <ExclamationCircleOutlined className="text-red-500" />
                  <Text>{validationStats.invalid}</Text>
                </div>
                <div className="flex items-center space-x-2">
                  <WarningOutlined className="text-yellow-500" />
                  <Text>{validationStats.warnings}</Text>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* 主内容区域 */}
        <div className="flex-1">
          {!currentVideo ? (
            <div className="h-full flex items-center justify-center">
              <Card className="text-center">
                <PlayCircleOutlined className="text-6xl text-gray-300 mb-4" />
                <Title level={4}>请选择一个MP4视频文件</Title>
                <Button 
                  type="primary" 
                  icon={<FolderOpenOutlined />}
                  onClick={handleLoadVideo}
                  loading={isProcessing}
                  size="large"
                  className="mt-4"
                >
                  选择视频文件
                </Button>
              </Card>
            </div>
          ) : (
            <>
              {activeTool === 'segmentation' && (
                <Tabs 
                  defaultActiveKey="segmentation"
                  className="h-full"
                  tabBarStyle={{ paddingLeft: 16, paddingRight: 16, margin: 0 }}
                >
                  <TabPane 
                    tab={
                      <span>
                        <ScissorOutlined />
                        分割界面
                      </span>
                    } 
                    key="segmentation"
                  >
                    <SegmentationView />
                  </TabPane>
                  
                  <TabPane 
                    tab={
                      <span>
                        <EyeOutlined />
                        审核界面
                      </span>
                    } 
                    key="review"
                  >
                    <ReviewView />
                  </TabPane>
                </Tabs>
              )}
              
              {activeTool === 'rotation' && (
                <VideoRotationView />
              )}
            </>
          )}
        </div>
        
        {/* 浮动按钮 - 显示/隐藏规则面板 */}
        {currentVideo && (
          <FloatButton
            icon={isRulesPanelVisible ? <EyeInvisibleOutlined /> : <EyeOutlined />}
            tooltip={isRulesPanelVisible ? '隐藏规则面板' : '显示规则面板'}
            onClick={toggleRulesPanel}
            style={{ right: 24, bottom: 24 }}
          />
        )}
        
        {isProcessing && (
          <div className="fixed inset-0 bg-black/20 flex items-center justify-center z-50">
            <div className="bg-white p-6 rounded-lg shadow-lg min-w-80">
              <div className="flex items-center mb-4">
                <Spin size="large" />
                <Text className="ml-3 text-lg">
                  {progress ? '正在分割视频...' : '处理中...'}
                </Text>
              </div>
              {progress && (
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <Text>进度: {progress.currentSegment} / {progress.totalSegments}</Text>
                    <Text>{progress.percentage}%</Text>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div 
                      className="bg-primary h-2 rounded-full transition-all"
                      style={{ width: `${progress.percentage}%` }}
                    />
                  </div>
                  <Text className="text-sm text-gray-600">
                    当前文件: {progress.currentFile}
                  </Text>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </ConfigProvider>
  );
};

export default App;
