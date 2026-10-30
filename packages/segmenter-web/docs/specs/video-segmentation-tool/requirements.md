# 需求文档

## 简介

视频分割工具是一个桌面应用程序，用于将MP4视频文件分割成多个符合特定时长和质量要求的片段。该系统提供两个主要界面：分割界面供操作人员使用，检查界面供审核人员验证分割结果。系统需要处理大型视频文件（半分钟到5分钟，可达数GB），并支持打包为独立可执行文件以便分发。

## 术语表

- **VideoSegmentationSystem**: 视频分割系统，整个应用程序
- **SegmentationInterface**: 分割界面，供操作人员使用的主界面
- **ReviewInterface**: 检查界面，供审核人员使用的验证界面
- **SegmentMetadata**: 片段元数据，包含起始时间、结束时间等信息的JSON数据
- **Timeline**: 时间轴，用于可视化和编辑视频片段的交互组件
- **SegmentPoint**: 分割点，标记视频片段起始或结束的时间位置
- **SourceVideo**: 原始视频，待分割的MP4视频文件
- **OutputSegment**: 输出片段，分割后生成的视频文件

## 需求

### 需求 1

**用户故事:** 作为视频分割操作员，我希望能够加载MP4视频文件并在时间轴上查看，以便开始分割工作

#### 验收标准

1. WHEN 用户选择一个MP4视频文件 THEN VideoSegmentationSystem SHALL 加载该视频并在SegmentationInterface中显示视频预览
2. WHEN 视频加载完成 THEN VideoSegmentationSystem SHALL 在Timeline上显示完整的视频时长
3. WHEN 加载的视频文件大小在500MB到5GB之间 THEN VideoSegmentationSystem SHALL 在30秒内完成加载并显示预览
4. WHEN 用户尝试加载非MP4格式文件 THEN VideoSegmentationSystem SHALL 显示错误提示并拒绝加载
5. WHEN 视频文件路径包含中文字符 THEN VideoSegmentationSystem SHALL 正确识别并加载该文件

### 需求 2

**用户故事:** 作为视频分割操作员，我希望能够在时间轴上创建和编辑分割点，以便精确控制视频片段的起止位置

#### 验收标准

1. WHEN 用户在Timeline上点击某个时间位置 THEN VideoSegmentationSystem SHALL 创建一个新的SegmentPoint
2. WHEN 用户拖动已存在的SegmentPoint THEN VideoSegmentationSystem SHALL 更新该SegmentPoint的时间位置并实时显示时间值
3. WHEN 用户选择一个现有片段并点击分割按钮 THEN VideoSegmentationSystem SHALL 在该片段中间位置创建新的SegmentPoint将其分割为两个片段
4. WHEN 用户删除一个SegmentPoint THEN VideoSegmentationSystem SHALL 合并相邻的两个片段
5. WHEN 用户调整SegmentPoint位置 THEN VideoSegmentationSystem SHALL 在视频预览中跳转到对应时间帧

### 需求 3

**用户故事:** 作为视频分割操作员，我希望系统能够保存分割点信息到JSON文件，以便后续可以重新加载或执行实际分割

#### 验收标准

1. WHEN 用户点击保存按钮 THEN VideoSegmentationSystem SHALL 将所有SegmentPoint信息序列化为JSON格式并保存到文件
2. WHEN 用户加载已存在的SegmentMetadata文件 THEN VideoSegmentationSystem SHALL 解析JSON并在Timeline上恢复所有SegmentPoint
3. WHEN SegmentMetadata文件与SourceVideo文件名匹配 THEN VideoSegmentationSystem SHALL 自动关联两者
4. WHEN JSON文件包含无效的时间值 THEN VideoSegmentationSystem SHALL 显示错误信息并拒绝加载
5. WHEN 保存SegmentMetadata THEN VideoSegmentationSystem SHALL 包含原始视频文件名、总时长和所有片段的起止时间

### 需求 4

**用户故事:** 作为视频分割操作员，我希望执行实际的视频分割操作，以便生成符合命名规范的输出片段文件

#### 验收标准

1. WHEN 用户点击执行分割按钮 THEN VideoSegmentationSystem SHALL 根据SegmentMetadata将SourceVideo分割成多个OutputSegment文件
2. WHEN 生成OutputSegment文件 THEN VideoSegmentationSystem SHALL 使用格式"原文件名-序号.mp4"命名，其中序号从1开始递增
3. WHEN 分割视频 THEN VideoSegmentationSystem SHALL 保持原始视频的编码质量和参数
4. WHEN 分割过程中 THEN VideoSegmentationSystem SHALL 显示进度百分比和当前处理的片段编号
5. WHEN 所有片段分割完成 THEN VideoSegmentationSystem SHALL 显示成功消息并列出生成的文件路径

### 需求 5

**用户故事:** 作为视频分割操作员，我希望看到分割规则的参考提示，以便在不熟悉规则时查阅，熟悉后可以隐藏

