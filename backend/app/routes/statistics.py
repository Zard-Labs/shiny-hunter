"""Statistics, history, and hunt management endpoints."""
import os
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func as sql_func
from typing import Optional

from app.database import get_db
from app.models import Encounter, Hunt
from app.schemas import StatisticsResponse, HistoryResponse, EncounterResponse, HuntResponse
from app.services.game_engine import game_engine
from app.utils.logger import logger


def _normalize_screenshot_path(path: str) -> str:
    """Convert absolute filesystem paths to relative URL paths.

    Existing DB records may contain full Windows paths like
    ``C:\\Users\\...\\encounters\\encounter_0001.png``.  New records
    store ``/encounters/filename.png`` already, so this is a no-op
    for them.
    """
    if not path:
        return path
    if path.startswith("/encounters/"):
        return path  # already a proper URL path
    filename = os.path.basename(path)  # handles both / and \ separators
    return f"/encounters/{filename}"


router = APIRouter(prefix="/api/statistics", tags=["statistics"])


# ---------------------------------------------------------------------------
#  Helper: get active hunt or a specific hunt by ID
# ---------------------------------------------------------------------------
def _get_hunt(db: Session, hunt_id: Optional[str] = None) -> Optional[Hunt]:
    """Return the requested hunt, or the active hunt if hunt_id is None."""
    if hunt_id:
        return db.query(Hunt).filter(Hunt.id == hunt_id).first()
    return db.query(Hunt).filter(Hunt.status == 'active').first()


