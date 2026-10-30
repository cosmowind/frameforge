# 图标文件说明

这个目录用于存放应用图标文件。

## 需要的图标文件

### Windows
- `icon.ico` - Windows 图标文件
  - 推荐尺寸: 256x256 像素或更大
  - 格式: ICO

### macOS
- `icon.icns` - macOS 图标文件
  - 格式: ICNS

### Linux
- `icon.png` - Linux 图标文件
  - 推荐尺寸: 512x512 像素
  - 格式: PNG

## 如何创建图标

1. 准备一张正方形的 PNG 图片（推荐 512x512 或 1024x1024）
2. 使用在线工具转换：
   - Windows ICO: https://convertio.co/zh/png-ico/
   - macOS ICNS: https://cloudconvert.com/png-to-icns
3. 将转换后的文件放在这个目录

## 注意事项

- 如果没有提供图标文件，electron-builder 会使用默认图标
- 图标文件名必须完全匹配（区分大小写）
- 建议使用简洁、清晰的图标设计
