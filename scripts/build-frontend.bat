@echo off
REM ============================================================
REM  ShinyStarter - Build Frontend (Vite)
REM  Builds the React frontend into static files
REM ============================================================

echo.
echo ========================================
echo   Building ShinyStarter Frontend
echo ========================================
echo.

cd /d "%~dp0..\frontend"

REM Check if node_modules exists
if not exist "node_modules" (
    echo [INFO] Installing npm dependencies...
    call npm install
    if errorlevel 1 (
        echo [ERROR] npm install failed!
        exit /b 1
    )
)

REM Clean previous build
if exist "dist" (
    echo [INFO] Cleaning previous build...
    rmdir /s /q dist
)

REM Build with Vite
echo [INFO] Running Vite build...
call npm run build

if errorlevel 1 (
    echo.
    echo [ERROR] Vite build failed!
    exit /b 1
)

echo.
echo [OK] Frontend built successfully!
echo     Output: frontend\dist\
echo.
