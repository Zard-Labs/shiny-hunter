@echo off
REM ============================================================
REM  ShinyStarter - Build Backend (PyInstaller)
REM  Bundles the Python backend into a standalone executable
REM ============================================================

echo.
echo ========================================
echo   Building ShinyStarter Backend
echo ========================================
echo.

cd /d "%~dp0..\backend"

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found at backend\venv
    echo Please create one first:
    echo   cd backend
    echo   python -m venv venv
    echo   venv\Scripts\activate
    echo   pip install -r requirements.txt
    echo   pip install pyinstaller
    exit /b 1
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Ensure PyInstaller is installed
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing PyInstaller...
    pip install pyinstaller
)

REM Clean previous build
if exist "build" (
    echo [INFO] Cleaning previous build directory...
    rmdir /s /q build
)
if exist "dist" (
    echo [INFO] Cleaning previous dist directory...
    rmdir /s /q dist
)

REM Run PyInstaller
echo [INFO] Running PyInstaller...
pyinstaller pyinstaller.spec --noconfirm

if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller build failed!
    exit /b 1
)

REM Move output to project root backend-dist
echo [INFO] Moving output to backend-dist...
cd /d "%~dp0.."
if exist "backend-dist" rmdir /s /q backend-dist
move "backend\dist\backend" "backend-dist"

REM Clean up build artifacts in backend/
rmdir /s /q "backend\build" 2>nul
rmdir /s /q "backend\dist" 2>nul

echo.
echo [OK] Backend built successfully!
echo     Output: backend-dist\backend.exe
echo.
