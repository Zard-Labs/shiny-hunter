"""Calibration endpoints for detection zone management and visual calibration."""
import yaml
import cv2
import base64
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Dict, Optional
from pathlib import Path

from app.config import settings, is_packaged, get_user_data_path
from app.services.video_capture import video_capture
from app.utils.logger import logger


router = APIRouter(prefix="/api/calibration", tags=["calibration"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class ZoneSaveRequest(BaseModel):
    """Request to save a detection zone."""
    zone_type: str  # "shiny", "gender", "nature", or "encounter"
    coordinates: Dict[str, int]  # upper_x, upper_y, lower_x, lower_y


class ColorBoundsSaveRequest(BaseModel):
    """Request to save encounter sparkle HSV color bounds."""
    lower_hsv: list  # [H, S, V]  e.g. [0, 0, 200]
    upper_hsv: list  # [H, S, V]  e.g. [60, 100, 255]


# ── Helpers ──────────────────────────────────────────────────────────────────

ZONE_TYPE_MAP = {
    "shiny": "shiny_zone",
    "gender": "gender_zone",
    "nature": "nature_text_zone",
    "encounter": "encounter_shiny_zone",
}


def _get_config_path() -> Path:
    """Resolve config.yaml path for both packaged and development modes."""
    if is_packaged():
        return get_user_data_path() / "config.yaml"
    return Path(__file__).parent.parent.parent / "config.yaml"


def _load_config_data() -> dict:
    """Load the current config.yaml contents."""
    config_path = _get_config_path()
    if config_path.exists():
        with open(config_path, 'r') as f:
            return yaml.safe_load(f) or {}
    return {}


def _save_config_data(config_data: dict):
    """Write config data back to config.yaml."""
    config_path = _get_config_path()
    with open(config_path, 'w') as f:
        yaml.safe_dump(config_data, f, default_flow_style=False, sort_keys=False)
    logger.info(f"Config saved to {config_path}")


def _get_frame_size() -> Dict[str, int]:
    """Get the current frame dimensions based on crop mode."""
    if settings.crop_mode == "4:3":
        return {"width": 640, "height": 480}
    return {"width": 640, "height": 360}


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/current")
async def get_current_calibration():
    """
    Get all current calibration zone coordinates, crop mode, and frame size.
    
    Returns zone coordinates for shiny, gender, and nature detection,
    plus frame metadata needed for the visual calibration UI.
    """
    # Build zones dict from current in-memory settings
    zones = {}

    if settings.shiny_zone:
        zones["shiny"] = settings.shiny_zone
    else:
        zones["shiny"] = {
            "upper_x": 264, "upper_y": 109,
            "lower_x": 312, "lower_y": 151,
        }

    if settings.gender_zone:
        zones["gender"] = settings.gender_zone
    else:
        zones["gender"] = {
            "upper_x": 284, "upper_y": 68,
            "lower_x": 311, "lower_y": 92,
        }

    if settings.nature_text_zone:
        zones["nature"] = settings.nature_text_zone
    else:
        zones["nature"] = {
            "upper_x": 0, "upper_y": 300,
            "lower_x": 350, "lower_y": 380,
        }

    if settings.encounter_shiny_zone:
        zones["encounter"] = settings.encounter_shiny_zone
    else:
        zones["encounter"] = {
            "upper_x": 320, "upper_y": 40,
            "lower_x": 580, "lower_y": 200,
        }

    # Encounter sparkle HSV color bounds
    color_bounds = settings.encounter_color_bounds if settings.encounter_color_bounds else {
        "lower_hsv": [0, 0, 200],
        "upper_hsv": [60, 100, 255],
    }

    return {
        "zones": zones,
        "encounter_color_bounds": color_bounds,
        "crop_mode": settings.crop_mode,
        "frame_size": _get_frame_size(),
    }


@router.post("/zone")
async def save_zone(request: ZoneSaveRequest):
    """
    Save a detection zone and apply it immediately.
    
    Persists the zone coordinates to config.yaml and updates
    the in-memory settings so the change takes effect without restart.
    
    Valid zone_type values: "shiny", "gender", "nature"
    Coordinates must include: upper_x, upper_y, lower_x, lower_y
    """
    if request.zone_type not in ZONE_TYPE_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid zone_type '{request.zone_type}'. "
                   f"Valid types: {list(ZONE_TYPE_MAP.keys())}"
        )

    required_keys = {"upper_x", "upper_y", "lower_x", "lower_y"}
    missing = required_keys - set(request.coordinates.keys())
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing coordinate keys: {missing}. "
                   f"Required: {required_keys}"
        )

    # Validate coordinates are sensible
    coords = request.coordinates
    if coords["lower_x"] <= coords["upper_x"] or coords["lower_y"] <= coords["upper_y"]:
        raise HTTPException(
            status_code=400,
            detail="lower_x must be > upper_x and lower_y must be > upper_y"
        )

    config_key = ZONE_TYPE_MAP[request.zone_type]

    # 1. Update in-memory settings immediately
    setattr(settings, config_key, dict(coords))
    logger.info(f"In-memory {config_key} updated: {coords}")

    # 2. Persist to config.yaml
    try:
        config_data = _load_config_data()

        if "detection" not in config_data:
            config_data["detection"] = {}

        config_data["detection"][config_key] = {
            "upper_x": coords["upper_x"],
            "upper_y": coords["upper_y"],
            "lower_x": coords["lower_x"],
            "lower_y": coords["lower_y"],
        }

        _save_config_data(config_data)

    except Exception as e:
        logger.error(f"Failed to persist zone to config.yaml: {e}")
        # In-memory update already applied, so detection still works
        return {
            "status": "partial",
            "message": f"{request.zone_type} zone applied in-memory but failed to save to disk: {e}",
            "zone_type": request.zone_type,
            "coordinates": coords,
        }

    return {
        "status": "success",
        "message": f"{request.zone_type.capitalize()} zone saved and applied",
        "zone_type": request.zone_type,
        "coordinates": coords,
    }


