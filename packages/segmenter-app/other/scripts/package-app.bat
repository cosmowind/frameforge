@echo off
chcp 65001 >nul

REM 切换到脚本所在目录
cd /d "%~dp0"

echo ========================================
echo 视频分割工具 - 打包脚本
echo ========================================
echo.
echo 当前目录: %CD%
echo.

echo [1/3] 检查依赖...
if not exist "node_modules\" (
    echo 正在安装依赖...
    call npm install
    if errorlevel 1 (
        echo 依赖安装失败！
        pause
        exit /b 1
    )
) else (
    echo 依赖已安装 ✓
)
echo.

echo [2/3] 构建应用...
call npm run build
if errorlevel 1 (
    echo 构建失败！
    pause
    exit /b 1
)
echo 构建完成 ✓
echo.

echo [3/3] 打包应用...
echo 首次打包可能需要较长时间，请耐心等待...
call npm run package
if errorlevel 1 (
    echo 打包失败！
    pause
    exit /b 1
)
echo.

echo ========================================
echo 打包完成！
echo ========================================
echo.
echo 安装程序位置: release\视频分割工具 Setup 1.0.0.exe
echo.
echo 现在可以将安装程序分享给其他用户了！
echo.
pause
