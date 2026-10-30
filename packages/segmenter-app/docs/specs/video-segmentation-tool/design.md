# 设计文档

## 概述

视频分割工具是一个基于Web技术构建的桌面应用程序，使用Electron框架实现跨平台支持，并使用FFmpeg进行视频处理。应用程序提供两个主要界面：分割界面和检查界面，通过React构建响应式UI，使用视频时间轴组件实现精确的片段编辑功能。

技术栈选择：
- **前端框架**: React + TypeScript - 提供类型安全和组件化开发
- **桌面框架**: Electron - 支持打包为独立可执行文件
- **视频处理**: FFmpeg - 高质量视频分割，保持原始编码参数
- **UI库**: Ant Design + Tailwind CSS - 快速构建美观界面
- **状态管理**: Zustand - 轻量级状态管理
- **视频播放**: Video.js - 强大的HTML5视频播放器

## 架构

### 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                     Electron Main Process                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Window Mgmt  │  │ File System  │  │ FFmpeg Processor │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ IPC
                              │
┌─────────────────────────────────────────────────────────────┐
│                   Electron Renderer Process                  │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                      React App                          │ │
│  │                                                          │ │
│  │  ┌──────────────────┐      ┌──────────────────┐       │ │
│  │  │ Segmentation UI  │      │   Review UI      │       │ │
│  │  │                  │      │                  │       │ │
│  │  │ - Timeline       │      │ - Segment List   │       │ │
│  │  │ - Video Preview  │      │ - Video Player   │       │ │
│  │  │ - Rules Panel    │      │ - Annotation     │       │ │
│  │  └──────────────────┘      └──────────────────┘       │ │
│  │                                                          │ │
│  │  ┌──────────────────────────────────────────────────┐  │ │
│  │  │            State Management (Zustand)            │  │ │
│  │  └──────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 分层架构

1. **表现层 (Presentation Layer)**
   - React组件：SegmentationView, ReviewView, Timeline, VideoPlayer
   - UI状态管理和用户交互处理

2. **业务逻辑层 (Business Logic Layer)**
   - SegmentManager: 管理片段的创建、编辑、删除
   - ValidationService: 验证片段时长和规则
   - MetadataService: 处理JSON序列化和反序列化

3. **数据访问层 (Data Access Layer)**
   - FileService: 文件读写操作
   - VideoService: 视频元数据提取

4. **基础设施层 (Infrastructure Layer)**
   - FFmpegService: 视频分割执行
   - IPCService: 主进程和渲染进程通信

## 组件和接口

### 核心数据模型

```typescript
interface SegmentPoint {
  id: string;
  time: number; // 秒
  type: 'start' | 'end';
}

interface VideoSegment {
  id: string;
  startTime: number;
  endTime: number;
  duration: number;
  index: number;
  isValid: boolean;
  warnings: string[];
  annotation?: SegmentAnnotation;
}

interface SegmentAnnotation {
  hasIssue: boolean;
  note: string;
  reviewedBy?: string;
  reviewedAt?: Date;
}

interface SegmentMetadata {
  version: string;
  sourceVideoName: string;
  sourceVideoDuration: number;
  createdAt: Date;
  modifiedAt: Date;
  segments: VideoSegment[];
}

interface VideoInfo {
  filename: string;
  path: string;
  duration: number;
  width: number;
  height: number;
  codec: string;
  bitrate: number;
}
```

### Timeline组件接口

```typescript
interface TimelineProps {
  videoDuration: number;
  segments: VideoSegment[];
  currentTime: number;
  onSegmentCreate: (time: number) => void;
  onSegmentUpdate: (segmentId: string, startTime: number, endTime: number) => void;
  onSegmentDelete: (segmentId: string) => void;
  onSegmentSplit: (segmentId: string) => void;
  onTimeChange: (time: number) => void;
}

interface TimelineState {
  scale: number; // 缩放级别
  scrollPosition: number;
  selectedSegmentId: string | null;
  isDragging: boolean;
  dragTarget: 'start' | 'end' | null;
}
```

### SegmentManager服务接口

```typescript
interface ISegmentManager {
  createSegment(startTime: number, endTime: number): VideoSegment;
  updateSegment(segmentId: string, updates: Partial<VideoSegment>): void;
  deleteSegment(segmentId: string): void;
  splitSegment(segmentId: string): [VideoSegment, VideoSegment];
  validateSegment(segment: VideoSegment): ValidationResult;
  getAllSegments(): VideoSegment[];
  getSegmentById(id: string): VideoSegment | null;
}

interface ValidationResult {
  isValid: boolean;
  warnings: string[];
  errors: string[];
}
```

### FFmpegService接口

```typescript
interface IFFmpegService {
  splitVideo(
    inputPath: string,
    segments: VideoSegment[],
    outputDir: string,
    onProgress: (progress: ProgressInfo) => void
  ): Promise<SplitResult>;
  
  extractVideoInfo(videoPath: string): Promise<VideoInfo>;
  
  extractFrame(videoPath: string, time: number): Promise<string>; // 返回base64
}

interface ProgressInfo {
  currentSegment: number;
  totalSegments: number;
  percentage: number;
  currentFile: string;
}

interface SplitResult {
  success: boolean;
  outputFiles: string[];
  errors: string[];
}
```

### MetadataService接口

```typescript
interface IMetadataService {
  saveMetadata(metadata: SegmentMetadata, filePath: string): Promise<void>;
  loadMetadata(filePath: string): Promise<SegmentMetadata>;
  validateMetadata(metadata: unknown): metadata is SegmentMetadata;
  exportReviewReport(metadata: SegmentMetadata): Promise<string>;
}
```

## 数据模型

### 状态管理结构

使用Zustand管理应用状态：

```typescript
interface AppState {
  // 视频相关
  currentVideo: VideoInfo | null;
  videoElement: HTMLVideoElement | null;
  
  // 片段相关
  segments: VideoSegment[];
  selectedSegmentId: string | null;
  
  // 元数据
  metadata: SegmentMetadata | null;
  metadataPath: string | null;
  
  // UI状态
  currentView: 'segmentation' | 'review';
  isRulesPanelVisible: boolean;
  isProcessing: boolean;
  progress: ProgressInfo | null;
  
  // 操作
  loadVideo: (path: string) => Promise<void>;
  loadMetadata: (path: string) => Promise<void>;
  saveMetadata: (path: string) => Promise<void>;
  addSegment: (startTime: number, endTime: number) => void;
  updateSegment: (id: string, updates: Partial<VideoSegment>) => void;
  deleteSegment: (id: string) => void;
  splitSegment: (id: string) => void;
  executeSegmentation: (outputDir: string) => Promise<void>;
  toggleRulesPanel: () => void;
  switchView: (view: 'segmentation' | 'review') => void;
}
```

### 文件命名规范

- 原始视频: `gx010033.mp4`
- 输出片段: `gx010033-1.mp4`, `gx010033-2.mp4`, ...
- 元数据文件: `gx010033-metadata.json`
- 审核报告: `gx010033-review-report.json`

## 正确性属性

*属
性是指在系统的所有有效执行中都应该成立的特征或行为——本质上是关于系统应该做什么的正式陈述。属性充当人类可读规范和机器可验证正确性保证之间的桥梁。*

### 属性 1: 视频加载后时间轴显示正确时长
*对于任何*有效的MP4视频文件，加载后时间轴显示的时长应该等于视频的实际时长
**验证: 需求 1.2**

### 属性 2: 非MP4文件被正确拒绝
*对于任何*非MP4格式的文件（.avi, .mov, .txt等），加载操作应该返回错误并且不创建视频对象
**验证: 需求 1.4**

### 属性 3: 创建分割点增加片段数量
*对于任何*有效的时间位置（在0到视频时长之间），在该位置创建分割点应该使片段数量增加1
**验证: 需求 2.1**

### 属性 4: 更新分割点改变片段边界
*对于任何*现有的分割点和新的有效时间位置，更新分割点位置应该改变相关片段的起止时间
**验证: 需求 2.2**

### 属性 5: 分割片段产生两个子片段
*对于任何*现有片段，分割操作应该产生两个新片段，且两个新片段的时长之和等于原片段时长
**验证: 需求 2.3**

### 属性 6: 删除分割点减少片段数量
*对于任何*现有的分割点，删除操作应该使片段数量减少1，且相邻片段合并
**验证: 需求 2.4**

### 属性 7: 元数据序列化往返一致性
*对于任何*片段集合，序列化为JSON后再反序列化应该得到等价的片段集合（所有片段的起止时间保持一致）
**验证: 需求 3.1, 3.2**

### 属性 8: 匹配文件名自动关联
*对于任何*视频文件和同名的元数据文件（如gx010033.mp4和gx010033-metadata.json），系统应该自动识别并关联两者
**验证: 需求 3.3**

### 属性 9: 无效JSON被正确拒绝
*对于任何*包含无效时间值的JSON文件（负数、超出范围、非数字等），加载操作应该返回错误并拒绝加载
**验证: 需求 3.4**

### 属性 10: 元数据包含完整信息
*对于任何*片段集合，保存的元数据JSON应该包含原始视频文件名、总时长和所有片段的起止时间
**验证: 需求 3.5**

### 属性 11: 输出文件命名符合规范
*对于任何*原始视频文件名和片段数量，生成的输出文件名应该符合"原文件名-序号.mp4"格式，序号从1开始连续递增
**验证: 需求 4.2**

### 属性 12: 分割保持视频编码参数
*对于任何*视频分割操作，输出片段的编码参数（编解码器、比特率、分辨率）应该与原始视频保持一致
**验证: 需求 4.3**

### 属性 13: 分割过程报告进度
*对于任何*分割操作，处理过程中应该触发进度回调，报告当前处理的片段编号和完成百分比
**验证: 需求 4.4**

### 属性 14: 规则面板切换改变可见性
*对于任何*规则面板状态，点击切换按钮应该改变面板的可见性状态（显示变为隐藏，隐藏变为显示）
**验证: 需求 5.2, 5.3**

### 属性 15: 片段时长正确计算
*对于任何*片段的起止时间，计算的时长应该等于结束时间减去开始时间
**验证: 需求 6.1**

### 属性 16: 短片段显示警告
*对于任何*时长小于5秒的片段，系统应该标记该片段为无效并显示警告
**验证: 需求 6.2**

### 属性 17: 长片段显示警告
*对于任何*时长大于25秒的片段，系统应该标记该片段为无效并显示警告
**验证: 需求 6.3**

### 属性 18: 存在无效片段时阻止执行
*对于任何*包含无效片段（时长不在5-25秒范围内）的片段集合，执行分割操作前应该显示确认对话框并列出所有问题片段
**验证: 需求 6.4**

### 属性 19: 审核界面显示完整片段信息
*对于任何*片段列表，每个片段的显示应该包含序号、起止时间和时长信息
**验证: 需求 7.2**

### 属性 20: 点击片段跳转播放
*对于任何*片段列表中的片段，点击该片段应该使视频播放器跳转到该片段的开始时间
**验证: 需求 7.3**

### 属性 21: 标记片段更新显示状态
*对于任何*片段，标记为有问题后应该在片段列表中显示问题标记图标
**验证: 需求 8.2**

### 属性 22: 备注保存到元数据
*对于任何*片段的备注文本，添加备注后应该更新该片段在元数据中的annotation字段
**验证: 需求 8.3**

### 属性 23: 审核报告包含所有问题片段
*对于任何*包含问题标记的元数据，导出的审核报告应该包含所有标记为有问题的片段及其备注
**验证: 需求 8.4**

### 属性 24: 核心操作按钮数量限制
*对于任何*单个界面视图，显示的核心操作按钮数量应该不超过2个
**验证: 需求 9.3**

### 属性 25: 打包文件大小限制
*对于任何*打包操作，生成的可执行文件大小应该不超过200MB
**验证: 需求 10.4**

## 错误处理

### 错误类型和处理策略

1. **文件系统错误**
   - 文件不存在: 显示友好错误消息，提示用户选择有效文件
   - 文件权限不足: 提示用户检查文件权限或选择其他位置
   - 磁盘空间不足: 在分割前检查可用空间，不足时提前警告

2. **视频处理错误**
   - 视频格式不支持: 明确提示仅支持MP4格式
   - 视频损坏: 提示文件可能损坏，建议使用其他文件
   - FFmpeg执行失败: 记录详细错误日志，显示简化的用户消息

3. **数据验证错误**
   - JSON格式错误: 提示文件格式不正确，无法解析
   - 时间值无效: 指出具体哪个时间值有问题（负数、超出范围等）
   - 片段重叠: 检测并提示用户调整片段边界

4. **用户输入错误**
   - 无效的时间输入: 实时验证并高亮显示错误
   - 空文件名: 阻止保存并提示输入有效文件名
   - 重复的输出文件: 询问用户是否覆盖

### 错误恢复机制

- **自动保存**: 每次编辑后自动保存元数据到临时文件
- **撤销/重做**: 支持操作历史，允许用户撤销错误操作
- **状态恢复**: 应用崩溃后重启时恢复上次的工作状态
- **部分成功处理**: 分割过程中如果某个片段失败，继续处理其他片段，最后报告失败的片段

