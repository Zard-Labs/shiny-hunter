"""FastAPI main application."""
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pathlib import Path
import asyncio

from app.config import settings, get_frontend_dist_path, is_packaged, get_user_data_path
from app.database import init_db, get_db
from app.routes import automation, control, statistics, websocket, camera, templates
from app.services.esp32_manager import esp32_manager
from app.services.video_capture import video_capture
from app.services.opencv_detector import opencv_detector
from app.services.game_engine import game_engine
from app.utils.logger import logger

# Create FastAPI app
app = FastAPI(
    title="Shiny Charmander Hunter",
    description="Automated shiny hunting system for Pokemon Red on Switch",
    version="1.1.1"
)

# Configure CORS - in desktop mode, allow all origins since Electron loads from localhost
cors_origins = settings.cors_origins
if is_packaged():
    cors_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (encounters directory)
if is_packaged():
    encounters_dir = get_user_data_path() / settings.screenshot_directory
else:
    encounters_dir = Path(__file__).parent.parent / settings.screenshot_directory
encounters_dir.mkdir(exist_ok=True)
app.mount("/encounters", StaticFiles(directory=str(encounters_dir)), name="encounters")

# Register routers
app.include_router(automation.router)
app.include_router(control.router)
app.include_router(statistics.router)
app.include_router(websocket.router)
app.include_router(camera.router)
app.include_router(templates.router)

# Background task for running automation
automation_task = None


async def run_automation():
    """Background task that runs automation loop."""
    logger.info("Automation loop started")
    
    while game_engine.is_running:
        try:
            # Get database session
            db = next(get_db())
            
            # Run one cycle
            should_stop = await game_engine.run_cycle(db)
            
            if should_stop:
                logger.info("Shiny found! Stopping automation")
                break
            
            # Small delay to prevent CPU overload
            await asyncio.sleep(0.1)
        
        except Exception as e:
            logger.error(f"Error in automation loop: {e}")
            await asyncio.sleep(1)  # Wait before retrying
    
    logger.info("Automation loop stopped")


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("=" * 60)
    logger.info("  Shiny Charmander Hunter - Starting Up")
    logger.info("=" * 60)
    
    # Initialize database
    init_db()
    logger.info("[OK] Database initialized")
    
    # Load OpenCV templates
    opencv_detector.load_templates()
    logger.info("[OK] OpenCV templates loaded")
    
    # Connect to ESP32
    if esp32_manager.connect():
        logger.info("[OK] ESP32-S3 connected")
    else:
        logger.warning("[!] ESP32-S3 not connected (will retry on demand)")
    
    # Open video capture
    if video_capture.open():
        logger.info("[OK] Video capture opened")
    else:
        logger.warning("[!] Video capture not available (will retry on demand)")
    
    logger.info("=" * 60)
    logger.info(f"  Server ready at http://{settings.host}:{settings.port}")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    logger.info("Shutting down...")
    
    # Stop automation if running
    if game_engine.is_running:
        game_engine.stop()
    
    # Disconnect ESP32
    esp32_manager.disconnect()
    
    # Close video capture
    video_capture.close()
    
    logger.info("Shutdown complete")


@app.post("/api/automation/start-with-task")
async def start_automation_with_task(background_tasks: BackgroundTasks):
    """Start automation and run background task."""
    global automation_task
    
    if game_engine.is_running:
        return {"status": "already_running", "session_id": game_engine.session_id}
    
    # Get database session
    db = next(get_db())
    
    # Start automation
    session_id = game_engine.start(db)
    
    # Start background task
    background_tasks.add_task(run_automation)
    
    return {
        "status": "started",
        "session_id": session_id,
        "message": "Automation started successfully"
    }


# ── Frontend SPA Serving ──────────────────────────────────
# Serve the built React frontend. In packaged desktop mode, the frontend
# is bundled as static files. The SPA catch-all must be registered AFTER
# all API routes to avoid intercepting /api/* and /ws/* requests.

_frontend_dist = get_frontend_dist_path()
_frontend_index = _frontend_dist / "index.html"


@app.get("/")
async def root():
    """Serve React SPA index.html if available, otherwise return API info."""
    if _frontend_index.exists():
        return FileResponse(str(_frontend_index), media_type="text/html")
    return {
        "name": "Shiny Charmander Hunter API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "automation": "/api/automation",
            "control": "/api/control",
            "statistics": "/api/statistics",
            "websocket": "/ws",
            "docs": "/docs"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "services": {
            "esp32": esp32_manager.connected,
            "camera": video_capture.is_open,
            "automation": game_engine.is_running
        }
    }


# Mount React static assets (JS, CSS, images) AFTER all routes
# This must be last to avoid catching API routes
if _frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(_frontend_dist / "assets")), name="frontend-assets")
    
    # SPA catch-all: any non-API, non-WS path returns index.html
    # This handles client-side routing in React
    @app.get("/{full_path:path}")
    async def spa_catchall(full_path: str):
        """Catch-all route for React SPA client-side routing."""
        # Don't intercept API, WebSocket, docs, or static file paths
        if full_path.startswith(("api/", "ws", "docs", "openapi", "encounters/")):
            return None
        if _frontend_index.exists():
            return FileResponse(str(_frontend_index), media_type="text/html")
        return {"error": "Frontend not found"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )
