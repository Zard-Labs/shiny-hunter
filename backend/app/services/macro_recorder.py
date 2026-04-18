"""Macro recording service for capturing button presses + video.

Records gameplay sessions to help users build automation templates:
- Continuous video recording via cv2.VideoWriter (MJPEG/AVI)
- Auto-screenshots at every button press
- Step boundary markers
- Frame extraction from recorded video for template image selection
"""
import asyncio
import cv2
import json
import numpy as np
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.config import is_packaged, get_user_data_path
from app.utils.logger import logger


# ════════════════════════════════════════════════════════════════════
#  Data classes
# ════════════════════════════════════════════════════════════════════

@dataclass
class RecordingEvent:
    """A single event recorded during a macro recording session."""
    timestamp: float          # seconds relative to recording start
    event_type: str           # 'button_press' | 'step_marker' | 'manual_screenshot'
    button: Optional[str] = None        # e.g. 'A', 'B', 'UP', etc.
    frame_number: int = 0               # corresponding video frame number
    screenshot_index: Optional[int] = None  # index into screenshots/ dir
    label: Optional[str] = None         # user label for step markers


@dataclass
class RecordingSession:
    """Metadata + events for a complete recording session."""
    id: str
    started_at: str                         # ISO datetime
    ended_at: Optional[str] = None
    status: str = "recording"               # recording | stopped | converted
    events: List[RecordingEvent] = field(default_factory=list)
    total_frames: int = 0
    fps: float = 10.0
    duration: float = 0.0
    frame_width: int = 0
    frame_height: int = 0
    screenshot_count: int = 0

    def to_dict(self) -> dict:
        """Serialize to JSON-safe dict."""
        return {
            "id": self.id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "status": self.status,
            "events": [asdict(e) for e in self.events],
            "total_frames": self.total_frames,
            "fps": self.fps,
            "duration": self.duration,
            "frame_width": self.frame_width,
            "frame_height": self.frame_height,
            "screenshot_count": self.screenshot_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RecordingSession":
        """Deserialize from a dict (loaded from JSON)."""
        events = [RecordingEvent(**e) for e in data.get("events", [])]
        return cls(
            id=data["id"],
            started_at=data["started_at"],
            ended_at=data.get("ended_at"),
            status=data.get("status", "stopped"),
            events=events,
            total_frames=data.get("total_frames", 0),
            fps=data.get("fps", 10.0),
            duration=data.get("duration", 0.0),
            frame_width=data.get("frame_width", 0),
            frame_height=data.get("frame_height", 0),
            screenshot_count=data.get("screenshot_count", 0),
        )


# ════════════════════════════════════════════════════════════════════
#  MacroRecorderService
# ════════════════════════════════════════════════════════════════════

class MacroRecorderService:
    """
    Core service for macro recording.

    Lifecycle:
    1. start_session()  → opens VideoWriter, starts frame capture thread
    2. log_button_press() → called from button route during recording
    3. mark_step()       → user marks a step boundary
    4. stop_session()    → finalizes video, persists session JSON
    5. get_frame()       → extracts a frame from the recorded video
    6. extract_frame()   → saves a video frame as a named PNG
    """

    # Target recording FPS (lower than live feed to save disk space)
    RECORDING_FPS = 10.0

    # Delay after button press before capturing screenshot (let game react)
    SCREENSHOT_DELAY = 0.15  # seconds

    def __init__(self):
        self._session: Optional[RecordingSession] = None
        self._video_writer: Optional[cv2.VideoWriter] = None
        self._recording_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._frame_counter: int = 0
        self._start_time: float = 0.0
        self._lock = threading.Lock()

    # ── Properties ───────────────────────────────────────────────

    @property
    def is_recording(self) -> bool:
        """Whether a recording session is currently active."""
        return self._session is not None and self._session.status == "recording"

    @property
    def current_session(self) -> Optional[RecordingSession]:
        """The currently active (or last stopped) session."""
        return self._session

    # ── Storage paths ────────────────────────────────────────────

    def _recordings_base(self) -> Path:
        """Base directory for all recording sessions."""
        if is_packaged():
            base = get_user_data_path() / "recordings"
        else:
            base = Path(__file__).parent.parent.parent / "recordings"
        base.mkdir(parents=True, exist_ok=True)
        return base

    def _session_dir(self, session_id: str) -> Path:
        """Directory for a specific recording session."""
        d = self._recordings_base() / session_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _screenshots_dir(self, session_id: str) -> Path:
        """Screenshots subdirectory for a session."""
        d = self._session_dir(session_id) / "screenshots"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _extracted_dir(self, session_id: str) -> Path:
        """Extracted frames subdirectory for a session."""
        d = self._session_dir(session_id) / "extracted"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _video_path(self, session_id: str) -> Path:
        """Path to the video file for a session."""
        return self._session_dir(session_id) / "recording.avi"

    def _session_json_path(self, session_id: str) -> Path:
        """Path to the session metadata JSON file."""
        return self._session_dir(session_id) / "session.json"

    # ── Session lifecycle ────────────────────────────────────────

    def start_session(self) -> RecordingSession:
        """
        Start a new recording session.

        Opens a cv2.VideoWriter and starts a background thread that
        grabs frames from the live video feed at RECORDING_FPS.

        Raises:
            RuntimeError: If already recording or video capture unavailable.
        """
        if self.is_recording:
            raise RuntimeError("A recording session is already active")

        from app.services.video_capture import video_capture

        if not video_capture.is_open:
            raise RuntimeError("Video capture is not open — cannot record")

        # Determine frame dimensions from the live feed
        result = video_capture.read_frame()
        if result is None:
            raise RuntimeError("Cannot read frame from video capture")
        color_frame, _ = result
        h, w = color_frame.shape[:2]

        session_id = str(uuid.uuid4())
        self._session = RecordingSession(
            id=session_id,
            started_at=datetime.utcnow().isoformat(),
            fps=self.RECORDING_FPS,
            frame_width=w,
            frame_height=h,
        )

        # Open VideoWriter (MJPEG in AVI container)
        video_path = self._video_path(session_id)
        fourcc = cv2.VideoWriter_fourcc(*"MJPG")
        self._video_writer = cv2.VideoWriter(
            str(video_path), fourcc, self.RECORDING_FPS, (w, h)
        )
        if not self._video_writer.isOpened():
            self._session = None
            raise RuntimeError(f"Failed to open VideoWriter at {video_path}")

        self._frame_counter = 0
        self._start_time = time.time()
        self._stop_event.clear()

        # Start background recording thread
        self._recording_thread = threading.Thread(
            target=self._recording_loop,
            name="MacroRecorder-Thread",
            daemon=True,
        )
        self._recording_thread.start()

        logger.info(
            f"Macro recording started: session={session_id}, "
            f"size={w}x{h}, fps={self.RECORDING_FPS}"
        )
        return self._session

    def stop_session(self) -> RecordingSession:
        """
        Stop the current recording session.

        Finalizes the video file and persists the session metadata.

        Returns:
            The completed RecordingSession.

        Raises:
            RuntimeError: If no active recording session.
        """
        if not self.is_recording:
            raise RuntimeError("No active recording session to stop")

        session = self._session

        # Stop the recording thread
        self._stop_event.set()
        if self._recording_thread and self._recording_thread.is_alive():
            self._recording_thread.join(timeout=3.0)
        self._recording_thread = None

        # Finalize video
        if self._video_writer:
            self._video_writer.release()
            self._video_writer = None

        # Update session metadata
        session.status = "stopped"
        session.ended_at = datetime.utcnow().isoformat()
        session.total_frames = self._frame_counter
        session.duration = time.time() - self._start_time

        # Persist to JSON
        self._save_session(session)

        logger.info(
            f"Macro recording stopped: session={session.id}, "
            f"frames={session.total_frames}, "
            f"duration={session.duration:.1f}s, "
            f"events={len(session.events)}"
        )
        return session

    # ── Event logging ────────────────────────────────────────────

    async def log_button_press(self, button: str) -> RecordingEvent:
        """
        Log a button press event during recording.

        Waits a short delay (SCREENSHOT_DELAY) then captures a screenshot
        from the live feed so the game has time to react to the input.

        Args:
            button: Button name (e.g. 'A', 'B', 'UP').

        Returns:
            The created RecordingEvent.
        """
        if not self.is_recording:
            raise RuntimeError("Not currently recording")

        # Small delay to let the game screen update after the button press
        await asyncio.sleep(self.SCREENSHOT_DELAY)

        from app.services.video_capture import video_capture

        timestamp = time.time() - self._start_time

        # Capture screenshot
        screenshot_index = self._session.screenshot_count
        result = video_capture.read_frame()
        if result is not None:
            color_frame, _ = result
            screenshot_path = (
                self._screenshots_dir(self._session.id)
                / f"screenshot_{screenshot_index:04d}.png"
            )
            cv2.imwrite(str(screenshot_path), color_frame)
            self._session.screenshot_count += 1

        with self._lock:
            current_frame = self._frame_counter

        event = RecordingEvent(
            timestamp=round(timestamp, 3),
            event_type="button_press",
            button=button,
            frame_number=current_frame,
            screenshot_index=screenshot_index,
        )
        self._session.events.append(event)

        logger.debug(
            f"Recording event: {button} at t={timestamp:.2f}s "
            f"(frame {current_frame}, screenshot {screenshot_index})"
        )
        return event

    def mark_step(self, label: Optional[str] = None) -> RecordingEvent:
        """
        Add a step boundary marker to the recording.

        Args:
            label: Optional user-provided label for this step.

        Returns:
            The created step marker event.
        """
        if not self.is_recording:
            raise RuntimeError("Not currently recording")

        timestamp = time.time() - self._start_time
        with self._lock:
            current_frame = self._frame_counter

        event = RecordingEvent(
            timestamp=round(timestamp, 3),
            event_type="step_marker",
            frame_number=current_frame,
            label=label,
        )
        self._session.events.append(event)

        logger.debug(
            f"Step marker at t={timestamp:.2f}s "
            f"(frame {current_frame}, label={label!r})"
        )
        return event

    async def capture_manual_screenshot(self) -> RecordingEvent:
        """
        Manually capture an extra screenshot without a button press.

        Returns:
            The created screenshot event.
        """
        if not self.is_recording:
            raise RuntimeError("Not currently recording")

        from app.services.video_capture import video_capture

        timestamp = time.time() - self._start_time
        screenshot_index = self._session.screenshot_count

        result = video_capture.read_frame()
        if result is not None:
            color_frame, _ = result
            screenshot_path = (
                self._screenshots_dir(self._session.id)
                / f"screenshot_{screenshot_index:04d}.png"
            )
            cv2.imwrite(str(screenshot_path), color_frame)
            self._session.screenshot_count += 1

        with self._lock:
            current_frame = self._frame_counter

        event = RecordingEvent(
            timestamp=round(timestamp, 3),
            event_type="manual_screenshot",
            frame_number=current_frame,
            screenshot_index=screenshot_index,
        )
        self._session.events.append(event)

        logger.debug(
            f"Manual screenshot at t={timestamp:.2f}s "
            f"(frame {current_frame}, screenshot {screenshot_index})"
        )
        return event

    # ── Video frame access ───────────────────────────────────────

    def get_frame(self, session_id: str, frame_number: int) -> Optional[np.ndarray]:
        """
        Extract a specific frame from a recorded video.

        Args:
            session_id: Recording session ID.
            frame_number: 0-based frame index.

        Returns:
            BGR color frame as numpy array, or None if not found.
        """
        video_path = self._video_path(session_id)
        if not video_path.exists():
            return None

        cap = cv2.VideoCapture(str(video_path))
        try:
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if frame_number < 0 or frame_number >= total:
                return None

            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = cap.read()
            if not ret or frame is None:
                return None
            return frame
        finally:
            cap.release()

    def extract_frame_as_image(
        self, session_id: str, frame_number: int, name: str
    ) -> Optional[Path]:
        """
        Extract a video frame and save it as a named PNG in the extracted/ dir.

        Used when the user picks an arbitrary video frame for a template image.

        Args:
            session_id: Recording session ID.
            frame_number: 0-based frame index.
            name: Filename stem (e.g. 'boot_screen').

        Returns:
            Path to the saved PNG, or None on failure.
        """
        frame = self.get_frame(session_id, frame_number)
        if frame is None:
            return None

        out_path = self._extracted_dir(session_id) / f"{name}.png"
        cv2.imwrite(str(out_path), frame)
        logger.info(
            f"Extracted frame {frame_number} from session {session_id} → {out_path}"
        )
        return out_path

    # ── Session CRUD ─────────────────────────────────────────────

    def list_sessions(self) -> List[dict]:
        """List all saved recording sessions (metadata only, no events)."""
        sessions = []
        base = self._recordings_base()
        for session_dir in sorted(base.iterdir()):
            json_path = session_dir / "session.json"
            if json_path.exists():
                try:
                    data = json.loads(json_path.read_text(encoding="utf-8"))
                    # Return summary without full events list
                    sessions.append({
                        "id": data["id"],
                        "started_at": data["started_at"],
                        "ended_at": data.get("ended_at"),
                        "status": data.get("status", "stopped"),
                        "total_frames": data.get("total_frames", 0),
                        "fps": data.get("fps", 10.0),
                        "duration": data.get("duration", 0.0),
                        "event_count": len(data.get("events", [])),
                        "screenshot_count": data.get("screenshot_count", 0),
                    })
                except Exception as e:
                    logger.warning(f"Failed to load session {session_dir.name}: {e}")
        return sessions

    def get_session(self, session_id: str) -> Optional[RecordingSession]:
        """
        Load a recording session from disk.

        If the session is currently active (in-memory), returns that instead.
        """
        # If it's the active session, return from memory
        if self._session and self._session.id == session_id:
            return self._session

        json_path = self._session_json_path(session_id)
        if not json_path.exists():
            return None

        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            return RecordingSession.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load session {session_id}: {e}")
            return None

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a recording session and all its files.

        Cannot delete the currently active session.
        """
        if self._session and self._session.id == session_id and self.is_recording:
            raise RuntimeError("Cannot delete an active recording session")

        import shutil

        session_dir = self._session_dir(session_id)
        if session_dir.exists():
            shutil.rmtree(session_dir)
            logger.info(f"Deleted recording session: {session_id}")
            return True
        return False

    def get_screenshot_path(
        self, session_id: str, screenshot_index: int
    ) -> Optional[Path]:
        """Get the path to a specific auto-captured screenshot."""
        path = (
            self._screenshots_dir(session_id)
            / f"screenshot_{screenshot_index:04d}.png"
        )
        return path if path.exists() else None

    def get_extracted_path(self, session_id: str, name: str) -> Optional[Path]:
        """Get the path to a named extracted frame."""
        path = self._extracted_dir(session_id) / f"{name}.png"
        return path if path.exists() else None

    # ── Recording status ─────────────────────────────────────────

    def get_status(self) -> dict:
        """Get the current recording status."""
        if not self.is_recording:
            return {
                "recording": False,
                "session_id": None,
                "elapsed": 0,
                "event_count": 0,
                "frame_count": 0,
            }

        elapsed = time.time() - self._start_time
        return {
            "recording": True,
            "session_id": self._session.id,
            "elapsed": round(elapsed, 1),
            "event_count": len(self._session.events),
            "frame_count": self._frame_counter,
            "screenshot_count": self._session.screenshot_count,
        }

    # ── Internal ─────────────────────────────────────────────────

    def _recording_loop(self):
        """
        Background thread: grabs frames from the live feed and writes
        them to the VideoWriter at RECORDING_FPS.
        """
        from app.services.video_capture import video_capture

        interval = 1.0 / self.RECORDING_FPS
        logger.info(
            f"Recording loop started (target {self.RECORDING_FPS}fps, "
            f"interval {interval*1000:.0f}ms)"
        )

        while not self._stop_event.is_set():
            loop_start = time.time()

            try:
                result = video_capture.read_frame()
                if result is not None and self._video_writer:
                    color_frame, _ = result
                    self._video_writer.write(color_frame)
                    with self._lock:
                        self._frame_counter += 1
            except Exception as e:
                logger.error(f"Error in recording loop: {e}")

            # Sleep for remainder of interval
            elapsed = time.time() - loop_start
            sleep_time = max(0.001, interval - elapsed)
            self._stop_event.wait(timeout=sleep_time)

        logger.info(
            f"Recording loop exited ({self._frame_counter} frames written)"
        )

    def _save_session(self, session: RecordingSession):
        """Persist session metadata to JSON on disk."""
        json_path = self._session_json_path(session.id)
        json_path.write_text(
            json.dumps(session.to_dict(), indent=2), encoding="utf-8"
        )
        logger.debug(f"Session saved: {json_path}")


# Global singleton
macro_recorder = MacroRecorderService()
