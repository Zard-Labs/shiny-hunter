"""Camera device management endpoints."""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
import cv2
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

from app.services.video_capture import video_capture
from app.config import settings, is_packaged, get_user_data_path
from app.utils.logger import logger


router = APIRouter(prefix="/api/camera", tags=["camera"])

# Thread pool for blocking camera operations
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="CameraScan")

# Cache for device list to avoid frequent scanning
_device_cache: Optional[List[dict]] = None
_device_cache_time: float = 0
_CACHE_TTL = 30.0  # seconds


class CameraDevice(BaseModel):
    """Camera device information."""
    index: int
    name: str
    is_current: bool
    available: bool


class CameraSelectRequest(BaseModel):
    """Request to select a camera."""
    index: int


class CropModeRequest(BaseModel):
    """Request to set crop mode."""
    mode: str  # "4:3" or "16:9"


def _scan_devices_blocking() -> List[dict]:
    """
    Scan for available camera devices (blocking, runs in thread pool).
    
    Skips the currently active camera index to avoid interfering with it.
    Uses MSMF backend for scanning since DSHOW probing can disrupt active captures.
    """
    devices = []
    current_index = settings.camera_index
    
    for idx in range(5):
        try:
            if idx == current_index and video_capture.is_open:
                # Don't probe the active camera — we know it works
                width = 1920  # Assume HD since we set it on open
                height = 1080
                fps = 30
                name = f"Device {idx}: {width}x{height} @ {fps:.0f}fps 🎥 (Active)"
                devices.append({
                    "index": idx,
                    "name": name,
                    "is_current": True,
                    "available": True
                })
                continue
            
            # Use MSMF for probing (less disruptive than DSHOW on Windows)
            cap = cv2.VideoCapture(idx, cv2.CAP_MSMF)
            is_available = cap.isOpened()
            
            name = f"Device {idx}"
            
            if is_available:
                ret, frame = cap.read()
                if ret and frame is not None:
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    
                    name = f"Device {idx}: {width}x{height} @ {fps:.0f}fps"
                    
                    if width >= 1920 and height >= 1080:
                        name += " 🎥"
                    elif width == 640 and height == 480:
                        name += " ⚠️"
                else:
                    name = f"Device {idx}: Available but no frame"
            
            cap.release()
            
            devices.append({
                "index": idx,
                "name": name,
                "is_current": (idx == current_index),
                "available": is_available
            })
        
        except Exception as e:
            logger.debug(f"Error checking camera {idx}: {e}")
            devices.append({
                "index": idx,
                "name": f"Device {idx}: Unavailable",
                "is_current": (idx == current_index),
                "available": False
            })
    
    return devices


@router.get("/devices", response_model=List[CameraDevice])
async def list_camera_devices():
    """
    List all available camera devices.
    
    Uses a cached result (30s TTL) to avoid frequent device scanning.
    Scanning runs in a thread pool to avoid blocking the event loop.
    Skips the active camera device to prevent interference.
    """
    global _device_cache, _device_cache_time
    
    now = time.time()
    
    # Return cached result if fresh enough
    if _device_cache is not None and (now - _device_cache_time) < _CACHE_TTL:
        # Update is_current flag in case camera was switched
        for d in _device_cache:
            d["is_current"] = (d["index"] == settings.camera_index)
        return [CameraDevice(**d) for d in _device_cache]
    
    # Scan in a thread to avoid blocking the async loop
    loop = asyncio.get_event_loop()
    devices = await loop.run_in_executor(_executor, _scan_devices_blocking)
    
    # Cache the result
    _device_cache = devices
    _device_cache_time = now
    
    available_devices = [d for d in devices if d["available"]]
    result = available_devices if available_devices else devices[:3]
    
    return [CameraDevice(**d) for d in result]


@router.post("/select")
async def select_camera(request: CameraSelectRequest):
    """
    Switch to a different camera device.
    
    Uses VideoCapture.switch_camera() for thread-safe switching.
    Invalidates the device cache on success.
    """
    global _device_cache, _device_cache_time
    
    try:
        success = video_capture.switch_camera(request.index)
        
        if success:
            settings.camera_index = request.index
            
            # Invalidate cache
            _device_cache = None
            _device_cache_time = 0
            
            logger.info(f"Switched to camera {request.index}")
            return {
                "status": "success",
                "message": f"Switched to camera {request.index}",
                "camera_index": request.index
            }
        else:
            logger.error(f"Failed to open camera {request.index}")
            return {
                "status": "error",
                "message": f"Failed to open camera {request.index}",
                "camera_index": settings.camera_index
            }
    
    except Exception as e:
        logger.error(f"Error switching camera: {e}")
        return {
            "status": "error",
            "message": str(e),
            "camera_index": settings.camera_index
        }


@router.get("/current")
async def get_current_camera():
    """Get currently selected camera index and status."""
    return {
        "index": settings.camera_index,
        "is_open": video_capture.is_open,
        "frame_count": video_capture.frame_count
    }


@router.post("/save-to-config")
async def save_camera_to_config(request: CameraSelectRequest):
    """Save the selected camera index to config.yaml."""
    import yaml
    from pathlib import Path
    
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
        
        config_data['hardware']['camera_index'] = request.index
        
        with open(config_path, 'w') as f:
            yaml.safe_dump(config_data, f, default_flow_style=False, sort_keys=False)
        
        return {
            "status": "success",
            "message": f"Camera index {request.index} saved to config.yaml"
        }
    
    except Exception as e:
        logger.error(f"Error saving camera config: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/crop-mode")
async def get_crop_mode():
    """Get the current crop mode setting."""
    return {
        "mode": settings.crop_mode
    }


@router.post("/crop-mode")
async def set_crop_mode(request: CropModeRequest):
    """
    Set the crop mode at runtime (takes effect on the next frame).
    
    - "4:3": Crop 16:9 to 4:3 (for GBA/DS games with black bars), resize to 640x480
    - "16:9": Keep full frame (for Switch/modern consoles), resize to 640x360
    """
    valid_modes = {"4:3", "16:9"}
    if request.mode not in valid_modes:
        return {
            "status": "error",
            "message": f"Invalid crop mode '{request.mode}'. Valid: {valid_modes}"
        }
    
    old_mode = settings.crop_mode
    settings.crop_mode = request.mode
    logger.info(f"Crop mode changed: {old_mode} -> {request.mode}")
    
    return {
        "status": "success",
        "message": f"Crop mode set to {request.mode}",
        "mode": request.mode
    }


@router.post("/crop-mode/save")
async def save_crop_mode_to_config(request: CropModeRequest):
    """Save the crop mode to config.yaml for persistence across restarts."""
    import yaml
    from pathlib import Path
    
    valid_modes = {"4:3", "16:9"}
    if request.mode not in valid_modes:
        return {
            "status": "error",
            "message": f"Invalid crop mode '{request.mode}'. Valid: {valid_modes}"
        }
    
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
        
        config_data['hardware']['crop_mode'] = request.mode
        
        with open(config_path, 'w') as f:
            yaml.safe_dump(config_data, f, default_flow_style=False, sort_keys=False)
        
        return {
            "status": "success",
            "message": f"Crop mode '{request.mode}' saved to config.yaml"
        }
    
    except Exception as e:
        logger.error(f"Error saving crop mode config: {e}")
        return {
            "status": "error",
            "message": str(e)
        }
