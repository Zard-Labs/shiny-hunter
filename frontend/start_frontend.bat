@echo off
echo ================================================
echo   Starting Shiny Hunter Frontend Dashboard
echo ================================================
echo.

cd /d "%~dp0"

if not exist "node_modules\" (
    echo [ERROR] Dependencies not installed!
    echo [INFO] Run 'npm install' first
    pause
    exit /b 1
)

echo [INFO] Starting Vite dev server on http://localhost:3000
echo [INFO] Press Ctrl+C to stop
echo.

npm run dev

pause
