"""Data-driven game automation engine with template interpreter."""
import asyncio
import json
import time
import uuid
import cv2
import numpy as np
from concurrent.futures import ThreadPoolExecutor
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


# ════════════════════════════════════════════════════════════════════
#  Continuous background sparkle monitor
# ════════════════════════════════════════════════════════════════════

class SparkleMonitor:
    """
    Continuous background sparkle detector.

    Runs as an asyncio task alongside the macro loop.  While active it
    keeps the video-capture ring buffer enabled and periodically grabs a
    sliding window of recent frames, running
    ``opencv_detector.detect_battle_sparkle()`` on them.

    If a shiny sparkle is detected the monitor:
      1. Sets :attr:`shiny_detected` to ``True``
      2. Stores the guilty frames + detection details
      3. The macro loop checks the flag each cycle and stops

    The monitor is **opt-in** — only started when the loaded template
    contains ``"continuous_monitor": {"enabled": true}`` in its
    definition.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        detection_config: Dict[str, Any],
        definition: Dict[str, Any],
    ):
        from app.config import settings

        # ── Tunables from template config ─────────────────────
        self._analysis_interval: float = config.get("analysis_interval", 0.75)
        self._ring_buffer_frames: int = config.get("ring_buffer_frames", 180)
        self._analysis_frames: int = config.get("analysis_frames", 60)

        # ── Detection parameters (shared with inline step) ────
        # Global settings override per-template values so the user
        # only needs to calibrate the encounter zone once.
        self._detection_config = detection_config

        # Zone: prefer global calibration, fall back to template definition
        if settings.encounter_shiny_zone:
            zone = dict(settings.encounter_shiny_zone)
        else:
            zone = detection_config.get("zone", {})
        self._zone = zone

        self._spark_threshold = detection_config.get("spark_threshold", 500)
        self._peak_threshold = detection_config.get("peak_threshold", 1000)
        self._min_spike_frames = detection_config.get("min_spike_frames", 3)
        self._spike_delta_pct = detection_config.get("spike_delta_pct", 0.15)
        self._min_variance = detection_config.get("min_variance", 50.0)

        # Color bounds: prefer global calibration, fall back to template
        if settings.encounter_color_bounds:
            global_bounds = settings.encounter_color_bounds
            self._lower_hsv = global_bounds.get("lower_hsv")
            self._upper_hsv = global_bounds.get("upper_hsv")
        else:
            color_bounds = detection_config.get("color_bounds", {})
            self._lower_hsv = color_bounds.get("lower_hsv")
            self._upper_hsv = color_bounds.get("upper_hsv")

        # ── Runtime state ─────────────────────────────────────
        self._running = False
        self._last_analyzed_frame_id: int = 0
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sparkle")

        # ── Results (read by the game engine) ─────────────────
        self.shiny_detected: bool = False
        self.shiny_details: Optional[Dict] = None
        self.shiny_frames: Optional[List[np.ndarray]] = None
        self._last_stats: Optional[Dict] = None  # latest analysis for overlay

    # ──────────────────────────────────────────────────────────
    #  Lifecycle
    # ──────────────────────────────────────────────────────────

    async def run(self):
        """Main monitor loop — call as an ``asyncio.create_task()``."""
        logger.info(
            f"[SparkleMonitor] Started — interval={self._analysis_interval}s, "
            f"ring_buffer={self._ring_buffer_frames}, "
            f"analysis_frames={self._analysis_frames}"
        )
        video_capture.enable_ring_buffer(max_frames=self._ring_buffer_frames)
        self._running = True

        try:
            while self._running:
                await self._analyse_once()
                if self.shiny_detected:
                    break
                await asyncio.sleep(self._analysis_interval)
        finally:
            video_capture.disable_ring_buffer()
            self._executor.shutdown(wait=False)
            logger.info("[SparkleMonitor] Stopped")

    def stop(self):
        """Signal the monitor to stop on its next iteration."""
        self._running = False

    # ──────────────────────────────────────────────────────────
    #  Analysis
    # ──────────────────────────────────────────────────────────

    @property
    def last_stats(self) -> Optional[Dict]:
        """Latest analysis stats for real-time overlay display."""
        return self._last_stats

    async def _analyse_once(self):
        """Grab frames from ring buffer and run sparkle detection."""
        # Skip if no new frames since last analysis
        current_frame_id = video_capture.frame_id
        if current_frame_id == self._last_analyzed_frame_id:
            return
        self._last_analyzed_frame_id = current_frame_id

        frames = video_capture.get_frame_window(num_frames=self._analysis_frames)
        if len(frames) < 20:
            return  # not enough frames yet

        # Run the CPU-heavy sparkle detection in a thread to avoid
        # blocking the asyncio event loop
        loop = asyncio.get_event_loop()
        is_shiny, details = await loop.run_in_executor(
            self._executor,
            self._detect,
            frames,
        )

        # Store latest stats for real-time overlay
        ux = self._zone.get("upper_x", 320)
        uy = self._zone.get("upper_y", 40)
        lx = self._zone.get("lower_x", 580)
        ly = self._zone.get("lower_y", 200)
        roi_total = (lx - ux) * (ly - uy) if (lx > ux and ly > uy) else 1

        self._last_stats = {
            "zone": self._zone,
            "roi_total_pixels": roi_total,
            "peak_count": details.get("peak_count", 0),
            "stddev": details.get("stddev", 0),
            "elevated_frames": details.get("elevated_frames", 0),
            "total_frames": details.get("total_frames", 0),
            "baseline": details.get("baseline", 0),
            "result": "SHINY" if is_shiny else "normal",
            "is_shiny": is_shiny,
        }

        if is_shiny:
            logger.info(
                f"[SparkleMonitor] *** SHINY SPARKLE DETECTED *** "
                f"peak={details.get('peak_count', 0)}"
            )
            self.shiny_detected = True
            self.shiny_details = details
            self.shiny_frames = frames

    def _detect(self, frames: List[np.ndarray]):
        """Synchronous wrapper around ``detect_battle_sparkle``.

        Adds a **saturation cap** post-check: if the peak bright-pixel
        count exceeds 70% of the ROI's total pixels, the detection is
        overridden to ``normal``.  This filters out battle-entry screen
        flashes where the entire ROI goes white — a real shiny sparkle
        only illuminates a small portion of the ROI.
        """
        is_shiny, details = opencv_detector.detect_battle_sparkle(
            frames,
            zone=self._zone,
            spark_threshold=self._spark_threshold,
            peak_threshold=self._peak_threshold,
            min_spike_frames=self._min_spike_frames,
            lower_hsv=self._lower_hsv,
            upper_hsv=self._upper_hsv,
            spike_delta_pct=self._spike_delta_pct,
            min_variance=self._min_variance,
        )

        # ── Saturation cap: reject screen flashes ────────────
        if is_shiny:
            ux = self._zone.get("upper_x", 320)
            uy = self._zone.get("upper_y", 40)
            lx = self._zone.get("lower_x", 580)
            ly = self._zone.get("lower_y", 200)
            roi_total = (lx - ux) * (ly - uy) if (lx > ux and ly > uy) else 1
            peak_count = details.get("peak_count", 0)
            saturation_ratio = peak_count / roi_total if roi_total > 0 else 0

            if saturation_ratio > 0.70:
                logger.info(
                    f"[SparkleMonitor] Rejected false positive — "
                    f"peak {peak_count}/{roi_total} = {saturation_ratio:.0%} "
                    f"saturation (>70% = screen flash, not sparkle)"
                )
                return False, details

        return is_shiny, details


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

        # ── Continuous sparkle monitor (opt-in per template) ──
        self._sparkle_monitor: Optional[SparkleMonitor] = None
        self._sparkle_monitor_task: Optional[asyncio.Task] = None

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

        # ── Start continuous sparkle monitor if template opts in ──
        self._start_sparkle_monitor_if_enabled()

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
        # Stop the background sparkle monitor if running
        if self._sparkle_monitor:
            self._sparkle_monitor.stop()
        if self._sparkle_monitor_task and not self._sparkle_monitor_task.done():
            self._sparkle_monitor_task.cancel()
        # Clear references so stale shiny_detected flag doesn't persist
        self._sparkle_monitor = None
        self._sparkle_monitor_task = None
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
        self._sparkle_monitor = None
        self._sparkle_monitor_task = None

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

    def get_sparkle_monitor_stats(self) -> Optional[Dict]:
        """Return the latest sparkle monitor analysis stats, or None."""
        if self._sparkle_monitor and self._sparkle_monitor.last_stats:
            return self._sparkle_monitor.last_stats
        return None

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
            "continuous_monitor_active": self._sparkle_monitor is not None and self._sparkle_monitor._running,
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

        # ── Check background sparkle monitor for shiny ────────
        if self._sparkle_monitor and self._sparkle_monitor.shiny_detected:
            return await self._handle_monitor_shiny(db)

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
        elif step_type == "battle_shiny_check":
            return await self._run_battle_shiny_check_step(step, frame, gray, db)
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
    #  Step type: battle_shiny_check
    # ================================================================

    async def _run_battle_shiny_check_step(self, step: Dict, frame, gray,
                                            db: Session) -> bool:
        """Execute a ``battle_shiny_check`` step.

        Unlike the summary-screen ``shiny_check`` (which analyses a single
        static frame), this step captures a *window* of consecutive frames
        using the video-capture ring buffer and runs multi-frame sparkle
        detection to catch the brief shiny animation.

        Flow:
            1. On first entry, enable the ring buffer and record entry time.
            2. Wait ``capture_window_seconds`` for the sparkle to play.
            3. Grab the frame window from the ring buffer.
            4. Run ``opencv_detector.detect_battle_sparkle()``.
            5. Save a screenshot (the peak-sparkle frame).
            6. If shiny → DB save, notify, stop.
            7. If not shiny → execute ``on_normal_actions``, transition.
            8. Disable the ring buffer.
        """
        curr_time = time.time()

        # ── 1. First-entry setup: enable ring buffer ─────────────
        pre_delay = step.get("pre_check_delay", 0.5)
        if self.wait_start_time == 0.0:
            self.wait_start_time = curr_time
            ring_size = step.get("ring_buffer_frames", 90)
            video_capture.enable_ring_buffer(ring_size)
            logger.info(f"Battle sparkle check: ring buffer enabled ({ring_size} frames)")

        # ── 2. Wait for capture window ───────────────────────────
        capture_window = step.get("capture_window_seconds", 1.5)
        total_wait = pre_delay + capture_window
        if curr_time - self.wait_start_time < total_wait:
            return False

        # ── 3. Grab frame window ─────────────────────────────────
        window_frames_count = step.get("analysis_frames", 45)
        frames = video_capture.get_frame_window(window_frames_count)
        logger.info(f"Battle sparkle check: captured {len(frames)} frames for analysis")

        if not frames:
            logger.warning("No frames in ring buffer — skipping sparkle check")
            video_capture.disable_ring_buffer()
            # Transition to on_normal anyway
            on_normal = step.get("on_normal_actions", [])
            await self._execute_actions(on_normal)
            transition = step.get("on_normal_transition")
            if transition:
                await self._transition_to(transition)
            return False

        # ── 4. Run sparkle analysis ──────────────────────────────
        from app.config import settings as _settings
        detection_cfg = self._definition.get("detection", {}) if self._definition else {}

        # Zone: prefer global calibration, fall back to template/step
        if _settings.encounter_shiny_zone:
            zone = dict(_settings.encounter_shiny_zone)
        else:
            zone = detection_cfg.get("zone", step.get("zone", {
                "upper_x": 320, "upper_y": 40,
                "lower_x": 580, "lower_y": 200,
            }))

        spark_threshold = detection_cfg.get("spark_threshold",
                                            step.get("spark_threshold", 10))
        peak_threshold = detection_cfg.get("peak_threshold",
                                           step.get("peak_threshold", 50))
        min_spike_frames = detection_cfg.get("min_spike_frames",
                                             step.get("min_spike_frames", 3))
        spike_delta_pct = detection_cfg.get("spike_delta_pct",
                                            step.get("spike_delta_pct", 0.15))
        min_variance = detection_cfg.get("min_variance",
                                         step.get("min_variance", 50.0))

        # Color bounds: prefer global calibration, fall back to template
        if _settings.encounter_color_bounds:
            _global_bounds = _settings.encounter_color_bounds
            lower_hsv = _global_bounds.get("lower_hsv")
            upper_hsv = _global_bounds.get("upper_hsv")
        else:
            color_bounds = detection_cfg.get("color_bounds", {})
            lower_hsv = color_bounds.get("lower_hsv")
            upper_hsv = color_bounds.get("upper_hsv")

        # Prepare debug directory for ROI/mask visualisations
        self.encounter_count += 1
        screenshot_dir = self._screenshot_dir()
        debug_dir = screenshot_dir / "sparkle_debug"

        is_shiny, details = opencv_detector.detect_battle_sparkle(
            frames,
            zone=zone,
            spark_threshold=spark_threshold,
            peak_threshold=peak_threshold,
            min_spike_frames=min_spike_frames,
            lower_hsv=lower_hsv,
            upper_hsv=upper_hsv,
            spike_delta_pct=spike_delta_pct,
            min_variance=min_variance,
            debug_dir=str(debug_dir),
            encounter_num=self.encounter_count,
        )

        # ── 5. Save screenshot (peak sparkle frame) ─────────────
        peak_idx = details.get("peak_frame_index", 0)
        best_frame = frames[peak_idx] if peak_idx < len(frames) else frames[-1]

        screenshot_path = screenshot_dir / f"encounter_{self.encounter_count:04d}.png"
        cv2.imwrite(str(screenshot_path), best_frame)
        logger.info(f"[Screenshot] Saved: {screenshot_path.name}")

        if self.hunt_id:
            screenshot_url = f"/encounters/{self.hunt_id}/{screenshot_path.name}"
        else:
            screenshot_url = f"/encounters/{screenshot_path.name}"

        # ── 5b. Save video clip of sparkle analysis frames ───────
        video_clip_url = None
        try:
            h, w = frames[0].shape[:2]
            clip_path = None
            clip_filename = None

            # Try codecs in order of browser compatibility
            codec_options = [
                ('VP90', '.webm'),   # VP9 in WebM — best compression + browser support
                ('VP80', '.webm'),   # VP8 in WebM — good browser support
                ('avc1', '.mp4'),    # H.264 in MP4 — needs OpenH264 library
                ('mp4v', '.mp4'),    # MPEG-4 Part 2 — fallback (limited browser support)
            ]
            for codec, ext in codec_options:
                clip_filename = f"encounter_{self.encounter_count:04d}_clip{ext}"
                clip_path = screenshot_dir / clip_filename
                fourcc = cv2.VideoWriter_fourcc(*codec)
                writer = cv2.VideoWriter(str(clip_path), fourcc, 30.0, (w, h))
                if writer.isOpened():
                    for f in frames:
                        writer.write(f)
                    writer.release()
                    logger.info(
                        f"[VideoClip] Saved: {clip_filename} "
                        f"({len(frames)} frames, codec={codec})"
                    )
                    break
                else:
                    writer.release()
                    logger.debug(f"[VideoClip] Codec {codec} not available, trying next")
                    clip_path = None
                    clip_filename = None

            if clip_path and clip_filename:
                if self.hunt_id:
                    video_clip_url = f"/encounters/{self.hunt_id}/{clip_filename}"
                else:
                    video_clip_url = f"/encounters/{clip_filename}"
            else:
                logger.warning("[VideoClip] No working video codec found — clip not saved")
        except Exception as e:
            logger.warning(f"Failed to save video clip: {e}")

        # ── 6. Disable ring buffer ───────────────────────────────
        video_capture.disable_ring_buffer()

        # ── 7. Handle result ─────────────────────────────────────
        peak_count = details.get("peak_count", 0)
        confidence = peak_count / peak_threshold if peak_threshold else 0

        if is_shiny:
            return await self._handle_shiny_found(
                best_frame, screenshot_path, screenshot_url,
                peak_count, peak_threshold, db,
                video_clip_url=video_clip_url,
            )

        # ── 8. Not shiny — log and continue ──────────────────────
        gender = "Unknown"
        nature = "Unknown"

        logger.info(
            f"Encounter {self.encounter_count} -> "
            f"Sparkle peak: {peak_count} (not shiny)"
        )

        encounter = Encounter(
            encounter_number=self.encounter_count,
            pokemon_name=self.pokemon_name,
            is_shiny=False,
            gender=gender,
            nature=nature,
            session_id=self.session_id,
            hunt_id=self.hunt_id,
            screenshot_path=screenshot_url,
            video_clip_path=video_clip_url,
            detection_confidence=confidence,
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
            "video_clip_url": video_clip_url,
        })

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
                                   db: Session,
                                   video_clip_url: str = None) -> bool:
        """Handle a confirmed shiny detection."""
        logger.info(f"\n*** SHINY FOUND AFTER {self.encounter_count} ENCOUNTERS! ***")

        encounter = Encounter(
            encounter_number=self.encounter_count,
            pokemon_name=self.pokemon_name,
            is_shiny=True,
            session_id=self.session_id,
            hunt_id=self.hunt_id,
            screenshot_path=screenshot_url,
            video_clip_path=video_clip_url,
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
            "video_clip_url": video_clip_url,
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

            elif action_type == "log_encounter":
                await self._log_encounter(action)

            else:
                logger.warning(f"Unknown action type: {action_type}")

    # ================================================================
    #  Condition checking
    # ================================================================

    def _check_condition(self, condition: Dict, gray) -> bool:
        """Evaluate a rule condition against the current frame.

        Currently supports:
            * ``template_match`` — OpenCV template matching (with optional ROI)
        """
        cond_type = condition.get("type", "")

        if cond_type == "template_match":
            template_key = condition.get("template", "")
            threshold = condition.get("threshold", 0.80)
            roi = condition.get("roi")  # None when absent → full-frame search
            match, score = opencv_detector.check_template(
                gray, template_key, threshold, roi=roi
            )
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

    # ================================================================
    #  Continuous sparkle monitor helpers
    # ================================================================

    def _start_sparkle_monitor_if_enabled(self):
        """Start the background sparkle monitor if the template opts in.

        Reads ``continuous_monitor`` from the loaded definition.  If
        ``enabled`` is truthy, creates a :class:`SparkleMonitor` and
        launches it as an ``asyncio.Task``.
        """
        if not self._definition:
            return

        cm_config = self._definition.get("continuous_monitor", {})
        if not cm_config.get("enabled", False):
            return

        detection_config = self._definition.get("detection", {})

        self._sparkle_monitor = SparkleMonitor(
            config=cm_config,
            detection_config=detection_config,
            definition=self._definition,
        )
        self._sparkle_monitor_task = asyncio.create_task(
            self._sparkle_monitor.run()
        )
        logger.info("[SparkleMonitor] Background sparkle monitor task created")

    def toggle_sparkle_monitor(self, enabled: bool) -> Dict[str, Any]:
        """Toggle the continuous sparkle monitor on or off at runtime.

        Called from the API endpoint.  When enabling, creates a new
        :class:`SparkleMonitor` and starts it.  When disabling, stops
        the current monitor.

        Returns a status dict for the API response.
        """
        if enabled:
            # Already running?
            if self._sparkle_monitor and self._sparkle_monitor._running:
                return {"status": "already_active", "active": True}

            if not self._definition:
                return {"status": "error", "message": "No template loaded", "active": False}

            detection_config = self._definition.get("detection", {})
            cm_config = self._definition.get("continuous_monitor", {})
            # Use defaults if not specified in template
            cm_config.setdefault("analysis_interval", 0.75)
            cm_config.setdefault("ring_buffer_frames", 180)
            cm_config.setdefault("analysis_frames", 60)

            self._sparkle_monitor = SparkleMonitor(
                config=cm_config,
                detection_config=detection_config,
                definition=self._definition,
            )
            self._sparkle_monitor_task = asyncio.create_task(
                self._sparkle_monitor.run()
            )
            logger.info("[SparkleMonitor] Enabled via runtime toggle")
            return {"status": "enabled", "active": True}
        else:
            if self._sparkle_monitor:
                self._sparkle_monitor.stop()
            if self._sparkle_monitor_task and not self._sparkle_monitor_task.done():
                self._sparkle_monitor_task.cancel()
            self._sparkle_monitor = None
            self._sparkle_monitor_task = None
            logger.info("[SparkleMonitor] Disabled via runtime toggle")
            return {"status": "disabled", "active": False}

    async def _log_encounter(self, action: Dict):
        """Action handler for ``log_encounter``.

        Increments the encounter counter, snaps a screenshot from the
        current frame, writes a non-shiny encounter record to the DB,
        and sends a WebSocket update.  Runs almost instantly so the
        macro can continue to flee without delay.
        """
        from app.database import get_db

        self.encounter_count += 1

        # Grab current frame for screenshot
        result = video_capture.read_frame()
        if result is None:
            logger.warning("[log_encounter] No frame available for screenshot")
            return

        frame, _ = result
        screenshot_dir = self._screenshot_dir()
        screenshot_path = screenshot_dir / f"encounter_{self.encounter_count:04d}.png"
        cv2.imwrite(str(screenshot_path), frame)
        logger.info(f"[Screenshot] Saved: {screenshot_path.name}")

        if self.hunt_id:
            screenshot_url = f"/encounters/{self.hunt_id}/{screenshot_path.name}"
        else:
            screenshot_url = f"/encounters/{screenshot_path.name}"

        # Write encounter to DB
        try:
            db = next(get_db())
            encounter = Encounter(
                encounter_number=self.encounter_count,
                pokemon_name=self.pokemon_name,
                is_shiny=False,
                gender="Unknown",
                nature="Unknown",
                session_id=self.session_id,
                hunt_id=self.hunt_id,
                screenshot_path=screenshot_url,
                detection_confidence=0,
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
        except Exception as e:
            logger.error(f"[log_encounter] DB error: {e}")

        await self.send_ws_update("encounter_detected", {
            "encounter_number": self.encounter_count,
            "gender": "Unknown",
            "nature": "Unknown",
            "is_shiny": False,
            "screenshot_url": screenshot_url,
        })

        logger.info(f"Encounter {self.encounter_count} logged (continuous monitor mode)")

    async def _handle_monitor_shiny(self, db: Session) -> bool:
        """Handle a shiny detection from the background sparkle monitor.

        Saves a video clip from the monitor's captured frames, updates
        the most recent encounter record to ``is_shiny=True``, sends
        WebSocket notifications, and stops the engine.
        """
        monitor = self._sparkle_monitor
        if not monitor or not monitor.shiny_details:
            return False

        details = monitor.shiny_details
        frames = monitor.shiny_frames or []

        logger.info(
            f"\n*** SHINY FOUND BY BACKGROUND MONITOR "
            f"AFTER {self.encounter_count} ENCOUNTERS! ***"
        )

        # ── Save video clip from the monitor's frames ─────────
        video_clip_url = None
        screenshot_url = None
        screenshot_dir = self._screenshot_dir()

        if frames:
            # Save peak-frame screenshot
            peak_idx = details.get("peak_frame_index", 0)
            best_frame = frames[peak_idx] if peak_idx < len(frames) else frames[-1]
            screenshot_path = screenshot_dir / f"shiny_encounter_{self.encounter_count:04d}.png"
            cv2.imwrite(str(screenshot_path), best_frame)
            logger.info(f"[Screenshot] Shiny saved: {screenshot_path.name}")

            if self.hunt_id:
                screenshot_url = f"/encounters/{self.hunt_id}/{screenshot_path.name}"
            else:
                screenshot_url = f"/encounters/{screenshot_path.name}"

            # Save video clip
            try:
                h, w = frames[0].shape[:2]
                codec_options = [
                    ('VP90', '.webm'),
                    ('VP80', '.webm'),
                    ('avc1', '.mp4'),
                    ('mp4v', '.mp4'),
                ]
                for codec, ext in codec_options:
                    clip_filename = f"shiny_encounter_{self.encounter_count:04d}_clip{ext}"
                    clip_path = screenshot_dir / clip_filename
                    fourcc = cv2.VideoWriter_fourcc(*codec)
                    writer = cv2.VideoWriter(str(clip_path), fourcc, 30.0, (w, h))
                    if writer.isOpened():
                        for f in frames:
                            writer.write(f)
                        writer.release()
                        logger.info(
                            f"[VideoClip] Shiny saved: {clip_filename} "
                            f"({len(frames)} frames, codec={codec})"
                        )
                        if self.hunt_id:
                            video_clip_url = f"/encounters/{self.hunt_id}/{clip_filename}"
                        else:
                            video_clip_url = f"/encounters/{clip_filename}"
                        break
                    else:
                        writer.release()
            except Exception as e:
                logger.warning(f"Failed to save shiny video clip: {e}")

        # ── Update the most recent encounter in DB to is_shiny=True ──
        peak_count = details.get("peak_count", 0)
        peak_threshold = self._sparkle_monitor._peak_threshold if self._sparkle_monitor else 1000
        confidence = peak_count / peak_threshold if peak_threshold else 0

        last_encounter = db.query(Encounter).filter(
            Encounter.hunt_id == self.hunt_id
        ).order_by(Encounter.encounter_number.desc()).first()

        if last_encounter:
            last_encounter.is_shiny = True
            last_encounter.detection_confidence = confidence
            if video_clip_url:
                last_encounter.video_clip_path = video_clip_url
            if screenshot_url:
                last_encounter.screenshot_path = screenshot_url

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
            "video_clip_url": video_clip_url,
            "timestamp": datetime.utcnow().isoformat(),
            "detection_source": "continuous_monitor",
        })

        self.stop()
        return True


# Global game engine instance
game_engine = DataDrivenGameEngine()
