# Windows Installation Guide

## Quick Fix for Pillow Error

If you're getting the `KeyError: '__version__'` error when installing Pillow, follow these steps:

### Method 1: Manual Installation (Recommended)

```cmd
cd backend

REM Delete old venv if it exists
rmdir /s /q venv

REM Create fresh virtual environment
python -m venv venv

REM Activate
venv\Scripts\activate

REM Upgrade pip first (IMPORTANT!)
python -m pip install --upgrade pip setuptools wheel

REM Install packages one by one to identify issues
pip install fastapi
pip install "uvicorn[standard]"
pip install python-multipart
pip install websockets
pip install sqlalchemy
pip install pydantic
pip install pydantic-settings
pip install numpy
pip install opencv-python
pip install pillow
pip install python-dotenv
pip install aiofiles
pip install requests
pip install pyyaml
pip install pyserial

REM Start server
python -m uvicorn app.main:app --reload
```

### Method 2: Use Pre-compiled Wheels

If Pillow still fails, download pre-compiled wheel from:
https://www.lfd.uci.edu/~gohlke/pythonlibs/#pillow

Example for Python 3.11 on Windows 64-bit:
```cmd
pip install Pillow-10.2.0-cp311-cp311-win_amd64.whl
```

### Method 3: Install Visual C++ Build Tools

Pillow requires C++ compiler on Windows. Install:
**Visual Studio Build Tools 2022**: https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022

Select "Desktop development with C++" workload.

### Method 4: Use Conda (Alternative)

```cmd
conda create -n shiny python=3.11
conda activate shiny
cd backend
pip install -r requirements.txt
```

## Verification

After successful installation, test with:

```cmd
python -c "import cv2, fastapi, uvicorn; print('All packages imported successfully!')"
```

## Running the Server

```cmd
cd backend
venv\Scripts\activate
python -m uvicorn app.main:app --reload
```

Server should start at: http://localhost:8000

## Common Issues

### "No module named uvicorn"

```cmd
pip install uvicorn[standard]
```

### "No module named cv2"

```cmd
pip install opencv-python
```

### Camera not found

Check camera index in [`config.yaml`](config.yaml):
```yaml
hardware:
  camera_index: 0  # Try 0, 1, 2, etc.
```

List available cameras:
```python
import cv2
for i in range(5):
    cap = cv2.VideoCapture(i)
    if cap.isOpened():
        print(f"Camera {i}: Available")
        cap.release()
    else:
        print(f"Camera {i}: Not available")
```

### ESP32 connection fails

1. Check ESP32 is powered and WiFi AP is active
2. Connect to `ESP32-ShinyHunter` WiFi network
3. Verify IP: `ping 192.168.4.1`
4. Test endpoint: `curl http://192.168.4.1/status`

## Python Version

Recommended: **Python 3.10 or 3.11**

Check version:
```cmd
python --version
```

Download from: https://www.python.org/downloads/

## Alternative: Docker (Advanced)

If all else fails, use Docker:

```cmd
cd backend
docker build -t shiny-backend .
docker run -p 8000:8000 --device=/dev/video0 shiny-backend
```

(Requires Docker Desktop for Windows)
