import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import subprocess
import sys
import os

import asyncio

MANAGED_SERVICES = [
    {"name": "iot_generator", "cmd": [sys.executable, "iot/emulator/telemetry_generator.py"]},
    {"name": "vision_service", "cmd": [sys.executable, "ai/vision/vision_service.py", "--interval", "0.022"]},
    {"name": "audio_service", "cmd": [sys.executable, "ai/audio/audio_service.py"]},
    {"name": "wokwi_bridge", "cmd": [sys.executable, "iot/bridge/wokwi_bridge.py"]},
]

async def process_watchdog(project_root: str):
    """Resilient supervisor: keeps background IoT, Vision, and Audio services alive."""
    while True:
        await asyncio.sleep(3.0)
        for svc in MANAGED_SERVICES:
            proc = svc.get("proc")
            if proc is None or proc.poll() is not None:
                code = proc.returncode if proc else "None"
                logger.warning(f"[SUPERVISOR] Service '{svc['name']}' not running (exit code: {code}). Restarting...")
                try:
                    svc["proc"] = subprocess.Popen(svc["cmd"], cwd=project_root)
                    logger.info(f"[SUPERVISOR] Spawned '{svc['name']}' (PID {svc['proc'].pid})")
                except Exception as ex:
                    logger.error(f"[SUPERVISOR] Failed to restart '{svc['name']}': {ex}")

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

    # --- AUTO-START SENSORS WITH RESILIENT WATCHDOG ---
    watchdog_task = None
    if os.environ.get("TESTING") != "1":
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        for svc in MANAGED_SERVICES:
            try:
                svc["proc"] = subprocess.Popen(svc["cmd"], cwd=project_root)
                logger.info(f"[NEXUS] Started '{svc['name']}' (PID {svc['proc'].pid})")
            except Exception as e:
                logger.error(f"[NEXUS] Could not start '{svc['name']}': {e}")
        watchdog_task = asyncio.create_task(process_watchdog(project_root))
    # --------------------------------------------------

    yield
    logger.info("[NEXUS] Shutting down services.")
    if watchdog_task:
        watchdog_task.cancel()
    for svc in MANAGED_SERVICES:
        p = svc.get("proc")
        if p and p.poll() is None:
            try:
                p.terminate()
            except Exception:
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
        host="0.0.0.0",
        port=settings.BACKEND_PORT,
        reload=False
    )
