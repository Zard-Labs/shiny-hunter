"""API endpoints for macro recording lifecycle, frame serving, and template conversion."""
import json
import shutil
import uuid
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import cv2
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, FileResponse, JSONResponse
from pydantic import BaseModel

from app.config import is_packaged, get_user_data_path
from app.database import get_db
from app.models import AutomationTemplate, TemplateImage
from app.services.macro_recorder import macro_recorder
from app.utils.logger import logger


router = APIRouter(prefix="/api/macro-recording", tags=["macro-recording"])


# ── Request models ───────────────────────────────────────────────

class MarkStepRequest(BaseModel):
    label: Optional[str] = None


class ExtractFrameRequest(BaseModel):
    frame_number: int
    name: str  # filename stem, e.g. 'boot_screen'


class ConvertRequest(BaseModel):
    """Request to convert a recording session into an automation template."""
    name: str
    description: Optional[str] = ""
    game: str = "Pokemon RedGreen"
    pokemon_name: str = "Starters"
    step_groups: List[dict]
    # Each step_group: {
    #   "name": "BOOT",
    #   "display_name": "Boot and Navigate",
    #   "template_image": {"source": "screenshot"|"extracted"|"frame", "index"|"name"|"frame_number": ...},
    #   "event_indices": [0, 1, 2, 3],  # indices into session events
    # }


# ── Recording lifecycle ──────────────────────────────────────────

@router.post("/start")
async def start_recording():
    """Start a new macro recording session."""
    try:
        session = macro_recorder.start_session()
        return {
            "status": "recording",
            "session_id": session.id,
            "message": "Recording started",
        }
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/stop")
async def stop_recording():
    """Stop the current recording session."""
    try:
        session = macro_recorder.stop_session()
        return {
            "status": "stopped",
            "session_id": session.id,
            "duration": round(session.duration, 1),
            "total_frames": session.total_frames,
            "event_count": len(session.events),
            "screenshot_count": session.screenshot_count,
            "message": "Recording stopped",
        }
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/status")
async def get_recording_status():
    """Get the current macro recording status."""
    return macro_recorder.get_status()


@router.post("/mark-step")
async def mark_step(req: MarkStepRequest):
    """Add a step boundary marker during recording."""
    try:
        event = macro_recorder.mark_step(req.label)
        return {
            "status": "ok",
            "event": asdict(event),
        }
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/screenshot")
async def manual_screenshot():
    """Manually capture an extra screenshot during recording."""
    try:
        event = await macro_recorder.capture_manual_screenshot()
        return {
            "status": "ok",
            "event": asdict(event),
        }
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


# ── Session CRUD ─────────────────────────────────────────────────

@router.get("/sessions")
async def list_sessions():
    """List all saved recording sessions."""
    return macro_recorder.list_sessions()


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get full session details including all events."""
    session = macro_recorder.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.to_dict()


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a recording session and all its files."""
    try:
        deleted = macro_recorder.delete_session(session_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"status": "deleted", "session_id": session_id}
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


# ── Frame & screenshot serving ───────────────────────────────────

