# ESP32-S3 Firmware — ShinyStarter Controller

## Overview

This firmware turns the Xiao ESP32-S3 into a Nintendo Switch Pro Controller, controlled via WiFi commands from the ShinyStarter backend. It includes a **captive portal** for easy WiFi configuration — no code editing required.

## Features

- **WiFi Captive Portal**: First-time setup via web browser — no hardcoded credentials
- **NVS Credential Storage**: WiFi credentials persist across reboots and firmware updates
- **HTTP Server**: Receives button commands on port 80
- **Interactive Web UI**: NES-styled controller interface for manual testing
- **USB HID**: Emulates Switch Pro Controller via USB-C (NSGamepad/TinyUSB)
- **Mobile-Friendly**: Web UI works on phones and tablets

---

## 🚀 Flashing the Firmware

### Option A: Browser-Based (Recommended — No Tools Required)

1. Visit the **[ShinyStarter Installer](https://zard-labs.github.io/shiny-hunter)** page in Chrome or Edge
2. Connect your ESP32-S3 to this computer via USB-C
3. Click **"Install Firmware"** and select the serial port
4. Wait ~30 seconds for the flash to complete

> ⚠️ Requires a **USB-C data cable** (not charge-only) and **Google Chrome** or **Microsoft Edge**

### Option B: PlatformIO (For Developers)

```bash
# Install PlatformIO
pip install platformio

# Navigate to esp32 directory
cd esp32

# Compile and upload
platformio run --target upload

# Monitor serial output
platformio device monitor
```

---

## 📶 WiFi Setup (First Time)

After flashing, the ESP32 needs to know your home WiFi network:

1. **ESP32 creates a setup network**: Look for `ShinyStarter-Setup` in your WiFi list
2. **Connect to it** from your phone or laptop (open network, no password)
3. **A config page opens automatically** (or navigate to `http://192.168.4.1`)
4. **Select your home WiFi** from the scanned list and enter the password
5. **Click Save** — the ESP32 reboots and connects to your home network
6. **Note the IP address** from the serial monitor or your router's DHCP client list

### Reconfiguring WiFi

To change the WiFi network, visit `http://<ESP32_IP>/reset-wifi` in your browser. The ESP32 will clear its saved credentials and reboot into setup mode.

---

## 🎮 Using the Controller

### Hardware Setup

```
ESP32-S3 USB-C ────► Nintendo Switch (Controller Input)
ESP32-S3 WiFi  ◄──► PC/Backend (HTTP Commands)
```

1. After WiFi is configured, plug the ESP32-S3 into the Nintendo Switch via USB-C
2. The Switch should recognize it as a Pro Controller
3. The backend (or web UI) sends HTTP commands over WiFi to press buttons

### Web UI Testing

1. Open your browser and navigate to `http://<ESP32_IP>` (IP shown in serial monitor)
2. An interactive NES-styled controller interface appears
3. Click buttons to test — the Switch responds in real time

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Interactive controller web UI |
| `/button` | POST | Send button command (JSON: `{"cmd": 1}`) |
| `/status` | GET | Get controller status and connection info |
| `/reset-wifi` | GET | Clear WiFi credentials and reboot into setup mode |

### Button Command Codes

| Code | Button | Code | Button |
|------|--------|------|--------|
| `0x00` | Release All | `0x09` | PLUS (Start) |
| `0x01` | A | `0x0A` | MINUS (Select) |
| `0x02` | B | `0x0B` | HOME |
| `0x03` | X | `0x0C` | CAPTURE |
| `0x04` | Y | `0x10` | D-pad UP |
| `0x05` | L | `0x11` | D-pad DOWN |
| `0x06` | R | `0x12` | D-pad LEFT |
| `0x07` | ZL | `0x13` | D-pad RIGHT |
| `0x08` | ZR | `0x20` | RESET combo |

### Example: Send A Button Press

```bash
curl -X POST http://<ESP32_IP>/button \
  -H "Content-Type: application/json" \
  -d '{"cmd": 1}'
```

---

## 🔧 Troubleshooting

### Switch doesn't recognize controller

1. **Check USB cable** — must support data transfer (not charge-only)
2. **Replug** — disconnect and reconnect the USB-C cable
3. **Check serial output** — look for `USB HID Gamepad initialized` message

### Can't connect to ShinyStarter-Setup WiFi

1. The ESP32 only broadcasts this network when it has **no saved WiFi credentials**
2. If it connected to a network already, use `/reset-wifi` to clear credentials
3. Try pressing the **reset button** on the ESP32 board

### WiFi connects but can't reach the ESP32

1. Check the IP address in the serial monitor
2. Ensure your PC/phone is on the **same network** as the ESP32
3. Try pinging the IP: `ping <ESP32_IP>`
4. Check your router's firewall settings

### Commands not working

1. **Test status**: `curl http://<ESP32_IP>/status`
2. **Check serial monitor** for command logs
3. Ensure the Switch recognizes the controller before sending commands

---

## 📋 Technical Details

### Hardware: XIAO-ESP32-S3

| Spec | Value |
|------|-------|
| **MCU** | ESP32-S3 (Xtensa Dual-Core 240MHz) |
| **RAM** | 512KB SRAM + 2MB PSRAM |
| **Flash** | 8MB |
| **WiFi** | 802.11 b/g/n (2.4GHz) |
| **USB** | Native USB OTG (TinyUSB) |
| **Size** | 21 × 17.5 mm |

### Dependencies

- **ArduinoJson** — HTTP request parsing
- **switch_ESP32 (NSGamepad)** — Nintendo Switch Pro Controller HID emulation
- **Preferences** — NVS flash storage for WiFi credentials (built-in)
- **DNSServer** — Captive portal DNS redirect (built-in)

### Build Flags

```ini
-DBOARD_HAS_NATIVE_USB
-DARDUINO_USB_MODE=1
-DARDUINO_USB_CDC_ON_BOOT=1
```

---

## License

MIT License
