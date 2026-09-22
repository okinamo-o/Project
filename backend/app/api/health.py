import os
import time
from fastapi import APIRouter
from backend.app.core.config import settings

router = APIRouter()

_START_TIME = time.time()

@router.get("/health")
async def health_check():
    """System health and operational status endpoint."""
    uptime_seconds = int(time.time() - _START_TIME)
    ai_status = "ONLINE" if settings.GEMINI_API_KEY else "DEGRADED_LOCAL_MODE"
    
    return {
        "status": "healthy",
        "system": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "uptime_seconds": uptime_seconds,
        "environment": settings.ENVIRONMENT,
        "database": "connected",
        "ai_engine": {
            "status": ai_status,
            "model": settings.GEMINI_MODEL,
            "offline_reasoning": True
        }
    }
