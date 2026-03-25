# 📹 Video Capture Diagnosis

## Current Situation

Your system shows:
- ✅ Camera opens successfully (Device 0 and Device 1 both at 1920x1080 @ 30fps)
- ✅ NO "Failed to read frame" errors after latest fix
- ❌ Video feed shows briefly then drops to 0 FPS
- ❌ Both webcam and Elgato have same behavior

## 🔍 Root Cause

This is NOT a camera problem - it's a **WebSocket streaming issue**.

The WebSocket is connected but the video stream task might be:
1. Failing silently
2. read_frame() returning None (no frames available)
3. Encoding failing
4. Rate limiting/throttling

## 🧪 Test Directly

Let's test video capture outside the WebSocket:

```python
# Test script - save as test_capture.py in backend folder
import cv2
import time

# Test device 0 (webcam)
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
print(f"Device 0 opened: {cap.isOpened()}")

for i in range(10):
    ret, frame = cap.read()
    print(f"Frame {i}: ret={ret}, shape={frame.shape if ret else None}")
    time.sleep(0.1)

cap.release()
print("Done")
```

Run it:
```bash
cd backend
venv\Scripts\activate
python test_capture.py
```

Expected output:
```
Device 0 opened: True
Frame 0: ret=True, shape=(1080, 1920, 3)
Frame 1: ret=True, shape=(1080, 1920, 3)
...
```

## 💡 Quick Workaround

Since both cameras exhibit the same freeze behavior, the issue is in the WebSocket streaming loop, not the cameras.

### Option 1: Use OBS Virtual Camera
1. Open OBS Studio
2. Add Video Capture Device → Select your Elgato
3. Start Virtual Camera (Tools menu)
4. In dashboard, select "OBS Virtual Camera" device
5. OBS handles the buffering, OpenCV gets clean frames

### Option 2: Use Static Image Mode (For Testing)
Temporarily skip video streaming and just capture screenshots on demand for automation.

### Option 3: debug WebSocket Streaming
The issue might be:
- WebSocket task crashing silently
- asyncio.sleep(0.1) blocking other tasks
- video_capture.read_frame() returning None consistently
- cv2.imencode failing
- base64 encoding issues

## 🎯 Recommended Next Step

**USE DEVICE 0 (Webcam) TO TEST THE SYSTEM**

Even though video feed freezes, you can:
1. Use webcam pointed at your Switch screen (low-tech but works!)
2. Complete templates and calibration
3. Test the automation flow end-to-end
4. Fix video streaming issues later

OR

**USE OBS VIRTUAL CAMERA** - This is the most reliable solution for capture cards with OpenCV.

The core automation (ESP32 control, state machine, detection) doesn't need real-time video feed. Video is mainly for monitoring. The automation reads frames directly from video_capture service.