# ---------------------------------------------------------------------------
#  GET /current  —  DB-backed statistics (survives server restart)
# ---------------------------------------------------------------------------
@router.get("/current", response_model=StatisticsResponse)
async def get_current_statistics(
    hunt_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get statistics for a hunt (defaults to the active hunt).
    
    Reads directly from the database so stats survive server restarts.
    """
    try:
        hunt = _get_hunt(db, hunt_id)
        if not hunt:
            return StatisticsResponse(
                encounters=0,
                natures={},
                genders={},
                last_encounter=None,
                hunt_id=None,
                hunt_name=None
            )
        
        # Count encounters for this hunt
        total = db.query(sql_func.count(Encounter.id)).filter(
            Encounter.hunt_id == hunt.id
        ).scalar() or 0
        
        # Aggregate genders
        gender_rows = db.query(
            Encounter.gender, sql_func.count(Encounter.id)
        ).filter(
            Encounter.hunt_id == hunt.id,
            Encounter.gender.isnot(None)
        ).group_by(Encounter.gender).all()
        
        genders = {g: c for g, c in gender_rows}
        # Ensure all keys present
        for key in ('Male', 'Female', 'Unknown'):
            genders.setdefault(key, 0)
        
        # Aggregate natures
        nature_rows = db.query(
            Encounter.nature, sql_func.count(Encounter.id)
        ).filter(
            Encounter.hunt_id == hunt.id,
            Encounter.nature.isnot(None)
        ).group_by(Encounter.nature).all()
        
        natures = {n: c for n, c in nature_rows}
        
        # Last encounter
        last_enc = db.query(Encounter).filter(
            Encounter.hunt_id == hunt.id
        ).order_by(desc(Encounter.timestamp)).first()
        
        last_encounter = None
        if last_enc:
            last_encounter = {
                "gender": last_enc.gender or "Unknown",
                "nature": last_enc.nature or "Unknown"
            }
        
        return StatisticsResponse(
            encounters=total,
            natures=natures,
            genders=genders,
            last_encounter=last_encounter,
            hunt_id=hunt.id,
            hunt_name=hunt.name
        )
    
    except Exception as e:
        logger.error(f"Error getting current statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
#  GET /history  —  paginated encounter history with optional hunt filter
# ---------------------------------------------------------------------------
@router.get("/history", response_model=HistoryResponse)
async def get_encounter_history(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session_id: Optional[str] = None,
    hunt_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get paginated encounter history, optionally filtered by hunt or session."""
    try:
        query = db.query(Encounter)
        
        if hunt_id:
            query = query.filter(Encounter.hunt_id == hunt_id)
        elif session_id:
            query = query.filter(Encounter.session_id == session_id)
        else:
            # Default: show active hunt's encounters
            active_hunt = db.query(Hunt).filter(Hunt.status == 'active').first()
            if active_hunt:
                query = query.filter(Encounter.hunt_id == active_hunt.id)
        
        total = query.count()
        
        encounters = query.order_by(desc(Encounter.timestamp))\
            .offset(offset)\
            .limit(limit)\
            .all()
        
        # Normalise screenshot_path for every record so the frontend
        # always receives a relative URL (handles legacy absolute paths).
        enc_responses = []
        for e in encounters:
            resp = EncounterResponse.from_orm(e)
            if resp.screenshot_path:
                resp.screenshot_path = _normalize_screenshot_path(resp.screenshot_path)
            enc_responses.append(resp)

        return HistoryResponse(
            total=total,
            encounters=enc_responses,
        )
    
    except Exception as e:
        logger.error(f"Error getting encounter history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
#  GET /hunts  —  list all hunts (active + archived)
# ---------------------------------------------------------------------------
@router.get("/hunts", response_model=list[HuntResponse])
async def get_hunts(db: Session = Depends(get_db)):
    """List all hunts, newest first. The active hunt is always first."""
    try:
        hunts = db.query(Hunt).order_by(
            desc(Hunt.status == 'active'),  # active first
            desc(Hunt.started_at)
        ).all()
        
        return [HuntResponse.from_orm(h) for h in hunts]
    
    except Exception as e:
        logger.error(f"Error listing hunts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
#  POST /reset  —  archive current hunt, start a new one
# ---------------------------------------------------------------------------
@router.post("/reset")
async def reset_hunt(db: Session = Depends(get_db)):
    """Archive the current hunt and create a fresh one.
    
    This is the 'New Hunt' action — old encounters are preserved
    under the archived hunt and a new active hunt begins at 0.
    """
    try:
        if game_engine.is_running:
            raise HTTPException(
                status_code=409,
                detail="Cannot reset while automation is running. Stop first."
            )
        
        # Archive the current active hunt
        active_hunt = db.query(Hunt).filter(Hunt.status == 'active').first()
        if active_hunt:
            # Count final encounters
            total = db.query(sql_func.count(Encounter.id)).filter(
                Encounter.hunt_id == active_hunt.id
            ).scalar() or 0
            
            active_hunt.status = 'archived'
            active_hunt.ended_at = datetime.utcnow()
            active_hunt.total_encounters = total
        
        # Figure out hunt number for the name
        hunt_count = db.query(sql_func.count(Hunt.id)).scalar() or 0
        new_hunt_number = hunt_count + 1
        
        # Create a new active hunt
        new_hunt_id = str(uuid.uuid4())
        new_hunt = Hunt(
            id=new_hunt_id,
            name=f"Hunt #{new_hunt_number}",
            status='active',
            total_encounters=0
        )
        db.add(new_hunt)
        db.commit()
        
        # Reset in-memory state
        game_engine.reset_in_memory()
        
        logger.info(f"[OK] New hunt started: {new_hunt.name} (ID: {new_hunt_id})")
        
        return {
            "status": "success",
            "message": f"New hunt '{new_hunt.name}' started. Previous hunt archived.",
            "hunt_id": new_hunt_id,
            "hunt_name": new_hunt.name
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting hunt: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
#  GET /charts  —  aggregated chart data
# ---------------------------------------------------------------------------
@router.get("/charts")
async def get_chart_data(
    session_id: Optional[str] = None,
    hunt_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get aggregated data for charts, optionally filtered by hunt."""
    try:
        query = db.query(Encounter)
        
        if hunt_id:
            query = query.filter(Encounter.hunt_id == hunt_id)
        elif session_id:
            query = query.filter(Encounter.session_id == session_id)
        else:
            # Default: active hunt
            active_hunt = db.query(Hunt).filter(Hunt.status == 'active').first()
            if active_hunt:
                query = query.filter(Encounter.hunt_id == active_hunt.id)
        
        encounters = query.all()
        
        # Aggregate nature distribution
        nature_counts = {}
        for e in encounters:
            if e.nature:
                nature_counts[e.nature] = nature_counts.get(e.nature, 0) + 1
        
        # Aggregate gender ratio
        gender_counts = {'Male': 0, 'Female': 0, 'Unknown': 0}
        for e in encounters:
            if e.gender:
                gender_counts[e.gender] = gender_counts.get(e.gender, 0) + 1
        
        nature_distribution = [
            {"name": name, "count": count}
            for name, count in sorted(nature_counts.items(), key=lambda x: x[1], reverse=True)
        ]
        
        return {
            "nature_distribution": nature_distribution,
            "gender_ratio": gender_counts,
            "total_encounters": len(encounters)
        }
    
    except Exception as e:
        logger.error(f"Error getting chart data: {e}")
        raise HTTPException(status_code=500, detail=str(e))