#### 验收标准

1. WHEN SegmentationInterface首次加载 THEN VideoSegmentationSystem SHALL 在侧边栏显示分割规则参考面板
2. WHEN 用户点击隐藏按钮 THEN VideoSegmentationSystem SHALL 折叠规则参考面板并保留展开按钮
3. WHEN 用户点击展开按钮 THEN VideoSegmentationSystem SHALL 重新显示规则参考面板
4. WHEN 规则参考面板显示 THEN VideoSegmentationSystem SHALL 包含片段时长要求、画面内容要求和长视频切分规则的关键要点
5. WHEN 用户调整窗口大小 THEN VideoSegmentationSystem SHALL 保持规则面板的可读性和布局合理性

### 需求 6

**用户故事:** 作为视频分割操作员，我希望系统能够验证片段时长，以便确保所有片段符合5-25秒的要求

#### 验收标准

1. WHEN 用户创建或调整片段 THEN VideoSegmentationSystem SHALL 实时计算并显示该片段的时长
2. WHEN 片段时长小于5秒 THEN VideoSegmentationSystem SHALL 在该片段上显示警告标记
3. WHEN 片段时长大于25秒 THEN VideoSegmentationSystem SHALL 在该片段上显示警告标记
4. WHEN 用户尝试执行分割且存在时长不符合要求的片段 THEN VideoSegmentationSystem SHALL 显示确认对话框列出所有问题片段
5. WHEN 所有片段时长在5到25秒之间 THEN VideoSegmentationSystem SHALL 在执行分割按钮上显示就绪状态

### 需求 7

**用户故事:** 作为审核人员，我希望能够加载原始视频和分割元数据文件，以便按顺序检查所有分割片段

#### 验收标准

1. WHEN 用户在ReviewInterface中加载SourceVideo和SegmentMetadata THEN VideoSegmentationSystem SHALL 解析并显示所有片段的列表
2. WHEN 片段列表显示 THEN VideoSegmentationSystem SHALL 为每个片段显示序号、起止时间和时长
3. WHEN 用户点击列表中的某个片段 THEN VideoSegmentationSystem SHALL 在视频播放器中播放该片段对应的时间范围
4. WHEN 片段播放结束 THEN VideoSegmentationSystem SHALL 自动跳转到下一个片段并开始播放
5. WHEN 用户点击暂停按钮 THEN VideoSegmentationSystem SHALL 停止自动播放并保持在当前片段

### 需求 8

**用户故事:** 作为审核人员，我希望能够在检查界面中标记有问题的片段，以便反馈给操作员进行调整

#### 验收标准

1. WHEN 用户在ReviewInterface中查看某个片段 THEN VideoSegmentationSystem SHALL 提供标记按钮
2. WHEN 用户标记一个片段为有问题 THEN VideoSegmentationSystem SHALL 在片段列表中显示问题标记图标
3. WHEN 用户为问题片段添加备注 THEN VideoSegmentationSystem SHALL 保存备注文本到SegmentMetadata
4. WHEN 用户导出审核结果 THEN VideoSegmentationSystem SHALL 生成包含所有问题片段和备注的报告文件
5. WHEN SegmentMetadata包含审核标记 THEN VideoSegmentationSystem SHALL 在SegmentationInterface中高亮显示这些片段

### 需求 9

**用户故事:** 作为用户，我希望应用程序具有美观舒适的界面，以便长时间使用时减少视觉疲劳

#### 验收标准

1. WHEN 应用程序启动 THEN VideoSegmentationSystem SHALL 使用低饱和度柔和渐变色作为背景
2. WHEN 显示交互组件 THEN VideoSegmentationSystem SHALL 使用圆角边框和柔和阴影效果
3. WHEN 单个界面显示 THEN VideoSegmentationSystem SHALL 限制核心操作按钮数量不超过2个并提供充足留白
4. WHEN 显示文本内容 THEN VideoSegmentationSystem SHALL 使用合理的行间距和段落间距
5. WHEN 用户执行操作 THEN VideoSegmentationSystem SHALL 提供微妙的视觉反馈动画

### 需求 10

**用户故事:** 作为系统管理员，我希望能够将应用程序打包为独立可执行文件，以便分发给不同用户使用

#### 验收标准

1. WHEN 执行打包命令 THEN VideoSegmentationSystem SHALL 生成单个可执行文件包含所有必要依赖
2. WHEN 用户在未安装Python环境的Windows系统上运行可执行文件 THEN VideoSegmentationSystem SHALL 正常启动并运行所有功能
3. WHEN 可执行文件运行 THEN VideoSegmentationSystem SHALL 在10秒内完成启动并显示主界面
4. WHEN 打包完成 THEN VideoSegmentationSystem SHALL 生成的可执行文件大小不超过200MB
5. WHEN 应用程序使用外部库进行视频处理 THEN VideoSegmentationSystem SHALL 将所有必要的编解码器和库文件打包到可执行文件中
