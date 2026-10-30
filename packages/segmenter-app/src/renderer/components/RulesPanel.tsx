import React from 'react';
import { Card, Typography, Divider, List, Tag, Button } from 'antd';
import { 
  EyeInvisibleOutlined,
  InfoCircleOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined 
} from '@ant-design/icons';
import { useAppStore } from '../store/useAppStore';

const { Title, Text, Paragraph } = Typography;

const RulesPanel: React.FC = () => {
  const { toggleRulesPanel } = useAppStore();

  const rules = [
    {
      title: '片段时长要求',
      items: [
        '每个片段时长必须大于 5 秒',
        '每个片段时长必须小于 25 秒',
        '少于等于 5 秒的片段不保留',
        '大于等于 25 秒的片段需要继续切分'
      ]
    },
    {
      title: '画面内容要求',
      items: [
        '双手都出现在画面中',
        '双手位置尽量在画面偏中心区域',
        '视频要能全程双手看得见',
        '画面尽量稳定、清晰',
        '动作连续，不要切得太碎'
      ]
    },
    {
      title: '长视频切分规则',
      items: [
        '40秒优质视频切成 20秒 + 20秒',
        '每个输出片段仍要满足 5-25 秒要求',
        '尽量切成长度自然、内容完整的片段',
        '不要为了硬凑时长而把动作切断'
      ]
    }
  ];

  const invalidContent = [
    '双手长时间不在画面里',
    '双手明显不在中心区域',
    '画面模糊、抖动严重、遮挡严重',
    '基本没有有效动作的信息',
    '时长过短、没有保留价值的片段'
  ];

  return (
    <div className="h-full flex flex-col p-4">
      {/* 标题栏 */}
      <div className="flex items-center justify-between mb-4">
        <Title level={4} className="mb-0">分割规则参考</Title>
        <Button
          type="text"
          size="small"
          icon={<EyeInvisibleOutlined />}
          onClick={toggleRulesPanel}
          title="隐藏规则面板"
        />
      </div>

      {/* 规则内容 */}
      <div className="flex-1 overflow-y-auto space-y-4">
        {/* 目的说明 */}
        <Card size="small">
          <div className="flex items-start space-x-2">
            <InfoCircleOutlined className="text-blue-500 mt-1" />
            <div>
              <Text strong>目的</Text>
              <Paragraph className="text-sm text-gray-600 mb-0 mt-1">
                将原始视频切割成可用的视频片段，方便后续筛选和跑算法
              </Paragraph>
            </div>
          </div>
        </Card>

        {/* 切割要求 */}
        {rules.map((rule, index) => (
          <Card key={index} size="small">
            <div className="flex items-start space-x-2">
              <CheckCircleOutlined className="text-green-500 mt-1" />
              <div className="flex-1">
                <Text strong>{rule.title}</Text>
                <List
                  size="small"
                  className="mt-2"
                  dataSource={rule.items}
                  renderItem={(item) => (
                    <List.Item className="py-1 border-0">
                      <Text className="text-sm">• {item}</Text>
                    </List.Item>
                  )}
                />
              </div>
            </div>
          </Card>
        ))}

        <Divider />

        {/* 需要删除的内容 */}
        <Card size="small">
          <div className="flex items-start space-x-2">
            <ExclamationCircleOutlined className="text-red-500 mt-1" />
            <div className="flex-1">
              <Text strong className="text-red-600">需要删除的无效片段</Text>
              <List
                size="small"
                className="mt-2"
                dataSource={invalidContent}
                renderItem={(item) => (
                  <List.Item className="py-1 border-0">
                    <Text className="text-sm text-red-600">✗ {item}</Text>
                  </List.Item>
                )}
              />
            </div>
          </div>
        </Card>

        {/* 执行原则 */}
        <Card size="small">
          <Text strong>执行原则</Text>
          <Paragraph className="text-sm text-gray-600 mt-2 mb-0">
            如果不确定某个片段是否应该保留，请优先按照以下原则判断：
          </Paragraph>
          <List
            size="small"
            className="mt-2"
            dataSource={[
              '宁可少保留明显无效片段，也不要把很多没用内容留下来',
              '优先保留双手清晰、居中、动作连续的片段',
              '保证最终输出的视频片段更干净、更方便后续使用'
            ]}
            renderItem={(item) => (
              <List.Item className="py-1 border-0">
                <Text className="text-sm">• {item}</Text>
              </List.Item>
            )}
          />
        </Card>

        {/* 快捷提示 */}
        <div className="bg-blue-50 p-3 rounded">
          <Text strong className="text-blue-700">💡 快捷提示</Text>
          <div className="mt-2 space-y-1">
            <div className="flex items-center space-x-2">
              <Tag color="green">有效</Tag>
              <Text className="text-sm">5-25秒，双手清晰居中</Text>
            </div>
            <div className="flex items-center space-x-2">
              <Tag color="orange">警告</Tag>
              <Text className="text-sm">时长接近边界值</Text>
            </div>
            <div className="flex items-center space-x-2">
              <Tag color="red">无效</Tag>
              <Text className="text-sm">时长不符合要求</Text>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default RulesPanel;