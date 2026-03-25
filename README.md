# 🌟 ShinyStarter - Automated Shiny Pokemon Hunter

<div align="center">

**Automated shiny hunting system for Pokemon Red on Nintendo Switch**

![Status](https://img.shields.io/badge/status-active-success)
![Backend](https://img.shields.io/badge/backend-FastAPI-009688)
![Frontend](https://img.shields.io/badge/frontend-React-61dafb)
![Hardware](https://img.shields.io/badge/hardware-ESP32--C6-red)

</div>

---

## 🎯 Overview

ShinyStarter is a complete automation system that hunts for shiny Pokemon in Pokemon Red (Nintendo Switch) by:
- **Emulating controller inputs** via ESP32-C6 USB HID
- **Capturing video feed** from Elgato capture card
- **Detecting shiny Pokemon** using OpenCV color analysis
- **Providing real-time dashboard** with statistics and monitoring

### Key Features
- ⚡ **Fully Automated**: Soft resets, menu navigation, shiny detection
- 📊 **Live Statistics**: Real-time encounter tracking, nature/gender distribution
- 🎥 **Video Feed**: Live capture with detection zone overlays
- 🎮 **Manual Control**: Test button presses before automation
- 🎯 **Calibration Tools**: Configure detection zones and templates
- 📈 **Data Visualization**: Charts for natures, genders, and odds
- 💾 **Screenshot Capture**: Auto-saves every encounter

---

## 🏗️ System Architecture

```
┌─────────────┐        ┌──────────────┐        ┌─────────────────┐
│   Nintendo  │  HDMI  │   Elgato Neo │  USB   │       PC        │
│   Switch    ├───────►│ Capture Card ├───────►│   (Backend)     │
│             │        └──────────────┘        │   Port 8000     │
└──────┬──────┘                                 └────────┬────────┘
       │                                                 │
       │ USB-C (Controller)                             │ WiFi/HTTP
       │                                                 │
       │        ┌──────────────┐                        │
       └────────┤   ESP32-C6   │◄───────────────────────┘
                │ (HID Device) │
                └──────────────┘
                                                         
┌─────────────────────────────────────────────────────────┐
│          Browser: http://localhost:3000                 │
│      React Dashboard (Real-time WebSocket UI)           │
└─────────────────────────────────────────────────────────┘
```

**Component Breakdown:**
- **ESP32-C6**: Emulates Switch Pro Controller via USB HID, receives commands via WiFi
- **Elgato Neo**: Captures 1080p video feed at 30 FPS
- **Backend**: FastAPI server handles automation, OpenCV detection, statistics
- **Frontend**: React dashboard with cyberpunk UI for real-time monitoring

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.8+** with pip
- **Node.js 18+** with npm
- **ESP32-C6** (Seeed Xiao ESP32-C6 or similar)
- **Elgato Capture Card** (HD60, Neo, HD60S+, etc.)
- **Nintendo Switch** with Pokemon Red

### 1. Backend Setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac
pip install -r requirements.txt
```

**Configure `backend/config.yaml`:**
- Set ESP32 IP address (if using WiFi)
- Set camera index (usually 0 or 1)
- Adjust detection thresholds if needed

**Start Backend:**
```bash
start_server.bat              # Windows
# ./start_server.sh           # Linux/Mac
```

Backend will be available at `http://localhost:8000`

### 2. Frontend Setup

```bash
cd frontend
npm install
```

**Start Frontend:**
```bash
start_frontend.bat            # Windows
# ./start_frontend.sh         # Linux/Mac
```

Dashboard will be available at `http://localhost:3000`

### 3. ESP32 Firmware

```bash
cd esp32
platformio run --target upload
```

See [`esp32/README.md`](esp32/README.md) for detailed ESP32 setup instructions.

---

## 📋 Complete Setup Guide

### Step 1: Backend Verification ✅

Your backend is **already running** and shows:
- ✅ ESP32 connected (usb_hid mode)
- ✅ Video capture opened (1920x1080 @ 30fps)
- ✅ Server ready at http://0.0.0.0:8000

### Step 2: Frontend Dashboard ✅

Your frontend is **already running** at `http://localhost:3000`

**Open in browser now** to see:
- 📹 Live video feed from capture card
- ⚡ Control panel with start/stop automation
- 📊 Real-time statistics and charts
- 📜 Encounter history table
- 🎯 Calibration tools

### Step 3: Capture Template Images (REQUIRED)

The automation needs template images to recognize game screens.

#### Navigate and Screenshot These Screens:

**Save to: `backend/templates/pokemon_red/`**

1. **title_screen.png** - Game Freak logo or title screen
2. **load_game.png** - "CONTINUE" option on menu
3. **nickname_screen.png** - "Want to give a nickname?" text
4. **oak_lab.png** - Professor Oak in the lab
5. **pokemon_menu.png** - "POKEMON" entry in START menu
6. **choose_pokemon.png** - "CHOOSE A POKEMON" screen
7. **summary_screen.png** - Pokemon info/summary screen

**Save to: `backend/templates/natures/`**

8. Capture all 25 nature name images (adamant.png, modest.png, etc.)

#### How to Capture:
1. Use Windows Snipping Tool or ShareX
2. Play Pokemon Red and navigate to each screen
3. Take screenshot of the specific UI element
4. Save with exact name to templates folder
5. Images should be clear PNG format

### Step 4: Calibrate Detection Zones (REQUIRED)

The system needs to know WHERE to look for shiny stars and gender symbols.

**In the Dashboard:**
1. Navigate to Charmander's summary screen
2. Click "🎯 CALIBRATE" button
3. Find the shiny star location (above Pokeball icon)
4. Enter coordinates: Upper-Left (X,Y) and Lower-Right (X,Y)
5. Repeat for gender symbol (next to name)
6. Click "SAVE ZONE"

**Default coordinates** (may need adjustment based on your capture resolution):
- **Shiny Zone**: `ux: 264, uy: 109, lx: 312, ly: 151`
- **Gender Zone**: `ux: 284, uy: 68, lx: 311, ly: 92`

### Step 5: Game Save Setup

Your Pokemon Red save must be positioned correctly:

1. **Start Point**: Oak's lab, right after receiving Charmander
2. **Party Position**: Charmander in slot 3 (third position)
3. **Nickname**: Declined (automation expects no nickname prompt)
4. **Save State**: Standing in lab, ready to open menu

### Step 6: Test Automation

1. **Test Manual Controls First**:
   - Click individual buttons (A, B, START)
   - Verify Switch responds correctly
   - Try the SOFT RESET button

2. **Start Automation**:
   - Click "▶ START" in dashboard
   - Watch state machine progress
   - Monitor statistics panel
   - Check video feed for detection overlays

3. **Monitor Progress**:
   - Encounter counter increases
   - Nature/gender charts populate
   - History table fills with logs
   - System auto-saves screenshots

4. **When Shiny Found**:
   - Automation stops automatically
   - Screenshot saved to `backend/encounters/`
   - Notification appears in dashboard
   - Celebrate! 🎉

---

## 📁 Project Structure

```
ShinyStarter/
├── backend/               # Python FastAPI server
│   ├── app/
│   │   ├── main.py       # Server entry point
│   │   ├── routes/       # API endpoints
│   │   ├── services/     # Game engine, OpenCV, ESP32 manager
│   │   └── utils/        # Helper functions
│   ├── templates/        # OpenCV template images (REQUIRED)
│   ├── encounters/       # Auto-saved screenshots
│   ├── config.yaml       # Main configuration
│   └── requirements.txt
│
├── frontend/             # React dashboard
│   ├── src/
│   │   ├── App.jsx       # Root component
│   │   ├── components/   # UI components
│   │   ├── hooks/        # WebSocket, automation hooks
│   │   └── services/     # API client
│   ├── package.json
│   └── vite.config.js
│
├── esp32/                # ESP32-C6 firmware
│   ├── src/main.cpp      # Controller emulation
│   ├── platformio.ini    # Build configuration
│   └── README.md
│
├── plans/                # Architecture documentation
├── NEXT_STEPS.md        # Detailed next steps guide
└── README.md            # This file
```

---

## 🎮 How It Works

### Automation Loop

```
1. PHASE_1_BOOT
   ├─ Detect title screen
   ├─ Press A through menus
   └─ Decline nickname

2. PHASE_2_OVERWORLD
   ├─ Wait for Oak in lab
   └─ Press B to clear dialogue

3. PHASE_3_MENU
   ├─ Press START to open menu
   ├─ Navigate to POKEMON
   ├─ Select Charmander (3rd slot)
   └─ Open summary/info screen

4. PHASE_4_CHECK
   ├─ Capture screenshot
   ├─ Analyze shiny zone (yellow pixels)
   ├─ Detect gender (blue/red pixels)
   ├─ Detect nature (template matching)
   └─ Log to database

5. Decision:
   ├─ If SHINY → STOP automation ✨
   └─ If normal → Soft reset (A+B+START+SELECT) → Loop to step 1
```

### Detection Methods

**Shiny Detection (Color Masking)**:
- Crop region above Pokeball icon
- Convert to HSV color space
- Count yellow pixels (20+ = shiny)
- Threshold: `HSV [20-35, 100-255, 150-255]`

**Gender Detection (Color Masking)**:
- Crop region next to name
- Male: Blue pixels (10+)
- Female: Red/pink pixels (10+)

**Nature Detection (Template Matching)**:
- Match nature text against 25 templates
- Method: Normalized correlation
- Threshold: 0.85 confidence

**Screen Navigation (Template Matching)**:
- Match UI elements to navigate menus
- Confirms correct game state
- Triggers appropriate button presses

---

## 🖥️ API Endpoints

### Automation Control
- `POST /api/automation/start` - Start hunting
- `POST /api/automation/stop` - Stop hunting
- `GET /api/automation/status` - Get current state

### Statistics
- `GET /api/statistics/current` - Current session stats
- `GET /api/statistics/history` - Encounter log (paginated)
- `GET /api/statistics/charts` - Chart data

### Manual Control
- `POST /api/control/button` - Send button press
- `GET /api/control/esp32/status` - ESP32 connection status

### Calibration
- `POST /api/calibration/zone` - Save detection zone
- `POST /api/calibration/template` - Upload template
- `GET /api/calibration/current` - Get current calibration

### WebSocket
- `ws://localhost:8000/ws` - Real-time events and video stream

See full API docs at `http://localhost:8000/docs` (Swagger UI)

---

## 🎨 Dashboard Features

<table>
<tr>
<td width="50%">

### Control Panel
- ▶️ Start/Stop automation
- 🎮 Manual button controls
- 🔄 Soft reset button
- 🎯 Calibration modal
- 📊 Connection status

</td>
<td width="50%">

### Statistics Panel
- 🔢 Total encounters
- 📈 Shiny probability
- ♂️♀️ Gender distribution
- 🎲 Nature frequency chart
- ⏱️ Session duration

</td>
</tr>
<tr>
<td width="50%">

### Live Feed
- 📹 Real-time video stream
- 🎯 Detection zone overlays
- 📊 FPS counter
- 🔍 Visual debugging

</td>
<td width="50%">

### History Table
- 📜 Complete encounter log
- ✨ Shiny highlighting
- 🖼️ Screenshot viewer
- 📊 Detailed stats per encounter

</td>
</tr>
</table>

---

## 📊 Current Status

### ✅ Completed Components

| Component | Status | Notes |
|-----------|--------|-------|
| Backend API | ✅ Running | Port 8000, all endpoints active |
| ESP32 Connection | ✅ Connected | USB HID mode, Switch control verified |
| Video Capture | ✅ Active | 1920x1080 @ 30fps from Elgato |
| Database | ✅ Ready | SQLite with encounter tracking |
| Frontend Dashboard | ✅ Running | Port 3000, cyberpunk UI |
| WebSocket | ✅ Live | Real-time updates working |
| Manual Controls | ✅ Working | Button press API functional |

### 📸 Required Before Automation

| Task | Status | Priority |
|------|--------|----------|
| Capture 7 UI templates | ❌ Needed | HIGH |
| Capture 25 nature templates | ❌ Needed | HIGH |
| Calibrate shiny zone | ❌ Needed | HIGH |
| Calibrate gender zone | ❌ Needed | MEDIUM |
| Position game save | ❌ Manual | HIGH |
| Test button presses | ⚠️ Recommended | HIGH |

---

## 🎮 Hardware Setup

### Required Hardware
1. **Nintendo Switch** with Pokemon Red (via NSO)
2. **Elgato Capture Card** (HD60, Neo, HD60S+)
3. **ESP32-C6** (Seeed Xiao ESP32-C6 recommended)
4. **USB-C Cable** (ESP32 to Switch)
5. **HDMI Cable** (Switch to Elgato)

### Connection Diagram

```
[Switch] ─(HDMI)→ [Elgato] ─(USB)→ [PC]
   ↑
   └─(USB-C Controller)─ [ESP32-C6] ←(WiFi Commands)─ [PC]
```

### ESP32 Communication Modes

**Current Mode: WiFi + USB HID (Recommended)**
- ESP32 → Switch: USB-C cable (controller emulation)
- PC → ESP32: WiFi HTTP commands
- No additional hardware needed
- ESP32 IP configured in `backend/config.yaml`

**Alternative: UART Serial**
- Requires USB-to-Serial adapter
- More complex wiring but lower latency
- See architecture docs for details

---

## 🛠️ Installation Guide

### Windows Installation (Recommended)

See [`backend/WINDOWS_INSTALL.md`](backend/WINDOWS_INSTALL.md) for detailed Windows setup.

**Quick Windows Setup:**
```cmd
:: 1. Install Python 3.8+
:: 2. Install Node.js 18+

:: Backend
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
start_server.bat

:: Frontend (new terminal)
cd frontend
npm install
start_frontend.bat

:: ESP32 (optional, if not already flashed)
cd esp32
platformio run --target upload
```

### Linux/Mac Installation

```bash
# Backend
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
chmod +x start_server.sh
./start_server.sh

# Frontend (new terminal)
cd frontend
npm install
chmod +x start_frontend.sh
./start_frontend.sh

# ESP32
cd esp32
platformio run --target upload
```

---

## 📖 Usage Guide

### Initial Setup (First Time)

1. **Start Both Servers**:
   ```bash
   # Terminal 1: Backend
   cd backend && start_server.bat
   
   # Terminal 2: Frontend  
   cd frontend && start_frontend.bat
   ```

2. **Open Dashboard**: Navigate to `http://localhost:3000` in browser

3. **Verify Connections**:
   - WebSocket: Should show "Connected" (green indicator)
   - ESP32: Should show "OK (usb_hid)"
   - Video Feed: Should display capture card stream

4. **Test Manual Controls**:
   - Click A, B, START buttons
   - Verify Switch responds
   - Confirms ESP32 is controlling correctly

### Template Capture

**CRITICAL**: You must capture template images before automation works.

1. **Play Pokemon Red** on your Switch
2. **Navigate to each required screen**
3. **Take screenshots** using:
   - Windows: Snipping Tool, ShareX, OBS
   - Mac: Shift+Cmd+4
   - Linux: Flameshot, Spectacle
4. **Save to template folders** with exact names
5. **Verify in dashboard**: Calibration modal shows uploaded templates

See [`NEXT_STEPS.md`](NEXT_STEPS.md) for detailed template list.

### Zone Calibration

1. **Load Pokemon Red** and get to Charmander's summary screen
2. **Click "🎯 CALIBRATE"** in dashboard
3. **Identify zones**:
   - Shiny star appears above the Pokeball icon
   - Gender symbol appears next to Pokemon name
4. **Find pixel coordinates**:
   - Use image editor (GIMP, Photoshop) to get X,Y positions
   - Or use trial and error with live feed overlays
5. **Enter coordinates** and save

### Running Automation

1. **Position Your Save**:
   - Load Pokemon Red
   - Be in Oak's lab, right after receiving Charmander
   - Save the game at this point

2. **Start Hunting**:
   - Click "▶ START" in dashboard
   - Watch state machine progress
   - Statistics update in real-time

3. **Monitor Progress**:
   - Live feed shows detection zones
   - Encounter counter increments
   - Charts populate with data
   - History table logs each reset

4. **When Shiny Found**:
   - Automation stops automatically
   - Screenshot saved to `backend/encounters/`
   - Dashboard shows shiny notification
   - Review encounter details in history

---

## 🔧 Configuration

### Backend Config (`backend/config.yaml`)

```yaml
hardware:
  esp32_ip: "192.168.4.1"           # ESP32 WiFi IP
  esp32_port: 80                     # HTTP port
  communication_mode: "wifi"         # or "uart"
  camera_index: 0                    # Capture card index

automation:
  button_hold_duration: 0.1          # Seconds per press
  soft_reset_hold: 0.5               # Reset combo duration

detection:
  shiny_zone:                        # Coordinates for star
    upper_x: 264
    upper_y: 109
    lower_x: 312
    lower_y: 151
  yellow_star_threshold: 20          # Minimum pixels for shiny
```

### Frontend Config (`.env` optional)

```env
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws
```

---

## 📊 Statistics & Tracking

The system tracks comprehensive statistics:

- **Total Encounters**: Every reset is logged
- **Shiny Probability**: Cumulative odds calculated (1 - (8191/8192)^n)
- **Gender Ratio**: Male vs Female distribution
- **Nature Frequency**: Which natures appear most often
- **Session Tracking**: Group encounters by session ID
- **Screenshot Archive**: Every encounter auto-saved

All data stored in `backend/shiny_hunter.db` (SQLite).

---

## 🐛 Troubleshooting

### ESP32 Disconnected
- Check WiFi connection to ESP32
- Verify IP address in config.yaml
- Try manual button test first
- See [`esp32/README.md`](esp32/README.md) for ESP32 debugging

### Video Feed Not Showing
- Check camera index in config.yaml (try 0, 1, 2)
- Verify Elgato is connected
- Backend logs should show "Video capture opened"
- Try different capture devices in Device Manager

### Templates Not Matching
- Ensure templates are high-quality PNG
- Verify correct resolution (should match your capture res)
- Adjust threshold values in config.yaml
- Check backend logs for detection attempts

### Automation Stops Immediately
- Templates may not match current game screen
- Game save not positioned correctly
- Check state machine logs in dashboard
- Verify detection zones are calibrated

### WebSocket Disconnected
- Backend may have crashed - check logs
- Firewall blocking port 8000
- CORS issues - check backend cors_origins
- Try refreshing browser

---

## 📚 Documentation

- [`plans/shiny-charmander-hunt-architecture.md`](plans/shiny-charmander-hunt-architecture.md) - Complete system architecture
- [`NEXT_STEPS.md`](NEXT_STEPS.md) - Detailed setup checklist
- [`backend/README.md`](backend/README.md) - Backend documentation
- [`frontend/README.md`](frontend/README.md) - Frontend documentation
- [`esp32/README.md`](esp32/README.md) - ESP32 firmware guide
- API Docs: `http://localhost:8000/docs` (Swagger UI)

---

## 🎯 Expected Performance

- **Reset Speed**: ~30-60 seconds per encounter (depending on game speed)
- **Video Processing**: 10-30 FPS (sufficient for turn-based game)
- **Detection Accuracy**: 95%+ with proper calibration
- **Shiny Odds**: 1/8192 (Gen 1/2) - expect ~4-8 hours average

---

## 🌟 Success Checklist

Before you start your first automated hunt, verify:

- [ ] Backend running on port 8000
- [ ] Frontend running on port 3000
- [ ] ESP32 connected (shows "OK" in dashboard)
- [ ] Video feed displaying in dashboard
- [ ] Manual button controls work
- [ ] All 7 UI templates captured
- [ ] All 25 nature templates captured
- [ ] Shiny zone calibrated
- [ ] Gender zone calibrated
- [ ] Game save positioned in Oak's lab
- [ ] Charmander in party slot 3

---

## 🤝 Contributing

This is a personal automation project. Feel free to fork and customize for your own shiny hunts!

### Extending for Other Pokemon
1. Adjust state machine in `backend/app/services/game_engine.py`
2. Capture new templates for different game screens
3. Update menu navigation logic
4. Modify detection zones for different Pokemon

---

## 📜 License

This project is for educational and personal use. Nintendo, Pokemon, and Switch are trademarks of Nintendo Co., Ltd.

---

## 🎉 Credits

Built with:
- FastAPI for blazing-fast async backend
- React for responsive UI
- OpenCV for computer vision
- ESP32-C6 for hardware control
- Recharts for beautiful data visualization

**Good luck on your shiny hunt!** ✨🔥

---

## 🔗 Quick Links

- **Backend API**: http://localhost:8000/docs
- **Frontend Dashboard**: http://localhost:3000
- **Backend Logs**: `backend/bot_history.log`
- **Screenshots**: `backend/encounters/`
- **Configuration**: `backend/config.yaml`
