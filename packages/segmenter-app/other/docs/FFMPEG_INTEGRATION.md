# FFmpeg 集成说明

## 概述

本应用已经将 FFmpeg 完全集成，用户安装后无需单独安装 FFmpeg 即可使用所有视频处理功能。

## 技术方案

### 使用的包

- `@ffmpeg-installer/ffmpeg` - 提供预编译的 FFmpeg 二进制文件
- `@ffprobe-installer/ffprobe` - 提供预编译的 FFprobe 二进制文件

### 优点

1. **开箱即用**: 用户无需安装任何额外软件
2. **跨平台**: 自动选择适合当前平台的二进制文件
3. **版本一致**: 所有用户使用相同版本的 FFmpeg
4. **简化部署**: 无需配置环境变量或系统路径

## 开发环境配置

### 首次设置

1. 安装 FFmpeg 依赖：
```bash
npm install @ffmpeg-installer/ffmpeg @ffprobe-installer/ffprobe
```

或使用批处理脚本：
```bash
install-ffmpeg.bat
```

2. 验证安装：
```bash
npm list @ffmpeg-installer/ffmpeg @ffprobe-installer/ffprobe
```

### 代码使用

在 `src/main/main.ts` 中：

```typescript
// 导入 FFmpeg 和 FFprobe 路径
const ffmpegPath = require('@ffmpeg-installer/ffmpeg').path;
const ffprobePath = require('@ffprobe-installer/ffprobe').path;

// 使用时直接引用路径
const command = `"${ffmpegPath}" -i "${inputPath}" ...`;
```

## 打包配置

### package.json 配置

```json
{
  "build": {
    "asarUnpack": [
      "node_modules/@ffmpeg-installer/**/*",
      "node_modules/@ffprobe-installer/**/*"
    ]
  }
}
```

`asarUnpack` 配置确保 FFmpeg 二进制文件不会被打包进 asar 归档，而是解压到 `app.asar.unpacked` 目录，这样才能正常执行。

## 打包后的文件结构

```
应用安装目录/
├── resources/
│   ├── app.asar                    # 应用代码（压缩）
│   └── app.asar.unpacked/          # 未压缩的文件
│       └── node_modules/
│           ├── @ffmpeg-installer/
│           │   └── win32-x64/
│           │       └── ffmpeg.exe  # FFmpeg 可执行文件
│           └── @ffprobe-installer/
│               └── win32-x64/
│                   └── ffprobe.exe # FFprobe 可执行文件
```

## 文件大小

- FFmpeg: 约 50-80MB
- FFprobe: 约 10-20MB
- 总计: 约 60-100MB

加上 Electron 运行时（约 100MB），最终安装包约 200-250MB。

## 支持的平台

- ✅ Windows (x64)
- ✅ macOS (x64, arm64)
- ✅ Linux (x64, arm64)

这些包会自动根据目标平台选择正确的二进制文件。

## 常见问题

### Q: 为什么不使用系统安装的 FFmpeg？

**A**: 
1. 用户体验差 - 需要用户手动安装和配置
2. 版本不一致 - 不同用户可能使用不同版本
3. 路径问题 - 需要配置环境变量
4. 兼容性问题 - 某些系统可能没有安装

### Q: 打包后的应用会很大吗？

**A**: 是的，约 200-250MB。但这是一次性成本，用户获得的是：
- 完全独立的应用
- 无需任何额外安装
- 开箱即用的体验

### Q: 可以减小文件大小吗？

**A**: 可以考虑：
1. 使用更小的 FFmpeg 构建（移除不需要的编解码器）
2. 使用在线 FFmpeg 服务（需要网络连接）
3. 让用户自行安装 FFmpeg（用户体验差）

通常不建议优化，因为会牺牲用户体验。

### Q: FFmpeg 许可证问题？

**A**: 
- FFmpeg 使用 LGPL 或 GPL 许可证
- 我们只是分发二进制文件，不修改源代码
- 需要在应用中包含 FFmpeg 的许可证声明
- 建议在"关于"页面添加 FFmpeg 版权信息

### Q: 如何更新 FFmpeg 版本？

**A**: 
```bash
npm update @ffmpeg-installer/ffmpeg @ffprobe-installer/ffprobe
```

然后重新打包应用。

### Q: 开发时如何测试？

**A**: 
```bash
npm run build
npm start
```

这会使用打包的 FFmpeg 运行应用。

### Q: 打包失败，提示找不到 FFmpeg？

**A**: 
1. 确保已安装依赖：`npm install`
2. 确保已安装 FFmpeg 包：`install-ffmpeg.bat`
3. 检查 `node_modules/@ffmpeg-installer` 目录是否存在
4. 重新构建：`npm run build`

## 测试 FFmpeg 集成

### 测试脚本

创建 `test-ffmpeg.js`：

```javascript
const ffmpegPath = require('@ffmpeg-installer/ffmpeg').path;
const ffprobePath = require('@ffprobe-installer/ffprobe').path;
const { execSync } = require('child_process');

console.log('FFmpeg 路径:', ffmpegPath);
console.log('FFprobe 路径:', ffprobePath);

// 测试 FFmpeg
try {
  const version = execSync(`"${ffmpegPath}" -version`, { encoding: 'utf8' });
  console.log('\nFFmpeg 版本信息:');
  console.log(version.split('\n')[0]);
} catch (error) {
  console.error('FFmpeg 测试失败:', error.message);
}

// 测试 FFprobe
try {
  const version = execSync(`"${ffprobePath}" -version`, { encoding: 'utf8' });
  console.log('\nFFprobe 版本信息:');
  console.log(version.split('\n')[0]);
} catch (error) {
  console.error('FFprobe 测试失败:', error.message);
}
```

运行测试：
```bash
node test-ffmpeg.js
```

## 许可证声明

建议在应用的"关于"页面添加：

```
本应用使用 FFmpeg (https://ffmpeg.org/)
FFmpeg 是根据 LGPL 2.1 或更高版本许可的开源软件
FFmpeg 版权归其各自作者所有
```

## 参考资源

- [FFmpeg 官网](https://ffmpeg.org/)
- [@ffmpeg-installer/ffmpeg](https://www.npmjs.com/package/@ffmpeg-installer/ffmpeg)
- [@ffprobe-installer/ffprobe](https://www.npmjs.com/package/@ffprobe-installer/ffprobe)
- [Electron Builder 文档](https://www.electron.build/)
