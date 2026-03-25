# Backend - Python FastAPI Server

## Overview

FastAPI backend for the Shiny Charmander hunting system. Handles game automation, OpenCV detection, ESP32 communication, and WebSocket updates.

## Installation

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt
```

## Running the Server

### Development Mode

```bash
python -m uvicorn app.main:app --reload
```

Server starts at: `http://localhost:8000`

### Production Mode

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Configuration

Edit [`config.yaml`](config.yaml) to configure:

- **ESP32 connection** (WiFi IP or UART port)
- **Camera index** for Elgato capture
- **Detection zones** for shiny/gender
- **Template thresholds** for matching

## Hardware Setup

### ESP32-S3 WiFi Configuration

The ESP32-S3 controller operates in **WiFi Station Mode**, connecting to your home/office WiFi network (not as an Access Point).

**Requirements:**
- ESP32-S3 must be connected to the same WiFi network as your backend PC
- Both devices must be able to communicate (no AP isolation enabled on router)
- Firewall must allow HTTP traffic on port 80

**Setup Steps:**

1. **Flash ESP32-S3 Firmware:**
   ```bash
   cd esp32
   platformio run --target upload
   ```

2. **Find ESP32 IP Address:**
   
   The ESP32 will print its IP during boot. Check serial monitor:
   ```bash
   platformio device monitor
   ```
   
   Look for output like:
   ```
   ✓ WiFi connected to network
      SSID: YourNetworkName
      IP Address: 192.168.1.105
   ```

3. **Update Backend Configuration:**
   
   Edit `backend/config.yaml`:
   ```yaml
   hardware:
     esp32_ip: "192.168.1.105"  # Use the IP from step 2
   ```

4. **Test Connection:**
   ```bash
   # From backend PC, test ESP32 connectivity:
   curl http://192.168.1.105/status
   
   # Expected response:
   # {"status":"ok","connected":true,"mode":"usb_hid"}
   ```

5. **Access Web UI (Optional):**
   
   Open browser to `http://192.168.1.105` for manual controller testing with a beautiful NES-styled interface.

**Network Architecture:**
```
Your PC (Backend)          ESP32-S3             Nintendo Switch
192.168.1.x            192.168.1.105
     │                      │                        │
     │   Home WiFi Network  │                        │
     │◄──────HTTP──────────►│                        │
     │   (Port 80)          │        USB-C           │
     │                      │◄──────HID─────────────►│
     └──────────────────────┴────────────────────────┘
              Home Router (e.g., 192.168.1.1)
```

**Troubleshooting:**

| Issue | Solution |
|-------|----------|
| Backend can't connect to ESP32 | Verify both devices on same network, try pinging ESP32 IP |
| IP address changes after reboot | Configure DHCP reservation in router (recommended) |
| Firewall blocks connection | Allow port 80 inbound/outbound in Windows Firewall |
| ESP32 won't connect to WiFi | Update WiFi credentials in `esp32/src/main.cpp` lines 21-22 |
| "Connection timeout" errors | Check ESP32 is powered on and router not blocking devices |

**Static IP Configuration (Recommended):**

