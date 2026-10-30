@echo off
chcp 65001 >nul

REM 切换到脚本所在目录
cd /d "%~dp0"

echo ========================================
echo 安装 FFmpeg 依赖
echo ========================================
echo.
echo 当前目录: %CD%
echo.

echo 正在安装 FFmpeg 和 FFprobe...
echo 这些包比较大（约 50-100MB），请耐心等待...
echo.

call npm install @ffmpeg-installer/ffmpeg @ffprobe-installer/ffprobe

if errorlevel 1 (
    echo.
    echo ========================================
    echo 安装失败！
    echo ========================================
    echo.
    echo 可能的原因：
    echo 1. 网络连接问题
    echo 2. npm 配置问题
    echo.
    echo 解决方案：
    echo 1. 检查网络连接
    echo 2. 尝试使用国内镜像：
    echo    npm config set registry https://registry.npmmirror.com
    echo 3. 重新运行此脚本
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo 安装成功！
echo ========================================
echo.
echo FFmpeg 和 FFprobe 已成功安装
echo 现在可以运行 package-app.bat 进行打包了
echo.
pause
