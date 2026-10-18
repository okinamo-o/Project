import asyncio
import base64
from fastapi.responses import StreamingResponse
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

# In-memory latest snapshot cache and stream bytes cache
_LATEST_SNAPSHOTS: Dict[str, Dict[str, Any]] = {}
_LATEST_STREAM_BYTES: Dict[str, bytes] = {}
_LAST_DB_EVENT: Dict[str, Dict[str, Any]] = {}

@router.post("/event")
async def ingest_vision_event(
    event_data: VisionEventCreate,
    db: AsyncSession = Depends(get_db)
):
    """Ingest structured vision event from local OpenCV vision service at up to 30 FPS."""
    now = datetime.datetime.now(datetime.timezone.utc)
    ts = now.isoformat()

    # Pre-decode JPEG bytes once so the 30 FPS MJPEG stream generator doesn't repeat base64 decoding
    raw_jpeg = None
    if event_data.snapshot_base64:
        b64_str = event_data.snapshot_base64
        if b64_str.startswith("data:image"):
            b64_str = b64_str.split(",", 1)[-1]
        try:
            raw_jpeg = base64.b64decode(b64_str)
        except Exception:
            pass

    # Update in-memory snapshot cache and stream bytes for ultra-fluid 30 FPS video stream
    _LATEST_SNAPSHOTS[event_data.room_id] = {
        "room_id": event_data.room_id,
        "timestamp": ts,
        "event_type": event_data.event_type,
        "occupancy": event_data.occupancy_count,
        "snapshot_base64": event_data.snapshot_base64
    }
    if raw_jpeg:
        _LATEST_STREAM_BYTES[event_data.room_id] = raw_jpeg

    # Throttle DB writes & Fusion evaluation to state changes or 1Hz heartbeat (avoids SQLite disk thrashing at 30 FPS)
    last_info = _LAST_DB_EVENT.get(event_data.room_id)
    should_persist = (
        last_info is None or
        last_info["event_type"] != event_data.event_type or
        last_info["occupancy"] != event_data.occupancy_count or
        (now - last_info["time"]).total_seconds() >= 1.0
    )

    if should_persist:
        _LAST_DB_EVENT[event_data.room_id] = {
            "event_type": event_data.event_type,
            "occupancy": event_data.occupancy_count,
            "time": now
        }

        meta = {
            "occupancy_count": event_data.occupancy_count,
            "bounding_boxes": event_data.bounding_boxes,
            **event_data.metadata
        }

        db_event = VisionEvent(
            room_id=event_data.room_id,
            timestamp=now,
            event_type=event_data.event_type,
            confidence=event_data.confidence,
            event_metadata=meta
        )
        db.add(db_event)
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.warning(f"Could not commit vision event to DB: {e}")

        # Record in fusion engine & evaluate
        fusion_engine.record_signal(event_data.room_id, "vision", {
            "event_type": event_data.event_type,
            "occupancy": event_data.occupancy_count,
            "confidence": event_data.confidence
        })
        await fusion_engine.evaluate_room(event_data.room_id, db)

        # Sync occupancy to Firebase Realtime Database
        sync_telemetry_to_firebase(event_data.room_id, {
            "occupancy": event_data.occupancy_count
        })

        # Broadcast via WebSocket on state changes/heartbeats
        payload = {
            "type": "VISION_EVENT",
            "room_id": event_data.room_id,
            "event_type": event_data.event_type,
            "occupancy": event_data.occupancy_count,
            "confidence": event_data.confidence,
            "snapshot_base64": event_data.snapshot_base64,
            "timestamp": ts
        }
        await event_manager.broadcast(payload)

    return {"status": "ingested", "room_id": event_data.room_id}

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

@router.get("/stream/{room_id}")
async def stream_room_camera(room_id: str):
    """Real-time multipart MJPEG 30 FPS video stream from the latest edge vision frames."""
    async def frame_generator():
        last_ts = None
        try:
            while True:
                snap = _LATEST_SNAPSHOTS.get(room_id)
                if snap:
                    cur_ts = snap.get("timestamp")
                    if cur_ts != last_ts:
                        last_ts = cur_ts
                        raw_bytes = _LATEST_STREAM_BYTES.get(room_id)
                        if not raw_bytes and snap.get("snapshot_base64"):
                            b64_data = snap["snapshot_base64"]
                            if b64_data.startswith("data:image"):
                                b64_data = b64_data.split(",", 1)[-1]
                            try:
                                raw_bytes = base64.b64decode(b64_data)
                                snap["raw_jpeg"] = raw_bytes
                            except Exception:
                                pass
                        if raw_bytes:
                            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + raw_bytes + b"\r\n")
                await asyncio.sleep(0.015)
        except (asyncio.CancelledError, GeneratorExit):
            pass

    return StreamingResponse(
        frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )
