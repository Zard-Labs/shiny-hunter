"""ESP32-S3 communication manager for WiFi/UART commands."""
import requests
import serial
import asyncio
import time
from typing import Optional
from app.config import settings
from app.utils.command_builder import build_command, get_button_name
from app.utils.logger import logger


class ESP32Manager:
    """
    Manager for communicating with ESP32-S3.
    Supports both WiFi (HTTP) and UART (Serial) communication modes.
    """
    
    def __init__(self):
        self.mode = settings.communication_mode
        self.connected = False
        self.serial_port: Optional[serial.Serial] = None
        
        if self.mode == "wifi":
            self.base_url = f"http://{settings.esp32_ip}:{settings.esp32_port}"
            logger.info(f"ESP32 Manager initialized in WiFi mode: {self.base_url}")
        else:
            logger.info(f"ESP32 Manager initialized in UART mode: {settings.serial_port}")
    
    def connect(self) -> bool:
        """
        Establish connection to ESP32-S3.
        
        Returns:
            True if connected successfully, False otherwise
        """
        try:
            if self.mode == "wifi":
                # Test connection with status request
                response = requests.get(f"{self.base_url}/status", timeout=2)
                if response.status_code == 200:
                    self.connected = True
                    logger.info("[OK] Connected to ESP32-S3 via WiFi")
                    return True
                else:
                    logger.error(f"ESP32-S3 returned status {response.status_code}")
                    return False
            
            else:  # UART mode
                self.serial_port = serial.Serial(
                    settings.serial_port,
                    settings.baud_rate,
                    timeout=1
                )
                time.sleep(0.5)  # Allow port to stabilize
                self.connected = True
                logger.info(f"[OK] Connected to ESP32-S3 via UART on {settings.serial_port}")
                return True
        
        except Exception as e:
            logger.error(f"Failed to connect to ESP32-S3: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Disconnect from ESP32-S3."""
        if self.mode == "uart" and self.serial_port:
            self.serial_port.close()
            self.serial_port = None
        self.connected = False
        logger.info("Disconnected from ESP32-S3")
    
    def send_button(self, button: str, hold: float = None, wait: float = None) -> bool:
        """
        Send button command to ESP32-S3.
        
        Args:
            button: Button name (e.g., 'A', 'START', 'UP')
            hold: Button hold duration in seconds (uses config default if None)
            wait: Wait after release in seconds (uses config default if None)
        
        Returns:
            True if command sent successfully, False otherwise
        """
        if not self.connected:
            logger.warning("Not connected to ESP32-S3")
            return False
        
        hold_duration = hold if hold is not None else settings.button_hold_duration
        wait_duration = wait if wait is not None else settings.button_release_delay
        
        try:
            cmd = build_command(button)
            
            if self.mode == "wifi":
                # Send button press
                response = requests.post(
                    f"{self.base_url}/button",
                    json={"cmd": cmd},
                    timeout=1
                )
                
                if response.status_code != 200:
                    logger.error(f"ESP32-S3 returned status {response.status_code}")
                    return False
                
                # Hold button
                time.sleep(hold_duration)
                
                # Send release
                requests.post(
                    f"{self.base_url}/button",
                    json={"cmd": 0x00},
                    timeout=1
                )
                
                # Wait after release
                time.sleep(wait_duration)
                
                logger.debug(f"Sent button: {button} (hold={hold_duration}s, wait={wait_duration}s)")
                return True
            
            else:  # UART mode
                if not self.serial_port:
                    logger.error("Serial port not initialized")
                    return False
                
                # Send button press
                self.serial_port.write(bytes([cmd]))
                time.sleep(hold_duration)
                
                # Send release
                self.serial_port.write(bytes([0x00]))
                time.sleep(wait_duration)
                
                logger.debug(f"Sent button: {button} (hold={hold_duration}s, wait={wait_duration}s)")
                return True
        
        except Exception as e:
            logger.error(f"Error sending button {button}: {e}")
            return False
    
    def send_combo(self, button: str, hold: float) -> bool:
        """
        Send button combo (e.g., RESET) and hold for specified duration.
        
        Args:
            button: Button name (typically 'RESET')
            hold: Hold duration in seconds
        
        Returns:
            True if command sent successfully
        """
        if not self.connected:
            logger.warning("Not connected to ESP32-S3")
            return False
        
        try:
            cmd = build_command(button)
            
            if self.mode == "wifi":
                # Send combo press
                response = requests.post(
                    f"{self.base_url}/button",
                    json={"cmd": cmd},
                    timeout=1
                )
                
                if response.status_code != 200:
                    return False
                
                # Hold for duration
                time.sleep(hold)
                
                # Send release
                requests.post(
                    f"{self.base_url}/button",
                    json={"cmd": 0x00},
                    timeout=1
                )
                
                logger.info(f"Sent combo: {button} (hold={hold}s)")
                return True
            
            else:  # UART mode
                if not self.serial_port:
                    return False
                
                self.serial_port.write(bytes([cmd]))
                time.sleep(hold)
                self.serial_port.write(bytes([0x00]))
                
                logger.info(f"Sent combo: {button} (hold={hold}s)")
                return True
        
        except Exception as e:
            logger.error(f"Error sending combo {button}: {e}")
            return False
    
    def get_status(self) -> dict:
        """
        Get ESP32-S3 status.
        
        Returns:
            Status dictionary
        """
        if not self.connected:
            return {"connected": False}
        
        try:
            if self.mode == "wifi":
                response = requests.get(f"{self.base_url}/status", timeout=2)
                if response.status_code == 200:
                    return {"connected": True, **response.json()}
                return {"connected": False}
            else:
                return {"connected": True, "mode": "uart", "port": settings.serial_port}
        
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return {"connected": False, "error": str(e)}


# Global ESP32 manager instance
esp32_manager = ESP32Manager()
