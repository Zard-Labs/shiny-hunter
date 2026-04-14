/**
 * ESP32-S3 Firmware for Nintendo Switch Pro Controller Emulation
 *
 * Features:
 * - WiFi Station mode with captive portal for first-time setup
 * - Credentials saved to NVS flash (persist across reboots/reflashes)
 * - HTTP server for command reception and web UI
 * - Interactive web UI for manual testing
 * - USB HID emulation as Switch Pro Controller
 *
 * Hardware: Xiao ESP32-S3
 * Connection: USB-C to Nintendo Switch (controller), WiFi to home network (commands)
 *
 * First Boot:
 *   1. ESP32 creates "ShinyStarter-Setup" WiFi network
 *   2. Connect to it, browser opens config page automatically
 *   3. Select your home WiFi and enter password
 *   4. ESP32 saves credentials and reboots into Station mode
 */

#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <ESPmDNS.h>
#include <Preferences.h>
#include <ArduinoJson.h>
#include "switch_ESP32.h"

// ==================== Configuration ====================
#define AP_SSID          "ShinyStarter-Setup"
#define AP_PASSWORD      ""                    // Open network for easy setup
#define MDNS_HOSTNAME    "shinystarter"        // Reachable at shinystarter.local
#define WIFI_CONNECT_TIMEOUT_MS  15000         // 15 seconds to connect
#define WIFI_RECONNECT_INTERVAL  10000         // Check every 10 seconds
#define DNS_PORT         53
#define HTTP_PORT        80

// ==================== Global Objects ====================
WebServer server(HTTP_PORT);
DNSServer dnsServer;
Preferences preferences;
NSGamepad Gamepad;

bool apMode = false;         // true = captive portal mode, false = normal station mode
String savedSSID = "";
String savedPassword = "";

// Auto-release timer — allows precise local timing instead of WiFi round-trip timing
volatile bool pendingRelease = false;
unsigned long releaseTime = 0;

// ==================== Forward Declarations ====================
void handleConfigPage();
void handleScanNetworks();
void handleConfigSave();
void handleButtonRequest();
void handleStatus();
void handleResetWiFi();
void handleRoot();

// ==================== Button Commands ====================
#define CMD_RELEASE     0x00
#define CMD_BTN_A       0x01
#define CMD_BTN_B       0x02
#define CMD_BTN_X       0x03
#define CMD_BTN_Y       0x04
#define CMD_BTN_L       0x05
#define CMD_BTN_R       0x06
#define CMD_BTN_ZL      0x07
#define CMD_BTN_ZR      0x08
#define CMD_BTN_PLUS    0x09
#define CMD_BTN_MINUS   0x0A
#define CMD_BTN_HOME    0x0B
#define CMD_BTN_CAPTURE 0x0C
#define CMD_DPAD_UP     0x10
#define CMD_DPAD_DOWN   0x11
#define CMD_DPAD_LEFT   0x12
#define CMD_DPAD_RIGHT  0x13
#define CMD_RESET       0x20

// ==================== WiFi Credential Storage ====================

String loadSSID() {
    preferences.begin("wifi", true);  // read-only
    String ssid = preferences.getString("ssid", "");
    preferences.end();
    return ssid;
}

String loadPassword() {
    preferences.begin("wifi", true);  // read-only
    String pass = preferences.getString("password", "");
    preferences.end();
    return pass;
}

void saveCredentials(const String& ssid, const String& password) {
    preferences.begin("wifi", false);  // read-write
    preferences.putString("ssid", ssid);
    preferences.putString("password", password);
    preferences.end();
    Serial.printf("Credentials saved for SSID: %s\n", ssid.c_str());
}

void clearCredentials() {
    preferences.begin("wifi", false);
    preferences.clear();
    preferences.end();
    Serial.println("WiFi credentials cleared from NVS");
}

// ==================== WiFi Connection ====================

