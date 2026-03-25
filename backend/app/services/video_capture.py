"""Video capture service for Elgato Neo capture card.

Uses a dedicated background thread for frame capture to avoid blocking
the async event loop. Provides thread-safe frame access and auto-recovery.
"""
import cv2
import numpy as np
import threading
import time
from typing import Optional, Tuple
from app.config import settings
from app.utils.logger import logger


class VideoCapture:
    """
    Video capture service with dedicated capture thread.
    
    Architecture:
    - A background thread continuously reads frames from cv2.VideoCapture
    - The latest frame is stored in a thread-safe buffer
    - read_frame() returns the latest cached frame (non-blocking)
    - Auto-recovery reopens the device after sustained failures
    """
    
    def __init__(self):
        self.cap: Optional[cv2.VideoCapture] = None
        self.camera_index = settings.camera_index
        self.is_open = False
        self.frame_count = 0
        
        # Thread-safe frame buffer
        self._lock = threading.Lock()
        self._latest_frame: Optional[np.ndarray] = None
        self._latest_gray: Optional[np.ndarray] = None
        self._frame_id: int = 0  # Increments on each new frame
        
        # Capture thread
        self._capture_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Auto-recovery settings
        self._consecutive_failures = 0
        self._max_failures_before_recovery = 90  # ~3 seconds at 30fps
        self._recovery_backoff = 1.0
        self._max_recovery_backoff = 10.0
        
        # Pre-encoded JPEG for WebSocket broadcast (encode once, send to all)
        self._encoded_jpeg: Optional[bytes] = None
        self._encoded_frame_id: int = -1  # Which frame_id was encoded
    
    def open(self) -> bool:
        """
        Open video capture device and start the capture thread.
        
        Returns:
            True if opened successfully, False otherwise
        """
        # Stop any existing capture thread
        self._stop_capture_thread()
        
        try:
            # Try DirectShow first (best for capture cards on Windows)
            self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            
            if not self.cap.isOpened():
                logger.warning("DirectShow failed, trying MSMF backend...")
                self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_MSMF)
            
            if not self.cap.isOpened():
                logger.warning("MSMF failed, trying default backend...")
                self.cap = cv2.VideoCapture(self.camera_index)
            
            if not self.cap.isOpened():
                logger.error(f"Failed to open camera at index {self.camera_index} with all backends")
                return False
            
            # Set camera properties for best quality
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            
            # Reduce internal buffer size to minimize latency
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            # Warmup: read and discard first few frames
            for _ in range(5):
                self.cap.read()
            
            self.is_open = True
            self.frame_count = 0
            self._consecutive_failures = 0
            self._recovery_backoff = 1.0
            
            # Get actual properties
            width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            
            logger.info(f"[OK] Video capture opened: {width}x{height} @ {fps}fps")
            
            # Start the background capture thread
            self._start_capture_thread()
            
            return True
        
        except Exception as e:
            logger.error(f"Error opening video capture: {e}")
            return False
    
    def close(self):
        """Close video capture device and stop the capture thread."""
        self._stop_capture_thread()
        
        if self.cap:
            self.cap.release()
            self.cap = None
        
        self.is_open = False
        
        # Clear the frame buffer
        with self._lock:
            self._latest_frame = None
            self._latest_gray = None
            self._encoded_jpeg = None
        
        logger.info("Video capture closed")
    
    def _start_capture_thread(self):
        """Start the background frame capture thread."""
        self._stop_event.clear()
        self._capture_thread = threading.Thread(
            target=self._capture_loop,
            name="VideoCapture-Thread",
            daemon=True
        )
        self._capture_thread.start()
        logger.info("Capture thread started")
    
    def _stop_capture_thread(self):
        """Stop the background frame capture thread."""
        if self._capture_thread and self._capture_thread.is_alive():
            self._stop_event.set()
            self._capture_thread.join(timeout=3.0)
            if self._capture_thread.is_alive():
                logger.warning("Capture thread did not stop cleanly")
            else:
                logger.info("Capture thread stopped")
        self._capture_thread = None
    
    def _capture_loop(self):
        """
        Background thread that continuously reads frames from the capture device.
        Runs at device framerate (~30fps). Stores latest frame in thread-safe buffer.
        Handles auto-recovery on sustained failures.
        """
        logger.info("Capture loop running")
        
        while not self._stop_event.is_set():
            if not self.cap or not self.cap.isOpened():
                # Device lost — attempt recovery
                self._handle_recovery()
                continue
            
            try:
                ret, raw_frame = self.cap.read()
                
                if not ret or raw_frame is None:
                    self._consecutive_failures += 1
                    
                    if self._consecutive_failures == 30:
                        logger.warning("30 consecutive frame read failures")
                    
                    if self._consecutive_failures >= self._max_failures_before_recovery:
                        logger.error(f"Capture failed {self._consecutive_failures} times, attempting recovery...")
                        self._handle_recovery()
                    else:
                        # Brief sleep to avoid tight-looping on failures
                        time.sleep(0.01)
                    continue
                
                # Success — process the frame
                self._consecutive_failures = 0
                self._recovery_backoff = 1.0
                self.frame_count += 1
                
                # Crop 16:9 to 4:3 (remove black bars from capture card)
                h, w = raw_frame.shape[:2]
                crop_x = (w - int(h * (4 / 3))) // 2
                if crop_x > 0:
                    raw_frame = raw_frame[:, crop_x : w - crop_x]
                
                # Resize to standard 640x480
                frame = cv2.resize(raw_frame, (640, 480))
                
                # Create grayscale version for template matching
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                # Store in thread-safe buffer
                with self._lock:
                    self._latest_frame = frame
                    self._latest_gray = gray
                    self._frame_id += 1
                
                if self.frame_count % 300 == 0:
                    logger.info(f"Capture thread: {self.frame_count} frames captured")
                
                # Small sleep to yield CPU (~30fps target)
                # The cap.read() itself is blocking and paces us, but add tiny sleep
                # to ensure other threads can acquire the lock
                time.sleep(0.001)
            
            except Exception as e:
                logger.error(f"Error in capture loop: {e}")
                self._consecutive_failures += 1
                time.sleep(0.1)
        
        logger.info("Capture loop exited")
    
    def _handle_recovery(self):
        """
        Attempt to recover from capture device failure.
        Uses exponential backoff between attempts.
        """
        logger.info(f"Attempting capture recovery (backoff: {self._recovery_backoff:.1f}s)...")
        
        # Release existing capture
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None
        
        # Wait before retrying (exponential backoff)
        self._stop_event.wait(timeout=self._recovery_backoff)
        if self._stop_event.is_set():
            return
        
        # Try to reopen
        try:
            self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            
            if not self.cap.isOpened():
                self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_MSMF)
            
            if not self.cap.isOpened():
                self.cap = cv2.VideoCapture(self.camera_index)
            
            if self.cap.isOpened():
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
                self.cap.set(cv2.CAP_PROP_FPS, 30)
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                
                # Warmup
                for _ in range(5):
                    self.cap.read()
                
                self._consecutive_failures = 0
                self._recovery_backoff = 1.0
                self.is_open = True
                
                width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = self.cap.get(cv2.CAP_PROP_FPS)
                logger.info(f"[OK] Capture recovered: {width}x{height} @ {fps}fps")
            else:
                raise RuntimeError("All backends failed")
        
        except Exception as e:
            logger.warning(f"Recovery failed: {e}")
            self.is_open = False
            # Increase backoff for next attempt
            self._recovery_backoff = min(
                self._recovery_backoff * 2, 
                self._max_recovery_backoff
            )
            self._consecutive_failures = 0  # Reset to restart the failure counter
    
    def read_frame(self) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """
        Read the latest frame from the capture buffer (non-blocking).
        
        This does NOT call cv2.VideoCapture.read() directly — it returns
        the latest frame captured by the background thread.
        
        Returns:
            Tuple of (color_frame, gray_frame) if available, None otherwise
        """
        with self._lock:
            if self._latest_frame is None:
                return None
            # Return copies to avoid race conditions with the capture thread
            return self._latest_frame.copy(), self._latest_gray.copy()
    
    def get_encoded_jpeg(self, quality: int = 80) -> Optional[Tuple[bytes, int]]:
        """
        Get the latest frame as JPEG bytes, encoding only once per new frame.
        Used by the WebSocket broadcast to avoid encoding per-client.
        
        Args:
            quality: JPEG quality (0-100)
        
        Returns:
            Tuple of (jpeg_bytes, frame_id) if available, None otherwise
        """
        with self._lock:
            if self._latest_frame is None:
                return None
            
            current_id = self._frame_id
            
            # Only re-encode if we have a new frame
            if self._encoded_frame_id != current_id:
                ret, buffer = cv2.imencode(
                    '.jpg', 
                    self._latest_frame, 
                    [cv2.IMWRITE_JPEG_QUALITY, quality]
                )
                if ret:
                    self._encoded_jpeg = buffer.tobytes()
                    self._encoded_frame_id = current_id
                else:
                    return None
            
            return self._encoded_jpeg, current_id
    
    def flush_buffer(self, num_frames: int = 15):
        """
        Flush camera buffer by waiting for fresh frames.
        
        With the threaded capture, this just waits for the buffer to refresh.
        The capture thread is always reading the latest frames.
        
        Args:
            num_frames: Approximate number of frames to wait for
        """
        if not self.is_open:
            return
        
        logger.debug(f"Flushing buffer (waiting ~{num_frames/30:.1f}s for fresh frames)")
        # Wait for approximately num_frames worth of time at 30fps
        time.sleep(num_frames / 30.0)
    
    def switch_camera(self, new_index: int) -> bool:
        """
        Thread-safe camera switching.
        
        Args:
            new_index: New camera device index
        
        Returns:
            True if switch successful, False otherwise
        """
        logger.info(f"Switching camera from {self.camera_index} to {new_index}")
        
        old_index = self.camera_index
        self.close()
        
        self.camera_index = new_index
        success = self.open()
        
        if not success:
            logger.error(f"Failed to open camera {new_index}, reverting to {old_index}")
            self.camera_index = old_index
            self.open()
            return False
        
        return True


# Global video capture instance
video_capture = VideoCapture()
