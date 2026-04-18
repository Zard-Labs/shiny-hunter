"""Manual control endpoints for testing ESP32."""
import yaml
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.config import settings, get_user_data_path, is_packaged
from app.schemas import ButtonCommand
from app.services.esp32_manager import esp32_manager
from app.services.macro_recorder import macro_recorder
from app.utils.logger import logger


class ESP32ConfigUpdate(BaseModel):
    """Request to update ESP32 connection settings."""
    ip: str
    port: Optional[int] = None
    save: bool = False


router = APIRouter(prefix="/api/control", tags=["control"])


@router.post("/button")
async def send_button_command(command: ButtonCommand):
    """Send manual button press to ESP32-S3.
    
    The ESP32 firmware handles precise press/release timing locally via
    duration_ms, so this endpoint awaits the full cycle.  The asyncio.Lock
    inside esp32_manager serializes concurrent requests.
    """
    if not esp32_manager.connected:
        raise HTTPException(
            status_code=503,
            detail="ESP32-S3 not connected. Please connect first."
        )
    
    try:
        success = await esp32_manager.send_button(command.button)
        if not success:
            raise HTTPException(
                status_code=500,
                detail=f"Button press failed: {command.button}"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Button press error ({command.button}): {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
    # Macro recording hook: log the button press + auto-capture screenshot
    recording_event = None
    if macro_recorder.is_recording:
        try:
            recording_event = await macro_recorder.log_button_press(command.button)
        except Exception as e:
            logger.warning(f"Macro recording hook error: {e}")

    return {
        "status": "success",
        "button": command.button,
        "message": f"Button {command.button} sent",
        "recording_event": recording_event is not None,
    }


@router.get("/esp32/status")
async def get_esp32_status():
    """Get ESP32-S3 connection status."""
    try:
        status = await esp32_manager.get_status()
        return status
    
    except Exception as e:
        logger.error(f"Error getting ESP32 status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/esp32/connect")
async def connect_esp32():
    """Connect to ESP32-S3."""
    try:
        success = await esp32_manager.connect()
        
        if not success:
            raise HTTPException(
                status_code=503,
                detail="Failed to connect to ESP32-S3"
            )
        
        return {
            "status": "connected",
            "message": "Successfully connected to ESP32-S3"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error connecting to ESP32: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/esp32/disconnect")
async def disconnect_esp32():
    """Disconnect from ESP32-S3."""
    try:
        await esp32_manager.disconnect()
        
        return {
            "status": "disconnected",
            "message": "Disconnected from ESP32-S3"
        }
    
    except Exception as e:
        logger.error(f"Error disconnecting from ESP32: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/esp32/config")
async def get_esp32_config():
    """Get current ESP32 connection configuration."""
    return {
        "ip": settings.esp32_ip,
        "port": settings.esp32_port,
        "communication_mode": settings.communication_mode,
        "connected": esp32_manager.connected
    }


@router.put("/esp32/config")
async def update_esp32_config(config: ESP32ConfigUpdate):
    """
    Update ESP32 IP/hostname and optionally save to config.yaml.
    
    Disconnects from current ESP32, updates the address, and attempts to reconnect.
    If save=true, persists the new IP/port to config.yaml for future startups.
    """
    try:
        ip = config.ip.strip()
        port = config.port
        
        if not ip:
            raise HTTPException(status_code=400, detail="IP address or hostname is required")
        
        # Attempt to connect with the new IP
        success = await esp32_manager.update_ip(ip, port)
        
        # Save to config.yaml if requested
        if config.save:
            if is_packaged():
                config_path = get_user_data_path() / "config.yaml"
            else:
                config_path = Path(__file__).parent.parent.parent / "config.yaml"
            
            try:
                if config_path.exists():
                    with open(config_path, 'r') as f:
                        config_data = yaml.safe_load(f) or {}
                else:
                    config_data = {}
                
                if 'hardware' not in config_data:
                    config_data['hardware'] = {}
                
                config_data['hardware']['esp32_ip'] = ip
                if port is not None:
                    config_data['hardware']['esp32_port'] = port
                
                with open(config_path, 'w') as f:
                    yaml.safe_dump(config_data, f, default_flow_style=False, sort_keys=False)
                
                logger.info(f"ESP32 config saved to {config_path}")
            except Exception as e:
                logger.error(f"Failed to save config: {e}")
                # Don't fail the whole request if save fails
        
        return {
            "status": "success" if success else "connection_failed",
            "connected": success,
            "ip": settings.esp32_ip,
            "port": settings.esp32_port,
            "saved": config.save,
            "message": (
                f"Connected to ESP32 at {ip}" if success
                else f"ESP32 address updated to {ip} but connection failed"
            )
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating ESP32 config: {e}")
        raise HTTPException(status_code=500, detail=str(e))
