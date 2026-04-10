# 🖥️ ShinyStarter Desktop App

Desktop application wrapper for ShinyStarter, built with Electron. Bundles the Python backend and React frontend into a single installable application — no Python, Node.js, or terminal commands required for end users.

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Electron Main Process                          │
│  ├── Spawns backend.exe (PyInstaller bundle)    │
│  ├── Polls /health until ready                  │
│  ├── Creates BrowserWindow → localhost:8000     │
│  └── Manages lifecycle: start, crash, shutdown  │
├─────────────────────────────────────────────────┤
│  Electron Renderer (BrowserWindow)              │
│  └── React UI served by FastAPI at :8000        │
│      ├── REST API: /api/*                       │
│      └── WebSocket: /ws                         │
├─────────────────────────────────────────────────┤
│  Python Backend (backend.exe)                   │
│  ├── FastAPI + uvicorn                          │
│  ├── OpenCV detection                           │
│  ├── SQLite database                            │
│  └── ESP32 communication (WiFi/Serial)          │
└─────────────────────────────────────────────────┘
```

## Development Setup

### Prerequisites
- Node.js 18+
- Python 3.10+ with the backend virtual environment set up (see `backend/README.md`)

### Running in Development Mode

1. **Start the backend** (in a separate terminal):
   ```bash
   cd backend
   venv\Scripts\activate
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

2. **Build the frontend** (so FastAPI can serve it):
   ```bash
   cd frontend
   npm install
   npm run build
   ```

3. **Start the Electron app in dev mode**:
   ```bash
   cd desktop
   npm install
   npm run dev
   ```

   In dev mode (`--dev` flag), Electron will try to use the already-running Python backend. If no backend is detected, it will attempt to start one using `python` from the backend directory.

### Running Electron with Vite Dev Server

For hot-reload of the React frontend during development, you can run the Vite dev server separately and have Electron load from it. However, the default approach (backend serves built frontend) is simpler.

## Building for Distribution

### Quick Build (All Steps)

```bash
scripts\build-all.bat
```

This runs all three build steps in sequence and produces the final installer.

### Individual Build Steps

#### 1. Build Python Backend (PyInstaller)

```bash
scripts\build-backend.bat
```
- Requires: Python venv with all dependencies + PyInstaller
- Output: `backend-dist/backend.exe` (+ supporting files)

#### 2. Build React Frontend (Vite)

```bash
scripts\build-frontend.bat
```
- Requires: Node.js, npm
- Output: `frontend/dist/` (static HTML/JS/CSS)

#### 3. Package Desktop App (electron-builder)

```bash
scripts\build-desktop.bat
```
- Requires: Steps 1 & 2 completed
- Output: `desktop/dist/ShinyStarter Setup 1.0.0.exe` (NSIS installer)
- Output: `desktop/dist/ShinyStarter-Portable-1.0.0.exe` (portable)

## Directory Structure

```
desktop/
├── main/
│   ├── index.js              # Electron main process entry
│   ├── backend-manager.js    # Python backend lifecycle manager
│   └── splash.html           # Loading screen (shown during startup)
├── preload/
│   └── index.js              # Secure IPC bridge (contextBridge)
├── resources/
│   ├── icon.ico              # App icon (Windows)
│   ├── icon.png              # App icon (PNG)
│   └── README.md             # Icon generation instructions
├── package.json              # Electron deps + electron-builder config
└── README.md                 # This file
```

## Configuration

### Electron-Builder Config

Build configuration is in `package.json` under the `"build"` key:
- **NSIS installer**: customizable, non-one-click, allows directory selection
- **Portable**: single-file executable
- **extraResources**: bundles `backend-dist/` and `frontend/dist/`

### App Data Location

In the packaged app, user data is stored in:
```
%APPDATA%\ShinyStarter\
├── config.yaml       # User configuration
├── shinyhunter.db    # SQLite database
├── encounters/       # Screenshot captures
├── templates/        # Detection templates
└── logs/
    ├── backend.log   # Python backend logs
    └── electron.log  # Electron logs
```

## IPC API (Preload Bridge)

The preload script exposes `window.electronAPI` to the renderer:

| Method | Description |
|--------|-------------|
| `getVersion()` | Returns app version string |
| `isPackaged()` | Returns boolean |
| `minimize()` | Minimize window |
| `maximize()` | Toggle maximize |
| `close()` | Close window |
| `showNotification(title, body)` | Show native OS notification |
| `openExternal(url)` | Open URL in system browser |
| `openLogs()` | Open logs directory in Explorer |
| `getBackendStatus()` | Get backend running status |
| `onBackendStatus(callback)` | Listen for backend status changes |

## Troubleshooting

### Backend fails to start
- Check `%APPDATA%\ShinyStarter\logs\electron.log` for error details
- Ensure port 8000 is not in use by another application
- If Windows Defender blocks `backend.exe`, add an exclusion for the install directory

### Antivirus flags backend.exe
PyInstaller-bundled executables are sometimes flagged as false positives. Options:
1. Add an exclusion in your antivirus for the ShinyStarter install directory
2. Code-sign the executable with a certificate (see electron-builder docs)

### App shows blank white screen
The backend likely hasn't finished starting. Wait a few more seconds. If it persists, restart the app and check logs.

### Camera/ESP32 not detected
Same troubleshooting as the web version — check `config.yaml` in `%APPDATA%\ShinyStarter\` for correct camera index and ESP32 IP address.
