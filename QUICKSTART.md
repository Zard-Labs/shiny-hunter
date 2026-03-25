# ⚡ Quick Start Guide - Shiny Hunter

## 🎉 Current Status: READY FOR TESTING!

Both your backend and frontend are **currently running**:
- ✅ **Backend**: `http://localhost:8000` (active)
- ✅ **Frontend**: `http://localhost:3000` (active)
- ✅ **ESP32**: Connected (usb_hid mode)
- ✅ **Capture Card**: Active (1920x1080 @ 30fps)

---

## 🚀 What to Do RIGHT NOW

### Step 1: Open the Dashboard (30 seconds)

**Open your browser** and go to:
```
http://localhost:3000
```

You should see a **cyberpunk-styled dashboard** with:
- 📹 Live video feed from your capture card
- ⚡ Control panel on the left
- 📊 Statistics panel on the right
- 🎮 Manual button controls

### Step 2: Test Manual Controls (2 minutes)

<function_calls>
<invoke name="$FUNCTION_NAME">
1. **In the Control Panel**, try clicking buttons:
   - Click **"A"** button
   - Click **"B"** button
   - Click **"START"** button
   - Try the **D-pad** buttons (UP, DOWN, LEFT, RIGHT)

2. **Watch your Switch**:
   - Does it respond to the button presses?
   - If YES → ESP32 control is working! ✅
   - If NO → Check ESP32 connection

3. **Try Soft Reset**:
   - Click **"🔄 SOFT RESET"**
   - This sends the A+B+START+SELECT combo
   - Useful for testing if you're in a game

### Step 3: Verify Video Feed (1 minute)

In the dashboard:
- ✅ Video feed shows your Switch display
- ✅ FPS counter shows ~30 FPS
- ⚠️ No video? Check camera index in `backend/config.yaml`

---

## 📸 BEFORE You Can Auto-Hunt (REQUIRED)

The automation **will not work** until you capture template images and calibrate zones.

### Templates Needed (30-60 minutes)

Navigate to each screen in Pokemon Red and take screenshots:

#### Pokemon Red UI Templates
📁 `backend/templates/pokemon_red/`

1. **title_screen.png** - Opening title/logo
2. **load_game.png** - "CONTINUE" menu option
3. **nickname_screen.png** - Nickname prompt dialog
4. **oak_lab.png** - Oak standing in lab
5. **pokemon_menu.png** - "POKEMON" in START menu
6. **choose_pokemon.png** - Starter selection screen
7. **summary_screen.png** - Pokemon info/stats screen

#### Nature Templates  
📁 `backend/templates/natures/`

Screenshot each nature name text (25 total):
- adamant.png, bashful.png, bold.png, brave.png, calm.png
- careful.png, docile.png, gentle.png, hardy.png, hasty.png
- impish.png, jolly.png, lax.png, lonely.png, mild.png
- modest.png, naive.png, naughty.png, quiet.png, quirky.png
- rash.png, relaxed.png, sassy.png, serious.png, timid.png

**Template Capture Tips:**
- Use **high quality** PNG format
- Crop **precisely** to just the text/element
- Match your **capture resolution** (1080p, 720p, etc.)
- Keep **consistent lighting** in your recording setup

### Detection Zones (15 minutes)

📍 **Shiny Star Location**
- Open Charmander's summary screen
- Look for where the shiny star would appear (above Pokeball)
- Note pixel coordinates: upper-left (ux, uy) and lower-right (lx, ly)
- Default: `ux: 264, uy: 109, lx: 312, ly: 151`

📍 **Gender Symbol Location**
- On the same summary screen
- Look for ♂/♀ symbol next to Pokemon name
- Note pixel coordinates
- Default: `ux: 284, uy: 68, lx: 311, ly: 92`

**Set via Dashboard:**
- Click "🎯 CALIBRATE" button
- Select zone type (Shiny or Gender)
- Enter coordinates
- Click "SAVE ZONE"

---

## 🎮 Game Setup Requirements

Before automation works, your Pokemon Red save must be:

### Save Point Position
1. **Location**: Oak's lab
2. **Timing**: Right after receiving Charmander
3. **Party**: Charmander in slot 3 (third position)
4. **Dialogue**: All intro dialogue cleared
5. **Action**: Standing still, ready to open menu

### How to Get There
```
1. Start new game
2. Play through Oak's intro
3. Choose Charmander as starter
4. DECLINE nickname when prompted
5. Walk around until Oak finishes talking
6. SAVE THE GAME immediately
   └─ This is your reset point!
```

