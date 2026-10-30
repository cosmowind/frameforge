@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================================
echo   视频管理系统 - 跳过自动预处理
echo ============================================================
echo.
echo 检查依赖...

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.x
    echo        下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

python -m pip show flask >nul 2>&1
if %errorlevel% neq 0 (
    echo 正在安装依赖...
    python -m pip install -r requirements.txt
)

echo.
echo 已禁用自动预处理（可在 Web 界面手动触发）
echo.
python src/run.py --no-preprocess
pause
