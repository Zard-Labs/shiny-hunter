# 🌟 ShinyStarter — Automated Shiny Pokémon Hunter

<div align="center">

**Template-driven shiny hunting automation for Pokémon Red & Green on Nintendo Switch**

![Status](https://img.shields.io/badge/status-active-success)
![Backend](https://img.shields.io/badge/backend-FastAPI-009688)
![Frontend](https://img.shields.io/badge/frontend-React-61dafb)
![Desktop](https://img.shields.io/badge/desktop-Electron-47848f)
![Hardware](https://img.shields.io/badge/hardware-ESP32--S3-red)

[Install Firmware](https://zard-labs.github.io/shiny-hunter) · [API Docs](http://localhost:8000/docs) · [Report Bug](https://github.com/Zard-Labs/shiny-hunter/issues)

</div>

---

## Overview

ShinyStarter automates shiny hunting across multiple Pokémon games by combining computer vision with hardware controller emulation. A data-driven template engine lets you define any hunt strategy — starter resets, wild encounters, static encounters — without writing code.

### Key Features

- 🧩 **Template Engine** — JSON-defined state machines drive all automation; create, edit, clone, and share hunt strategies
- 🎮 **Multiple Hunt Types** — starter soft-resets, wild encounter sparkle detection, Magikarp purchases, static encounters
- 🖥️ **Desktop App** — one-click Electron installer bundles everything (no Python/Node.js required for end users)
- 📡 **Browser Firmware Installer** — flash ESP32-S3 from Chrome/Edge with zero tools installed
- 📶 **WiFi Captive Portal** — ESP32 self-serves a setup page for WiFi config, no hardcoded credentials
- 🎥 **Live Dashboard** — real-time video feed, detection overlays, statistics, and encounter history
- ✨ **Dual Detection** — yellow-star pixel analysis for summary screens + battle-sparkle detection with continuous background monitoring (sparkle detection is ⚠️ **alpha**)
- 📊 **Hunt Tracking** — group encounters into hunts, view per-hunt stats, archive and start fresh

---

## Architecture

```
┌─────────────┐        ┌──────────────┐        ┌──────────────────────┐
│  Nintendo    │  HDMI  │  Capture     │  USB   │  PC                  │
│  Switch      ├───────►│  Card        ├───────►│  Backend :8000       │
└──────┬───────┘        └──────────────┘        │  (FastAPI + OpenCV)  │
       │                                         └──────────┬───────────┘
       │ USB-C (Controller)                                 │
       │                                                     │ WiFi / HTTP
       │        ┌──────────────┐                             │
       └────────┤  ESP32-S3    │◄────────────────────────────┘
                │  (USB HID)   │
                └──────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  Desktop App (Electron)  — or —  Browser: http://localhost:3000  │
│  React Dashboard with real-time WebSocket updates                │
└──────────────────────────────────────────────────────────────────┘
```

| Component | Role |
|-----------|------|
| **ESP32-S3** (Xiao) | Emulates Switch Pro Controller via USB HID; receives commands over WiFi |
| **Capture Card** | Feeds 1080p video to the backend for OpenCV analysis |
| **Backend** | FastAPI server — template interpreter, detection engine, statistics, WebSocket |
| **Frontend** | React dashboard — live feed, controls, template library, calibration |
| **Desktop** | Electron wrapper — bundles backend + frontend into a single installer |

---

## Getting Started

### Option A: Desktop App (Recommended)

1. Download the latest **ShinyStarter Setup** from [Releases](https://github.com/Zard-Labs/shiny-hunter/releases)
2. Install and launch — the backend starts automatically
3. Flash ESP32 firmware (see [Firmware Setup](#firmware-setup) below)
4. Plug in your capture card and ESP32, then open the app

### Option B: Developer Setup

```bash
# Backend
cd backend
python -m venv venv && venv\Scripts\activate   # Windows
pip install -r requirements.txt
start_server.bat                                # or ./start_server.sh

# Frontend (separate terminal)
cd frontend
npm install && npm run dev

# ESP32 firmware
cd esp32
platformio run --target upload
```

Backend: `http://localhost:8000` · Frontend: `http://localhost:3000` · API Docs: `http://localhost:8000/docs`

---

## Firmware Setup

### Flash the ESP32-S3

**Browser (recommended):** Visit the [ShinyStarter Installer](https://zard-labs.github.io/shiny-hunter) in Chrome or Edge, connect the ESP32-S3 via USB-C, and click Install. No tools needed.

**PlatformIO (developers):** `cd esp32 && platformio run --target upload`

### Connect to WiFi

1. After flashing, join the `ShinyStarter-Setup` WiFi network from your phone or laptop
2. A config page opens automatically — select your home WiFi and enter the password
3. The ESP32 reboots and joins your network; note its IP address from the serial monitor or router
4. Enter that IP in the dashboard's ESP32 Config panel (or `backend/config.yaml`)

To reconfigure WiFi later, visit `http://<ESP32_IP>/reset-wifi`.

### Hardware Wiring

```
[Switch] ─(HDMI)→ [Capture Card] ─(USB)→ [PC]
   ↑
   └─(USB-C)─ [ESP32-S3]  ◄─(WiFi)─ [PC]
```

> **Requires:** XIAO ESP32-S3, USB-C data cable, any HDMI capture card (Elgato HD60, Neo, etc.), Nintendo Switch

---

## How It Works

### Template-Driven Automation

Every hunt is defined by an **automation template** — a JSON document containing:

- **Steps**: ordered state-machine stages (boot → navigate → check → reset)
- **Rules**: per-step conditions (`template_match`, `timeout`) and actions (`press_button`, `wait`)
- **Detection config**: which method to use, HSV thresholds, zone coordinates
- **Soft-reset timing**: hold duration, wait-after, retry limits

Templates can be created visually in the dashboard's **Template Library** or written as JSON.

### Included Hunt Templates

| Template | Strategy |
|----------|----------|
| 🔥 Starter Hunt | Soft-reset, check summary for yellow star |
| 🐟 Magikarp Hunt | Purchase Magikarp, check summary |
| 🌿 Wild Encounter | Walk in grass, detect battle-entry sparkle — ⚠️ **Alpha** |
| 🗿 Static Encounter | Initiate encounter, detect sparkle — ⚠️ **Alpha** |

### Detection Methods

| Method | How It Works |
|--------|-------------|
| **Yellow Star (summary)** | Crop ROI above Pokéball icon → HSV mask → count yellow pixels ≥ threshold |
| **Battle Sparkle** | Analyze ring buffer of recent frames for bright-pixel spikes during battle entry — ⚠️ **Alpha** |
| **Continuous Monitor** | Background async task running sparkle analysis alongside the macro loop — ⚠️ **Alpha** |

---

## Dashboard

The React frontend provides:

- **Live Video Feed** — real-time stream with detection zone overlays
- **Control Panel** — start/stop automation, manual button presses, soft reset
- **Template Library** — browse, create, edit, clone, import/export hunt templates
- **Hunt Selector** — switch between current and past hunts
- **Statistics Panel** — encounter count, shiny probability, nature & gender charts
- **History Table** — paginated log with screenshot viewer and shiny highlighting
- **Calibration Tools** — ROI zone picker, snapshot capture, HSV tuning
- **Camera Selector** — scan and switch capture devices, set crop mode
- **ESP32 Config** — set controller IP address from the UI

---

## Project Structure

```
ShinyStarter/
├── backend/                   # Python FastAPI server
│   ├── app/
│   │   ├── main.py            # App entry, static serving
│   │   ├── models.py          # AutomationTemplate, Hunt, Encounter, TemplateImage
│   │   ├── routes/            # REST + WebSocket endpoints
│   │   ├── services/          # Game engine, OpenCV detector, ESP32 manager, video capture
│   │   └── utils/             # Command builder, logger
│   ├── seed_templates/        # Pre-built hunt templates (auto-seeded on first run)
│   ├── config.yaml            # Runtime configuration
│   └── requirements.txt
│
├── frontend/                  # React + Vite dashboard
│   └── src/
│       ├── components/        # 15+ UI components
│       ├── hooks/             # useWebSocket
│       └── services/          # API client
│
├── desktop/                   # Electron desktop wrapper
│   ├── main/                  # Main process + backend lifecycle manager
│   ├── preload/               # Secure IPC bridge
│   └── package.json           # electron-builder config
│
├── esp32/                     # ESP32-S3 firmware (PlatformIO)
│   ├── src/main.cpp           # WiFi captive portal + USB HID controller
│   └── platformio.ini
│
├── docs/                      # GitHub Pages — web firmware installer
│   ├── index.html
│   └── firmware/              # Compiled firmware binaries + manifest
│
└── scripts/                   # Build pipeline (backend → frontend → desktop)
    ├── build-all.bat
    ├── build-backend.bat
    ├── build-frontend.bat
    └── build-desktop.bat
```

---

## API Reference

All endpoints are documented interactively at `http://localhost:8000/docs` (Swagger UI).

| Group | Prefix | Key Endpoints |
|-------|--------|---------------|
| Automation | `/api/automation` | `POST start`, `POST stop`, `GET status` |
| Templates | `/api/automation-templates` | Full CRUD, `POST activate`, `GET export`, `POST import`, `POST clone` |
| Statistics | `/api/statistics` | `GET current`, `GET history`, `GET charts` |
| Hunts | `/api/statistics` | `POST new-hunt`, `GET hunts` |
| Control | `/api/control` | `POST button`, `GET esp32/status`, `POST esp32/connect` |
| Calibration | `/api/calibration` | `POST zone`, `GET snapshot`, `GET current` |
| Camera | `/api/camera` | `GET devices`, `POST select`, `POST crop-mode` |
| WebSocket | `/ws` | Real-time state updates, encounter events, video frames |

---

## Configuration

### Backend (`backend/config.yaml`)

```yaml
hardware:
  esp32_ip: "192.168.1.105"     # ESP32 WiFi IP
  esp32_port: 80
  camera_index: 0               # Capture card device index

detection:
  shiny_zone:                   # Coordinates for star detection
    upper_x: 264
    upper_y: 109
    lower_x: 312
    lower_y: 151
  yellow_star_threshold: 20
```

### Desktop App Data

When running as a packaged desktop app, user data lives in:

```
%APPDATA%\ShinyStarter\
├── config.yaml       # Configuration
├── shinyhunter.db    # SQLite database
├── encounters/       # Screenshot captures
├── templates/        # Detection template images
└── logs/             # Backend + Electron logs
```

---

## Building from Source

The full build pipeline produces an installable Windows desktop app:

```bash
scripts\build-all.bat       # Runs all three steps:
```

| Step | Script | Output |
|------|--------|--------|
| 1. Backend | `build-backend.bat` | `backend-dist/backend.exe` (PyInstaller) |
| 2. Frontend | `build-frontend.bat` | `frontend/dist/` (Vite) |
| 3. Desktop | `build-desktop.bat` | `desktop/dist/ShinyStarter Setup *.exe` + portable |

---

## Contributing

### Adding Hunt Templates

Anyone can contribute a new hunt strategy:

1. Create a folder under `backend/seed_templates/` (e.g. `05_my_hunt/`)
2. Add a `definition.json` and an `images/` folder with reference screenshots
3. Test locally (delete `shiny_hunter.db`, restart backend, verify in Template Library)
4. Open a PR

See [`backend/seed_templates/README.md`](backend/seed_templates/README.md) for the full schema and guidelines.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| ESP32 not responding | Check WiFi — both devices must be on the same network. Try `curl http://<IP>/status` |
| Video feed black | Change camera index in dashboard Camera Selector (try 0, 1, 2) |
| Templates not matching | Recapture at your capture resolution; lower threshold in template editor |
| Automation stuck | Check state in dashboard Status Banner; review backend logs |
| WebSocket disconnected | Refresh browser; verify backend is running; check port 8000 firewall |
| Desktop app blank screen | Backend still starting — wait a few seconds. Check `%APPDATA%\ShinyStarter\logs\` |
| Switch doesn't see controller | Use a USB-C **data** cable (not charge-only); replug and check serial output |

---

## Documentation

- [`backend/README.md`](backend/README.md) — Backend API, services, database schema
- [`frontend/README.md`](frontend/README.md) — Dashboard components, hooks, styling
- [`esp32/README.md`](esp32/README.md) — Firmware, button codes, WiFi setup
- [`desktop/README.md`](desktop/README.md) — Electron app, IPC API, build config
- [`backend/seed_templates/README.md`](backend/seed_templates/README.md) — Template contribution guide
- [`CAMERA_SETUP_GUIDE.md`](CAMERA_SETUP_GUIDE.md) — Capture card configuration
- [`VIDEO_FEED_TROUBLESHOOTING.md`](VIDEO_FEED_TROUBLESHOOTING.md) — Video feed debugging

---

## License

MIT — This project is for educational and personal use. Nintendo, Pokémon, and Switch are trademarks of Nintendo Co., Ltd.

---

Built with FastAPI · React · OpenCV · Electron · ESP32-S3 · Recharts

**Good luck on your shiny hunt!** ✨🔥
