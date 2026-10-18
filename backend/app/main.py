import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import subprocess
import sys
import os

bg_processes = []

from backend.app.core.config import settings
from backend.app.core.events import event_manager
from backend.app.db.database import engine, Base, AsyncSessionLocal
from backend.app.db.seed import seed_initial_data
from backend.app.api.health import router as health_router
from backend.app.api.rooms import router as rooms_router
from backend.app.api.sensors import router as sensors_router
from backend.app.api.incidents import router as incidents_router
from backend.app.api.prediction import router as prediction_router
from backend.app.api.vision import router as vision_router
from backend.app.api.audio import router as audio_router
from backend.app.api.ai import router as ai_router
from backend.app.api.simulation import router as simulation_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger("nexus.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing NEXUS Database & Schema...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with AsyncSessionLocal() as session:
        await seed_initial_data(session)
    
    logger.info("[NEXUS] Systems initialized. Listening for real-time telemetry.")

    # --- AUTO-START SENSORS ---
    if os.environ.get("TESTING") != "1":
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        try:
            bg_processes.append(subprocess.Popen([sys.executable, "iot/emulator/telemetry_generator.py"], cwd=project_root))
            bg_processes.append(subprocess.Popen([sys.executable, "ai/vision/vision_service.py", "--interval", "0.2"], cwd=project_root))
            bg_processes.append(subprocess.Popen([sys.executable, "ai/audio/audio_service.py"], cwd=project_root))
            logger.info("[NEXUS] Background data generators started automatically.")
        except Exception as e:
            logger.error(f"[NEXUS] Could not start background generators: {e}")
    # --------------------------

    yield
    logger.info("[NEXUS] Shutting down services.")
    for p in bg_processes:
        try:
            p.terminate()
        except:
            pass
    await engine.dispose()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Multimodal AI Digital Twin for Intelligent Environmental Monitoring, Prediction and Decision Support",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
app.include_router(health_router, prefix="/api", tags=["Health"])
app.include_router(rooms_router, prefix="/api/rooms", tags=["Rooms"])
app.include_router(sensors_router, prefix="/api/sensors", tags=["Sensors"])
app.include_router(incidents_router, prefix="/api/incidents", tags=["Incidents"])
app.include_router(prediction_router, prefix="/api/prediction", tags=["Prediction"])
app.include_router(vision_router, prefix="/api/vision", tags=["Vision"])
app.include_router(audio_router, prefix="/api/audio", tags=["Audio"])
app.include_router(ai_router, prefix="/api/ai", tags=["AI"])
app.include_router(simulation_router, prefix="/api/simulation", tags=["Simulation"])

@app.websocket("/ws/telemetry")
async def websocket_telemetry_endpoint(websocket: WebSocket):
    """Real-time bi-directional telemetry and event stream for 3D Twin and UI."""
    await event_manager.connect(websocket)
    try:
        # Send initial welcome and ping
        await websocket.send_json({
            "type": "SYSTEM_CONNECTED",
            "message": "NEXUS Real-Time Telemetry Stream Established",
            "version": settings.VERSION
        })
        while True:
            # Handle incoming client commands / pings
            data = await websocket.receive_text()
            # Echo or process if needed
    except WebSocketDisconnect:
        await event_manager.disconnect(websocket)
    except Exception as e:
        logger.warning(f"[WS] Connection error: {e}")
        await event_manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=False
    )
