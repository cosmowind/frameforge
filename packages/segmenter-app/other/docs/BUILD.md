# 打包说明

## 重要：FFmpeg 依赖

本应用已经将 FFmpeg 打包进来，用户无需单独安装！

### 首次打包前的准备

1. **安装 FFmpeg 依赖**（只需要做一次）：
```bash
# 方式1：运行批处理脚本（推荐）
install-ffmpeg.bat

# 方式2：手动安装
npm install @ffmpeg-installer/ffmpeg @ffprobe-installer/ffprobe
```

注意：这两个包比较大（约 50-100MB），下载可能需要几分钟。

2. **验证安装**：
```bash
npm list @ffmpeg-installer/ffmpeg @ffprobe-installer/ffprobe
```

## 打包为 Windows 可执行文件

### 1. 安装依赖
```bash
npm install
```

### 2. 安装 FFmpeg（首次打包必须）
```bash
install-ffmpeg.bat
```

### 3. 构建应用
```bash
npm run build
```

### 4. 打包为 Windows 安装程序
```bash
npm run dist
```

或者使用一键打包脚本：
```bash
package-app.bat
```

打包完成后，安装程序会生成在 `release` 目录中：
- `release/视频分割工具 Setup 1.0.0.exe` - Windows 安装程序（约 200-250MB）

### 5. 分发
将生成的 `.exe` 文件分享给其他用户即可。用户双击安装后就能使用，**无需安装 FFmpeg**！

## 打包选项说明

- **NSIS 安装程序**: 
  - 支持自定义安装路径
  - 自动创建桌面快捷方式
  - 自动创建开始菜单快捷方式
  - 支持卸载

## 注意事项

1. **图标**: 如果需要自定义图标，请将图标文件放在 `build` 目录：
   - Windows: `build/icon.ico` (256x256 或更大)
   - macOS: `build/icon.icns`
   - Linux: `build/icon.png`

2. **文件大小**: 打包后的安装程序约 200-250MB，因为包含了：
   - Electron 运行时（约 100MB）
   - Node.js 运行时
   - FFmpeg 和 FFprobe（约 50-100MB）
   - 应用代码和依赖

3. **首次打包**: 
   - 首次打包需要先安装 FFmpeg 依赖（运行 `install-ffmpeg.bat`）
   - 首次打包会下载 Electron 二进制文件，可能需要较长时间
   - 后续打包会快很多

4. **FFmpeg 集成**: 
   - FFmpeg 已经打包进应用，用户无需单独安装
   - 使用 `@ffmpeg-installer/ffmpeg` 和 `@ffprobe-installer/ffprobe` 包
   - 这些二进制文件会被解压到 `app.asar.unpacked` 目录

5. **用户体验**: 
   - 用户安装后即可使用，无需任何额外配置
   - 所有视频处理功能开箱即用

## 快速打包命令

```bash
# 一键打包（推荐）
npm run dist

# 或者分步执行
npm run build
npm run package
```

## 测试打包结果

打包完成后，可以在 `release` 目录找到安装程序，双击安装测试。

## 常见问题

### Q: 打包失败，提示找不到文件
A: 确保先运行 `npm run build` 构建应用

### Q: 打包很慢
A: 首次打包需要下载 Electron 二进制文件，后续打包会快很多

### Q: 安装程序太大
A: 这是正常的，Electron 应用包含完整的浏览器引擎和 Node.js 运行时

### Q: 需要打包 macOS 或 Linux 版本
A: 修改 package.json 中的 build.target 配置，然后运行 `npm run package`
