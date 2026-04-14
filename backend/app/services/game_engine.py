"""Game automation engine with state machine for Pokemon Red."""
import asyncio
import time
import uuid
import cv2
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func

from app.config import settings, is_packaged, get_user_data_path
from app.models import Encounter, Session as DBSession, Hunt
from app.services.esp32_manager import esp32_manager
from app.services.video_capture import video_capture
from app.services.opencv_detector import opencv_detector
from app.utils.logger import logger


class GameEngine:
    """
    Game automation engine for Pokemon Red Charmander shiny hunting.
    Implements state machine for automated soft resets.
    """
    
    def __init__(self):
        self.state = "IDLE"
        self.is_running = False
        self.encounter_count = 0
        self.session_id: Optional[str] = None
        self.hunt_id: Optional[str] = None
        self.last_press_time = 0.0
        self.wait_start_time = 0.0
        
        # Stats tracking (in-memory, for the current session only)
        self.last_nature = "Waiting..."
        self.last_gender = "Waiting..."
        self.genders_seen: Dict[str, int] = {'Male': 0, 'Female': 0, 'Unknown': 0}
        self.natures_seen: Dict[str, int] = {}
        
        # WebSocket callback for sending updates
        self.ws_callback: Optional[callable] = None
    
    def set_websocket_callback(self, callback: callable):
        """Set callback function for sending WebSocket updates."""
        self.ws_callback = callback
    
    async def send_ws_update(self, msg_type: str, data: Dict[str, Any]):
        """Send WebSocket update if callback is set."""
        if self.ws_callback:
            await self.ws_callback({"type": msg_type, "data": data})
    
    def _load_state_from_db(self, db: Session):
        """Load encounter count and stats from the database.
        
        - encounter_count is GLOBAL (across all hunts) so image filenames
          never collide.
        - In-memory stats (genders, natures) are scoped to the active hunt
          so the dashboard shows current-hunt data while running.
        """
        # Global max encounter number (for image naming)
        max_enc = db.query(sql_func.max(Encounter.encounter_number)).scalar()
        self.encounter_count = max_enc or 0
        
        # Get active hunt
        active_hunt = db.query(Hunt).filter(Hunt.status == 'active').first()
        if active_hunt:
            self.hunt_id = active_hunt.id
            
            # Rebuild stats from the active hunt's encounters
            hunt_encounters = db.query(Encounter).filter(
                Encounter.hunt_id == active_hunt.id
            ).all()
            
            self.genders_seen = {'Male': 0, 'Female': 0, 'Unknown': 0}
            self.natures_seen = {}
            
            for enc in hunt_encounters:
                if enc.gender:
                    self.genders_seen[enc.gender] = self.genders_seen.get(enc.gender, 0) + 1
                if enc.nature:
                    self.natures_seen[enc.nature] = self.natures_seen.get(enc.nature, 0) + 1
            
            # Get last encounter for this hunt
            last_enc = db.query(Encounter).filter(
                Encounter.hunt_id == active_hunt.id
            ).order_by(Encounter.encounter_number.desc()).first()
            
            if last_enc:
                self.last_gender = last_enc.gender or "Unknown"
                self.last_nature = last_enc.nature or "Unknown"
            else:
                self.last_gender = "Waiting..."
                self.last_nature = "Waiting..."
            
            logger.info(
                f"Loaded state from DB: encounter_count={self.encounter_count}, "
                f"hunt_id={self.hunt_id}, "
                f"hunt_encounters={len(hunt_encounters)}"
            )
        else:
            logger.warning("No active hunt found in DB")
    
    def start(self, db: Session) -> str:
        """
        Start automation.
        
        Resumes encounter numbering from the database so images are
        never overwritten.  Stats are rebuilt from the active hunt.
        
        Args:
            db: Database session
        
        Returns:
            Session ID
        """
        if self.is_running:
            logger.warning("Automation already running")
            return self.session_id
        
        # Load state from database (encounter count + stats)
        self._load_state_from_db(db)
        
        # Get the active hunt (should always exist after init_db)
        active_hunt = db.query(Hunt).filter(Hunt.status == 'active').first()
        if active_hunt:
            self.hunt_id = active_hunt.id
        else:
            # Shouldn't happen, but create one just in case
            self.hunt_id = str(uuid.uuid4())
            new_hunt = Hunt(id=self.hunt_id, name="Hunt #1", status='active')
            db.add(new_hunt)
            db.commit()
        
        # Create new session linked to the active hunt
        self.session_id = str(uuid.uuid4())
        db_session = DBSession(
            id=self.session_id,
            hunt_id=self.hunt_id,
            status='active',
            total_encounters=0,
            shiny_found=False
        )
        db.add(db_session)
        db.commit()
        
        self.is_running = True
        self.state = "PHASE_1_BOOT"
        
        logger.info(
            f"[OK] Automation started - Session ID: {self.session_id}, "
            f"Hunt ID: {self.hunt_id}, resuming from encounter {self.encounter_count}"
        )
        return self.session_id
    
    def stop(self):
        """Stop automation."""
        self.is_running = False
        self.state = "STOPPED"
        logger.info("Automation stopped")
    
    def reset_in_memory(self):
        """Reset in-memory state (called when starting a new hunt)."""
        self.encounter_count = 0
        self.hunt_id = None
        self.session_id = None
        self.state = "IDLE"
        self.last_nature = "Waiting..."
        self.last_gender = "Waiting..."
        self.genders_seen = {'Male': 0, 'Female': 0, 'Unknown': 0}
        self.natures_seen = {}
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current automation status.
        
        Returns:
            Status dictionary
        """
        return {
            "is_running": self.is_running,
            "state": self.state,
            "encounter_count": self.encounter_count,
            "session_id": self.session_id,
            "hunt_id": self.hunt_id,
            "last_nature": self.last_nature,
            "last_gender": self.last_gender,
            "genders_seen": self.genders_seen,
            "natures_seen": self.natures_seen
        }
    
    async def run_cycle(self, db: Session) -> bool:
        """
        Run one cycle of the state machine.
        
        Args:
            db: Database session
        
        Returns:
            True if shiny found (should stop), False otherwise
        """
        if not self.is_running:
            return False
        
        # Read frame from camera
        result = video_capture.read_frame()
        if result is None:
            logger.error("Failed to read frame")
            return False
        
        frame, gray = result
        curr_time = time.time()
        
        # State machine
        if self.state == "PHASE_1_BOOT":
            return await self._phase_1_boot(frame, gray, curr_time)
        
        elif self.state == "PHASE_2_OVERWORLD":
            return await self._phase_2_overworld(frame, gray, curr_time)
        
        elif self.state == "PHASE_2_WAIT":
            return await self._phase_2_wait(curr_time)
        
        elif self.state == "PHASE_3_MENU":
            return await self._phase_3_menu(frame, gray, curr_time)
        
        elif self.state == "PHASE_4_CHECK":
            return await self._phase_4_check(frame, gray, db)
        
        return False
    
    async def _phase_1_boot(self, frame, gray, curr_time) -> bool:
        """Phase 1: Boot and navigate through initial menus."""
        # Check for nickname screen (exit condition)
        match, score = opencv_detector.check_template(gray, 'nick', 0.75)
        if match:
            
            await esp32_manager.send_button('START', wait=0.5)
            await esp32_manager.send_button('A', wait=0.5)

            self.last_press_time = curr_time
            self.state = "PHASE_2_OVERWORLD"
            await self.send_ws_update("state_update", {
                "state": self.state,
                "encounter_number": self.encounter_count,
                "is_running": True
            })
            logger.info("-> PHASE_2_OVERWORLD")
            return False
        
        # Check for load game menu
        match, score = opencv_detector.check_template(gray, 'load', 0.70)
        if match and curr_time - self.last_press_time > 0.6:
            await esp32_manager.send_button('A')
            self.last_press_time = curr_time
            return False
        
        # Check for title screen
        match, score = opencv_detector.check_template(gray, 'title', 0.80)
        if match and curr_time - self.last_press_time > 0.6:
            await esp32_manager.send_button('A')
            self.last_press_time = curr_time
            return False
        
        # Default: mash A to get through menus
        if curr_time - self.last_press_time > 0.6:
            await esp32_manager.send_button('A')
            self.last_press_time = curr_time
        
        return False
    
    async def _phase_2_overworld(self, frame, gray, curr_time) -> bool:
        """Phase 2: Clear dialogue in Oak's lab."""
        # Check for Oak in lab (exit condition)
        match, score = opencv_detector.check_template(gray, 'oak', 0.90)
        if match and curr_time - self.last_press_time > 0.6:
            logger.info("Oak detected, waiting 3.5s for text to clear")
            self.wait_start_time = curr_time
            self.state = "PHASE_2_WAIT"
            return False
        
        # Use B to clear dialogue
        if curr_time - self.last_press_time > 0.6:
            await esp32_manager.send_button('A', wait=0.5)
            await esp32_manager.send_button('START', wait=0.5)
            self.last_press_time = curr_time
        
        return False
    
    async def _phase_2_wait(self, curr_time) -> bool:
        """Phase 2 Wait: Non-blocking delay for text to clear."""
        await esp32_manager.send_button('A', wait=1.0)
        if curr_time - self.wait_start_time > 7.0:
            await esp32_manager.send_button('START', wait=1.0)
            self.state = "PHASE_3_MENU"
            await self.send_ws_update("state_update", {
                "state": self.state,
                "encounter_number": self.encounter_count,
                "is_running": True
            })
            logger.info("-> PHASE_3_MENU")
        
        return False
    
    async def _phase_3_menu(self, frame, gray, curr_time) -> bool:
        """Phase 3: Navigate menus to Charmander summary."""
        if curr_time - self.last_press_time < 0.8:
            return False  # Wait for menu animations
        
        # Check for summary screen (exit condition)
        match, score = opencv_detector.check_template(gray, 'summary', 0.85)
        if match:
            self.wait_start_time = curr_time
            self.state = "PHASE_4_CHECK"
            await self.send_ws_update("state_update", {
                "state": self.state,
                "encounter_number": self.encounter_count,
                "is_running": True
            })
            logger.info("-> PHASE_4_CHECK")
            return False
        
        # Check for choose Pokemon menu
        match, score = opencv_detector.check_template(gray, 'choose', 0.85)
        if match:
            # Select Charmander (3rd option - press DOWN twice)
            logger.info("FOUND THE CHOOSE NOW CLICKING A")
            await esp32_manager.send_button('A', wait=0.5)
            self.last_press_time = curr_time
            return False
        
        # Check for Pokemon menu entry
        match, score = opencv_detector.check_template(gray, 'pokemon', 0.85)
        if match:
            await esp32_manager.send_button('A', wait=0.1)
            self.last_press_time = curr_time
            return False
        
        return False
    
    async def _phase_4_check(self, frame, gray, db: Session) -> bool:
        """Phase 4: Check for shiny and log encounter."""
        curr_time = time.time()
        
        if curr_time - self.wait_start_time < 1.5:
            return False  # Wait for summary screen animation
        
        # Flush camera buffer for fresh frame (non-blocking wait)
        logger.info("Flushing camera buffer...")
        await asyncio.sleep(20 / 30.0)  # Wait ~0.67s for fresh frames
        
        # Get fresh frame
        result = video_capture.read_frame()
        if result is None:
            return False
        
        fresh_frame, fresh_gray = result
        
        # Save screenshot (global numbering — never overwrites)
        self.encounter_count += 1
        if is_packaged():
            screenshot_dir = get_user_data_path() / settings.screenshot_directory
        else:
            screenshot_dir = Path(__file__).parent.parent.parent / settings.screenshot_directory
        screenshot_dir.mkdir(exist_ok=True)
        screenshot_path = screenshot_dir / f"encounter_{self.encounter_count:04d}.png"
        cv2.imwrite(str(screenshot_path), fresh_frame)
        logger.info(f"[Screenshot] Saved: {screenshot_path.name}")
        
        # Detect shiny
        is_shiny, yellow_pixels = opencv_detector.detect_shiny(fresh_frame)
        logger.info(f"Shiny check: {yellow_pixels} yellow pixels (threshold: {settings.yellow_star_threshold})")
        
        if is_shiny:
            logger.info(f"\n*** SHINY FOUND AFTER {self.encounter_count} ENCOUNTERS! ***")
            
            # Save to database
            encounter = Encounter(
                encounter_number=self.encounter_count,
                pokemon_name="Charmander",
                is_shiny=True,
                session_id=self.session_id,
                hunt_id=self.hunt_id,
                screenshot_path=f"/encounters/{screenshot_path.name}",
                detection_confidence=yellow_pixels / settings.yellow_star_threshold,
                state_at_capture=self.state
            )
            db.add(encounter)
            
            # Update session
            session = db.query(DBSession).filter(DBSession.id == self.session_id).first()
            if session:
                session.shiny_found = True
                session.total_encounters = self.encounter_count
                session.ended_at = datetime.utcnow()
                session.status = 'completed'
            
            # Update hunt total
            hunt = db.query(Hunt).filter(Hunt.id == self.hunt_id).first()
            if hunt:
                hunt_count = db.query(sql_func.count(Encounter.id)).filter(
                    Encounter.hunt_id == self.hunt_id
                ).scalar()
                hunt.total_encounters = hunt_count
            
            db.commit()
            
            # Send WebSocket notification
            await self.send_ws_update("shiny_found", {
                "encounter_number": self.encounter_count,
                "screenshot_url": f"/encounters/{screenshot_path.name}",
                "timestamp": datetime.utcnow().isoformat()
            })
            
            self.stop()
            return True  # SHINY FOUND - STOP AUTOMATION
        
        # Not shiny - collect stats
        # Run CPU-bound OCR in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        gender = opencv_detector.detect_gender(fresh_frame)
        nature = await loop.run_in_executor(
            None, opencv_detector.detect_nature, fresh_frame
        )
        
        # Update in-memory stats
        self.last_gender = gender
        self.last_nature = nature
        self.genders_seen[gender] = self.genders_seen.get(gender, 0) + 1
        self.natures_seen[nature] = self.natures_seen.get(nature, 0) + 1
        
        logger.info(f"Encounter {self.encounter_count} -> Gender: {gender} | Nature: {nature}")
        
        # Save to database
        encounter = Encounter(
            encounter_number=self.encounter_count,
            pokemon_name="Charmander",
            is_shiny=False,
            gender=gender,
            nature=nature,
            session_id=self.session_id,
            hunt_id=self.hunt_id,
            screenshot_path=f"/encounters/{screenshot_path.name}",
            detection_confidence=yellow_pixels / settings.yellow_star_threshold,
            state_at_capture=self.state
        )
        db.add(encounter)
        
        # Update session encounter count
        session = db.query(DBSession).filter(DBSession.id == self.session_id).first()
        if session:
            session.total_encounters = self.encounter_count
        
        # Update hunt total
        hunt = db.query(Hunt).filter(Hunt.id == self.hunt_id).first()
        if hunt:
            hunt_count = db.query(sql_func.count(Encounter.id)).filter(
                Encounter.hunt_id == self.hunt_id
            ).scalar()
            hunt.total_encounters = hunt_count
        
        db.commit()
        
        # Send WebSocket update
        await self.send_ws_update("encounter_detected", {
            "encounter_number": self.encounter_count,
            "gender": gender,
            "nature": nature,
            "is_shiny": False,
            "screenshot_url": f"/encounters/{screenshot_path.name}"
        })
        
        # Soft reset with retry logic
        logger.info("Normal Pokemon. Soft resetting...")
        max_retries = 3
        reset_success = False
        
        for attempt in range(1, max_retries + 1):
            result = await esp32_manager.send_combo('RESET', settings.soft_reset_hold)
            if result:
                reset_success = True
                break
            else:
                logger.warning(f"RESET command failed (attempt {attempt}/{max_retries})")
                if attempt < max_retries:
                    await asyncio.sleep(1.0)  # Wait before retry
        
        if not reset_success:
            logger.error(
                f"RESET failed after {max_retries} attempts! "
                f"Game may be out of sync. Forcing state to PHASE_1_BOOT anyway."
            )
        
        await asyncio.sleep(settings.soft_reset_wait)
        
        self.state = "PHASE_1_BOOT"
        await self.send_ws_update("state_update", {
            "state": self.state,
            "encounter_number": self.encounter_count,
            "is_running": True
        })
        
        return False


# Global game engine instance
game_engine = GameEngine()
