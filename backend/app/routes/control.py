"""Manual control endpoints for testing ESP32."""
from fastapi import APIRouter, HTTPException

from app.schemas import ButtonCommand
from app.services.esp32_manager import esp32_manager
from app.utils.logger import logger


router = APIRouter(prefix="/api/control", tags=["control"])


@router.post("/button")
async def send_button_command(command: ButtonCommand):
    """Send manual button press to ESP32-S3."""
    try:
        if not esp32_manager.connected:
            raise HTTPException(
                status_code=503,
                detail="ESP32-S3 not connected. Please connect first."
            )
        
        success = esp32_manager.send_button(command.button)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to send button command: {command.button}"
            )
        
        return {
            "status": "success",
            "button": command.button,
            "message": f"Button {command.button} pressed successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending button command: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/esp32/status")
async def get_esp32_status():
    """Get ESP32-S3 connection status."""
    try:
        status = esp32_manager.get_status()
        return status
    
    except Exception as e:
        logger.error(f"Error getting ESP32 status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/esp32/connect")
async def connect_esp32():
    """Connect to ESP32-S3."""
    try:
        success = esp32_manager.connect()
        
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
        esp32_manager.disconnect()
        
        return {
            "status": "disconnected",
            "message": "Disconnected from ESP32-S3"
        }
    
    except Exception as e:
        logger.error(f"Error disconnecting from ESP32: {e}")
        raise HTTPException(status_code=500, detail=str(e))
