@echo off
chcp 65001 >nul

REM 切换到项目根目录
cd /d "%~dp0..\.."

echo ========================================
echo 文档更新和备份脚本
echo ========================================
echo.

echo [1/3] 检查 Git 状态...
git status
echo.

echo [2/3] 添加所有更改...
git add .
echo.

echo [3/3] 提交更改...
set /p commit_msg="请输入提交信息: "
if "%commit_msg%"=="" set commit_msg=docs: 更新文档

git commit -m "%commit_msg%"
echo.

echo ========================================
echo 完成！
echo ========================================
echo.
echo 提交信息: %commit_msg%
echo.
echo 如需推送到远程仓库，请运行: git push
echo.
pause
