"""Automation control endpoints."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
import asyncio
from enum import Enum

from app.database import get_db
from app.models import AutomationTemplate, TemplateImage
from app.schemas import AutomationStatus
from app.services.game_engine import game_engine
from app.services.video_capture import video_capture
from app.utils.logger import logger


router = APIRouter(prefix="/api/automation", tags=["automation"])

# Track the automation background task
_automation_task: asyncio.Task | None = None


async def _run_automation_loop():
    """Background coroutine that runs the automation state machine."""
    logger.info("Automation loop started")
    
    while game_engine.is_running:
        try:
            db = next(get_db())
            
            should_stop = await game_engine.run_cycle(db)
            
            if should_stop:
                logger.info("Shiny found! Stopping automation")
                break
            
            # Small delay to prevent CPU overload
            await asyncio.sleep(0.1)
        
        except Exception as e:
            logger.error(f"Error in automation loop: {e}")
            await asyncio.sleep(1)
    
    logger.info("Automation loop stopped")


class StartRequest(BaseModel):
    template_id: Optional[str] = None


@router.post("/start")
async def start_automation(
    body: Optional[StartRequest] = None,
    db: Session = Depends(get_db),
):
    """Start automated shiny hunting with background task.

    Optionally pass ``template_id`` to override the active template.
    If not provided, the currently active template is used.
    """
    global _automation_task
    
    try:
        if game_engine.is_running:
            return {"status": "already_running", "session_id": game_engine.session_id}
        
        # Verify camera is working
        if not video_capture.is_open:
            raise HTTPException(
                status_code=503,
                detail="Camera is not connected. Cannot start automation."
            )
        
        # ── Load the automation template ─────────────────────────
        template_id = body.template_id if body else None
        
        if template_id:
            tmpl = db.query(AutomationTemplate).filter(
                AutomationTemplate.id == template_id
            ).first()
        else:
            tmpl = db.query(AutomationTemplate).filter(
                AutomationTemplate.is_active == True
            ).first()
        
        if not tmpl:
            raise HTTPException(
                status_code=404,
                detail="No automation template found. Create or activate one first."
            )
        
        images = db.query(TemplateImage).filter(
            TemplateImage.automation_template_id == tmpl.id
        ).all()
        
        game_engine.load_template(tmpl, images)
        
        # ── Start the engine ─────────────────────────────────────
        session_id = game_engine.start(db)
        
        # Start the automation background task
        _automation_task = asyncio.create_task(_run_automation_loop())
        logger.info(f"Automation background task created for session {session_id}")
        
        return {
            "status": "started",
            "session_id": session_id,
            "template_id": tmpl.id,
            "template_name": tmpl.name,
            "message": f"Automation started with template '{tmpl.name}'"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting automation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_automation():
    """Stop automation gracefully."""
    try:
        if not game_engine.is_running:
            return {"status": "not_running", "message": "Automation is not running"}
        
        game_engine.stop()
        
        return {
            "status": "stopped",
            "message": "Automation stopped successfully"
        }
    
    except Exception as e:
        logger.error(f"Error stopping automation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_automation_status():
    """Get current automation state including template info."""
    try:
        status = game_engine.get_status()
        
        return {
            "is_running": status["is_running"],
            "state": status["state"],
            "encounter_count": status["encounter_count"],
            "session_id": status.get("session_id"),
            "template_id": status.get("template_id"),
            "template_name": status.get("template_name"),
            "pokemon_name": status.get("pokemon_name"),
            "current_step_index": status.get("current_step_index", -1),
            "total_steps": status.get("total_steps", 0),
            "step_display_name": status.get("step_display_name"),
            "step_type": status.get("step_type"),
            "continuous_monitor_active": status.get("continuous_monitor_active", False),
        }
    
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class MonitorToggleRequest(BaseModel):
    enabled: bool


@router.post("/continuous-monitor")
async def toggle_continuous_monitor(
    body: MonitorToggleRequest,
    db: Session = Depends(get_db),
):
    """Toggle the continuous background sparkle monitor on or off.

    Works both during automation and in standalone mode (for testing).
    In standalone mode, loads the active template's detection config.
    """
    try:
        # If no definition loaded yet, try loading the active template
        if body.enabled and not game_engine._definition:
            tmpl = db.query(AutomationTemplate).filter(
                AutomationTemplate.is_active == True
            ).first()
            if tmpl:
                images = db.query(TemplateImage).filter(
                    TemplateImage.automation_template_id == tmpl.id
                ).all()
                game_engine.load_template(tmpl, images)
            else:
                raise HTTPException(
                    status_code=404,
                    detail="No active template found. Create or activate one first."
                )

        result = game_engine.toggle_sparkle_monitor(body.enabled)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", "Unknown error"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling continuous monitor: {e}")
        raise HTTPException(status_code=500, detail=str(e))
