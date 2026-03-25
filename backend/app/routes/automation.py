"""Automation control endpoints."""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
import asyncio

from app.database import get_db
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


@router.post("/start")
async def start_automation(db: Session = Depends(get_db)):
    """Start automated shiny hunting with background task."""
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
        
        session_id = game_engine.start(db)
        
        # Start the automation background task
        _automation_task = asyncio.create_task(_run_automation_loop())
        logger.info(f"Automation background task created for session {session_id}")
        
        return {
            "status": "started",
            "session_id": session_id,
            "message": "Automation started successfully"
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


@router.get("/status", response_model=AutomationStatus)
async def get_automation_status():
    """Get current automation state."""
    try:
        status = game_engine.get_status()
        
        return AutomationStatus(
            is_running=status["is_running"],
            state=status["state"],
            encounter_count=status["encounter_count"],
            session_id=status.get("session_id")
        )
    
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
