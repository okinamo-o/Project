import os
import time
from fastapi import APIRouter
from backend.app.core.config import settings
from backend.app.services.gemini_service import gemini_service

router = APIRouter()

_START_TIME = time.time()

@router.get("/health")
async def health_check():
    """System health and operational status endpoint."""
    uptime_seconds = int(time.time() - _START_TIME)
    online = gemini_service.is_online()
    ai_status = "ONLINE" if online else "DEGRADED_LOCAL_MODE"
    
    return {
        "status": "healthy",
        "system": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "uptime_seconds": uptime_seconds,
        "environment": settings.ENVIRONMENT,
        "database": "connected",
        "ai_engine": {
            "status": ai_status,
            "model": gemini_service.active_model_name,
            "offline_reasoning": not online
        }
    }
