@echo off
echo ========================================
echo  Shiny Charmander Hunter - Backend
echo ========================================
echo.

cd /d %~dp0

if not exist config.yaml (
    echo No config.yaml found, copying from config.yaml.example...
    copy config.yaml.example config.yaml
    echo Please edit config.yaml with your ESP32 IP address and camera settings.
    echo.
)

if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
    echo.
)

echo Activating virtual environment...
call venv\Scripts\activate

echo Upgrading pip and setuptools...
python -m pip install --upgrade pip setuptools wheel

echo.
echo Installing dependencies...
pip install -r requirements.txt

echo.
echo Starting FastAPI server...
echo Server will be available at: http://localhost:8000
echo API docs at: http://localhost:8000/docs
echo.

python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
