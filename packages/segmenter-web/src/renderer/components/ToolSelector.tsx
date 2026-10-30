import React from 'react';
import { Radio, Typography, Tooltip } from 'antd';
import { ScissorOutlined, RotateRightOutlined } from '@ant-design/icons';
import { ToolType } from '../types';

const { Text } = Typography;

interface ToolSelectorProps {
  activeTool: ToolType;
  onToolChange: (tool: ToolType) => void;
  disabled?: boolean;
}

const ToolSelector: React.FC<ToolSelectorProps> = ({ 
  activeTool, 
  onToolChange, 
  disabled = false 
}) => {
  const tools = [
    {
      key: 'segmentation' as ToolType,
      label: '视频分割',
      icon: <ScissorOutlined />,
      description: '将视频分割成多个片段',
    },
    {
      key: 'rotation' as ToolType,
      label: '视频旋转',
      icon: <RotateRightOutlined />,
      description: '旋转视频并导出',
    },
  ];

  return (
    <div className="flex items-center gap-2">
      <Text strong className="text-sm">工具:</Text>
      <Radio.Group
        value={activeTool}
        onChange={(e) => onToolChange(e.target.value)}
        disabled={disabled}
        optionType="button"
        buttonStyle="solid"
        size="middle"
      >
        {tools.map((tool) => (
          <Tooltip key={tool.key} title={tool.description}>
            <Radio.Button value={tool.key}>
              <span className="flex items-center gap-1">
                {tool.icon}
                <span>{tool.label}</span>
              </span>
            </Radio.Button>
          </Tooltip>
        ))}
      </Radio.Group>
    </div>
  );
};

export default ToolSelector;