bool connectToWiFi(const String& ssid, const String& password) {
    Serial.printf("Connecting to WiFi: %s", ssid.c_str());
    
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid.c_str(), password.c_str());
    
    unsigned long startTime = millis();
    while (WiFi.status() != WL_CONNECTED && (millis() - startTime) < WIFI_CONNECT_TIMEOUT_MS) {
        delay(500);
        Serial.print(".");
    }
    
    if (WiFi.status() == WL_CONNECTED) {
        IPAddress IP = WiFi.localIP();
        Serial.println("\n[OK] WiFi connected!");
        Serial.printf("   SSID: %s\n", ssid.c_str());
        Serial.printf("   IP Address: %s\n", IP.toString().c_str());
        Serial.printf("   Signal Strength: %d dBm\n", WiFi.RSSI());
        
        // Start mDNS responder so device is reachable at shinystarter.local
        if (MDNS.begin(MDNS_HOSTNAME)) {
            MDNS.addService("http", "tcp", HTTP_PORT);
            Serial.printf("   mDNS: http://%s.local\n", MDNS_HOSTNAME);
        } else {
            Serial.println("   [WARN] mDNS failed to start");
        }
        
        return true;
    } else {
        Serial.println("\n[FAIL] WiFi connection failed");
        Serial.println("   Starting captive portal for reconfiguration...");
        WiFi.disconnect();
        return false;
    }
}

// ==================== Captive Portal ====================

String scanNetworksJSON() {
    int n = WiFi.scanNetworks();
    String json = "[";
    for (int i = 0; i < n; i++) {
        if (i > 0) json += ",";
        json += "{\"ssid\":\"" + WiFi.SSID(i) + "\",\"rssi\":" + String(WiFi.RSSI(i)) + ",\"enc\":" + String(WiFi.encryptionType(i) != WIFI_AUTH_OPEN) + "}";
    }
    json += "]";
    WiFi.scanDelete();
    return json;
}

void startCaptivePortal() {
    apMode = true;
    
    WiFi.mode(WIFI_AP);
    WiFi.softAP(AP_SSID, AP_PASSWORD);
    
    IPAddress apIP = WiFi.softAPIP();
    Serial.println("\n========================================");
    Serial.println("  CAPTIVE PORTAL MODE");
    Serial.println("========================================");
    Serial.printf("  WiFi Network: %s\n", AP_SSID);
    Serial.printf("  Config URL:   http://%s\n", apIP.toString().c_str());
    Serial.println("========================================\n");
    
    // DNS server redirects all domains to our IP (captive portal)
    dnsServer.start(DNS_PORT, "*", apIP);
    
    // Serve the config page on all routes
    server.on("/", handleConfigPage);
    server.on("/scan", handleScanNetworks);
    server.on("/save", HTTP_POST, handleConfigSave);
    server.on("/generate_204", handleConfigPage);    // Android captive portal detection
    server.on("/fwlink", handleConfigPage);           // Windows captive portal detection
    server.on("/hotspot-detect.html", handleConfigPage); // iOS captive portal detection
    server.onNotFound(handleConfigPage);              // Catch-all
    
    server.begin();
    Serial.println("[OK] Captive portal HTTP server started");
}

void handleScanNetworks() {
    String json = scanNetworksJSON();
    server.send(200, "application/json", json);
}

