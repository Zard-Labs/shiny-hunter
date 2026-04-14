"""ESP32-S3 communication manager for WiFi/UART commands.

Fully async — uses httpx for non-blocking HTTP and asyncio.sleep
for delays, so the event loop stays responsive during button presses.
"""
import httpx
import serial
import asyncio
import time
from typing import Optional
from app.config import settings
from app.utils.command_builder import build_command, get_button_name
from app.utils.logger import logger


class ESP32Manager:
    """
    Async manager for communicating with ESP32-S3.
    Supports both WiFi (HTTP via httpx) and UART (Serial) communication modes.
    """
    
    def __init__(self):
        self.mode = settings.communication_mode
        self.connected = False
        self.serial_port: Optional[serial.Serial] = None
        self._client: Optional[httpx.AsyncClient] = None
        
        if self.mode == "wifi":
            self.base_url = f"http://{settings.esp32_ip}:{settings.esp32_port}"
            logger.info(f"ESP32 Manager initialized in WiFi mode: {self.base_url}")
        else:
            logger.info(f"ESP32 Manager initialized in UART mode: {settings.serial_port}")
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the persistent async HTTP client.
        
        Uses a generous connect timeout (10s) for mDNS .local resolution
        which can be slow on the first lookup, while keeping read/write
        tight (2s) for responsive button commands.
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=10.0,   # mDNS .local can be slow on first resolve
                    read=2.0,
                    write=2.0,
                    pool=5.0,
                )
            )
        return self._client
    
    async def _close_client(self):
        """Close the async HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
    
    async def connect(self) -> bool:
        """
        Establish connection to ESP32-S3.
        
        Returns:
            True if connected successfully, False otherwise
        """
        try:
            if self.mode == "wifi":
                logger.info(f"Connecting to ESP32 at {self.base_url}/status ...")
                client = await self._get_client()
                response = await client.get(f"{self.base_url}/status")
                if response.status_code == 200:
                    self.connected = True
                    logger.info("[OK] Connected to ESP32-S3 via WiFi")
                    return True
                else:
                    logger.error(f"ESP32-S3 returned status {response.status_code}")
                    return False
            
            else:  # UART mode
                loop = asyncio.get_event_loop()
                self.serial_port = await loop.run_in_executor(
                    None,
                    lambda: serial.Serial(
                        settings.serial_port,
                        settings.baud_rate,
                        timeout=1
                    )
                )
                await asyncio.sleep(0.5)  # Allow port to stabilize
                self.connected = True
                logger.info(f"[OK] Connected to ESP32-S3 via UART on {settings.serial_port}")
                return True
        
        except Exception as e:
            logger.error(f"Failed to connect to ESP32-S3: {type(e).__name__}: {e}")
            self.connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from ESP32-S3."""
        if self.mode == "uart" and self.serial_port:
            self.serial_port.close()
            self.serial_port = None
        
        await self._close_client()
        self.connected = False
        logger.info("Disconnected from ESP32-S3")
    
    async def update_ip(self, ip: str, port: int = None) -> bool:
        """
        Update the ESP32 IP/hostname at runtime, then attempt to reconnect.
        
        Args:
            ip: New IP address or hostname (e.g., '192.168.1.105' or 'shinystarter.local')
            port: New port (default: keep current)
        
        Returns:
            True if reconnected successfully, False otherwise
        """
        # Disconnect from current
        if self.connected:
            await self.disconnect()
        
        # Update settings
        settings.esp32_ip = ip
        if port is not None:
            settings.esp32_port = port
        
        # Rebuild base URL
        if self.mode == "wifi":
            self.base_url = f"http://{settings.esp32_ip}:{settings.esp32_port}"
            logger.info(f"ESP32 address updated to: {self.base_url}")
        
        # Attempt to connect
        return await self.connect()
    
    async def send_button(self, button: str, hold: float = None, wait: float = None) -> bool:
        """
        Send button command to ESP32-S3 (non-blocking).
        
        Uses httpx for async HTTP and asyncio.sleep for delays,
        so the event loop stays responsive during hold/wait periods.
        
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
                client = await self._get_client()
                
                # Send button press
                response = await client.post(
                    f"{self.base_url}/button",
                    json={"cmd": cmd}
                )
                
                if response.status_code != 200:
                    logger.error(f"ESP32-S3 returned status {response.status_code}")
                    return False
                
                # Hold button (non-blocking)
                await asyncio.sleep(hold_duration)
                
                # Send release
                await client.post(
                    f"{self.base_url}/button",
                    json={"cmd": 0x00}
                )
                
                # Wait after release (non-blocking)
                await asyncio.sleep(wait_duration)
                
                logger.debug(f"Sent button: {button} (hold={hold_duration}s, wait={wait_duration}s)")
                return True
            
            else:  # UART mode
                if not self.serial_port:
                    logger.error("Serial port not initialized")
                    return False
                
                loop = asyncio.get_event_loop()
                
                # Send button press (in executor to avoid blocking)
                await loop.run_in_executor(
                    None, self.serial_port.write, bytes([cmd])
                )
                await asyncio.sleep(hold_duration)
                
                # Send release
                await loop.run_in_executor(
                    None, self.serial_port.write, bytes([0x00])
                )
                await asyncio.sleep(wait_duration)
                
                logger.debug(f"Sent button: {button} (hold={hold_duration}s, wait={wait_duration}s)")
                return True
        
        except Exception as e:
            logger.error(f"Error sending button {button}: {e}")
            return False
    
    async def send_combo(self, button: str, hold: float) -> bool:
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
                client = await self._get_client()
                
                # Send combo press
                response = await client.post(
                    f"{self.base_url}/button",
                    json={"cmd": cmd}
                )
                
                if response.status_code != 200:
                    return False
                
                # Hold for duration (non-blocking)
                await asyncio.sleep(hold)
                
                # Send release
                await client.post(
                    f"{self.base_url}/button",
                    json={"cmd": 0x00}
                )
                
                logger.info(f"Sent combo: {button} (hold={hold}s)")
                return True
            
            else:  # UART mode
                if not self.serial_port:
                    return False
                
                loop = asyncio.get_event_loop()
                
                await loop.run_in_executor(
                    None, self.serial_port.write, bytes([cmd])
                )
                await asyncio.sleep(hold)
                await loop.run_in_executor(
                    None, self.serial_port.write, bytes([0x00])
                )
                
                logger.info(f"Sent combo: {button} (hold={hold}s)")
                return True
        
        except Exception as e:
            logger.error(f"Error sending combo {button}: {e}")
            return False
    
    async def get_status(self) -> dict:
        """
        Get ESP32-S3 status.
        
        Returns:
            Status dictionary
        """
        if not self.connected:
            return {"connected": False}
        
        try:
            if self.mode == "wifi":
                client = await self._get_client()
                response = await client.get(f"{self.base_url}/status")
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
