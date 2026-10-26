import datetime
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from backend.app.db.database import get_db
from backend.app.models.schema import AudioEvent
from backend.app.core.events import event_manager
from backend.app.fusion.engine import fusion_engine

router = APIRouter()
logger = logging.getLogger("nexus.api.audio")

class AudioEventCreate(BaseModel):
    room_id: str = "lab_02"
    event_type: str = Field(..., description="NORMAL, SPEECH, ALARM, IMPACT, KNOCK, SUDDEN_NOISE, MACHINE_ANOMALY")
    confidence: float = 0.88
    rms_energy: float = 0.05
    spectral_centroid: float = 1200.0
    zero_crossing_rate: float = 0.08
    metadata: Dict[str, Any] = {}

@router.post("/event")
async def ingest_audio_event(
    event_data: AudioEventCreate,
    db: AsyncSession = Depends(get_db)
):
    """Ingest acoustic classification event from local DSP audio engine."""
    ts = datetime.datetime.now(datetime.timezone.utc)

    meta = {
        "rms_energy": event_data.rms_energy,
        "spectral_centroid": event_data.spectral_centroid,
        "zero_crossing_rate": event_data.zero_crossing_rate,
        **event_data.metadata
    }

    db_event = AudioEvent(
        room_id=event_data.room_id,
        timestamp=ts,
        event_type=event_data.event_type,
        confidence=event_data.confidence,
        event_metadata=meta
    )
    db.add(db_event)
    await db.commit()

    # Record in fusion engine
    fusion_engine.record_signal(event_data.room_id, "audio", {
        "event_type": event_data.event_type,
        "rms_energy": event_data.rms_energy,
        "spectral_centroid": event_data.spectral_centroid,
        "confidence": event_data.confidence
    })

    # Broadcast via WebSocket
    payload = {
        "type": "AUDIO_EVENT",
        "room_id": event_data.room_id,
        "event_type": event_data.event_type,
        "rms_energy": event_data.rms_energy,
        "spectral_centroid": event_data.spectral_centroid,
        "confidence": event_data.confidence,
        "timestamp": ts.isoformat()
    }
    await event_manager.broadcast(payload)

    # Evaluate fusion
    await fusion_engine.evaluate_room(event_data.room_id, db)

    return {"status": "ingested", "id": db_event.id, "event": payload}

@router.get("/latest/{room_id}")
async def get_latest_audio(
    room_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get the latest acoustic event for a monitored zone with staleness decay to NORMAL."""
    now = datetime.datetime.now(datetime.timezone.utc)
    query = (
        select(AudioEvent)
        .where(AudioEvent.room_id == room_id)
        .order_by(desc(AudioEvent.timestamp))
        .limit(1)
    )
    res = await db.execute(query)
    ev = res.scalar_one_or_none()
    if not ev:
        return {
            "room_id": room_id,
            "event_type": "NORMAL",
            "confidence": 1.0,
            "rms_energy": 0.0015,
            "spectral_centroid": 1800.0,
            "timestamp": now.isoformat()
        }

    # Acoustic events are physical and transient; if no event has arrived in > 4.0s,
    # the room environment has naturally reverted to NORMAL quiet baseline.
    ev_ts = ev.timestamp
    if ev_ts.tzinfo is None:
        ev_ts = ev_ts.replace(tzinfo=datetime.timezone.utc)
    age_seconds = (now - ev_ts).total_seconds()

    effective_type = ev.event_type if age_seconds <= 4.0 else "NORMAL"
    effective_confidence = ev.confidence if age_seconds <= 4.0 else 0.95

    return {
        "room_id": ev.room_id,
        "event_type": effective_type,
        "confidence": effective_confidence,
        "metadata": ev.event_metadata,
        "timestamp": ev.timestamp.isoformat(),
        "age_seconds": round(age_seconds, 2)
    }