void handleConfigSave() {
    String newSSID = server.arg("ssid");
    String newPassword = server.arg("password");
    
    if (newSSID.length() == 0) {
        server.send(400, "text/plain", "SSID is required");
        return;
    }
    
    // Save credentials
    saveCredentials(newSSID, newPassword);
    
    // Send success response
    String html = R"rawliteral(
<!DOCTYPE html><html><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ShinyStarter - Saved!</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Courier New',monospace;background:#1a1a1a;color:#f8f8f8;display:flex;justify-content:center;align-items:center;min-height:100vh;padding:20px}
.card{background:#3a3a3a;border:4px solid #5a5a5a;border-radius:8px;padding:30px;max-width:400px;width:100%;text-align:center}
h1{color:#d92626;font-size:24px;margin-bottom:20px}
p{color:#b0b0b0;margin-bottom:10px;font-size:14px}
.ok{color:#4caf50;font-size:18px;font-weight:bold}
</style></head><body>
<div class="card">
<h1>✓ SAVED!</h1>
<p class="ok">WiFi credentials saved successfully.</p>
<p>Rebooting in 3 seconds...</p>
<p>After reboot, connect to your home WiFi and find the ESP32 IP in your router's DHCP client list or serial monitor.</p>
</div></body></html>
)rawliteral";
    
    server.send(200, "text/html", html);
    
    // Reboot after a short delay to let the response be sent
    delay(3000);
    ESP.restart();
}

void handleConfigPage() {
    // Scan networks in the background
    String networks = scanNetworksJSON();
    
    String html = R"rawliteral(
<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>ShinyStarter - WiFi Setup</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Courier New',monospace;background:#1a1a1a;background-image:repeating-linear-gradient(0deg,rgba(0,0,0,.15),rgba(0,0,0,.15) 1px,transparent 1px,transparent 2px);min-height:100vh;display:flex;justify-content:center;align-items:center;padding:20px}
.card{background:#8b8b8b;border:4px solid #3a3a3a;border-radius:8px;box-shadow:inset 0 0 0 3px #5a5a5a,inset 0 0 0 6px #b0b0b0,0 8px 0 #3a3a3a,0 12px 30px rgba(0,0,0,.7);padding:30px;max-width:480px;width:100%}
h1{text-align:center;color:#f8f8f8;font-size:20px;text-transform:uppercase;letter-spacing:2px;text-shadow:3px 3px 0 #3a3a3a;margin-bottom:8px}
.subtitle{text-align:center;color:#3a3a3a;font-size:12px;margin-bottom:20px;text-transform:uppercase;letter-spacing:1px}
label{display:block;color:#f8f8f8;font-size:12px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;text-shadow:1px 1px 0 #3a3a3a}
select,input[type=password],input[type=text]{width:100%;padding:12px;font-family:'Courier New',monospace;font-size:14px;border:3px solid #3a3a3a;border-radius:4px;background:#f8f8f8;color:#1a1a1a;margin-bottom:16px;box-shadow:inset 0 2px 4px rgba(0,0,0,.3)}
select{cursor:pointer}
.btn{width:100%;padding:14px;font-family:'Courier New',monospace;font-size:16px;font-weight:bold;text-transform:uppercase;letter-spacing:2px;border:3px solid #3a3a3a;border-radius:4px;cursor:pointer;box-shadow:0 4px 0 #a01010,0 6px 8px rgba(0,0,0,.5);background:#d92626;color:#f8f8f8;transition:all .1s}
.btn:active{transform:translateY(4px);box-shadow:none}
.btn-scan{background:#5a5a5a;box-shadow:0 4px 0 #3a3a3a,0 6px 8px rgba(0,0,0,.5);margin-bottom:16px;font-size:12px;padding:10px}
.info{background:#3a3a3a;border:2px solid #5a5a5a;padding:12px;margin-bottom:20px;font-size:11px;color:#b0b0b0;text-align:center}
.network-list{max-height:200px;overflow-y:auto;margin-bottom:16px}
.network{padding:10px;background:#5a5a5a;border:2px solid #3a3a3a;margin-bottom:4px;cursor:pointer;color:#f8f8f8;font-size:13px;display:flex;justify-content:space-between;align-items:center}
.network:hover{background:#8b5a9e}
.signal{font-size:11px;color:#b0b0b0}
.custom-ssid{display:none;margin-bottom:16px}
.toggle{color:#d92626;cursor:pointer;font-size:11px;text-align:center;margin-bottom:16px;text-decoration:underline}
</style></head><body>
<div class="card">
<h1>🎮 SHINYSTARTER</h1>
<div class="subtitle">WiFi Configuration</div>
<div class="info">Select your home WiFi network below.<br>The ESP32 will connect and be ready for commands.</div>
<form id="wifiForm" method="POST" action="/save">
<label>WiFi Network</label>
<div id="networkList" class="network-list"></div>
<input type="hidden" name="ssid" id="ssidInput">
<div class="toggle" onclick="toggleCustom()">✎ Enter SSID manually</div>
<div class="custom-ssid" id="customSSID">
<input type="text" name="custom_ssid" id="customSSIDInput" placeholder="Enter SSID...">
</div>
<label>Password</label>
<input type="password" name="password" id="passwordInput" placeholder="Enter WiFi password...">
<button type="button" class="btn btn-scan" onclick="rescan()">↻ RESCAN NETWORKS</button>
<button type="submit" class="btn">SAVE & CONNECT</button>
</form>
</div>
<script>
var networks=)rawliteral" + networks + R"rawliteral(;
var selectedSSID='';
function renderNetworks(nets){
  var el=document.getElementById('networkList');
  el.innerHTML='';
  nets.sort(function(a,b){return b.rssi-a.rssi});
  nets.forEach(function(n){
    var d=document.createElement('div');
    d.className='network';
    var bars=n.rssi>-50?'████':n.rssi>-60?'███░':n.rssi>-70?'██░░':'█░░░';
    d.innerHTML='<span>'+(n.enc?'🔒 ':'')+n.ssid+'</span><span class="signal">'+bars+' '+n.rssi+'dBm</span>';
    d.onclick=function(){selectNetwork(n.ssid)};
    el.appendChild(d);
  });
}
function selectNetwork(ssid){
  selectedSSID=ssid;
  document.getElementById('ssidInput').value=ssid;
  document.querySelectorAll('.network').forEach(function(el){el.style.background='#5a5a5a'});
  event.currentTarget.style.background='#8b5a9e';
}
function toggleCustom(){
  var el=document.getElementById('customSSID');
  el.style.display=el.style.display==='block'?'none':'block';
}
function rescan(){
  fetch('/scan').then(function(r){return r.json()}).then(function(n){networks=n;renderNetworks(n)});
}
document.getElementById('wifiForm').onsubmit=function(e){
  var custom=document.getElementById('customSSIDInput').value;
  if(custom){document.getElementById('ssidInput').value=custom}
  if(!document.getElementById('ssidInput').value){e.preventDefault();alert('Please select or enter a WiFi network')}
};
renderNetworks(networks);
</script></body></html>
)rawliteral";
    
    server.send(200, "text/html", html);
}

// ==================== Button Command Handler ====================

void handleButtonCommand(uint8_t cmd) {
    Gamepad.releaseAll();
    
    // Center analog sticks (0x80 = 128 = neutral position for NSGamepad)
    Gamepad.leftXAxis(0x80);
    Gamepad.leftYAxis(0x80);
    Gamepad.rightXAxis(0x80);
    Gamepad.rightYAxis(0x80);
    
    // Center D-pad
    Gamepad.dPad(NSGAMEPAD_DPAD_CENTERED);
    
    switch (cmd) {
        case CMD_RELEASE:
            break;
        case CMD_BTN_A:
            Gamepad.press(NSButton_A);
            break;
        case CMD_BTN_B:
            Gamepad.press(NSButton_B);
            break;
        case CMD_BTN_X:
            Gamepad.press(NSButton_X);
            break;
        case CMD_BTN_Y:
            Gamepad.press(NSButton_Y);
            break;
        case CMD_BTN_L:
            Gamepad.press(NSButton_LeftTrigger);
            break;
        case CMD_BTN_R:
            Gamepad.press(NSButton_RightTrigger);
            break;
        case CMD_BTN_ZL:
            Gamepad.press(NSButton_LeftThrottle);
            break;
        case CMD_BTN_ZR:
            Gamepad.press(NSButton_RightThrottle);
            break;
        case CMD_BTN_MINUS:
            Gamepad.press(NSButton_Minus);
            break;
        case CMD_BTN_PLUS:
            Gamepad.press(NSButton_Plus);
            break;
        case CMD_BTN_HOME:
            Gamepad.press(NSButton_Home);
            break;
        case CMD_BTN_CAPTURE:
            Gamepad.press(NSButton_Capture);
            break;
        case CMD_DPAD_UP:
            Gamepad.dPad(NSGAMEPAD_DPAD_UP);
            break;
        case CMD_DPAD_RIGHT:
            Gamepad.dPad(NSGAMEPAD_DPAD_RIGHT);
            break;
        case CMD_DPAD_DOWN:
            Gamepad.dPad(NSGAMEPAD_DPAD_DOWN);
            break;
        case CMD_DPAD_LEFT:
            Gamepad.dPad(NSGAMEPAD_DPAD_LEFT);
            break;
        case CMD_RESET:
            Gamepad.press(NSButton_A);
            Gamepad.press(NSButton_B);
            Gamepad.press(NSButton_Minus);
            Gamepad.press(NSButton_Plus);
            break;
    }
    
    // CRITICAL: Send the HID report to the Switch
    Gamepad.loop();
}

// ==================== HTTP Endpoints (Normal Mode) ====================

void handleButtonRequest() {
    if (server.method() != HTTP_POST) {
        server.send(405, "text/plain", "Method Not Allowed");
        return;
    }
    
    String body = server.arg("plain");
    JsonDocument doc;
    DeserializationError error = deserializeJson(doc, body);
    
    if (error) {
        server.send(400, "text/plain", "Invalid JSON");
        return;
    }
    
    uint8_t cmd = doc["cmd"];
    uint16_t duration = doc["duration_ms"] | 0;  // 0 = no auto-release (backward compatible)
    
    handleButtonCommand(cmd);
    
    // If duration specified and not a release command, schedule auto-release
    if (duration > 0 && cmd != CMD_RELEASE) {
        pendingRelease = true;
        releaseTime = millis() + duration;
        Serial.printf("Button command received: 0x%02X (auto-release in %ums)\n", cmd, duration);
    } else {
        pendingRelease = false;
        Serial.printf("Button command received: 0x%02X\n", cmd);
    }
    
    server.send(200, "application/json", "{\"status\":\"ok\"}");
}

void handleStatus() {
    String mode = apMode ? "setup" : "usb_hid";
    String ip = apMode ? WiFi.softAPIP().toString() : WiFi.localIP().toString();
    String json = "{\"status\":\"ok\",\"connected\":" + String(WiFi.status() == WL_CONNECTED ? "true" : "false") + ",\"mode\":\"" + mode + "\",\"ip\":\"" + ip + "\"}";
    server.send(200, "application/json", json);
}

void handleResetWiFi() {
    clearCredentials();
    
    String html = R"rawliteral(
<!DOCTYPE html><html><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ShinyStarter - Reset</title>
<style>
body{font-family:'Courier New',monospace;background:#1a1a1a;color:#f8f8f8;display:flex;justify-content:center;align-items:center;min-height:100vh}
.card{background:#3a3a3a;border:4px solid #5a5a5a;border-radius:8px;padding:30px;max-width:400px;text-align:center}
h1{color:#d92626;margin-bottom:20px}
p{color:#b0b0b0;margin-bottom:10px}
</style></head><body>
<div class="card">
<h1>WiFi Reset</h1>
<p>Credentials cleared. Rebooting into setup mode...</p>
<p>Connect to <strong>ShinyStarter-Setup</strong> WiFi to reconfigure.</p>
</div></body></html>
)rawliteral";
    
    server.send(200, "text/html", html);
    delay(2000);
    ESP.restart();
}

// Controller Web UI (served in normal station mode)
void handleRoot() {
    String html = R"rawliteral(
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="mobile-web-app-capable" content="yes">
    <title>ESP32-S3 Controller</title>
    <style>
        *{margin:0;padding:0;box-sizing:border-box}
        :root{--nes-gray:#8b8b8b;--nes-dark-gray:#5a5a5a;--nes-darker-gray:#3a3a3a;--nes-light-gray:#b0b0b0;--nes-red:#d92626;--nes-dark-red:#a01010;--nes-white:#f8f8f8;--nes-black:#1a1a1a;--nes-purple:#8b5a9e;--spacing-xs:8px;--spacing-sm:12px;--spacing-md:16px;--spacing-lg:20px;--touch-target-min:44px;--touch-target-large:70px}
        body{font-family:'Courier New',monospace;background:var(--nes-black);background-image:repeating-linear-gradient(0deg,rgba(0,0,0,.15),rgba(0,0,0,.15) 1px,transparent 1px,transparent 2px);min-height:100vh;display:flex;justify-content:center;align-items:center;padding:var(--spacing-md);overflow-x:hidden}
        .container{background:var(--nes-gray);border-radius:8px;box-shadow:inset 0 0 0 3px var(--nes-dark-gray),inset 0 0 0 6px var(--nes-light-gray),0 8px 0 var(--nes-darker-gray),0 12px 30px rgba(0,0,0,.7);padding:var(--spacing-lg);max-width:600px;width:100%;border:4px solid var(--nes-darker-gray)}
        h1{text-align:center;color:var(--nes-white);margin-bottom:var(--spacing-sm);font-size:clamp(16px,4vw,20px);text-transform:uppercase;letter-spacing:2px;text-shadow:3px 3px 0 var(--nes-darker-gray);font-weight:bold}
        .status{text-align:center;padding:var(--spacing-sm);background:var(--nes-darker-gray);margin-bottom:var(--spacing-md);display:flex;flex-wrap:wrap;justify-content:center;gap:var(--spacing-sm);border:2px solid var(--nes-dark-gray);box-shadow:inset 0 2px 4px rgba(0,0,0,.5)}
        .status-item{color:var(--nes-light-gray);font-size:11px;text-transform:uppercase}
        .status-online{color:var(--nes-red);font-weight:bold}
        .controller{background:var(--nes-dark-gray);padding:var(--spacing-md);margin-bottom:var(--spacing-md);border:3px solid var(--nes-darker-gray);box-shadow:inset 0 0 0 2px var(--nes-gray),inset 0 4px 8px rgba(0,0,0,.4)}
        .control-section{margin-bottom:var(--spacing-lg)}
        .section-label{text-align:center;color:var(--nes-red);font-size:10px;text-transform:uppercase;letter-spacing:2px;margin-bottom:var(--spacing-xs);font-weight:bold;text-shadow:1px 1px 0 var(--nes-black)}
        .button-row{display:flex;justify-content:center;align-items:center;gap:var(--spacing-sm);flex-wrap:wrap}
        button{padding:var(--spacing-sm) var(--spacing-lg);border:3px solid var(--nes-darker-gray);border-radius:4px;font-size:14px;font-weight:bold;cursor:pointer;transition:all .1s ease;background:var(--nes-light-gray);color:var(--nes-darker-gray);box-shadow:0 4px 0 var(--nes-darker-gray),0 6px 8px rgba(0,0,0,.5);min-width:var(--touch-target-min);min-height:var(--touch-target-min);user-select:none;-webkit-tap-highlight-color:transparent;touch-action:manipulation;display:inline-flex;align-items:center;justify-content:center;text-transform:uppercase;letter-spacing:1px;font-family:'Courier New',monospace}
        button:active{transform:translateY(4px);box-shadow:0 0 0 var(--nes-darker-gray),0 2px 4px rgba(0,0,0,.5)}
        .btn-system{background:var(--nes-purple);color:var(--nes-white);font-size:12px;min-width:70px;padding:10px 16px}
        .dpad-container{display:grid;grid-template-areas:". up ." "left center right" ". down .";gap:4px;width:fit-content;margin:0 auto;padding:var(--spacing-md);background:var(--nes-darker-gray);border:3px solid var(--nes-black);box-shadow:inset 0 2px 6px rgba(0,0,0,.6)}
        .btn-dpad{width:var(--touch-target-large);height:var(--touch-target-large);padding:0;font-size:24px;background:var(--nes-dark-gray);color:var(--nes-white);border:3px solid var(--nes-black);border-radius:0}
        .btn-dpad.up{grid-area:up}.btn-dpad.down{grid-area:down}.btn-dpad.left{grid-area:left}.btn-dpad.right{grid-area:right}
        .dpad-center{grid-area:center;width:var(--touch-target-large);height:var(--touch-target-large)}
        .action-buttons{display:grid;grid-template-areas:". y ." "x . a" ". b .";gap:var(--spacing-sm);width:fit-content;margin:0 auto;padding:var(--spacing-md);background:var(--nes-darker-gray);border:3px solid var(--nes-black)}
        .btn-action{border-radius:50%;width:80px;height:80px;padding:0;font-size:24px;font-weight:bold;box-shadow:0 6px 0 var(--nes-darker-gray),0 8px 8px rgba(0,0,0,.6);border:4px solid var(--nes-black)}
        .btn-action.a{grid-area:a;background:var(--nes-red);color:var(--nes-white)}
        .btn-action.b{grid-area:b;background:var(--nes-red);color:var(--nes-white)}
        .btn-action.x{grid-area:x;background:var(--nes-light-gray);color:var(--nes-darker-gray)}
        .btn-action.y{grid-area:y;background:var(--nes-light-gray);color:var(--nes-darker-gray)}
        .action-center{grid-area:center;width:80px;height:80px}
        .shoulder-buttons{display:grid;grid-template-columns:repeat(4,1fr);gap:var(--spacing-xs);margin-bottom:var(--spacing-md)}
        .btn-shoulder{min-width:unset;padding:var(--spacing-sm);font-size:12px;background:var(--nes-dark-gray);color:var(--nes-white);border:3px solid var(--nes-black)}
        .btn-reset{width:100%;background:var(--nes-red);color:var(--nes-white);padding:var(--spacing-md);font-size:14px;box-shadow:0 5px 0 var(--nes-dark-red),0 7px 8px rgba(0,0,0,.6);border:3px solid var(--nes-darker-gray)}
        .btn-release{width:100%;background:var(--nes-darker-gray);color:var(--nes-white);box-shadow:0 4px 0 var(--nes-black),0 6px 8px rgba(0,0,0,.5);border:3px solid var(--nes-black)}
        .feedback{text-align:center;margin-top:var(--spacing-md);padding:var(--spacing-sm);font-weight:bold;font-size:11px;display:none;text-transform:uppercase;letter-spacing:1px;border:2px solid}
        .feedback.success{background:var(--nes-darker-gray);color:var(--nes-white);border-color:var(--nes-red);display:block}
        .feedback.error{background:var(--nes-red);color:var(--nes-white);border-color:var(--nes-dark-red);display:block}
        @media(max-width:640px){body{padding:var(--spacing-xs)}.container{padding:var(--spacing-md);border-radius:4px}.btn-action{width:70px;height:70px;font-size:18px}.action-center{width:70px;height:70px}.btn-dpad{width:60px;height:60px;font-size:20px}.dpad-center{width:60px;height:60px}.status{font-size:12px;flex-direction:column;gap:var(--spacing-xs)}}
        @media(max-width:480px){.container{padding:var(--spacing-sm)}.controller{padding:var(--spacing-sm)}.btn-system{font-size:12px;min-width:60px;padding:8px 12px}button{font-size:14px}}
        @media(max-width:896px)and (orientation:landscape){body{padding:var(--spacing-xs)}.container{max-width:100%;display:grid;grid-template-columns:1fr 1fr;gap:var(--spacing-md)}h1,.status{grid-column:1/-1}.control-section:has(.dpad-container){grid-column:1}.control-section:has(.action-buttons){grid-column:2}.control-section:has(.btn-reset),.control-section:has(.btn-release){grid-column:1/-1}}
        @media(hover:none)and (pointer:coarse){button{font-size:16px}}
        @supports(padding:env(safe-area-inset-top)){.container{padding:max(var(--spacing-lg),env(safe-area-inset-top)) max(var(--spacing-lg),env(safe-area-inset-right)) max(var(--spacing-lg),env(safe-area-inset-bottom)) max(var(--spacing-lg),env(safe-area-inset-left))}}
    </style>
</head>
<body>
<div class="container">
<h1>🎮 SHINYSTARTER CONTROLLER</h1>
<div class="status">
<div class="status-item status-online">● ONLINE</div>
<div class="status-item">IP: )rawliteral" + WiFi.localIP().toString() + R"rawliteral(</div>
<div class="status-item">MODE: USB HID</div>
</div>
<div class="controller">
<div class="control-section">
<div class="section-label">SYSTEM</div>
<div class="button-row">
<button onclick="sendCommand(0x0A,'MINUS')" class="btn-system">−</button>
<button onclick="sendCommand(0x0B,'HOME')" class="btn-system">🏠</button>
<button onclick="sendCommand(0x09,'PLUS')" class="btn-system">+</button>
<button onclick="sendCommand(0x0C,'CAPTURE')" class="btn-system">📷</button>
</div>
</div>
<div class="control-section">
<div class="section-label">SHOULDERS</div>
<div class="shoulder-buttons">
<button onclick="sendCommand(0x05,'L')" class="btn-shoulder">L</button>
<button onclick="sendCommand(0x07,'ZL')" class="btn-shoulder">ZL</button>
<button onclick="sendCommand(0x08,'ZR')" class="btn-shoulder">ZR</button>
<button onclick="sendCommand(0x06,'R')" class="btn-shoulder">R</button>
</div>
</div>
<div class="control-section">
<div class="section-label">D-PAD</div>
<div class="dpad-container">
<button onclick="sendCommand(0x10,'UP')" class="btn-dpad up">↑</button>
<button onclick="sendCommand(0x12,'LEFT')" class="btn-dpad left">←</button>
<div class="dpad-center"></div>
<button onclick="sendCommand(0x13,'RIGHT')" class="btn-dpad right">→</button>
<button onclick="sendCommand(0x11,'DOWN')" class="btn-dpad down">↓</button>
</div>
</div>
<div class="control-section">
<div class="section-label">ACTIONS</div>
<div class="action-buttons">
<button onclick="sendCommand(0x04,'Y')" class="btn-action y">Y</button>
<button onclick="sendCommand(0x03,'X')" class="btn-action x">X</button>
<div class="action-center"></div>
<button onclick="sendCommand(0x01,'A')" class="btn-action a">A</button>
<button onclick="sendCommand(0x02,'B')" class="btn-action b">B</button>
</div>
</div>
<div class="control-section">
<div class="button-row">
<button onclick="sendCommand(0x20,'RESET')" class="btn-reset">🔄 RESET COMBO</button>
</div>
</div>
<div class="control-section" style="margin-bottom:0">
<div class="button-row">
<button onclick="sendCommand(0x00,'RELEASE')" class="btn-release">RELEASE ALL</button>
</div>
</div>
</div>
<div id="feedback" class="feedback"></div>
</div>
<script>
async function sendCommand(cmd,name,dur){const f=document.getElementById('feedback');const payload={cmd:cmd};if(cmd!==0x00){payload.duration_ms=dur||100}try{const r=await fetch('/button',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});if(r.ok){f.className='feedback success';f.textContent='✓ '+name+' (0x'+cmd.toString(16).toUpperCase().padStart(2,'0')+')';setTimeout(()=>f.style.display='none',2000)}else throw new Error('Failed')}catch(e){f.className='feedback error';f.textContent='✗ COMMAND FAILED';setTimeout(()=>f.style.display='none',3000)}}
document.addEventListener('contextmenu',function(e){if(e.target.tagName==='BUTTON')e.preventDefault()});
</script>
</body>
</html>
)rawliteral";

    server.send(200, "text/html", html);
}

// ==================== Normal Mode Server Setup ====================

void setupNormalServer() {
    server.on("/", handleRoot);
    server.on("/button", handleButtonRequest);
    server.on("/status", handleStatus);
    server.on("/reset-wifi", handleResetWiFi);
    
    server.begin();
    Serial.println("[OK] HTTP server started on port 80");
}

// ==================== Setup ====================

void setup() {
    Serial.begin(115200);
    delay(1000);
    
    Serial.println("\n\n========================================");
    Serial.println("  ShinyStarter Controller v1.0");
    Serial.println("========================================\n");
    
    // Initialize USB HID Gamepad
    Gamepad.begin();
    USB.begin();
    Serial.println("[OK] USB HID Gamepad initialized (NSGamepad)");
    
    // Load saved WiFi credentials from NVS
    savedSSID = loadSSID();
    savedPassword = loadPassword();
    
    if (savedSSID.length() > 0) {
        Serial.printf("[INFO] Found saved WiFi: %s\n", savedSSID.c_str());
        
        // Attempt to connect to saved WiFi
        if (connectToWiFi(savedSSID, savedPassword)) {
            // Success — start normal controller server
            setupNormalServer();
        } else {
            // Failed — fall back to captive portal
            startCaptivePortal();
        }
    } else {
        Serial.println("[INFO] No saved WiFi credentials found");
        startCaptivePortal();
    }
    
    Serial.println("\n========================================");
    if (apMode) {
        Serial.printf("  Setup Mode: Connect to '%s' WiFi\n", AP_SSID);
    } else {
        Serial.println("  System Ready! Waiting for commands...");
    }
    Serial.println("========================================\n");
}

// ==================== Main Loop ====================

void loop() {
    if (apMode) {
        // Captive portal mode — process DNS redirects
        dnsServer.processNextRequest();
    } else {
        // Normal mode — check WiFi connection periodically
        static unsigned long lastCheck = 0;
        if (millis() - lastCheck > WIFI_RECONNECT_INTERVAL) {
            if (WiFi.status() != WL_CONNECTED) {
                Serial.println("[WARN] WiFi disconnected, reconnecting...");
                WiFi.reconnect();
            }
            lastCheck = millis();
        }
    }
    
    // Auto-release timer — precise local timing for button presses
    if (pendingRelease && millis() >= releaseTime) {
        handleButtonCommand(CMD_RELEASE);
        pendingRelease = false;
    }
    
    // Handle HTTP requests (both modes)
    server.handleClient();
}
