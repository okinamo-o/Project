import datetime
import logging
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from backend.app.db.database import get_db
from backend.app.models.schema import Incident, IncidentEvidence, Room
from backend.app.schemas.schemas import IncidentResponse, IncidentCreate
from backend.app.core.events import event_manager
from backend.app.fusion.engine import fusion_engine
from backend.app.services.email_service import email_service
from backend.app.db.firebase_client import remove_incident_from_firebase, sync_room_state_to_firebase

router = APIRouter()
logger = logging.getLogger("nexus.api.incidents")


class EmailConfigUpdateRequest(BaseModel):
    recipient_email: Optional[str] = None
    auto_send: Optional[bool] = None
    smtp_password: Optional[str] = None


class SendRoomReportRequest(BaseModel):
    room_id: str
    recipient_email: Optional[str] = None
    incident_id: Optional[str] = None
    telemetry_override: Optional[Dict[str, float]] = None


@router.get("/email-config")
async def get_email_config():
    """Retrieve current email alert recipient configuration and recent sent room reports."""
    return email_service.get_config()


@router.post("/email-config")
async def update_email_config(req: EmailConfigUpdateRequest):
    """Update the target email recipient (default: louayhamdi438@gmail.com) and auto-send toggle."""
    return email_service.update_config(
        recipient_email=req.recipient_email,
        auto_send=req.auto_send,
        smtp_password=req.smtp_password,
    )


@router.post("/send-room-report")
async def send_room_report_endpoint(
    req: SendRoomReportRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate and dispatch a Warning / Alert / Status report for a specific room
    to the configured or provided email address (defaults to louayhamdi438@gmail.com).
    """
    room_id = req.room_id
    incident_obj = None

    if req.incident_id:
        res = await db.execute(
            select(Incident)
            .options(selectinload(Incident.evidence))
            .where(Incident.id == req.incident_id)
        )
        incident_obj = res.scalar_one_or_none()

    if not incident_obj:
        # Check for an active incident in this room first, otherwise most recent incident
        res_active = await db.execute(
            select(Incident)
            .options(selectinload(Incident.evidence))
            .where(Incident.room_id == room_id, Incident.status == "ACTIVE")
            .order_by(desc(Incident.created_at))
            .limit(1)
        )
        incident_obj = res_active.scalar_one_or_none()

    inc_dict: Optional[Dict[str, Any]] = None
    severity = "NORMAL"
    if incident_obj:
        severity = incident_obj.severity or "WARNING"
        inc_dict = {
            "id": incident_obj.id,
            "room_id": incident_obj.room_id,
            "type": incident_obj.type,
            "severity": incident_obj.severity,
            "confidence": incident_obj.confidence,
            "status": incident_obj.status,
            "summary": incident_obj.summary,
            "timeline": incident_obj.timeline or [],
            "evidence": [
                {
                    "source_type": e.source_type,
                    "source_id": e.source_id,
                    "contribution": e.contribution,
                    "explanation": e.explanation,
                }
                for e in (incident_obj.evidence or [])
            ],
        }

    # Build telemetry snapshot for this room
    smap = dict(fusion_engine._latest_sensors.get(room_id, {}))
    buf = fusion_engine._room_buffers.get(room_id, {})
    occ = 0
    if buf.get("vision"):
        occ = buf["vision"][-1]["data"].get("occupancy", 0)

    telem = {
        "temperature": smap.get("temperature", 22.0),
        "humidity": smap.get("humidity", 45.0),
        "gas": smap.get("gas", 80.0),
        "smoke": smap.get("smoke", 0.3),
        "light": smap.get("light", 500.0),
        "occupancy": occ,
    }
    if req.telemetry_override:
        telem.update(req.telemetry_override)

    report_record = await email_service.send_room_report(
        room_id=room_id,
        severity=severity,
        incident=inc_dict,
        telemetry=telem,
        recipient_email=req.recipient_email,
        trigger_source="MANUAL",
    )
    return report_record


@router.get("/email-preview/{report_id}")
async def preview_email_report(report_id: str):
    """View the exact HTML email report generated and dispatched for a room."""
    html = email_service.get_report_html(report_id)
    if not html:
        raise HTTPException(status_code=404, detail="Email report not found")
    return Response(content=html, media_type="text/html")


@router.get("", response_model=List[IncidentResponse])
async def get_incidents(
    status: Optional[str] = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve active and past incidents with full evidence attribution."""
    query = (
        select(Incident)
        .options(selectinload(Incident.evidence))
        .order_by(desc(Incident.created_at))
        .limit(limit)
    )
    if status:
        query = query.where(Incident.status == status)
    result = await db.execute(query)
    incidents = result.scalars().all()
    return incidents

@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_incident(incident_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieve a single incident by ID."""
    result = await db.execute(
        select(Incident)
        .options(selectinload(Incident.evidence))
        .where(Incident.id == incident_id)
    )
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident

@router.post("/{incident_id}/resolve", response_model=IncidentResponse)
async def resolve_incident(incident_id: str, db: AsyncSession = Depends(get_db)):
    """Resolve an incident and restore the room state to NORMAL."""
    result = await db.execute(
        select(Incident)
        .options(selectinload(Incident.evidence))
        .where(Incident.id == incident_id)
    )
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident.status = "RESOLVED"
    incident.resolved_at = datetime.datetime.now(datetime.timezone.utc)
    
    # Restore room state if no other active incidents in that room
    other_incidents = await db.execute(
        select(Incident).where(
            Incident.room_id == incident.room_id,
            Incident.status == "ACTIVE",
            Incident.id != incident.id
        )
    )
    if not other_incidents.scalars().first():
        room_res = await db.execute(select(Room).where(Room.id == incident.room_id))
        room = room_res.scalar_one_or_none()
        if room:
            room.state = "NORMAL"
        sync_room_state_to_firebase(incident.room_id, "NORMAL", None)

    await db.commit()
    await db.refresh(incident)

    # Sync incident removal from active RTDB and broadcast resolution to frontend
    remove_incident_from_firebase(incident.id)
    await event_manager.broadcast({
        "type": "INCIDENT_RESOLVED",
        "incident_id": incident.id,
        "room_id": incident.room_id,
        "resolved_at": incident.resolved_at.isoformat()
    })

    return incident
