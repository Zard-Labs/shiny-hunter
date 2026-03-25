# 🌟 Shiny Hunter Dashboard

Modern cyberpunk-styled React dashboard for monitoring and controlling the automated shiny hunting system.

## 🚀 Quick Start

### Install Dependencies
```bash
cd frontend
npm install
```

### Development Server
```bash
npm run dev
```

The dashboard will be available at `http://localhost:3000`

### Build for Production
```bash
npm run build
```

## 🎨 Features

### Real-Time Monitoring
- **Live Video Feed**: Stream from capture card with detection zone overlays
- **WebSocket Connection**: Real-time state updates and encounter notifications
- **System Status**: Monitor ESP32 connection, automation state, and backend health

### Statistics Dashboard
- **Encounter Counter**: Track total resets with live updates
- **Shiny Probability**: Real-time calculation of cumulative odds
- **Gender Distribution**: Live pie chart of male/female ratios
- **Nature Analysis**: Bar chart showing top 10 most common natures
- **Last Encounter**: Quick view of most recent Pokemon stats

### Control Panel
- **Automation Controls**: Start/stop automated hunting
- **Manual Button Inputs**: Test individual button presses (A, B, START, D-pad)
- **Soft Reset**: Emergency manual reset command
- **Calibration**: Configure detection zones and upload templates

### Encounter History
- **Complete Log**: Paginated table of all encounters
- **Shiny Highlighting**: Gold-highlighted rows for shiny finds
- **Screenshot Viewer**: Click any encounter to view full screenshot
- **Detailed Stats**: Gender, nature, timestamp, and detection confidence

### Calibration Tools
- **Zone Configuration**: Set precise coordinates for shiny/gender detection
- **Template Upload**: Add new OpenCV template images
- **Live Preview**: Visual feedback of detection zones on video feed

## 🎨 Design Philosophy

The dashboard features a **cyberpunk hacker aesthetic** with:
- Neon cyan/magenta/yellow color palette
- Glowing borders and text shadows
- Scanline overlay effects
- Holographic card animations
- Terminal-style monospace fonts
- Data-rich visualizations with Recharts

## 📡 API Integration

The frontend connects to the FastAPI backend at:
- **REST API**: `http://localhost:8000/api/*`
- **WebSocket**: `ws://localhost:8000/ws`

### Environment Variables

Create a `.env` file (optional):
```env
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws
```

## 🧩 Component Architecture

```
App.jsx (Root)
├── ControlPanel.jsx       # Automation + manual controls
├── StatusDisplay.jsx      # State machine + connection status
├── LiveFeed.jsx           # Video stream with overlays
├── StatisticsPanel.jsx    # Charts and encounter stats
├── HistoryTable.jsx       # Encounter log with modal
└── CalibrationModal.jsx   # Zone/template configuration
```

### Key Hooks
- **useWebSocket**: Manages WebSocket connection, handles reconnection
- Custom hooks can be added for automation state, statistics, etc.

### Services
- **api.js**: Axios-based API client for all backend endpoints

## 🎯 Usage

1. **Start the backend server first** (see backend/README.md)
2. **Launch the frontend**: `npm run dev`
3. **Open browser**: Navigate to `http://localhost:3000`
4. **Check connections**: Verify WebSocket and ESP32 are connected
5. **Calibrate (first time)**: Click "CALIBRATE" to set detection zones
6. **Start hunting**: Click "▶ START" to begin automated shiny hunting
7. **Monitor live**: Watch the video feed, stats update in real-time
8. **Review history**: Check encounter log for past Pokemon

## 🛠️ Development

### Tech Stack
- **React 18**: Modern hooks, concurrent features
- **Vite**: Lightning-fast HMR and build tool
- **Recharts**: Responsive charts for data visualization
- **Axios**: HTTP client with interceptors
- **WebSocket API**: Native browser WebSocket for real-time updates

### Styling
- **CSS Custom Properties**: Theming with CSS variables
- **CSS Animations**: Smooth transitions, glowing effects
- **Responsive Design**: Grid layout adapts to screen size

## 📦 Dependencies

```json
{
  "react": "^18.2.0",
  "react-dom": "^18.2.0",
  "axios": "^1.6.0",
  "recharts": "^2.10.0"
}
```

## 🐛 Troubleshooting

### WebSocket won't connect
- Ensure backend is running on port 8000
- Check CORS settings in backend config
- Verify firewall isn't blocking WebSocket connections

### Video feed not showing
- Check if capture card is detected by backend
- Ensure `/ws` endpoint is streaming video frames
- Verify WebSocket connection is established

### Charts not rendering
- Ensure statistics data is being fetched
- Check browser console for errors
- Verify recharts is installed correctly

## 📝 Future Enhancements

- [ ] Dark/light theme toggle
- [ ] Export statistics to CSV
- [ ] Discord webhook notifications
- [ ] Mobile responsive improvements
- [ ] Audio alerts for shiny detection
- [ ] Multi-session comparison view
- [ ] Custom color theme editor
