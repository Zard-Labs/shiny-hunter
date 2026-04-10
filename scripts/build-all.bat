@echo off
REM ============================================================
REM  ShinyStarter - Full Build Pipeline
REM  Runs all build steps: Backend → Frontend → Desktop
REM ============================================================

echo.
echo ████████████████████████████████████████████████████████████
echo █                                                          █
echo █   ShinyStarter Desktop App - Full Build Pipeline         █
echo █                                                          █
echo ████████████████████████████████████████████████████████████
echo.

set STARTTIME=%TIME%

REM Step 1: Build Backend
echo.
echo [1/3] Building Python Backend...
echo ─────────────────────────────────
call "%~dp0build-backend.bat"
if errorlevel 1 (
    echo.
    echo [FAILED] Backend build failed. Aborting.
    exit /b 1
)

REM Step 2: Build Frontend
echo.
echo [2/3] Building React Frontend...
echo ─────────────────────────────────
call "%~dp0build-frontend.bat"
if errorlevel 1 (
    echo.
    echo [FAILED] Frontend build failed. Aborting.
    exit /b 1
)

REM Step 3: Package Desktop App
echo.
echo [3/3] Packaging Desktop App...
echo ─────────────────────────────────
call "%~dp0build-desktop.bat"
if errorlevel 1 (
    echo.
    echo [FAILED] Desktop packaging failed. Aborting.
    exit /b 1
)

echo.
echo ████████████████████████████████████████████████████████████
echo █                                                          █
echo █   BUILD COMPLETE!                                        █
echo █                                                          █
echo █   Start time: %STARTTIME%                                  
echo █   End time:   %TIME%                                       
echo █                                                          █
echo █   Output files in: desktop\dist\                         █
echo █                                                          █
echo ████████████████████████████████████████████████████████████
echo.

REM List output files
echo  Distributable files:
echo  ─────────────────────────────────────────
dir /b "desktop\dist\*.exe" 2>nul
echo  ─────────────────────────────────────────
echo.
