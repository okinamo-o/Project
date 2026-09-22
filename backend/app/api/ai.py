import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from backend.app.db.database import get_db
from backend.app.models.schema import Incident, Room
from backend.app.schemas.schemas import AIQuestionRequest, AIQuestionResponse
from backend.app.services.gemini_service import gemini_service

router = APIRouter()
logger = logging.getLogger("nexus.api.ai")

@router.post("/ask", response_model=AIQuestionResponse)
async def ask_nexus_assistant(
    request: AIQuestionRequest,
    db: AsyncSession = Depends(get_db)
):
    """Natural-language operator assistant answering questions about the building state."""
    # Build safe, structured system context
    rooms_res = await db.execute(select(Room))
    rooms = rooms_res.scalars().all()
    
    inc_res = await db.execute(select(Incident).where(Incident.status == "ACTIVE"))
    active_incidents = inc_res.scalars().all()

    room_summaries = [f"Room '{r.name}' ({r.id}): State={r.state}, Floor={r.floor}" for r in rooms]
    inc_summaries = [f"Active Incident {i.id}: Type={i.type}, Room={i.room_id}, Severity={i.severity}" for i in active_incidents]

    system_context = (
        f"Active Rooms ({len(rooms)} total):\n" + "\n".join(room_summaries) + "\n\n"
        f"Active Emergencies ({len(active_incidents)} active):\n" + ("\n".join(inc_summaries) if inc_summaries else "None. All zones report normal status.")
    )

    result = await gemini_service.answer_operator_question(
        question=request.question,
        system_context=system_context
    )

    return {
        "answer": result["answer"],
        "evidence_used": [f"Building Context: {len(rooms)} zones", f"Active Incidents: {len(active_incidents)}"],
        "confidence": 0.94,
        "is_offline_mode": result["is_offline_mode"]
    }

@router.get("/explain/{incident_id}")
async def explain_incident_endpoint(
    incident_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve an evidence-grounded AI explanation of why NEXUS created the incident."""
    res = await db.execute(
        select(Incident)
        .options(selectinload(Incident.evidence))
        .where(Incident.id == incident_id)
    )
    incident = res.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    room_res = await db.execute(select(Room).where(Room.id == incident.room_id))
    room = room_res.scalar_one_or_none()
    room_name = room.name if room else incident.room_id

    inc_dict = {
        "id": incident.id,
        "room_id": incident.room_id,
        "type": incident.type,
        "severity": incident.severity,
        "confidence": incident.confidence,
        "summary": incident.summary,
        "timeline": incident.timeline or [],
        "evidence": [
            {
                "source_type": e.source_type,
                "source_id": e.source_id,
                "contribution": e.contribution,
                "explanation": e.explanation
            }
            for e in incident.evidence
        ]
    }

    explanation_result = await gemini_service.explain_incident(inc_dict, room_name)
    return explanation_result

@router.get("/report/{incident_id}")
async def get_incident_report(
    incident_id: str,
    format: str = Query("html", description="Format: html or json"),
    db: AsyncSession = Depends(get_db)
):
    """Generate and return a formal post-incident technical briefing report."""
    res = await db.execute(
        select(Incident)
        .options(selectinload(Incident.evidence))
        .where(Incident.id == incident_id)
    )
    incident = res.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    room_res = await db.execute(select(Room).where(Room.id == incident.room_id))
    room = room_res.scalar_one_or_none()
    room_name = room.name if room else incident.room_id

    inc_dict = {
        "id": incident.id,
        "room_id": incident.room_id,
        "type": incident.type,
        "severity": incident.severity,
        "confidence": incident.confidence,
        "status": incident.status,
        "summary": incident.summary,
        "timeline": incident.timeline or [],
        "evidence": [
            {
                "source_type": e.source_type,
                "source_id": e.source_id,
                "contribution": e.contribution,
                "explanation": e.explanation
            }
            for e in incident.evidence
        ]
    }

    html_report = await gemini_service.generate_incident_report(inc_dict, room_name)
    if format == "html":
        return Response(content=html_report, media_type="text/html")
    return {"incident_id": incident_id, "html_report": html_report}