@router.get("/sessions/{session_id}/frame/{frame_number}")
async def get_video_frame(session_id: str, frame_number: int):
    """
    Extract and serve a specific frame from the recorded video as JPEG.

    This seeks into the AVI file, decodes the requested frame, encodes
    it as JPEG, and returns it as an image response.  No browser video
    player needed.
    """
    frame = macro_recorder.get_frame(session_id, frame_number)
    if frame is None:
        raise HTTPException(
            status_code=404,
            detail=f"Frame {frame_number} not found in session {session_id}",
        )

    _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return Response(
        content=jpeg.tobytes(),
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/sessions/{session_id}/screenshot/{screenshot_index}")
async def get_screenshot(session_id: str, screenshot_index: int):
    """Serve an auto-captured screenshot PNG."""
    path = macro_recorder.get_screenshot_path(session_id, screenshot_index)
    if path is None:
        raise HTTPException(
            status_code=404,
            detail=f"Screenshot {screenshot_index} not found",
        )
    return FileResponse(
        str(path),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.post("/sessions/{session_id}/extract-frame")
async def extract_frame(session_id: str, req: ExtractFrameRequest):
    """
    Extract a video frame and save it as a named PNG for template use.

    The user scrubs the video, finds the perfect frame, and clicks
    "Use This Frame" — this endpoint saves it with a meaningful name.
    """
    out_path = macro_recorder.extract_frame_as_image(
        session_id, req.frame_number, req.name
    )
    if out_path is None:
        raise HTTPException(
            status_code=404,
            detail=f"Could not extract frame {req.frame_number}",
        )
    return {
        "status": "ok",
        "name": req.name,
        "frame_number": req.frame_number,
        "path": str(out_path),
    }


# ── Template conversion ─────────────────────────────────────────

@router.post("/sessions/{session_id}/convert")
async def convert_to_template(session_id: str, req: ConvertRequest):
    """
    Convert a recording session into an automation template.

    Takes step_groups that define how events are grouped into steps,
    which images to use for template matching, and step names.
    Produces a full AutomationTemplate with definition JSON, template
    images, and all required DB records.
    """
    session = macro_recorder.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status == "recording":
        raise HTTPException(
            status_code=409,
            detail="Cannot convert a session that is still recording",
        )

    try:
        template_id = _build_template_from_recording(session, req)
    except Exception as e:
        logger.error(f"Template conversion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    # Mark the session as converted
    session.status = "converted"
    # Re-save the session JSON
    json_path = macro_recorder._session_json_path(session_id)
    json_path.write_text(
        json.dumps(session.to_dict(), indent=2), encoding="utf-8"
    )

    return {
        "status": "ok",
        "template_id": template_id,
        "message": f"Template '{req.name}' created with {len(req.step_groups)} steps",
    }


# ── Conversion helper ────────────────────────────────────────────

def _build_template_from_recording(
    session, req: ConvertRequest
) -> str:
    """
    Construct an AutomationTemplate from a recording session + step groups.

    Returns the new template ID.
    """
    from sqlalchemy.orm import Session as DBSession
    from app.database import get_db

    db: DBSession = next(get_db())

    template_id = str(uuid.uuid4())

    # Build the definition steps
    steps = []
    for i, group in enumerate(req.step_groups):
        step_name = group.get("name", f"STEP_{i + 1}")
        display_name = group.get("display_name", step_name.replace("_", " ").title())
        event_indices = group.get("event_indices", [])
        template_image_info = group.get("template_image")

        # Build actions from the events in this group
        actions = []
        prev_timestamp = None
        for idx in event_indices:
            if idx >= len(session.events):
                continue
            event = session.events[idx]
            if event.event_type != "button_press":
                continue

            action = {"type": "press_button", "button": event.button}
            # Calculate wait time from previous button press
            if prev_timestamp is not None:
                wait = round(event.timestamp - prev_timestamp, 2)
                if wait > 0:
                    action["wait"] = wait
            prev_timestamp = event.timestamp
            actions.append(action)

        # Determine the template image key for this step
        image_key = step_name.lower()

        # Build the step
        next_step = (
            req.step_groups[i + 1]["name"]
            if i + 1 < len(req.step_groups)
            else None
        )

        step = {
            "name": step_name,
            "display_name": display_name,
            "type": "navigate",
            "cooldown": 0.6,
            "timeout": 45,
            "rules": [
                {
                    "condition": {
                        "type": "template_match",
                        "template": image_key,
                        "threshold": 0.8,
                    },
                    "actions": actions,
                }
            ],
            "default_action": [{"type": "press_button", "button": "A"}],
        }

        # Add transition to next step if there is one
        if next_step:
            step["rules"][0]["transition"] = next_step

        steps.append(step)

        # Copy the selected template image to the template's image directory
        if template_image_info:
            _copy_template_image(
                session, template_id, image_key, template_image_info, db
            )

    # Build the full definition
    definition = {
        "version": 1,
        "detection": {},
        "soft_reset": {
            "hold_duration": 0.5,
            "wait_after": 3,
            "max_retries": 3,
        },
        "steps": steps,
    }

    # Create the AutomationTemplate record
    template = AutomationTemplate(
        id=template_id,
        name=req.name,
        description=req.description or f"Generated from macro recording {session.id}",
        game=req.game,
        pokemon_name=req.pokemon_name,
        definition=json.dumps(definition),
        is_active=False,
        version=1,
    )
    db.add(template)
    db.commit()

    logger.info(
        f"Created template '{req.name}' (id={template_id}) "
        f"with {len(steps)} steps from recording {session.id}"
    )
    return template_id


def _copy_template_image(
    session, template_id: str, image_key: str, image_info: dict, db
):
    """
    Copy a recording screenshot/extracted frame into the template's image directory
    and create the TemplateImage DB record.
    """
    from app.routes.automation_templates import _template_dir

    source_type = image_info.get("source", "screenshot")
    source_path = None

    if source_type == "screenshot":
        idx = image_info.get("index", 0)
        source_path = macro_recorder.get_screenshot_path(session.id, idx)
    elif source_type == "extracted":
        name = image_info.get("name", "")
        source_path = macro_recorder.get_extracted_path(session.id, name)
    elif source_type == "frame":
        # Extract the frame on-the-fly
        frame_number = image_info.get("frame_number", 0)
        source_path = macro_recorder.extract_frame_as_image(
            session.id, frame_number, f"_temp_{image_key}"
        )

    if source_path is None or not source_path.exists():
        logger.warning(
            f"Could not find source image for step '{image_key}': {image_info}"
        )
        return

    # Copy to template directory
    tmpl_dir = _template_dir(template_id)
    tmpl_dir.mkdir(parents=True, exist_ok=True)
    dest_path = tmpl_dir / f"{image_key}.png"

    # Convert to grayscale for template matching (same as existing capture logic)
    img = cv2.imread(str(source_path))
    if img is not None:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        cv2.imwrite(str(dest_path), gray)

        # Also save color preview
        color_dest = tmpl_dir / f"{image_key}_color.png"
        cv2.imwrite(str(color_dest), img)

    # Create DB record
    template_image = TemplateImage(
        id=str(uuid.uuid4()),
        automation_template_id=template_id,
        key=image_key,
        label=image_key.replace("_", " ").title(),
        description=f"Captured from macro recording",
        threshold=0.8,
    )
    db.add(template_image)
    db.commit()

    logger.info(
        f"Template image '{image_key}' copied to template {template_id}"
    )
