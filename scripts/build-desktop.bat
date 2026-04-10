@echo off
REM ============================================================
REM  ShinyStarter - Build Desktop (electron-builder)
REM  Packages the Electron app with bundled backend and frontend
REM ============================================================

echo.
echo ========================================
echo   Packaging ShinyStarter Desktop App
echo ========================================
echo.

cd /d "%~dp0..\desktop"

REM Check prerequisites
if not exist "..\backend-dist\backend.exe" (
    echo [ERROR] Backend not built! Run build-backend.bat first.
    exit /b 1
)

if not exist "..\frontend\dist\index.html" (
    echo [ERROR] Frontend not built! Run build-frontend.bat first.
    exit /b 1
)

REM Install Electron dependencies if needed
if not exist "node_modules" (
    echo [INFO] Installing Electron dependencies...
    call npm install
    if errorlevel 1 (
        echo [ERROR] npm install failed!
        exit /b 1
    )
)

REM Clean previous desktop build
if exist "dist" (
    echo [INFO] Cleaning previous desktop build...
    rmdir /s /q dist
)

REM Build with electron-builder
echo [INFO] Running electron-builder...
call npx electron-builder --win nsis portable

if errorlevel 1 (
    echo.
    echo [ERROR] electron-builder failed!
    exit /b 1
)

echo.
echo [OK] Desktop app packaged successfully!
echo.
echo  Output files:
echo  ─────────────────────────────────────────
dir /b "dist\*.exe" 2>nul
echo  ─────────────────────────────────────────
echo.
echo  Location: desktop\dist\
echo.
