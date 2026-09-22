import datetime
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from backend.app.db.database import get_db
from backend.app.models.schema import Incident, IncidentEvidence, Room
from backend.app.schemas.schemas import IncidentResponse, IncidentCreate
from backend.app.core.events import event_manager

router = APIRouter()
logger = logging.getLogger("nexus.api.incidents")

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

    await db.commit()
    await db.refresh(incident)

    # Broadcast resolution to frontend
    await event_manager.broadcast({
        "type": "INCIDENT_RESOLVED",
        "incident_id": incident.id,
        "room_id": incident.room_id,
        "resolved_at": incident.resolved_at.isoformat()
    })

    return incident
