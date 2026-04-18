"""CRUD and management endpoints for automation templates."""
import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import cv2
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import is_packaged, get_user_data_path
from app.database import get_db
from app.models import AutomationTemplate, TemplateImage
from app.schemas import (
    AutomationTemplateCreate,
    AutomationTemplateUpdate,
    AutomationTemplateResponse,
    AutomationTemplateDetail,
    TemplateImageResponse,
    TemplateImageCapture,
)
from app.services.video_capture import video_capture
from app.services.opencv_detector import opencv_detector
from app.utils.logger import logger


router = APIRouter(prefix="/api/automation-templates", tags=["automation-templates"])


def _templates_base() -> Path:
    """Return the base directory for template image storage."""
    if is_packaged():
        return get_user_data_path() / "templates"
    return Path(__file__).parent.parent.parent / "templates"


def _template_dir(template_id: str) -> Path:
    """Return the directory for a specific template's images."""
    return _templates_base() / template_id


# ── Helpers ──────────────────────────────────────────────────────────

def _build_response(tmpl: AutomationTemplate, db: Session) -> dict:
    """Build an AutomationTemplateResponse-compatible dict."""
    definition = json.loads(tmpl.definition) if tmpl.definition else {}
    step_count = len(definition.get("steps", []))
    image_count = db.query(TemplateImage).filter(
        TemplateImage.automation_template_id == tmpl.id
    ).count()

    return {
        "id": tmpl.id,
        "name": tmpl.name,
        "description": tmpl.description,
        "game": tmpl.game,
        "pokemon_name": tmpl.pokemon_name,
        "is_active": tmpl.is_active,
        "version": tmpl.version,
        "step_count": step_count,
        "image_count": image_count,
        "created_at": tmpl.created_at,
        "updated_at": tmpl.updated_at,
    }


def _build_detail(tmpl: AutomationTemplate, db: Session) -> dict:
    """Build an AutomationTemplateDetail-compatible dict."""
    definition = json.loads(tmpl.definition) if tmpl.definition else {}
    images = db.query(TemplateImage).filter(
        TemplateImage.automation_template_id == tmpl.id
    ).all()

    tmpl_dir = _template_dir(tmpl.id)

    image_list = []
    for img in images:
        # Determine if the image file actually exists
        gray_path = tmpl_dir / f"{img.key}.png" if tmpl_dir.exists() else None
        captured = gray_path is not None and gray_path.exists()

        image_list.append({
            "id": img.id,
            "automation_template_id": img.automation_template_id,
            "key": img.key,
            "label": img.label,
            "description": img.description,
            "threshold": img.threshold,
            "captured": captured,
            "preview_url": f"/api/automation-templates/{tmpl.id}/images/{img.key}/preview"
                           if captured else None,
            "created_at": img.created_at,
        })

    return {
        "id": tmpl.id,
        "name": tmpl.name,
        "description": tmpl.description,
        "game": tmpl.game,
        "pokemon_name": tmpl.pokemon_name,
        "definition": definition,
        "is_active": tmpl.is_active,
        "version": tmpl.version,
        "created_at": tmpl.created_at,
        "updated_at": tmpl.updated_at,
        "images": image_list,
    }


# ── CRUD ─────────────────────────────────────────────────────────────

@router.get("", response_model=List[AutomationTemplateResponse])
async def list_templates(db: Session = Depends(get_db)):
    """List all automation templates (without definitions)."""
    templates = db.query(AutomationTemplate).order_by(
        AutomationTemplate.is_active.desc(),
        AutomationTemplate.updated_at.desc(),
    ).all()
    return [_build_response(t, db) for t in templates]


@router.get("/{template_id}")
async def get_template(template_id: str, db: Session = Depends(get_db)):
    """Get a single automation template with full definition and images."""
    tmpl = db.query(AutomationTemplate).filter(
        AutomationTemplate.id == template_id
    ).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")

    return _build_detail(tmpl, db)


@router.post("", status_code=201)
async def create_template(body: AutomationTemplateCreate,
                           db: Session = Depends(get_db)):
    """Create a new automation template."""
    template_id = str(uuid.uuid4())
    now = datetime.utcnow()

    tmpl = AutomationTemplate(
        id=template_id,
        name=body.name,
        description=body.description,
        game=body.game,
        pokemon_name=body.pokemon_name,
        definition=json.dumps(body.definition),
        is_active=False,
        created_at=now,
        updated_at=now,
        version=1,
    )
    db.add(tmpl)

    # Create TemplateImage rows for any templates referenced in the definition
    _sync_template_images(db, template_id, body.definition)

    db.commit()

    # Create the template image directory
    _template_dir(template_id).mkdir(parents=True, exist_ok=True)

    return _build_detail(tmpl, db)


