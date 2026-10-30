# 视频分割工具

一个基于 React + TypeScript 的纯前端视频分割工具，使用 FFmpeg WebAssembly 在浏览器中处理视频，无需上传到服务器。

## 快速开始

### 开发环境

```bash
# 安装依赖
npm install

# 开发模式
npm run dev

# 构建项目
npm run build

# 预览构建结果
npm run preview
```

### 部署

构建后的文件在 `dist` 目录下，可以部署到任何静态托管服务：

```bash
# 构建项目
npm run build

# 将 dist 目录部署到静态托管服务
```

支持的托管服务：
- GitHub Pages
- Vercel
- Netlify
- Cloudflare Pages
- 任何支持静态文件的 Web 服务器

## 核心功能

- ✅ 视频加载和预览（支持本地文件选择）
- ✅ 可视化时间轴编辑
- ✅ 片段管理（添加、删除、分割、调整）
- ✅ 智能验证系统（5-25秒时长要求）
- ✅ 元数据管理（保存/加载 JSON）
- ✅ 高质量视频分割（FFmpeg WebAssembly）
- ✅ 规则参考面板
- ✅ 撤销功能（Ctrl+Z）
- ✅ 直接下载分割后的视频片段
- ✅ **HEVC (H.265) 视频支持**（自动检测并转码播放）

## 技术栈

- **前端**: React 18 + TypeScript + Ant Design + Tailwind CSS
- **视频处理**: FFmpeg WebAssembly（在浏览器中运行）
- **状态管理**: Zustand
- **构建工具**: Vite 5

## 浏览器兼容性

支持现代浏览器：
- Chrome 90+
- Edge 90+
- Firefox 90+
- Safari 15+

**注意**: 视频处理需要浏览器支持 WebAssembly 和 SharedArrayBuffer。在生产环境中部署时，需要配置以下 HTTP 头：
- `Cross-Origin-Opener-Policy: same-origin`
- `Cross-Origin-Embedder-Policy: require-corp`

## 文件大小限制

- 建议视频文件大小：500MB - 5GB
- 更大的文件可能需要更长的处理时间
- 浏览器内存限制可能影响超大文件的处理

## 项目结构

```
video-segmentation-tool/
├── src/                    # 源代码
│   ├── renderer/          # React 应用
│   │   ├── components/    # UI 组件
│   │   ├── services/      # 业务逻辑服务
│   │   ├── store/         # 状态管理
│   │   └── types/         # TypeScript 类型定义
│   └── index.html         # 入口 HTML
├── docs/                   # 文档
├── build/                  # 构建资源
└── README.md              # 本文件
```

## 开发规范

请查看：[代码规范](docs/代码规范.md)

## 常见问题

### 视频处理很慢怎么办？
FFmpeg WebAssembly 的性能比原生 FFmpeg 慢，这是正常现象。建议：
- 使用较短的视频进行测试
- 关闭其他占用资源的浏览器标签页
- 使用 Chrome 浏览器获得最佳性能

### HEVC 视频无法播放怎么办？
本工具已支持 HEVC (H.265) 视频。加载 HEVC 视频时会自动转码为 H.264 格式播放：
- 首次加载 HEVC 视频需要等待转码完成
- 转码进度会实时显示
- 转码结果会自动缓存，下次加载同一视频无需重复转码

### 浏览器不支持怎么办？
请确保使用支持 WebAssembly 的现代浏览器。如果仍然有问题，请检查浏览器版本。

### 如何部署到生产环境？
1. 运行 `npm run build`
2. 将 `dist` 目录部署到静态托管服务
3. 配置必要的 HTTP 头（Cross-Origin-Opener-Policy 和 Cross-Origin-Embedder-Policy）

## 许可证

MIT

## 更新日志

- 2026-05-17: 新增 HEVC (H.265) 视频编码支持，自动检测并转码播放
- 2026-05-16: 转换为纯前端项目，使用 FFmpeg WebAssembly
- 2026-03-06: 项目重构，文档整理
- 2026-03-05: FFmpeg 集成，打包配置
- 2026-03-04: 核心功能完成

---

**注意**: 本项目遵循 [代码规范](docs/代码规范.md)，所有文档保持最新。
