# 📹 Video Feed Troubleshooting Guide

## ✅ Issue Fixed!

The WebSocket video streaming has been updated. The error was that the detection zone coordinates were being accessed incorrectly.

---

## 🔧 Steps to Resolve "Waiting for video feed..."

### Step 1: Refresh Your Browser (CRITICAL)

The backend server has reloaded with the fix. You need to:

1. **Go to your browser** at `http://localhost:3000`
2. **Press F5 or Ctrl+R** to refresh the page
3. **Wait 2-3 seconds** for WebSocket to reconnect

The video feed should now appear!

### Step 2: Check Browser Console (If Still Not Working)

1. **Press F12** to open Developer Tools
2. **Go to Console tab**
3. **Look for errors** related to WebSocket or video
4. **Check Network tab** to see if WebSocket connection is established

Expected console messages:
```
WebSocket connected
```

### Step 3: Verify WebSocket Connection

In the dashboard, check the top-right corner:
- Should show **green indicator** and "Connected"
- If red/disconnected, check if backend is running

### Step 4: Check Backend Terminal

Look at Terminal 1 (backend) for these messages:
```
✅ Good:
- "WebSocket client connected. Total: X"
- No error messages about streaming video

❌ Bad:
- "Error streaming video..."
- Any Python errors or tracebacks
```

---

## 🎯 What Changed

### Backend Fix Applied
The [`websocket.py`](backend/app/routes/websocket.py) handler now:
- ✅ Imports `settings` from config
- ✅ Correctly accesses zone coordinates as dictionaries
- ✅ Streams video frames at ~10 FPS<br/>
- ✅ Encodes frames as base64 JPEG
- ✅ Includes detection zone annotations

### Expected Behavior
- Video feed displays your capture card stream
- FPS counter shows ~10 FPS (backend streams at 10 FPS to reduce bandwidth)
- Detection zone overlays appear (green for shiny, magenta for gender)
- Smooth real-time streaming

---

## 🐛 Additional Troubleshooting

### Browser Shows Video But It's Black
**Cause**: Capture card detected but not receiving video
**Solution**:
1. Make sure Switch is ON and outputting HDMI
2. Check Elgato is properly connected
3. Try opening OBS or other capture software to verify Elgato works

### Video Feed Is Pixelated/Low Quality
**Cause**: JPEG compression for WebSocket streaming
**Solution**: This is normal - backend compresses to 85% quality for performance
- Original 1920x1080 feed is used for detection
- WebSocket stream is scaled down for display only

### Video Feed Is Frozen
**Cause**: WebSocket disconnected or backend crashed
**Solution**:
1. Check Terminal 1 for backend errors
2. Refresh browser page
3. Check if camera is still detected: `curl http://localhost:8000/health`

### Video Feed Lags Behind
**Cause**: Network congestion or slow encoding
**Solution**:
- Normal for ~100-200ms delay
- If >1 second lag, check backend logs
- Reduce stream FPS in websocket.py if needed (increase sleep time)

### "WebSocket Disconnected" in Dashboard
**Cause**: Backend not running or CORS issue
**Solution**:
1. Check Terminal 1 - backend should be running
2. Verify `config.yaml` cors_origins includes `http://localhost:3000`
3. Check firewall isn't blocking port 8000

---

## 📊 Expected Performance

| Metric | Value |
|--------|-------|
| Capture Resolution | 1920x1080 @ 30fps |
| Processing Resolution | 640x480 (scaled) |
| WebSocket Stream FPS | ~10 FPS |
| Stream Latency | 100-200ms |
| JPEG Quality | 85% |

---

## ✅ Verification Checklist

Before proceeding, verify:

- [ ] Browser refreshed after backend restart
- [ ] Dashboard shows "Connected" (green indicator)
- [ ] Video feed displays (not "Waiting for video feed...")
- [ ] FPS counter shows ~10 FPS
- [ ] Backend Terminal shows no "Error streaming video" messages
- [ ] WebSocket connections are stable (check backend logs)

---

## 🎉 Once Video Feed Works

You're ready for the next steps:

1. **Test Manual Controls**: Click buttons in Control Panel
2. **Capture Templates**: Screenshot Pokemon Red UI screens
3. **Calibrate Zones**: Set shiny/gender detection coordinates
4. **Start Automation**: Click "▶ START" and watch it hunt!

---

## 📞 Quick Commands

**Test video capture manually**:
```bash
cd backend
source venv/Scripts/activate
python -c "from app.services.video_capture import video_capture; video_capture.open(); print('Camera OK!' if video_capture.is_open else 'Camera FAIL')"
```

**Check WebSocket endpoint**:
```bash
curl http://localhost:8000/ws
# Should return "Method Not Allowed" (normal - needs WebSocket client)
```

**Test backend health**:
```bash
curl http://localhost:8000/health
# Should show: {"status":"healthy","services":{"esp32":true,"camera":true,"automation":false}}
```

---

## 🔍 Debug Mode

If still not working, enable debug logging:

1. Edit [`backend/config.yaml`](backend/config.yaml)
2. Change `logging.level` from `"INFO"` to `"DEBUG"`
3. Restart backend server
4. Check logs for detailed video streaming info

---

## 🚀 Next Actions

Once video feed displays correctly:

1. ✅ Video working → Proceed to manual control testing
2. ✅ Manual controls work → Start template capture
3. ✅ Templates captured → Calibrate detection zones
4. ✅ Zones calibrated → Begin automated hunting!

**Current Status**: Server reloaded with video streaming fix - **REFRESH YOUR BROWSER NOW**
