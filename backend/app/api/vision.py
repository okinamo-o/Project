import datetime
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from backend.app.db.database import get_db
from backend.app.models.schema import VisionEvent
from backend.app.core.events import event_manager
from backend.app.fusion.engine import fusion_engine
from backend.app.db.firebase_client import sync_telemetry_to_firebase

router = APIRouter()
logger = logging.getLogger("nexus.api.vision")

class VisionEventCreate(BaseModel):
    room_id: str = "lab_02"
    event_type: str = Field(..., description="PERSON_DETECTED, OCCUPANCY_CHANGE, SUDDEN_MOVEMENT, OBJECT_UNATTENDED")
    confidence: float = 0.90
    occupancy_count: int = 1
    bounding_boxes: List[Dict[str, Any]] = []
    snapshot_base64: Optional[str] = None
    metadata: Dict[str, Any] = {}

# In-memory latest snapshot cache for fast dashboard view
_LATEST_SNAPSHOTS: Dict[str, Dict[str, Any]] = {}

@router.post("/event")
async def ingest_vision_event(
    event_data: VisionEventCreate,
    db: AsyncSession = Depends(get_db)
):
    """Ingest structured vision event from local OpenCV vision service."""
    ts = datetime.datetime.now(datetime.timezone.utc)
    
    # Store event in DB
    meta = {
        "occupancy_count": event_data.occupancy_count,
        "bounding_boxes": event_data.bounding_boxes,
        **event_data.metadata
    }
    
    db_event = VisionEvent(
        room_id=event_data.room_id,
        timestamp=ts,
        event_type=event_data.event_type,
        confidence=event_data.confidence,
        event_metadata=meta
    )
    db.add(db_event)
    await db.commit()

    # Record in fusion engine
    fusion_engine.record_signal(event_data.room_id, "vision", {
        "event_type": event_data.event_type,
        "occupancy": event_data.occupancy_count,
        "confidence": event_data.confidence
    })

    # Cache latest snapshot
    _LATEST_SNAPSHOTS[event_data.room_id] = {
        "room_id": event_data.room_id,
        "timestamp": ts.isoformat(),
        "event_type": event_data.event_type,
        "occupancy": event_data.occupancy_count,
        "snapshot_base64": event_data.snapshot_base64
    }

    # Sync occupancy to Firebase Realtime Database
    sync_telemetry_to_firebase(event_data.room_id, {
        "occupancy": event_data.occupancy_count
    })

    # Broadcast via WebSocket
    payload = {
        "type": "VISION_EVENT",
        "room_id": event_data.room_id,
        "event_type": event_data.event_type,
        "occupancy": event_data.occupancy_count,
        "confidence": event_data.confidence,
        "snapshot_base64": event_data.snapshot_base64,
        "timestamp": ts.isoformat()
    }
    await event_manager.broadcast(payload)

    # Evaluate fusion
    await fusion_engine.evaluate_room(event_data.room_id, db)

    return {"status": "ingested", "id": db_event.id, "event": payload}

@router.get("/latest/{room_id}")
async def get_latest_vision(
    room_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get the latest vision detections and occupancy for a room."""
    query = (
        select(VisionEvent)
        .where(VisionEvent.room_id == room_id)
        .order_by(desc(VisionEvent.timestamp))
        .limit(1)
    )
    res = await db.execute(query)
    ev = res.scalar_one_or_none()
    if not ev:
        return {
            "room_id": room_id,
            "event_type": "NO_DETECTION",
            "occupancy": 0,
            "confidence": 1.0,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
    return {
        "room_id": ev.room_id,
        "event_type": ev.event_type,
        "confidence": ev.confidence,
        "occupancy": ev.event_metadata.get("occupancy_count", 0) if ev.event_metadata else 0,
        "metadata": ev.event_metadata,
        "timestamp": ev.timestamp.isoformat()
    }

@router.get("/snapshot/{room_id}")
async def get_room_snapshot(room_id: str):
    """Retrieve latest video frame snapshot for visual confirmation."""
    if room_id in _LATEST_SNAPSHOTS:
        return _LATEST_SNAPSHOTS[room_id]
    return {
        "room_id": room_id,
        "status": "NO_FRAME_CAPTURED",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