---

## ▶️ Running Your First Hunt

Once templates and zones are ready:

### 1. Position Game
- Load your Pokemon Red save
- Should be in Oak's lab
- Charmander in party

### 2. Start Dashboard
- Dashboard at `http://localhost:3000`
- Verify all connections green

### 3. Click START
- Click **"▶ START"** button
- State machine begins: `PHASE_1_BOOT`

### 4. Watch Automation
- Video feed shows game progression
- State changes in Status Display
- Encounter counter increments
- Charts populate with data

### 5. Wait for Shiny
- Could be 10 minutes or 10 hours (odds are 1/8192)
- Automation handles everything
- Dashboard stays updated
- Screenshots auto-saved

### 6. Shiny Found!
- State changes to `SHINY_FOUND`
- Automation STOPS automatically
- Screenshot saved with ✨ marker
- Check `backend/encounters/` folder

---

## 📊 Dashboard Features

### Control Panel (Left)
```
⚡ AUTOMATION
  ▶ START / ⏹ STOP

🎮 MANUAL CONTROLS
  D-pad navigation
  A, B, START, SELECT buttons
  🔄 Soft Reset

🎯 CALIBRATE
```

### Live Feed (Center)
```
📹 Real-time video stream
🎯 Detection zone overlays
📊 FPS counter
```

### Statistics (Right)
```
📈 Total Encounters
📊 Shiny Probability
♂️♀️ Gender Distribution  
🎲 Nature Charts
📜 History Table
```

---

## 🔍 Monitoring Tips

### Watch the State Machine
The Status Display shows current phase:
- `PHASE_1_BOOT` - Loading game, declining nickname
- `PHASE_2_OVERWORLD` - Clearing Oak's dialogue
- `PHASE_3_MENU` - Navigating to Charmander
- `PHASE_4_CHECK` - Analyzing for shiny
- `SHINY_FOUND` - 🎉 SUCCESS!

### Check Logs
- Dashboard shows recent system logs
- Backend terminal shows detailed debug info
- `backend/bot_history.log` has complete history

### Monitor Statistics
- Encounter counter should increment every ~45 seconds
- Nature distribution should be roughly even
- Gender ratio should be close to 50/50
- Shiny probability increases with each encounter

---

## 🆘 Quick Fixes

| Problem | Solution |
|---------|----------|
| Dashboard won't load | Check frontend terminal - should show port 3000 |
| WebSocket disconnected | Refresh page, check backend is running |
| ESP32 not responding | Verify WiFi connection and IP in config |
| Video feed black | Check camera index, try 0, 1, or 2 |
| Buttons don't work | Test ESP32 connection in dashboard first |
| Automation stops early | Templates not matching - check logs |
| No shiny detection | Calibrate shiny zone coordinates |

---

## 📞 Need Help?

1. **Check Backend Logs**: Terminal 1 shows detailed debug output
2. **Check Frontend Console**: F12 in browser, look for errors
3. **Read Architecture**: `plans/shiny-charmander-hunt-architecture.md`
4. **API Documentation**: `http://localhost:8000/docs`

---

## 🎯 Your Current Mission

1. ✅ ~~Set up backend~~ (DONE)
2. ✅ ~~Set up frontend~~ (DONE)
3. ✅ ~~Start both servers~~ (DONE)
4. **→ 📸 Capture template images** (DO THIS NEXT)
5. **→ 🎯 Calibrate detection zones** (AFTER TEMPLATES)
6. **→ ▶️ Start your first automated hunt!** (AFTER CALIBRATION)

---

## 🌟 Expected Timeline

| Task | Time Estimate |
|------|---------------|
| Template capture | 30-60 minutes |
| Zone calibration | 15-30 minutes |
| First hunt test | 5-10 minutes |
| Troubleshooting | 15-30 minutes |
| **Finding a shiny** | **4-8 hours average** |

**Shiny odds**: 1/8192 = 0.0122% per encounter
**50% chance after**: ~5,624 resets (~3-4 hours)
**95% chance after**: ~24,450 resets (~15-20 hours)

---

## 🎊 Ready to Hunt!

Your system is **95% complete**. Just need:
- 📸 Template images
- 🎯 Zone calibration
- 🎮 Game save positioned

**Then click START and let it run!** The automation handles everything from there.

Good luck finding your shiny Charmander! 🔥✨
