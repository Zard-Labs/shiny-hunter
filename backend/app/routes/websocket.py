"""WebSocket handler for real-time updates.

Uses a single broadcast pattern: one background task reads frames and
broadcasts to all connected clients, instead of each client reading independently.

Video frames are sent as raw binary JPEG bytes (no base64/JSON overhead).
Non-video messages (state updates, encounters, etc.) are sent as JSON text.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import json

from app.config import settings
from app.services.game_engine import game_engine
from app.services.video_capture import video_capture
from app.utils.logger import logger


router = APIRouter()


class ConnectionManager:
    """Manage WebSocket connections with single-producer broadcast."""
    
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self._broadcast_task: asyncio.Task | None = None
        self._last_frame_id: int = -1
        self._annotation_counter: int = 0
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        count = len(self.active_connections)
        logger.info(f"WebSocket client connected. Total: {count}")
        
        # Start broadcast task when first client connects
        if count == 1:
            self._start_broadcast()
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        count = len(self.active_connections)
        logger.info(f"WebSocket client disconnected. Total: {count}")
        
        # Stop broadcast task when last client disconnects
        if count == 0:
            self._stop_broadcast()
    
    def _start_broadcast(self):
        """Start the single video broadcast background task."""
        if self._broadcast_task and not self._broadcast_task.done():
            return
        self._broadcast_task = asyncio.create_task(self._broadcast_loop())
        logger.info("Video broadcast task started")
    
    def _stop_broadcast(self):
        """Stop the video broadcast background task."""
        if self._broadcast_task and not self._broadcast_task.done():
            self._broadcast_task.cancel()
            logger.info("Video broadcast task stopped")
        self._broadcast_task = None
    
    async def _broadcast_loop(self):
        """
        Single broadcast loop: reads one frame, sends raw JPEG to all clients.
        Runs at ~30 FPS for real-time feel.
        
        Video frames → binary WebSocket messages (raw JPEG bytes)
        Annotations → JSON text messages sent at lower frequency (~2/sec)
        """
        logger.info("Broadcast loop running (30fps binary)")
        frame_count = 0
        
        try:
            while self.active_connections:
                try:
                    # Get pre-encoded JPEG from the capture thread
                    result = video_capture.get_encoded_jpeg(quality=70)
                    
                    if result is not None:
                        jpeg_bytes, frame_id = result
                        
                        # Only broadcast if this is a new frame
                        if frame_id != self._last_frame_id:
                            self._last_frame_id = frame_id
                            
                            # Send raw JPEG bytes as binary to all clients (parallel)
                            await self._broadcast_binary(jpeg_bytes)
                            
                            frame_count += 1
                            self._annotation_counter += 1
                            
                            # Send annotations as JSON at lower frequency (~2/sec)
                            if self._annotation_counter >= 15:
                                self._annotation_counter = 0
                                annotations = {
                                    "shiny_zone": settings.shiny_zone if settings.shiny_zone else {
                                        "upper_x": 264, "upper_y": 109, 
                                        "lower_x": 312, "lower_y": 151
                                    },
                                    "gender_zone": settings.gender_zone if settings.gender_zone else {
                                        "upper_x": 284, "upper_y": 68, 
                                        "lower_x": 311, "lower_y": 92
                                    }
                                }
                                await self._broadcast_json({
                                    "type": "annotations",
                                    "data": annotations
                                })
                            
                            if frame_count % 300 == 0:
                                logger.info(
                                    f"Broadcast: {frame_count} frames sent to "
                                    f"{len(self.active_connections)} clients"
                                )
                    
                    # Target ~30 FPS broadcast rate
                    await asyncio.sleep(0.033)
                
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.error(f"Error in broadcast loop: {e}")
                    await asyncio.sleep(0.5)
        
        except asyncio.CancelledError:
            logger.info("Broadcast loop cancelled")
        
        logger.info(f"Broadcast loop exited (sent {frame_count} total frames)")
    
    async def _broadcast_binary(self, data: bytes):
        """Broadcast binary data to all connected clients in parallel."""
        if not self.active_connections:
            return
        
        # Send to all clients simultaneously
        results = await asyncio.gather(
            *[self._safe_send_bytes(conn, data) for conn in self.active_connections],
            return_exceptions=True
        )
        
        # Clean up disconnected clients
        disconnected = []
        for conn, result in zip(self.active_connections, results):
            if isinstance(result, Exception):
                disconnected.append(conn)
        
        for conn in disconnected:
            self.disconnect(conn)
    
    async def _safe_send_bytes(self, websocket: WebSocket, data: bytes):
        """Send binary data to a client, raising on failure."""
        try:
            await websocket.send_bytes(data)
        except Exception:
            raise  # Let gather handle it
    
    async def _broadcast_json(self, message: dict):
        """Broadcast a JSON message to all connected clients in parallel."""
        if not self.active_connections:
            return
        
        json_str = json.dumps(message)
        
        results = await asyncio.gather(
            *[self._safe_send_text(conn, json_str) for conn in self.active_connections],
            return_exceptions=True
        )
        
        # Clean up disconnected clients
        disconnected = []
        for conn, result in zip(self.active_connections, results):
            if isinstance(result, Exception):
                disconnected.append(conn)
        
        for conn in disconnected:
            self.disconnect(conn)
    
    async def _safe_send_text(self, websocket: WebSocket, text: str):
        """Send text data to a client, raising on failure."""
        try:
            await websocket.send_text(text)
        except Exception:
            raise  # Let gather handle it
    
    async def broadcast(self, message: dict):
        """Broadcast a non-video message to all connected clients."""
        await self._broadcast_json(message)


manager = ConnectionManager()


# Set game engine WebSocket callback
async def ws_callback(message: dict):
    """Callback for game engine to send WebSocket updates."""
    await manager.broadcast(message)


game_engine.set_websocket_callback(ws_callback)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time updates.
    
    Client receives two types of messages:
    - Binary messages: raw JPEG video frames (no base64, no JSON wrapping)
    - Text messages: JSON for state updates, encounters, annotations, etc.
      - {"type": "status", "data": {...}}
      - {"type": "state_update", "data": {...}}
      - {"type": "encounter_detected", "data": {...}}
      - {"type": "shiny_found", "data": {...}}
      - {"type": "annotations", "data": {"shiny_zone": {...}, "gender_zone": {...}}}
    
    Video frames are broadcast from a single background task (not per-client).
    """
    await manager.connect(websocket)
    
    try:
        # Send initial status
        status = game_engine.get_status()
        await websocket.send_json({
            "type": "status",
            "data": status
        })
        
        # Only handle incoming messages — video is broadcast separately
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                msg_type = message.get("type")
                
                if msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
                
                elif msg_type == "get_status":
                    status = game_engine.get_status()
                    await websocket.send_json({"type": "status", "data": status})
            
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                logger.warning("Invalid JSON received from websocket")
            except Exception as e:
                logger.error(f"Error handling websocket message: {e}")
                break
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)