To prevent IP address changes, configure a DHCP reservation in your router:
1. Find ESP32 MAC address (check router's connected devices list)
2. Create DHCP reservation: Map `192.168.1.105` to ESP32's MAC address
3. ESP32 will always receive the same IP on your network

Alternatively, configure a static IP directly in the ESP32 firmware (see `esp32/README.md`).

## API Documentation

Interactive API docs available at:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration loader
│   ├── database.py          # SQLAlchemy setup
│   ├── models.py            # Database models
│   ├── schemas.py           # Pydantic schemas
│   │
│   ├── routes/              # API endpoints
│   │   ├── automation.py    # Start/stop automation
│   │   ├── control.py       # Manual ESP32 controls
│   │   ├── statistics.py    # Stats and history
│   │   └── websocket.py     # WebSocket handler
│   │
│   ├── services/            # Core business logic
│   │   ├── esp32_manager.py # ESP32 WiFi/UART communication
│   │   ├── game_engine.py   # State machine automation
│   │   ├── opencv_detector.py # Shiny/template detection
│   │   └── video_capture.py  # Camera management
│   │
│   └── utils/               # Utilities
│       ├── command_builder.py # Button command encoding
│       └── logger.py         # Logging setup
│
├── templates/               # OpenCV template images
│   ├── pokemon_red/
│   └── natures/
│
├── encounters/              # Screenshot storage
├── config.yaml             # Configuration file
└── requirements.txt        # Python dependencies
```

## Services

### ESP32 Manager

Handles communication with ESP32-C6.

**WiFi Mode** (default):
```python
from app.services.esp32_manager import esp32_manager

esp32_manager.connect()  # Connect to http://192.168.4.1
esp32_manager.send_button('A')  # Send button A
esp32_manager.disconnect()
```

**UART Mode**:
Set `communication_mode: uart` in config.yaml

### Game Engine

State machine for automation.

```python
from app.services.game_engine import game_engine

game_engine.start(db)  # Start automation
status = game_engine.get_status()  # Get current state
game_engine.stop()  # Stop automation
```

**States:**
1. `PHASE_1_BOOT` - Navigate title/load screens
2. `PHASE_2_OVERWORLD` - Clear Oak's lab dialogue
3. `PHASE_2_WAIT` - Wait for text animation
4. `PHASE_3_MENU` - Navigate to Charmander summary
5. `PHASE_4_CHECK` - Detect shiny, log stats, soft reset

### OpenCV Detector

Image detection and analysis.

```python
from app.services.opencv_detector import opencv_detector

# Load templates
opencv_detector.load_templates()

# Check for UI element
match, confidence = opencv_detector.check_template(gray_frame, 'oak')

# Detect shiny
is_shiny, pixel_count = opencv_detector.detect_shiny(color_frame)

# Detect gender/nature
gender = opencv_detector.detect_gender(color_frame)
nature = opencv_detector.detect_nature(gray_frame)
```

### Video Capture

Manages Elgato Neo capture.

```python
from app.services.video_capture import video_capture

video_capture.open()  # Open camera
frame, gray = video_capture.read_frame()  # Read frame
video_capture.flush_buffer()  # Flush buffer
video_capture.close()
```

## Database

SQLite database with three tables:

### encounters
Stores all Pokemon encounters with screenshots.

```sql
CREATE TABLE encounters (
    id INTEGER PRIMARY KEY,
    encounter_number INTEGER,
    timestamp DATETIME,
    pokemon_name VARCHAR(20),
    is_shiny BOOLEAN,
    gender VARCHAR(10),
    nature VARCHAR(50),
    session_id VARCHAR(36),
    screenshot_path VARCHAR(255),
    detection_confidence FLOAT,
    state_at_capture VARCHAR(50)
);
```

### sessions
Groups encounters into hunting sessions.

```sql
CREATE TABLE sessions (
    id VARCHAR(36) PRIMARY KEY,
    started_at DATETIME,
    ended_at DATETIME,
    total_encounters INTEGER,
    shiny_found BOOLEAN,
    status VARCHAR(20)
);
```

### configuration
Stores calibration settings.

```sql
CREATE TABLE configuration (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT,
    updated_at DATETIME
);
```

## WebSocket Events

Connect to `ws://localhost:8000/ws` to receive real-time updates:

### Server → Client

```javascript
// State update
{
  "type": "state_update",
  "data": {
    "state": "PHASE_3_MENU",
    "encounter_number": 42,
    "is_running": true
  }
}

// Encounter detected
{
  "type": "encounter_detected",
  "data": {
    "encounter_number": 42,
    "gender": "Male",
    "nature": "Adamant",
    "is_shiny": false,
    "screenshot_url": "/encounters/encounter_0042.png"
  }
}

// Shiny found!
{
  "type": "shiny_found",
  "data": {
    "encounter_number": 137,
    "screenshot_url": "/encounters/encounter_0137.png",
    "timestamp": "2026-03-24T01:30:00Z"
  }
}
```

## Logging

Logs are written to:
- **Console**: Real-time output
- **File**: `bot_history.log`

Log levels: DEBUG, INFO, WARNING, ERROR

## Testing

### Manual ESP32 Test

```bash
# Connect to ESP32
curl -X POST http://localhost:8000/api/control/esp32/connect

# Send button A
curl -X POST http://localhost:8000/api/control/button \
  -H "Content-Type: application/json" \
  -d '{"button": "A"}'

# Check status
curl http://localhost:8000/api/control/esp32/status
```

### Test Automation

```bash
# Start automation
curl -X POST http://localhost:8000/api/automation/start

# Get status
curl http://localhost:8000/api/automation/status

# Stop automation
curl -X POST http://localhost:8000/api/automation/stop
```

### Test Statistics

```bash
# Current stats
curl http://localhost:8000/api/statistics/current

# Encounter history
curl "http://localhost:8000/api/statistics/history?limit=10"

# Chart data
curl http://localhost:8000/api/statistics/charts
```

## Calibration

### Capture Templates

1. Navigate to the screen you want to capture
2. Use OpenCV to crop the relevant region
3. Save as grayscale PNG in `templates/pokemon_red/`

Example script:
```python
import cv2

cap = cv2.VideoCapture(0)
ret, frame = cap.read()
frame = cv2.resize(frame, (640, 480))
gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

# Select ROI manually
roi = cv2.selectROI("Select", gray)
template = gray[int(roi[1]):int(roi[1]+roi[3]), int(roi[0]):int(roi[0]+roi[2])]

cv2.imwrite('templates/pokemon_red/my_template.png', template)
```

### Set Detection Zones

Edit `config.yaml` with your coordinates:

```yaml
detection:
  shiny_zone:
    upper_x: 264  # Top-left X
    upper_y: 109  # Top-left Y
    lower_x: 312  # Bottom-right X
    lower_y: 151  # Bottom-right Y
```

## Troubleshooting

### ESP32 Connection Failed

- Check ESP32 IP: `ping 192.168.4.1`
- Verify WiFi connected to `ESP32-ShinyHunter`
- Check `communication_mode` in config

### Camera Not Found

```bash
# List cameras (Linux)
ls /dev/video*

# Test camera
python -c "import cv2; print(cv2.VideoCapture(0).isOpened())"
```

Try different `camera_index` values: 0, 1, 2

### Template Not Matching

- Lower threshold in `config.yaml`
- Recapture template at correct resolution
- Check grayscale conversion

### Database Locked

```bash
# Close all connections and restart server
rm shiny_hunter.db
python -m uvicorn app.main:app --reload
```

## License

MIT License
