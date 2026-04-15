"""Data-driven game automation engine with template interpreter."""
import asyncio
import json
import time
import uuid
import cv2
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func

from app.config import settings, is_packaged, get_user_data_path
from app.models import Encounter, Session as DBSession, Hunt, AutomationTemplate, TemplateImage
from app.services.esp32_manager import esp32_manager
from app.services.video_capture import video_capture
from app.services.opencv_detector import opencv_detector
from app.utils.logger import logger


class DataDrivenGameEngine:
    """
    Data-driven game automation engine.

    Instead of hardcoded phases, this engine loads a JSON *definition*
    from an ``AutomationTemplate`` and interprets its steps at runtime.
    Each step defines rules, actions, transitions, and timing — making
    the engine reusable across any Pokémon automation workflow.

    Step types:
        * ``navigate``    – template-matching + button pressing
        * ``timed_wait``  – wait a duration, optionally pressing buttons
        * ``shiny_check`` – screenshot → detect → DB save → reset loop
    """

    def __init__(self):
        # ── Runtime state ───────────────────────────────────────
        self.state = "IDLE"
        self.is_running = False
        self.encounter_count = 0          # per-hunt counter (display + DB)
        self.session_id: Optional[str] = None
        self.hunt_id: Optional[str] = None
        self.last_press_time = 0.0
        self.wait_start_time = 0.0

        # ── Template definition (loaded from DB on start) ──────
        self.template_id: Optional[str] = None
        self.template_name: Optional[str] = None
        self.pokemon_name: str = "Charmander"
        self._definition: Optional[Dict[str, Any]] = None
        self._step_index: Dict[str, Dict] = {}        # name → step dict
        self._step_order: List[str] = []               # ordered step names
        self._soft_reset_config: Dict = {
            "hold_duration": 0.5,
            "wait_after": 3.0,
            "max_retries": 3,
        }

        # ── Stats tracking (in-memory, current session) ────────
        self.last_nature = "Waiting..."
        self.last_gender = "Waiting..."
        self.genders_seen: Dict[str, int] = {'Male': 0, 'Female': 0, 'Unknown': 0}
        self.natures_seen: Dict[str, int] = {}

        # ── WebSocket callback ─────────────────────────────────
        self.ws_callback: Optional[callable] = None

    # ================================================================
    #  WebSocket helpers
    # ================================================================

    def set_websocket_callback(self, callback: callable):
        """Set callback function for sending WebSocket updates."""
        self.ws_callback = callback

    async def send_ws_update(self, msg_type: str, data: Dict[str, Any]):
        """Send WebSocket update if callback is set."""
        if self.ws_callback:
            await self.ws_callback({"type": msg_type, "data": data})

    # ================================================================
    #  Template loading
    # ================================================================

    def load_template(self, template_row: AutomationTemplate,
                      image_rows: List[TemplateImage]):
        """
        Load an automation template definition and its images.

        Called once before :meth:`start` — typically from the automation
        route.  Parses the JSON definition and loads the OpenCV
        screenshot templates for the detector.

        Args:
            template_row: The ``AutomationTemplate`` ORM object
            image_rows:   List of ``TemplateImage`` ORM objects
        """
        self.template_id = template_row.id
        self.template_name = template_row.name
        self.pokemon_name = template_row.pokemon_name or "Unknown"

        definition = json.loads(template_row.definition)
        self._definition = definition

        # Build step index
        steps = definition.get("steps", [])
        self._step_index = {s["name"]: s for s in steps}
        self._step_order = [s["name"] for s in steps]

        # Soft reset config (per-template — varies by game)
        sr = definition.get("soft_reset", {})
        self._soft_reset_config = {
            "hold_duration": sr.get("hold_duration", 0.5),
            "wait_after": sr.get("wait_after", 3.0),
            "max_retries": sr.get("max_retries", 3),
        }

        # Build key→filename map from DB rows and load images
        image_map: Dict[str, str] = {}
        for img in image_rows:
            # Derive filename from image_path, or fall back to key + .png
            if img.image_path:
                image_map[img.key] = Path(img.image_path).name
            else:
                image_map[img.key] = f"{img.key}.png"

        opencv_detector.load_templates_for_automation(template_row.id, image_map)

        logger.info(
            f"Template loaded: '{self.template_name}' "
            f"({len(steps)} steps, {len(image_map)} images)"
        )

    # ================================================================
    #  State management helpers
    # ================================================================

    def _load_state_from_db(self, db: Session):
        """Load encounter count and stats from the database.

        - encounter_count is PER-HUNT so numbering restarts at 1 for each
          new hunt.  Screenshots are stored in per-hunt subdirectories
          (encounters/<hunt_id>/) so filenames never collide.
        - In-memory stats (genders, natures) are scoped to the active hunt.
        """
        active_hunt = db.query(Hunt).filter(Hunt.status == 'active').first()
        if active_hunt:
            self.hunt_id = active_hunt.id

            hunt_encounter_count = db.query(sql_func.count(Encounter.id)).filter(
                Encounter.hunt_id == active_hunt.id
            ).scalar() or 0
            self.encounter_count = hunt_encounter_count

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
                f"hunt_encounters={hunt_encounter_count}"
            )
        else:
            self.encounter_count = 0
            logger.warning("No active hunt found in DB")

    # ================================================================
    #  Start / Stop / Reset
    # ================================================================

    def start(self, db: Session) -> str:
        """Start automation.

        Resumes encounter numbering from the database so images are
        never overwritten.  Stats are rebuilt from the active hunt.
        """
        if self.is_running:
            logger.warning("Automation already running")
            return self.session_id

        if not self._definition:
            raise RuntimeError("No automation template loaded. Call load_template() first.")

        self._load_state_from_db(db)

        # Bind to the active hunt
        active_hunt = db.query(Hunt).filter(Hunt.status == 'active').first()
        if active_hunt:
            self.hunt_id = active_hunt.id
            # Link hunt to template if not already
            if not active_hunt.automation_template_id and self.template_id:
                active_hunt.automation_template_id = self.template_id
                db.commit()
        else:
            self.hunt_id = str(uuid.uuid4())
            new_hunt = Hunt(
                id=self.hunt_id,
                name="Hunt #1",
                status='active',
                automation_template_id=self.template_id,
            )
            db.add(new_hunt)
            db.commit()

        # Create new session
        self.session_id = str(uuid.uuid4())
        db_session = DBSession(
            id=self.session_id,
            hunt_id=self.hunt_id,
            status='active',
            total_encounters=0,
            shiny_found=False,
        )
        db.add(db_session)
        db.commit()

        self.is_running = True
        # Start at the first step
        if self._step_order:
            self.state = self._step_order[0]
        else:
            self.state = "IDLE"

        logger.info(
            f"[OK] Automation started — Template: '{self.template_name}', "
            f"Session: {self.session_id}, Hunt: {self.hunt_id}, "
            f"resuming from hunt encounter {self.encounter_count}"
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

    def _screenshot_dir(self) -> Path:
        """Return the per-hunt screenshot directory, creating it if needed.

        Layout: ``<screenshot_directory>/<hunt_id>/``
        Falls back to the flat ``<screenshot_directory>/`` when no hunt is set.
        """
        if is_packaged():
            base = get_user_data_path() / settings.screenshot_directory
        else:
            base = Path(__file__).parent.parent.parent / settings.screenshot_directory
        if self.hunt_id:
            target = base / self.hunt_id
        else:
            target = base
        target.mkdir(parents=True, exist_ok=True)
        return target

    def _get_step_info(self) -> Dict[str, Any]:
        """Compute current step metadata from the loaded template."""
        if not self._step_order or self.state in ("IDLE", "STOPPED"):
            return {
                "current_step_index": -1,
                "total_steps": len(self._step_order),
                "step_display_name": None,
                "step_type": None,
            }

        try:
            idx = self._step_order.index(self.state)
        except ValueError:
            idx = -1

        step = self._step_index.get(self.state)
        return {
            "current_step_index": idx,
            "total_steps": len(self._step_order),
            "step_display_name": step.get("display_name", self.state) if step else self.state,
            "step_type": step.get("type") if step else None,
        }

    def get_status(self) -> Dict[str, Any]:
        """Get current automation status."""
        step_info = self._get_step_info()
        return {
            "is_running": self.is_running,
            "state": self.state,
            "encounter_count": self.encounter_count,
            "session_id": self.session_id,
            "hunt_id": self.hunt_id,
            "template_id": self.template_id,
            "template_name": self.template_name,
            "pokemon_name": self.pokemon_name,
            "last_nature": self.last_nature,
            "last_gender": self.last_gender,
            "genders_seen": self.genders_seen,
            "natures_seen": self.natures_seen,
            **step_info,
        }

    # ================================================================
    #  Main cycle — dispatches to step-type handlers
    # ================================================================

    async def run_cycle(self, db: Session) -> bool:
        """Run one cycle of the state machine.

        Returns:
            True if shiny found (should stop), False otherwise
        """
        if not self.is_running:
            return False

        result = video_capture.read_frame()
        if result is None:
            logger.error("Failed to read frame")
            return False

        frame, gray = result
        curr_time = time.time()

        step = self._step_index.get(self.state)
        if step is None:
            logger.error(f"Unknown step '{self.state}' — stopping")
            self.stop()
            return False

        step_type = step.get("type", "navigate")

        if step_type == "navigate":
            return await self._run_navigate_step(step, frame, gray, curr_time)
        elif step_type == "timed_wait":
            return await self._run_timed_wait_step(step, curr_time)
        elif step_type == "shiny_check":
            return await self._run_shiny_check_step(step, frame, gray, db)
        else:
            logger.error(f"Unknown step type '{step_type}' in step '{self.state}'")
            return False

    # ================================================================
    #  Step type: navigate
    # ================================================================

    async def _run_navigate_step(self, step: Dict, frame, gray,
                                  curr_time: float) -> bool:
        """Execute a ``navigate`` step.

        Checks each rule's condition in order.  First match wins:
        execute its actions and optionally transition.  If no rule
        matches and cooldown has elapsed, execute ``default_action``.
        """
        cooldown = step.get("cooldown", 0.6)

        for rule in step.get("rules", []):
            condition = rule.get("condition", {})
            matched = self._check_condition(condition, gray)

            if matched:
                # Only act if past cooldown (unless the rule transitions)
                has_transition = "transition" in rule
                if not has_transition and curr_time - self.last_press_time < cooldown:
                    return False

                actions = rule.get("actions", [])
                await self._execute_actions(actions)
                self.last_press_time = curr_time

                if has_transition:
                    await self._transition_to(rule["transition"])

                return False

        # No rule matched — execute default action if past cooldown
        if curr_time - self.last_press_time >= cooldown:
            default = step.get("default_action")
            if default:
                if isinstance(default, dict):
                    default = [default]
                await self._execute_actions(default)
                self.last_press_time = curr_time

        return False

    # ================================================================
    #  Step type: timed_wait
    # ================================================================

    async def _run_timed_wait_step(self, step: Dict,
                                    curr_time: float) -> bool:
        """Execute a ``timed_wait`` step.

        On first entry, records ``wait_start_time``.  Each cycle
        executes ``during_wait_action``.  When the duration elapses,
        executes ``on_complete_actions`` and transitions.
        """
        duration = step.get("duration", 5.0)

        # Record entry time on first call
        if self.wait_start_time == 0.0 or self.state != step["name"]:
            self.wait_start_time = curr_time

        # During the wait
        during = step.get("during_wait_action")
        if during:
            if isinstance(during, dict):
                during = [during]
            await self._execute_actions(during)

        # Check if duration has elapsed
        if curr_time - self.wait_start_time >= duration:
            on_complete = step.get("on_complete_actions")
            if on_complete:
                if isinstance(on_complete, dict):
                    on_complete = [on_complete]
                await self._execute_actions(on_complete)

            transition = step.get("transition")
            if transition:
                await self._transition_to(transition)

        return False

    # ================================================================
    #  Step type: shiny_check
    # ================================================================

    async def _run_shiny_check_step(self, step: Dict, frame, gray,
                                     db: Session) -> bool:
        """Execute a ``shiny_check`` step.

        1. Wait ``pre_check_delay`` seconds after entering step
        2. Flush camera buffer for a fresh frame
        3. Save screenshot
        4. Run shiny detection
        5. If shiny → save to DB, notify, stop
        6. If not → detect gender/nature, save, soft-reset, transition
        """
        curr_time = time.time()

        # ── 1. Pre-check delay ──────────────────────────────────
        pre_delay = step.get("pre_check_delay", 1.5)
        if self.wait_start_time == 0.0:
            self.wait_start_time = curr_time
        if curr_time - self.wait_start_time < pre_delay:
            return False

        # ── 2. Flush camera buffer ──────────────────────────────
        flush_frames = step.get("buffer_flush_frames", 20)
        logger.info("Flushing camera buffer...")
        await asyncio.sleep(flush_frames / 30.0)

        result = video_capture.read_frame()
        if result is None:
            return False
        fresh_frame, fresh_gray = result

        # ── 3. Save screenshot (per-hunt subdirectory) ─────────
        self.encounter_count += 1
        screenshot_dir = self._screenshot_dir()
        screenshot_path = screenshot_dir / f"encounter_{self.encounter_count:04d}.png"
        cv2.imwrite(str(screenshot_path), fresh_frame)
        logger.info(f"[Screenshot] Saved: {screenshot_path.name}")

        # Build relative URL path for DB / WebSocket
        if self.hunt_id:
            screenshot_url = f"/encounters/{self.hunt_id}/{screenshot_path.name}"
        else:
            screenshot_url = f"/encounters/{screenshot_path.name}"

        # ── 4. Detect shiny (uses global calibration zones) ──────
        is_shiny, yellow_pixels = opencv_detector.detect_shiny(fresh_frame)
        threshold = settings.yellow_star_threshold
        logger.info(f"Shiny check: {yellow_pixels} yellow pixels (threshold: {threshold})")

        if is_shiny:
            return await self._handle_shiny_found(
                fresh_frame, screenshot_path, screenshot_url,
                yellow_pixels, threshold, db
            )

        # ── 5. Not shiny — collect stats ────────────────────────
        collect_gender = step.get("collect_gender", True)
        collect_nature = step.get("collect_nature", True)

        gender = "Unknown"
        nature = "Unknown"

        if collect_gender:
            gender = opencv_detector.detect_gender(fresh_frame)
        if collect_nature:
            loop = asyncio.get_event_loop()
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
            pokemon_name=self.pokemon_name,
            is_shiny=False,
            gender=gender,
            nature=nature,
            session_id=self.session_id,
            hunt_id=self.hunt_id,
            screenshot_path=screenshot_url,
            detection_confidence=yellow_pixels / threshold if threshold else 0,
            state_at_capture=self.state,
        )
        db.add(encounter)

        session = db.query(DBSession).filter(DBSession.id == self.session_id).first()
        if session:
            session.total_encounters = self.encounter_count

        hunt = db.query(Hunt).filter(Hunt.id == self.hunt_id).first()
        if hunt:
            hunt_count = db.query(sql_func.count(Encounter.id)).filter(
                Encounter.hunt_id == self.hunt_id
            ).scalar()
            hunt.total_encounters = hunt_count

        db.commit()

        await self.send_ws_update("encounter_detected", {
            "encounter_number": self.encounter_count,
            "gender": gender,
            "nature": nature,
            "is_shiny": False,
            "screenshot_url": screenshot_url,
        })

        # ── 6. Execute on_normal_actions and transition ─────────
        on_normal = step.get("on_normal_actions", [])
        await self._execute_actions(on_normal)

        transition = step.get("on_normal_transition")
        if transition:
            await self._transition_to(transition)

        return False

    # ================================================================
    #  Shiny found handler
    # ================================================================

    async def _handle_shiny_found(self, frame, screenshot_path: Path,
                                   screenshot_url: str,
                                   yellow_pixels: int, threshold: float,
                                   db: Session) -> bool:
        """Handle a confirmed shiny detection."""
        logger.info(f"\n*** SHINY FOUND AFTER {self.encounter_count} ENCOUNTERS! ***")

        encounter = Encounter(
            encounter_number=self.encounter_count,
            pokemon_name=self.pokemon_name,
            is_shiny=True,
            session_id=self.session_id,
            hunt_id=self.hunt_id,
            screenshot_path=screenshot_url,
            detection_confidence=yellow_pixels / threshold if threshold else 0,
            state_at_capture=self.state,
        )
        db.add(encounter)

        session = db.query(DBSession).filter(DBSession.id == self.session_id).first()
        if session:
            session.shiny_found = True
            session.total_encounters = self.encounter_count
            session.ended_at = datetime.utcnow()
            session.status = 'completed'

        hunt = db.query(Hunt).filter(Hunt.id == self.hunt_id).first()
        if hunt:
            hunt_count = db.query(sql_func.count(Encounter.id)).filter(
                Encounter.hunt_id == self.hunt_id
            ).scalar()
            hunt.total_encounters = hunt_count

        db.commit()

        await self.send_ws_update("shiny_found", {
            "encounter_number": self.encounter_count,
            "screenshot_url": screenshot_url,
            "timestamp": datetime.utcnow().isoformat(),
        })

        self.stop()
        return True

    # ================================================================
    #  Action execution
    # ================================================================

    async def _execute_actions(self, actions: List[Dict]):
        """Execute a sequence of action dicts.

        Each action is a dict like::

            {"type": "press_button", "button": "A", "hold": 0.1, "wait": 0.5}
            {"type": "wait", "duration": 1.0}
            {"type": "soft_reset"}
            {"type": "flush_camera", "frames": 20}
        """
        if not actions:
            return

        for action in actions:
            action_type = action.get("type", "")

            if action_type == "press_button":
                button = action.get("button", "A")
                hold = action.get("hold")
                wait = action.get("wait")
                await esp32_manager.send_button(button, hold=hold, wait=wait)

            elif action_type == "wait":
                duration = action.get("duration", 1.0)
                await asyncio.sleep(duration)

            elif action_type == "soft_reset":
                hold = action.get("hold", self._soft_reset_config["hold_duration"])
                wait_after = action.get("wait", self._soft_reset_config["wait_after"])
                max_retries = action.get("retries", self._soft_reset_config["max_retries"])

                logger.info("Soft resetting...")
                reset_success = False
                for attempt in range(1, max_retries + 1):
                    result = await esp32_manager.send_combo('RESET', hold)
                    if result:
                        reset_success = True
                        break
                    else:
                        logger.warning(f"RESET failed (attempt {attempt}/{max_retries})")
                        if attempt < max_retries:
                            await asyncio.sleep(1.0)

                if not reset_success:
                    logger.error(
                        f"RESET failed after {max_retries} attempts! "
                        f"Game may be out of sync."
                    )

                await asyncio.sleep(wait_after)

            elif action_type == "flush_camera":
                frames = action.get("frames", 20)
                await asyncio.sleep(frames / 30.0)

            else:
                logger.warning(f"Unknown action type: {action_type}")

    # ================================================================
    #  Condition checking
    # ================================================================

    def _check_condition(self, condition: Dict, gray) -> bool:
        """Evaluate a rule condition against the current frame.

        Currently supports:
            * ``template_match`` — OpenCV template matching
        """
        cond_type = condition.get("type", "")

        if cond_type == "template_match":
            template_key = condition.get("template", "")
            threshold = condition.get("threshold", 0.80)
            match, score = opencv_detector.check_template(gray, template_key, threshold)
            return match

        logger.warning(f"Unknown condition type: {cond_type}")
        return False

    # ================================================================
    #  Transition helper
    # ================================================================

    async def _transition_to(self, step_name: str):
        """Transition to a new step and send a WS update."""
        old_state = self.state
        self.state = step_name
        self.wait_start_time = 0.0  # Reset wait timer for timed_wait steps

        step_info = self._get_step_info()
        await self.send_ws_update("state_update", {
            "state": self.state,
            "encounter_number": self.encounter_count,
            "is_running": True,
            **step_info,
        })
        logger.info(f"-> {step_name} (from {old_state})")


# Global game engine instance
game_engine = DataDrivenGameEngine()
