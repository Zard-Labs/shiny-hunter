# 📹 Camera Setup Guide

## Current Situation

Based on your system:
- **Device 0**: HD Pro Webcam C920 (1920x1080 @ 30fps) 🎥 ← CURRENTLY WORKING
- **Device 1**: EPSON ET-8550 Printer (640x480 @ 0fps) ⚠️ ← DON'T USE (will fail)
- **Elgato**: Not showing up in first 2 indices

## 🔍 Finding Your Elgato

### Option 1: Use OBS Studio (Recommended)
1. Open OBS Studio
2. Add Sources → Video Capture Device
3. Click dropdown to select device
4. Try each device until you see your Switch
5. Note the device name or position in list
6. That device number maps to the camera index

### Option 2: Try Indices Manually
Your Elgato might be at index 2, 3, or higher. Try updating config:

Edit [`backend/config.yaml`](backend/config.yaml:16):
```yaml
hardware:
  camera_index: 2  # Try 2, then 3, then 4
```

Then restart backend server and check video feed.

### Option 3: Use Elgato's Software
1. **Close OBS** and any other apps using the capture card
2. **Open Elgato 4K Capture Utility** (if installed)
3. If capture card shows video there, it's connected properly
4. Close Elgato software (it holds exclusive access)
5. Try camera indices again in dashboard

## ⚠️ Current Device 0 Issue

Since Device 0 (your webcam) is streaming successfully at 15fps but you need the Elgato:

### Why "Failed to switch camera: undefined"?
- Device 1 (printer) can't provide video frames
- OpenCV opens it successfully but `read()` fails
- This causes cascading errors
- Frontend shows "undefined" because backend returns error without clear message

### Solution
**Keep using Device 0 for now** since it's working. The real fix is finding your Elgato device index.

## 🔧 Troubleshooting Steps

### Step 1: Check Device Manager
1. Press `Win + X` → Device Manager
2. Expand "Cameras" or "Imaging devices"
3. Look for "Elgato Game Capture HD60" or similar
4. Right-click → Properties → check if enabled

### Step 2: Check USB Connection
- Elgato connected via USB 3.0 port (blue port)?
- Try different USB ports
- USB cable firmly connected
- Switch outputting HDMI to Elgato?

### Step 3: Check Elgato Software
- Is Elgato software installed?
- Is it currently running? (Close it - conflicts with OpenCV)
- Check Elgato 4K Capture Utility settings

### Step 4: Try Default MSMF Backend
If DirectShow isn't detecting Elgato, try switching back:

Edit [`backend/app/services/video_capture.py`](backend/app/services/video_capture.py:29):
```python
# Remove cv2.CAP_DSHOW to use default backend
self.cap = cv2.VideoCapture(self.camera_index)
```

Some Elgato models work better with MSMF backend.

## 🎥 If Your Capture Device is Really at Index 0

**Good news**: You're already seeing video at 15fps from Device 0!

If this is actually your Elgato (maybe Windows renamed it or you're viewing it through passthrough):
1. Device 0 is working fine
2. Ignore the switching errors
3. Continue with template capture and calibration
4. The important thing is: **Is the video showing your Switch display?**

### Verify It's the Right Device:
- Is the video feed showing your Nintendo Switch screen?
- OR is it showing your webcam?

If showing Switch → You're good! Device 0 is correct.
If showing webcam → Need to find Elgato at higher index.

##  Alternative: Use Without Elgato Names

The system works fine with  generic "Device X" names. Key is:
1. Find which index shows your Switch display
2. Update `camera_index` in config.yaml
3. Restart backend
4. Video will work fine

**Bottom line**: Device names are just for convenience. What matters is finding the index that shows your Switch!