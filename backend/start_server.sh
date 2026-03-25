#!/bin/bash

echo "========================================"
echo " Shiny Charmander Hunter - Backend"
echo "========================================"
echo ""

cd "$(dirname "$0")"

if [ ! -f "config.yaml" ]; then
    echo "No config.yaml found, copying from config.yaml.example..."
    cp config.yaml.example config.yaml
    echo "Please edit config.yaml with your ESP32 IP address and camera settings."
    echo ""
fi

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo ""
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing dependencies..."
pip install -r requirements.txt -q

echo ""
echo "Starting FastAPI server..."
echo "Server will be available at: http://localhost:8000"
echo "API docs at: http://localhost:8000/docs"
echo ""

python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