### 日志记录

- **操作日志**: 记录所有用户操作和系统响应
- **错误日志**: 详细记录错误堆栈和上下文信息
- **性能日志**: 记录视频加载和分割的耗时
- **日志位置**: 存储在用户数据目录，便于问题排查

## 测试策略

### 单元测试

使用Jest作为测试框架，针对以下组件编写单元测试：

1. **SegmentManager测试**
   - 测试片段创建、更新、删除的基本功能
   - 测试片段分割逻辑的正确性
   - 测试边界条件（空片段列表、单个片段等）

2. **ValidationService测试**
   - 测试时长验证规则（5-25秒）
   - 测试时间值有效性检查
   - 测试片段重叠检测

3. **MetadataService测试**
   - 测试JSON序列化和反序列化
   - 测试文件名匹配逻辑
   - 测试无效数据的错误处理

4. **文件命名测试**
   - 测试输出文件名生成规则
   - 测试特殊字符处理
   - 测试序号递增逻辑

### 基于属性的测试

使用fast-check库进行基于属性的测试，每个测试运行至少100次迭代：

1. **属性测试配置**
   - 每个属性测试必须运行至少100次迭代
   - 每个测试必须使用注释标记对应的设计文档属性
   - 标记格式: `// Feature: video-segmentation-tool, Property X: [属性描述]`

2. **核心属性测试**
   - **属性 7**: 元数据序列化往返测试
     - 生成随机片段集合
     - 序列化后反序列化
     - 验证所有时间值保持一致
   
   - **属性 11**: 文件命名规范测试
     - 生成随机文件名和片段数量
     - 验证输出文件名格式正确
     - 验证序号连续递增
   
   - **属性 15**: 时长计算测试
     - 生成随机起止时间
     - 验证计算的时长等于差值
   
   - **属性 16-17**: 时长验证测试
     - 生成各种时长的片段
     - 验证警告标记正确显示

3. **生成器设计**
   - **时间生成器**: 生成0到视频时长之间的有效时间值
   - **片段生成器**: 生成有效的片段对象，确保起始时间小于结束时间
   - **文件名生成器**: 生成符合规范的视频文件名
   - **元数据生成器**: 生成完整的元数据对象

### 集成测试

1. **端到端工作流测试**
   - 加载视频 → 创建片段 → 保存元数据 → 执行分割
   - 加载视频和元数据 → 审核界面查看 → 标记问题 → 导出报告

2. **FFmpeg集成测试**
   - 使用小型测试视频验证分割功能
   - 验证输出视频的编码参数
   - 测试进度回调机制

3. **文件系统集成测试**
   - 测试文件读写操作
   - 测试路径处理（包括中文路径）
   - 测试错误场景（权限不足、磁盘满等）

### 测试数据

- **测试视频**: 准备不同时长和大小的MP4测试文件（5秒、30秒、2分钟）
- **测试元数据**: 准备各种场景的JSON文件（有效、无效、边界情况）
- **模拟数据**: 使用工厂函数生成测试用的片段和元数据对象

### 性能测试

虽然不在自动化测试范围内，但需要手动验证：
- 大文件（2-5GB）加载时间
- 多片段分割的总耗时
- UI响应性（时间轴拖动、视频预览）

## UI/UX设计指南

### 设计原则

1. **低饱和柔焦渐变**
   - 背景使用低饱和度的渐变色（如#F5F7FA到#E4E9F2）
   - 避免纯黑纯白的高对比
   - 营造温和舒适的视觉氛围

2. **简洁操作**
   - 每个界面最多2个核心操作按钮
   - 次要功能收起或弱化显示
   - 充足的留白和呼吸感

3. **圆润温和**
   - 所有组件使用圆角（border-radius: 8-12px）
   - 使用柔和阴影（box-shadow: 0 2px 8px rgba(0,0,0,0.08)）
   - 避免尖锐的边角

4. **微交互反馈**
   - 按钮悬停时轻微放大（scale: 1.02）
   - 操作成功时显示微妙的动画
   - 使用缓动函数（ease-in-out）

### 颜色方案

```css
/* 主色调 */
--primary: #6366F1;        /* 柔和的靛蓝 */
--primary-light: #818CF8;
--primary-dark: #4F46E5;

/* 背景色 */
--bg-primary: #F5F7FA;
--bg-secondary: #FFFFFF;
--bg-tertiary: #E4E9F2;

/* 文本色 */
--text-primary: #1F2937;
--text-secondary: #6B7280;
--text-tertiary: #9CA3AF;

/* 状态色 */
--success: #10B981;
--warning: #F59E0B;
--error: #EF4444;
--info: #3B82F6;

/* 阴影 */
--shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
--shadow-md: 0 2px 8px rgba(0, 0, 0, 0.08);
--shadow-lg: 0 4px 16px rgba(0, 0, 0, 0.12);
```

### 组件样式规范

1. **按钮**
   - 主按钮: 使用primary色，圆角12px，padding 12px 24px
   - 次按钮: 使用outline样式，相同圆角和padding
   - 悬停效果: 轻微放大和阴影加深

2. **时间轴**
   - 背景: 半透明白色（rgba(255,255,255,0.8)）
   - 片段块: 使用primary色，透明度0.7
   - 警告片段: 使用warning色
   - 拖动手柄: 圆形，直径12px

3. **视频播放器**
   - 使用Video.js的默认样式，调整颜色匹配主题
   - 控制栏使用半透明背景
   - 进度条使用primary色

4. **侧边栏**
   - 使用毛玻璃效果（backdrop-filter: blur(10px)）
   - 半透明背景（rgba(255,255,255,0.9)）
   - 柔和的分隔线

### 响应式设计

- 最小窗口宽度: 1024px
- 最小窗口高度: 768px
- 时间轴在窗口缩小时保持可用性
- 侧边栏可折叠以节省空间

## 技术实现细节

### FFmpeg命令

视频分割使用以下FFmpeg命令保持原始质量：

```bash
ffmpeg -i input.mp4 -ss [start_time] -to [end_time] -c copy output.mp4
```

参数说明：
- `-i input.mp4`: 输入文件
- `-ss [start_time]`: 起始时间（格式: HH:MM:SS.mmm）
- `-to [end_time]`: 结束时间
- `-c copy`: 复制编码，不重新编码，保持原始质量
- `output.mp4`: 输出文件

### Electron打包配置

使用electron-builder进行打包：

```json
{
  "build": {
    "appId": "com.videotools.segmentation",
    "productName": "视频分割工具",
    "win": {
      "target": "nsis",
      "icon": "assets/icon.ico"
    },
    "files": [
      "dist/**/*",
      "node_modules/**/*",
      "package.json"
    ],
    "extraResources": [
      {
        "from": "ffmpeg/",
        "to": "ffmpeg/",
        "filter": ["**/*"]
      }
    ],
    "nsis": {
      "oneClick": false,
      "allowToChangeInstallationDirectory": true
    }
  }
}
```

### 性能优化

1. **视频加载优化**
   - 使用视频元数据快速获取时长，不加载完整视频
   - 预览使用较低分辨率的缩略图

2. **时间轴渲染优化**
   - 使用虚拟滚动，只渲染可见区域
   - 使用Canvas绘制时间轴，提高性能

3. **分割操作优化**
   - 使用Worker线程执行FFmpeg，避免阻塞UI
   - 批量处理多个片段，减少FFmpeg启动开销

4. **内存管理**
   - 及时释放不再使用的视频对象
   - 限制同时加载的视频数量

## 部署和分发

### 打包流程

1. 构建React应用: `npm run build`
2. 打包Electron应用: `npm run package`
3. 生成安装程序: `npm run dist`

### 分发包内容

- Windows可执行文件（.exe）
- FFmpeg二进制文件
- 必要的运行时库
- 用户手册（PDF）

### 安装要求

- Windows 10或更高版本
- 至少4GB RAM
- 至少500MB可用磁盘空间
- 无需预装Python或Node.js

### 更新机制

- 使用electron-updater实现自动更新
- 检查更新但不强制安装
- 下载更新后提示用户重启应用

## 未来扩展

### 可能的功能增强

1. **批量处理**: 支持一次处理多个视频文件
2. **预设模板**: 保存常用的分割规则为模板
3. **快捷键**: 添加键盘快捷键提高操作效率
4. **视频预览增强**: 显示关键帧缩略图
5. **导出格式**: 支持导出为其他视频格式
6. **云同步**: 支持元数据文件云端同步

### 技术债务

- 考虑使用WebAssembly版本的FFmpeg，减少打包体积
- 优化大文件处理的内存占用
- 添加更完善的错误追踪和报告机制