@router.post("/encounter-color-bounds")
async def save_encounter_color_bounds(request: ColorBoundsSaveRequest):
    """
    Save the encounter sparkle HSV color bounds globally.

    Persists to config.yaml and updates in-memory settings so changes
    take effect immediately for the SparkleMonitor.
    """
    # Validate HSV arrays have exactly 3 elements each
    if len(request.lower_hsv) != 3 or len(request.upper_hsv) != 3:
        raise HTTPException(
            status_code=400,
            detail="Both lower_hsv and upper_hsv must be arrays of exactly 3 values [H, S, V]"
        )

    bounds = {
        "lower_hsv": [int(v) for v in request.lower_hsv],
        "upper_hsv": [int(v) for v in request.upper_hsv],
    }

    # 1. Update in-memory settings immediately
    settings.encounter_color_bounds = bounds
    logger.info(f"In-memory encounter_color_bounds updated: {bounds}")

    # 2. Persist to config.yaml
    try:
        config_data = _load_config_data()

        if "detection" not in config_data:
            config_data["detection"] = {}

        config_data["detection"]["encounter_color_bounds"] = bounds
        _save_config_data(config_data)

    except Exception as e:
        logger.error(f"Failed to persist encounter color bounds to config.yaml: {e}")
        return {
            "status": "partial",
            "message": f"Color bounds applied in-memory but failed to save to disk: {e}",
            "color_bounds": bounds,
        }

    return {
        "status": "success",
        "message": "Encounter color bounds saved and applied",
        "color_bounds": bounds,
    }


@router.get("/snapshot")
async def get_calibration_snapshot():
    """
    Capture a single frame from the video feed for visual calibration.
    
    Returns the frame as a JPEG image with frame dimensions in response headers.
    The frontend uses this to display a static image the user can click on
    to define detection zone boundaries.
    """
    result = video_capture.read_frame()
    if result is None:
        raise HTTPException(
            status_code=503,
            detail="No video frame available. Is the camera connected?"
        )

    color_frame, gray_frame = result
    h, w = color_frame.shape[:2]

    # Encode as JPEG
    success, buffer = cv2.imencode('.jpg', color_frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not success:
        raise HTTPException(status_code=500, detail="Failed to encode frame as JPEG")

    return Response(
        content=buffer.tobytes(),
        media_type="image/jpeg",
        headers={
            "X-Frame-Width": str(w),
            "X-Frame-Height": str(h),
            "Cache-Control": "no-cache",
        },
    )
