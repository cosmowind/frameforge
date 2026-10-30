# 视频分割工具

一个基于 Electron + React + TypeScript 的桌面应用程序，用于将 MP4 视频文件分割成多个符合特定时长和质量要求的片段。

## 快速开始

### 开发环境

```bash
# 安装依赖
npm install

# 开发模式
npm run dev

# 构建应用
npm run build

# 启动应用
npm start
```

### 打包分发

```bash
# 一键打包
npm run dist
```

详细打包说明请查看：[打包文档](other/docs/BUILD.md)

## 核心功能

详细功能列表请查看：[功能清单](docs/功能清单.md)

- ✅ 视频加载和预览
- ✅ 可视化时间轴编辑
- ✅ 片段管理（添加、删除、分割、调整）
- ✅ 智能验证系统（5-25秒时长要求）
- ✅ 元数据管理（保存/加载 JSON）
- ✅ 高质量视频分割（FFmpeg 集成）
- ✅ 规则参考面板
- ✅ 撤销功能（Ctrl+Z）
- ✅ 完整打包（包含 FFmpeg）

## 项目结构

详细目录结构请查看：[项目目录结构](docs/项目目录结构.md)

```
video-segmentation-tool/
├── src/                    # 源代码
├── docs/                   # 核心文档
├── other/                  # 辅助文件
├── .kiro/specs/           # 规格文档
└── README.md              # 本文件
```

## 技术栈

- **前端**: React 18 + TypeScript + Ant Design + Tailwind CSS
- **桌面**: Electron 28
- **视频处理**: FFmpeg（已集成）
- **状态管理**: Zustand
- **构建工具**: Vite 5

## 文档

### 核心文档（docs/）
- [项目目录结构](docs/项目目录结构.md) - 项目组织方式
- [功能清单](docs/功能清单.md) - 已完成功能列表
- [错误记录](docs/错误记录.md) - Bug 和解决方案
- [用户需求记录](docs/用户需求记录.md) - 需求历史
- [代码规范](docs/代码规范.md) - 开发流程和规范

### 辅助文档（other/docs/）
- [打包说明](other/docs/BUILD.md) - 详细打包步骤
- [FFmpeg 集成](other/docs/FFMPEG_INTEGRATION.md) - FFmpeg 技术细节
- [性能优化](other/docs/性能问题说明.md) - 性能问题排查

## 开发规范

请查看：[代码规范](docs/代码规范.md)

## 常见问题

### 打包相关
- 问题：打包失败，权限错误
- 解决：查看 [错误记录](docs/错误记录.md#打包权限问题)

### 性能相关
- 问题：打包后读取视频慢
- 解决：查看 [性能优化](other/docs/性能问题说明.md)

## 许可证

MIT

## 更新日志

- 2026-03-06: 项目重构，文档整理
- 2026-03-05: FFmpeg 集成，打包配置
- 2026-03-04: 核心功能完成

---

**注意**: 本项目遵循 [代码规范](docs/代码规范.md)，所有文档保持最新。
