"""Template management endpoints for capturing and managing OpenCV templates."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
from typing import List
import cv2

from app.services.video_capture import video_capture
from app.services.opencv_detector import opencv_detector
from app.config import is_packaged, get_user_data_path
from app.utils.logger import logger


router = APIRouter(prefix="/api/templates", tags=["templates"])

# Template definitions with descriptions for the UI
GAME_TEMPLATES = {
    "title_screen": {
        "filename": "title_screen.png",
        "label": "Title Screen",
        "description": "The game's main title/start screen",
        "phase": "Phase 1 - Boot"
    },
    "load_game": {
        "filename": "load_game.png",
        "label": "Load Game Menu",
        "description": "The 'Continue' / load save menu",
        "phase": "Phase 1 - Boot"
    },
    "nickname_screen": {
        "filename": "nickname_screen.png",
        "label": "Nickname Screen",
        "description": "The 'Give a nickname?' prompt",
        "phase": "Phase 1 - Boot"
    },
    "oak_lab": {
        "filename": "oak_lab.png",
        "label": "Oak's Lab",
        "description": "Professor Oak in his lab",
        "phase": "Phase 2 - Overworld"
    },
    "pokemon_menu": {
        "filename": "pokemon_menu.png",
        "label": "Pokemon Menu",
        "description": "The Pokemon party menu screen",
        "phase": "Phase 3 - Menu"
    },
    "choose_pokemon": {
        "filename": "choose_pokemon.png",
        "label": "Choose Pokemon",
        "description": "Starter selection screen (Charmander)",
        "phase": "Phase 3 - Menu"
    },
    "summary_screen": {
        "filename": "summary_screen.png",
        "label": "Summary Screen",
        "description": "Pokemon summary showing nature/stats",
        "phase": "Phase 4 - Check"
    },
}

if is_packaged():
    TEMPLATES_DIR = get_user_data_path() / "templates" / "pokemon_red"
else:
    TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates" / "pokemon_red"


class TemplateInfo(BaseModel):
    """Template status information."""
    key: str
    filename: str
    label: str
    description: str
    phase: str
    captured: bool
    preview_url: str | None


class CaptureRequest(BaseModel):
    """Request to capture a template from the current frame."""
    template_key: str


@router.get("/status", response_model=List[TemplateInfo])
async def get_template_status():
    """
    Get status of all required game screen templates.
    Returns captured/missing status and preview URLs.
    """
    result = []
    
    for key, info in GAME_TEMPLATES.items():
        filepath = TEMPLATES_DIR / info["filename"]
        captured = filepath.exists() and filepath.stat().st_size > 0
        
        result.append(TemplateInfo(
            key=key,
            filename=info["filename"],
            label=info["label"],
            description=info["description"],
            phase=info["phase"],
            captured=captured,
            preview_url=f"/api/templates/preview/{key}" if captured else None
        ))
    
    return result


@router.post("/capture")
async def capture_template(request: CaptureRequest):
    """
    Capture the current video frame and save it as a template image.
    
    The frame is saved as a grayscale PNG (matching what OpenCV template
    matching expects). After saving, reloads all templates into the detector.
    """
    if request.template_key not in GAME_TEMPLATES:
        raise HTTPException(
            status_code=400, 
            detail=f"Unknown template key: {request.template_key}. "
                   f"Valid keys: {list(GAME_TEMPLATES.keys())}"
        )
    
    # Read the current frame from capture
    result = video_capture.read_frame()
    if result is None:
        raise HTTPException(
            status_code=503, 
            detail="No video frame available. Is the camera connected?"
        )
    
    color_frame, gray_frame = result
    
    # Ensure templates directory exists
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    
    # Save as grayscale PNG (template matching uses grayscale)
    info = GAME_TEMPLATES[request.template_key]
    filepath = TEMPLATES_DIR / info["filename"]
    
    success = cv2.imwrite(str(filepath), gray_frame)
    
    if not success:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to save template image to {filepath}"
        )
    
    # Also save a color version for preview
    color_filepath = TEMPLATES_DIR / f"{request.template_key}_color.png"
    cv2.imwrite(str(color_filepath), color_frame)
    
    logger.info(f"Template captured: {request.template_key} -> {filepath}")
    
    # Reload all templates into the OpenCV detector
    opencv_detector.load_templates()
    logger.info("Templates reloaded into OpenCV detector")
    
    return {
        "status": "success",
        "template_key": request.template_key,
        "filename": info["filename"],
        "message": f"Template '{info['label']}' captured and saved",
        "preview_url": f"/api/templates/preview/{request.template_key}"
    }


@router.get("/preview/{template_key}")
async def get_template_preview(template_key: str):
    """
    Get a template image preview as PNG.
    Returns the color version if available, otherwise grayscale.
    """
    if template_key not in GAME_TEMPLATES:
        raise HTTPException(status_code=404, detail="Template not found")
    
    info = GAME_TEMPLATES[template_key]
    
    # Prefer color preview if it exists
    color_path = TEMPLATES_DIR / f"{template_key}_color.png"
    gray_path = TEMPLATES_DIR / info["filename"]
    
    if color_path.exists():
        return FileResponse(str(color_path), media_type="image/png")
    elif gray_path.exists():
        return FileResponse(str(gray_path), media_type="image/png")
    else:
        raise HTTPException(status_code=404, detail="Template image not found")


@router.delete("/{template_key}")
async def delete_template(template_key: str):
    """Delete a captured template image."""
    if template_key not in GAME_TEMPLATES:
        raise HTTPException(status_code=404, detail="Template not found")
    
    info = GAME_TEMPLATES[template_key]
    filepath = TEMPLATES_DIR / info["filename"]
    color_filepath = TEMPLATES_DIR / f"{template_key}_color.png"
    
    deleted = False
    if filepath.exists():
        filepath.unlink()
        deleted = True
    if color_filepath.exists():
        color_filepath.unlink()
    
    if deleted:
        # Reload templates
        opencv_detector.load_templates()
        logger.info(f"Template deleted: {template_key}")
        return {"status": "success", "message": f"Template '{info['label']}' deleted"}
    else:
        raise HTTPException(status_code=404, detail="Template file not found")


@router.post("/reload")
async def reload_templates():
    """Force reload all templates into the OpenCV detector."""
    opencv_detector.load_templates()
    
    # Count loaded templates
    loaded = sum(1 for t in opencv_detector.templates.values() if t is not None)
    total = len(GAME_TEMPLATES)
    
    return {
        "status": "success",
        "loaded": loaded,
        "total": total,
        "message": f"Loaded {loaded}/{total} game templates"
    }
