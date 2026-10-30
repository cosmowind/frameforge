@echo off
chcp 65001 >nul 2>&1
title Video Auto-Fill Helper
cd /d "%~dp0"
echo.
echo ============================================================
echo   Video Auto-Fill Helper  -  Starting...
echo ============================================================
echo   CWD: %CD%
echo.
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] python not found. Install Python 3.10+ first.
    pause
    exit /b 1
)
echo [OK] Python:
where python
echo.
echo [1/4] Killing all Chrome processes...
taskkill /F /IM chrome.exe >nul 2>nul
timeout /t 3 /nobreak >nul
echo       Done.
echo.
echo [2/4] Launching Chrome with --remote-debugging-port=9222...
set "CHROME_PATH="
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" set "CHROME_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe"
if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" set "CHROME_PATH=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
if "%CHROME_PATH%"=="" (
    echo [ERROR] Chrome not found.
    pause
    exit /b 1
)
echo       Chrome path: %CHROME_PATH%
set "CHROME_USER_DIR=%LOCALAPPDATA%\chrome_auto_fill_profile"
if exist "%CHROME_USER_DIR%\Default\Login Data" (
    echo       [INFO] Reusing previous Chrome profile
) else (
    echo       [INFO] First run: new Chrome profile
)
start "" "%CHROME_PATH%" --remote-debugging-port=9222 --user-data-dir="%CHROME_USER_DIR%" --remote-allow-origins=http://localhost:9222 --allow-running-insecure-content --disable-web-security "https://publish.example.com/vendors?tab=upload-history"
echo       Waiting 6s for Chrome to start...
timeout /t 6 /nobreak >nul
set PORT_OK=0
for /L %%i in (1,1,3) do (
    curl -s -o nul -w "       DevTools 9222 attempt %%i: status=%%{http_code}" http://localhost:9222/json/version
    echo.
    curl -s http://localhost:9222/json/version | findstr "Browser" >nul 2>&1
    if not errorlevel 1 (
        set PORT_OK=1
        goto :PORT_OK_DONE
    )
    timeout /t 2 /nobreak >nul
)
:PORT_OK_DONE
if "%PORT_OK%"=="0" (
    echo       [WARN] 9222 not ready. Try running manually:
    echo                "%CHROME_PATH%" --remote-debugging-port=9222 --user-data-dir="%CHROME_USER_DIR%"
) else (
    echo       [OK] DevTools port 9222 ready.
)
echo.
echo [3/4] Starting Flask backend on port 5000...
start "Flask-Server" /min cmd /k "cd /d %CD% && python src\run.py"
timeout /t 5 /nobreak >nul
curl -s -o nul -w "       Flask status: %%{http_code}" http://localhost:5000/api/upload-config
echo.
echo.
echo [4/4] Running filter setup (Capture=Stereo, Excludes tags)...
python src\scripts\setup_filters.py
echo.
echo [5/6] Starting Playwright helper (Ctrl+B to autofill)...
echo.
echo   =====================================================
echo    Ready:
echo      1) Click any Stereo video tile to open upload form
echo      2) Fill 3 fields, then Ctrl+B to auto-fill 20+ fields
echo      3) Click Save on publish.example.com, move to next video
echo   =====================================================
echo.
python src\scripts\auto_fill_helper.py --connect
echo.
echo ============================================================
echo  Helper stopped. Flask still running (look in taskbar).
echo ============================================================
pause