@router.put("/{template_id}")
async def update_template(template_id: str,
                            body: AutomationTemplateUpdate,
                            db: Session = Depends(get_db)):
    """Update an existing automation template."""
    tmpl = db.query(AutomationTemplate).filter(
        AutomationTemplate.id == template_id
    ).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")

    if body.name is not None:
        tmpl.name = body.name
    if body.description is not None:
        tmpl.description = body.description
    if body.game is not None:
        tmpl.game = body.game
    if body.pokemon_name is not None:
        tmpl.pokemon_name = body.pokemon_name
    if body.definition is not None:
        tmpl.definition = json.dumps(body.definition)
        _sync_template_images(db, template_id, body.definition)

    tmpl.version = (tmpl.version or 0) + 1
    tmpl.updated_at = datetime.utcnow()
    db.commit()

    return _build_detail(tmpl, db)


@router.delete("/{template_id}")
async def delete_template(template_id: str, db: Session = Depends(get_db)):
    """Delete an automation template and its images."""
    tmpl = db.query(AutomationTemplate).filter(
        AutomationTemplate.id == template_id
    ).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")

    if tmpl.is_active:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete the active template. Activate another one first."
        )

    # Delete image rows
    db.query(TemplateImage).filter(
        TemplateImage.automation_template_id == template_id
    ).delete()

    # Delete the template row
    db.delete(tmpl)
    db.commit()

    # Delete the image directory
    tmpl_dir = _template_dir(template_id)
    if tmpl_dir.exists():
        shutil.rmtree(str(tmpl_dir), ignore_errors=True)

    return {"status": "deleted", "template_id": template_id}


# ── Activate / Clone / Export / Import ───────────────────────────────

@router.post("/{template_id}/activate")
async def activate_template(template_id: str, db: Session = Depends(get_db)):
    """Set a template as the active one (deactivates all others)."""
    tmpl = db.query(AutomationTemplate).filter(
        AutomationTemplate.id == template_id
    ).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")

    # Deactivate all
    db.query(AutomationTemplate).update({AutomationTemplate.is_active: False})
    tmpl.is_active = True
    db.commit()

    return {"status": "activated", "template_id": template_id, "name": tmpl.name}


@router.post("/{template_id}/clone")
async def clone_template(template_id: str, db: Session = Depends(get_db)):
    """Clone an existing template (including images on disk)."""
    source = db.query(AutomationTemplate).filter(
        AutomationTemplate.id == template_id
    ).first()
    if not source:
        raise HTTPException(status_code=404, detail="Template not found")

    new_id = str(uuid.uuid4())
    now = datetime.utcnow()

    clone = AutomationTemplate(
        id=new_id,
        name=f"{source.name} (Copy)",
        description=source.description,
        game=source.game,
        pokemon_name=source.pokemon_name,
        definition=source.definition,
        is_active=False,
        created_at=now,
        updated_at=now,
        version=1,
    )
    db.add(clone)

    # Clone image rows
    source_images = db.query(TemplateImage).filter(
        TemplateImage.automation_template_id == template_id
    ).all()

    for img in source_images:
        new_img = TemplateImage(
            id=str(uuid.uuid4()),
            automation_template_id=new_id,
            key=img.key,
            label=img.label,
            description=img.description,
            threshold=img.threshold,
            created_at=now,
        )
        db.add(new_img)

    db.commit()

    # Copy image files
    src_dir = _template_dir(template_id)
    dst_dir = _template_dir(new_id)
    if src_dir.exists():
        shutil.copytree(str(src_dir), str(dst_dir))
    else:
        dst_dir.mkdir(parents=True, exist_ok=True)

    return _build_detail(clone, db)


@router.get("/{template_id}/export")
async def export_template(template_id: str, db: Session = Depends(get_db)):
    """Export a template as a JSON document (definition + metadata)."""
    tmpl = db.query(AutomationTemplate).filter(
        AutomationTemplate.id == template_id
    ).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")

    images = db.query(TemplateImage).filter(
        TemplateImage.automation_template_id == template_id
    ).all()

    export_data = {
        "name": tmpl.name,
        "description": tmpl.description,
        "game": tmpl.game,
        "pokemon_name": tmpl.pokemon_name,
        "definition": json.loads(tmpl.definition),
        "images": [
            {
                "key": img.key,
                "label": img.label,
                "description": img.description,
                "threshold": img.threshold,
            }
            for img in images
        ],
        "exported_at": datetime.utcnow().isoformat(),
        "version": tmpl.version,
    }

    return JSONResponse(content=export_data, headers={
        "Content-Disposition": f'attachment; filename="{tmpl.name}.json"'
    })


class ImportRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    game: Optional[str] = None
    pokemon_name: Optional[str] = None
    definition: dict
    images: Optional[list] = None


@router.post("/import", status_code=201)
async def import_template(body: ImportRequest, db: Session = Depends(get_db)):
    """Import a template from an exported JSON document."""
    template_id = str(uuid.uuid4())
    now = datetime.utcnow()

    tmpl = AutomationTemplate(
        id=template_id,
        name=body.name or "Imported Template",
        description=body.description,
        game=body.game or "Pokemon Red",
        pokemon_name=body.pokemon_name or "Unknown",
        definition=json.dumps(body.definition),
        is_active=False,
        created_at=now,
        updated_at=now,
        version=1,
    )
    db.add(tmpl)

    # Create image rows from import data
    if body.images:
        for img_data in body.images:
            db.add(TemplateImage(
                id=str(uuid.uuid4()),
                automation_template_id=template_id,
                key=img_data.get("key", ""),
                label=img_data.get("label"),
                description=img_data.get("description"),
                threshold=img_data.get("threshold", 0.80),
                created_at=now,
            ))
    else:
        _sync_template_images(db, template_id, body.definition)

    db.commit()
    _template_dir(template_id).mkdir(parents=True, exist_ok=True)

    return _build_detail(tmpl, db)


# ── Template Image Management ────────────────────────────────────────

@router.get("/{template_id}/images")
async def list_template_images(template_id: str, db: Session = Depends(get_db)):
    """List all template images for an automation template."""
    tmpl = db.query(AutomationTemplate).filter(
        AutomationTemplate.id == template_id
    ).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")

    images = db.query(TemplateImage).filter(
        TemplateImage.automation_template_id == template_id
    ).all()

    tmpl_dir = _template_dir(template_id)
    result = []
    for img in images:
        gray_path = tmpl_dir / f"{img.key}.png"
        captured = gray_path.exists()
        result.append({
            "id": img.id,
            "automation_template_id": img.automation_template_id,
            "key": img.key,
            "label": img.label,
            "description": img.description,
            "threshold": img.threshold,
            "captured": captured,
            "preview_url": f"/api/automation-templates/{template_id}/images/{img.key}/preview"
                           if captured else None,
            "created_at": img.created_at,
        })

    return result


@router.post("/{template_id}/images/capture")
async def capture_template_image(template_id: str,
                                  body: TemplateImageCapture,
                                  db: Session = Depends(get_db)):
    """Capture the current video frame as a template image."""
    tmpl = db.query(AutomationTemplate).filter(
        AutomationTemplate.id == template_id
    ).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")

    # Read the current frame
    result = video_capture.read_frame()
    if result is None:
        raise HTTPException(
            status_code=503,
            detail="No video frame available. Is the camera connected?"
        )

    color_frame, gray_frame = result

    # Ensure directory exists
    tmpl_dir = _template_dir(template_id)
    tmpl_dir.mkdir(parents=True, exist_ok=True)

    # Save grayscale and color versions
    gray_path = tmpl_dir / f"{body.key}.png"
    color_path = tmpl_dir / f"{body.key}_color.png"
    cv2.imwrite(str(gray_path), gray_frame)
    cv2.imwrite(str(color_path), color_frame)

    # Upsert the TemplateImage row
    existing = db.query(TemplateImage).filter(
        TemplateImage.automation_template_id == template_id,
        TemplateImage.key == body.key,
    ).first()

    if existing:
        existing.label = body.label or existing.label
        existing.description = body.description or existing.description
        existing.threshold = body.threshold
        existing.image_path = str(gray_path)
        existing.color_image_path = str(color_path)
    else:
        db.add(TemplateImage(
            id=str(uuid.uuid4()),
            automation_template_id=template_id,
            key=body.key,
            label=body.label,
            description=body.description,
            image_path=str(gray_path),
            color_image_path=str(color_path),
            threshold=body.threshold,
        ))

    db.commit()

    logger.info(f"Template image captured: {body.key} for template {template_id}")

    return {
        "status": "success",
        "key": body.key,
        "template_id": template_id,
        "preview_url": f"/api/automation-templates/{template_id}/images/{body.key}/preview",
    }


@router.get("/{template_id}/images/{image_key}/preview")
async def get_image_preview(template_id: str, image_key: str):
    """Get a template image preview (color version preferred)."""
    tmpl_dir = _template_dir(template_id)
    color_path = tmpl_dir / f"{image_key}_color.png"
    gray_path = tmpl_dir / f"{image_key}.png"

    no_cache_headers = {"Cache-Control": "no-cache, must-revalidate"}

    if color_path.exists():
        return FileResponse(str(color_path), media_type="image/png", headers=no_cache_headers)
    elif gray_path.exists():
        return FileResponse(str(gray_path), media_type="image/png", headers=no_cache_headers)
    else:
        raise HTTPException(status_code=404, detail="Image not found")


class CreateImageRequest(BaseModel):
    """Create a new template image entry (without capturing)."""
    key: str
    label: Optional[str] = None
    description: Optional[str] = None
    threshold: float = 0.80


class UpdateImageRequest(BaseModel):
    """Update template image metadata."""
    label: Optional[str] = None
    description: Optional[str] = None
    threshold: Optional[float] = None


@router.post("/{template_id}/images")
async def create_template_image(template_id: str,
                                 body: CreateImageRequest,
                                 db: Session = Depends(get_db)):
    """Create a new template image entry (without capturing a frame)."""
    tmpl = db.query(AutomationTemplate).filter(
        AutomationTemplate.id == template_id
    ).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")

    # Check if key already exists
    existing = db.query(TemplateImage).filter(
        TemplateImage.automation_template_id == template_id,
        TemplateImage.key == body.key,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Image key '{body.key}' already exists")

    img = TemplateImage(
        id=str(uuid.uuid4()),
        automation_template_id=template_id,
        key=body.key,
        label=body.label or body.key.replace("_", " ").title(),
        description=body.description,
        threshold=body.threshold,
    )
    db.add(img)
    db.commit()

    return {
        "status": "created",
        "key": body.key,
        "template_id": template_id,
        "id": img.id,
    }


@router.put("/{template_id}/images/{image_key}")
async def update_template_image(template_id: str, image_key: str,
                                 body: UpdateImageRequest,
                                 db: Session = Depends(get_db)):
    """Update template image metadata (label, description, threshold)."""
    img = db.query(TemplateImage).filter(
        TemplateImage.automation_template_id == template_id,
        TemplateImage.key == image_key,
    ).first()
    if not img:
        raise HTTPException(status_code=404, detail=f"Image '{image_key}' not found")

    if body.label is not None:
        img.label = body.label
    if body.description is not None:
        img.description = body.description
    if body.threshold is not None:
        img.threshold = body.threshold

    db.commit()

    return {
        "status": "updated",
        "key": image_key,
        "template_id": template_id,
        "label": img.label,
        "description": img.description,
        "threshold": img.threshold,
    }


@router.delete("/{template_id}/images/{image_key}")
async def delete_template_image(template_id: str, image_key: str,
                                 db: Session = Depends(get_db)):
    """Delete a template image (DB row and files)."""
    img = db.query(TemplateImage).filter(
        TemplateImage.automation_template_id == template_id,
        TemplateImage.key == image_key,
    ).first()

    if img:
        db.delete(img)
        db.commit()

    # Remove files
    tmpl_dir = _template_dir(template_id)
    for suffix in [".png", "_color.png"]:
        path = tmpl_dir / f"{image_key}{suffix}"
        if path.exists():
            path.unlink()

    return {"status": "deleted", "key": image_key, "template_id": template_id}


# ── Internal helpers ─────────────────────────────────────────────────

def _sync_template_images(db: Session, template_id: str, definition: dict):
    """Create TemplateImage rows for all templates referenced in the definition.

    Scans rule conditions for ``template_match`` references and ensures
    a corresponding ``TemplateImage`` row exists.
    """
    referenced_keys: set = set()

    for step in definition.get("steps", []):
        for rule in step.get("rules", []):
            cond = rule.get("condition", {})
            if cond.get("type") == "template_match":
                key = cond.get("template")
                if key:
                    referenced_keys.add(key)

    # Get existing keys
    existing = db.query(TemplateImage.key).filter(
        TemplateImage.automation_template_id == template_id
    ).all()
    existing_keys = {row[0] for row in existing}

    # Create missing
    for key in referenced_keys - existing_keys:
        db.add(TemplateImage(
            id=str(uuid.uuid4()),
            automation_template_id=template_id,
            key=key,
            label=key.replace("_", " ").title(),
            threshold=0.80,
        ))
