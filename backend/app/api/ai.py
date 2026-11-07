import datetime
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from backend.app.db.database import get_db
from backend.app.models.schema import Incident, Room, SensorReading, VisionEvent, AudioEvent
from backend.app.schemas.schemas import AIQuestionRequest, AIQuestionResponse
from backend.app.services.gemini_service import gemini_service
from backend.app.services.email_service import email_service
from backend.app.fusion.engine import fusion_engine

router = APIRouter()
logger = logging.getLogger("nexus.api.ai")

@router.post("/ask", response_model=AIQuestionResponse)
async def ask_nexus_assistant(
    request: AIQuestionRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Natural-language operator assistant with complete end-to-end project knowledge,
    including real-time building state, chronological event history, past incidents,
    sensor ranges (min/max/avg), hardware specs, and ML safety physics.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    two_hours_ago = now - datetime.timedelta(hours=2)
    q_lower = request.question.lower()

    # 1. Resolve target room from current question, or recent conversation history, or UI selected room
    focused_room = request.room_id or "classroom_01"
    room_alias_map = {
        "classroom_01": ["classroom 1", "classroom 01", "class 1", "classroom1", "room 1", "c1"],
        "classroom_02": ["classroom 2", "classroom 02", "class 2", "classroom2", "room 2", "c2"],
        "lab_02": ["lab 2", "lab 02", "chemistry", "chem lab", "lab2", "chemistry lab", "physics lab"],
        "lab_01": ["lab 1", "lab 01", "computer lab", "lab1", "comp lab"],
        "server_room": ["server room", "servers", "datacenter", "server"],
        "storage_room": ["storage room", "storage", "chemical storage"],
        "main_hall": ["main hall", "hall", "hallway"],
        "entrance": ["entrance", "main entrance", "lobby"],
        "emergency_exit": ["emergency exit", "fire exit"]
    }
    matched_in_question = False
    for r_id, aliases in room_alias_map.items():
        if any(alias in q_lower for alias in aliases):
            focused_room = r_id
            matched_in_question = True
            break

    # If the user's message didn't name a room (e.g. "sounds good", "what about the gas sensor there?"),
    # check the recent conversation history so we stay focused on the room just discussed!
    if not matched_in_question and request.history:
        for msg in reversed(request.history):
            msg_text = (msg.get("text") or "").lower()
            found_hist_room = None
            for r_id, aliases in room_alias_map.items():
                if any(alias in msg_text for alias in aliases):
                    found_hist_room = r_id
                    break
            if found_hist_room:
                focused_room = found_hist_room
                break

    # 2. Query all rooms for current overview
    rooms_res = await db.execute(select(Room))
    rooms = rooms_res.scalars().all()

    room_summaries = []
    for r in rooms:
        smap = fusion_engine._latest_sensors.get(r.id, {})
        buf = fusion_engine._room_buffers.get(r.id, {})
        occ = 0
        if buf.get("vision"):
            occ = buf["vision"][-1]["data"].get("occupancy", 0)
        
        telems = []
        if "temperature" in smap: telems.append(f"Temp={smap['temperature']:.1f}°C")
        if "humidity" in smap: telems.append(f"Humidity={smap['humidity']:.0f}%")
        if "gas" in smap: telems.append(f"Gas={smap['gas']:.0f}ppm")
        if "smoke" in smap: telems.append(f"Smoke={smap['smoke']:.1f}%")
        if "light" in smap: telems.append(f"Light={smap['light']:.0f}lux")
        if occ > 0: telems.append(f"Occupancy={occ} people")
        
        telem_str = f" | Telemetry: {', '.join(telems)}" if telems else ""
        room_summaries.append(f"- Room '{r.name}' ({r.id}): State={r.state}, Floor={r.floor}{telem_str}")

    # 3. Active Incidents across building
    inc_active_res = await db.execute(
        select(Incident)
        .where(Incident.status == "ACTIVE")
        .order_by(desc(Incident.created_at))
    )
    active_incidents = inc_active_res.scalars().all()
    active_inc_summaries = []
    for i in active_incidents:
        created_str = i.created_at.strftime("%Y-%m-%d %H:%M:%S UTC") if i.created_at else "Recent"
        active_inc_summaries.append(f"- [{created_str}] Incident {i.id}: Type={i.type}, Room={i.room_id}, Severity={i.severity}, Summary={i.summary}")

    # 4. Historical Incidents (Past 24 Hours, Active & Resolved)
    inc_hist_res = await db.execute(
        select(Incident)
        .order_by(desc(Incident.created_at))
        .limit(15)
    )
    all_recent_incidents = inc_hist_res.scalars().all()
    hist_inc_lines = []
    focused_room_inc_lines = []
    for i in all_recent_incidents:
        created_str = i.created_at.strftime("%H:%M:%S UTC") if i.created_at else "Earlier"
        if i.resolved_at and i.created_at:
            dur_sec = max(1, int((i.resolved_at - i.created_at).total_seconds()))
            res_time = i.resolved_at.strftime("%H:%M:%S UTC")
            if dur_sec <= 30:
                res_str = f"RESOLVED TRANSIENT EVENT — Auto-cleared in {dur_sec}s at {res_time}"
            else:
                res_str = f"Resolved at {res_time} (Duration: {dur_sec}s)"
        elif i.resolved_at:
            res_str = f"Resolved at {i.resolved_at.strftime('%H:%M:%S UTC')}"
        else:
            res_str = "Currently ACTIVE"
        line = f"- [{created_str}] {i.id} ({i.room_id.upper()}): {i.type} [{i.severity}] — Status: {i.status} ({res_str}). Summary: {i.summary}"
        hist_inc_lines.append(line)
        if i.room_id == focused_room:
            focused_room_inc_lines.append(line)

    # 5. Statistical Telemetry Ranges (Past 2 Hours) for Focused Room
    dev_ids = [f"esp32_{focused_room}"]
    if focused_room == "classroom_01":
        dev_ids.append("esp32_classroom01")
    elif focused_room == "lab_02":
        dev_ids.append("esp32_lab02")

    q_stats = (
        select(
            SensorReading.sensor_type,
            func.min(SensorReading.value).label("min_val"),
            func.max(SensorReading.value).label("max_val"),
            func.avg(SensorReading.value).label("avg_val"),
            func.count(SensorReading.id).label("cnt")
        )
        .where(SensorReading.device_id.in_(dev_ids))
        .where(SensorReading.timestamp >= two_hours_ago)
        .group_by(SensorReading.sensor_type)
    )
    stats_rows = (await db.execute(q_stats)).all()
    stats_lines = []
    for s in stats_rows:
        unit = "°C" if s.sensor_type == "temperature" else "%" if s.sensor_type in ["humidity", "smoke"] else "ppm" if s.sensor_type == "gas" else "lux" if s.sensor_type == "light" else ""
        stats_lines.append(f"- {s.sensor_type.capitalize()}: Min = {s.min_val:.1f}{unit}, Max = {s.max_val:.1f}{unit}, Average = {s.avg_val:.1f}{unit} (over {s.cnt} readings)")

    # 6. In-Memory Chronological Timeline from Fusion Engine
    buf = fusion_engine._get_buffer(focused_room)
    timeline_items = buf.get("timeline", [])[-15:]
    timeline_lines = [f"- [{t.get('time', '')[:19]}] [{t.get('source')}] {t.get('description')}" for t in timeline_items]

    # 7. Recent Conversation History
    history_lines = []
    if request.history:
        for msg in request.history[-6:]:
            role_label = "Operator" if msg.get("role") == "user" else "NEXUS Assistant"
            text_val = (msg.get("text") or "").strip()
            if text_val:
                history_lines.append(f"**{role_label}**: {text_val[:500]}")

    # 8. Comprehensive System Intelligence Context
    focused_room_obj = next((r for r in rooms if r.id == focused_room), None)
    focused_room_name = focused_room_obj.name if focused_room_obj else focused_room

    # If the operator asks in chat to email/send a report for the room, trigger it automatically!
    chat_dispatched_note = ""
    if any(k in q_lower for k in ["send report", "email report", "send a report", "mail report", "send to mail", "send to my mail", "send to email"]):
        smap_f = dict(fusion_engine._latest_sensors.get(focused_room, {}))
        buf_f = fusion_engine._room_buffers.get(focused_room, {})
        occ_f = buf_f["vision"][-1]["data"].get("occupancy", 0) if buf_f.get("vision") else 0
        active_for_room = next((i for i in active_incidents if i.room_id == focused_room), None)
        inc_dict_f = {
            "id": active_for_room.id,
            "room_id": active_for_room.room_id,
            "type": active_for_room.type,
            "severity": active_for_room.severity,
            "confidence": active_for_room.confidence,
            "summary": active_for_room.summary,
        } if active_for_room else None
        rep_rec = await email_service.send_room_report(
            room_id=focused_room,
            severity=active_for_room.severity if active_for_room else "NORMAL",
            incident=inc_dict_f,
            telemetry={
                "temperature": smap_f.get("temperature", 22.0),
                "humidity": smap_f.get("humidity", 45.0),
                "gas": smap_f.get("gas", 80.0),
                "smoke": smap_f.get("smoke", 0.3),
                "light": smap_f.get("light", 500.0),
                "occupancy": occ_f,
            },
            trigger_source="AI_ASSISTANT",
        )
        chat_dispatched_note = f"- Action Executed Just Now: Dispatched room report {rep_rec['report_id']} for {focused_room_name} to {rep_rec['recipient_email']} (Preview: {rep_rec['preview_url']}).\n"

    system_context = (
        f"### RECENT CONVERSATION HISTORY\n"
        + ("\n".join(history_lines) if history_lines else "- Start of conversation.") + "\n\n"
        f"### FOCUSED ROOM CONTEXT\n"
        f"Target/Focused Room: {focused_room_name} ({focused_room})\n"
        f"Email Alert & Warning Recipient: {email_service.recipient_email} (Auto-Dispatch on Warning/Alert: {'Enabled' if email_service.auto_send else 'Disabled'})\n"
        + chat_dispatched_note + "\n"
        f"### HISTORICAL INCIDENTS IN {focused_room_name.upper()} ({focused_room})\n"
        + ("\n".join(focused_room_inc_lines) if focused_room_inc_lines else f"- Zero incidents recorded in {focused_room_name}. Room has remained 100% NORMAL.") + "\n\n"
        f"### SENSOR STATISTICS (Past 2 Hours for {focused_room_name})\n"
        + ("\n".join(stats_lines) if stats_lines else "- No historical readings recorded in the past 2 hours.") + "\n\n"
        f"### CHRONOLOGICAL EVENT TIMELINE (Recent Events in {focused_room_name})\n"
        + ("\n".join(timeline_lines) if timeline_lines else "- Nominal state maintained, no anomalous timeline events.") + "\n\n"
        f"### ACTIVE HAZARDS & EMERGENCIES (Building-Wide)\n"
        + ("\n".join(active_inc_summaries) if active_inc_summaries else "- None. All zones report normal status.") + "\n\n"
        f"### HISTORICAL INCIDENTS LOG (All Rooms Building-Wide)\n"
        + ("\n".join(hist_inc_lines) if hist_inc_lines else "- No historical incidents on record.") + "\n\n"
        f"### REAL-TIME BUILDING STATUS (All 9 Rooms)\n"
        + "\n".join(room_summaries) + "\n\n"
        f"### PROJECT ARCHITECTURE, HARDWARE & MACHINE LEARNING SPECIFICATIONS\n"
        f"- Building Layout: 9 zones across 2 floors.\n"
        f"  * Floor 1: Entrance, Main Hall, Classroom 01, Classroom 02, Emergency Exit.\n"
        f"  * Floor 2: Server Room, Computer Lab 01, Chemistry Lab 02, Storage Room.\n"
        f"- Hardware Sensor Nodes:\n"
        f"  * Classroom 01: ESP32 DevKit node (`esp32_classroom01`) with DHT22 (GPIO 4: Temp/Humidity), MQ-2 (GPIO 34: Gas), Optical Smoke (GPIO 36), LDR Photoresistor (GPIO 35: Fire Light/Flash), PIR camera presence (GPIO 13), Blue Camera LED (GPIO 2), Red Hazard LED (GPIO 12), and Buzzer (GPIO 15).\n"
        f"  * Student Audio Privacy Policy: Microphone surveillance is strictly OMITTED in Classroom 01 to protect student privacy.\n"
        f"  * Chemistry Lab 02: ESP32 DevKit node (`esp32_lab02`) with DHT22, MQ-2 Gas, Optical Smoke, PIR Motion, LDR (GPIO 35), Alert LED (GPIO 2), Buzzer (GPIO 15), and 16kHz microphone audio DSP (voice, siren alarm at 2.5kHz, impact).\n"
        f"  * Virtual Room Nodes: Server Room, Classroom 02, Lab 01, Storage Room, Main Hall, Entrance, Emergency Exit.\n"
        f"- Machine Learning & Sensor Fusion Engine:\n"
        f"  * IsolationForest ML pipeline trained on 7 features with 99.34% accuracy.\n"
        f"  * Real-Life Safety Physics: Warm ambient temperatures alone (e.g. 39°C summer heat or hot coffee near sensor) without smoke, gas, or fire flash are physically benign and NEVER trigger an alarm or buzzer.\n"
        f"  * Structural Fire Conflagration requires 3-sensor ML corroboration: Heat (>=32°C) + Smoke (>=6%) + High Lux flame light (>=700 lux). High temp + smoke WITHOUT high Lux (e.g. 500 lux normal light or 20 lux dark) means no optical flame radiance is present and no fire hazard is detected.\n"
        f"  * Hysteresis & State Latching prevents alarm flickering.\n"
        f"- Vision Subsystem: 45 FPS Edge surveillance with YOLOv5n person detector and YuNet face detector.\n"
    )

    result = await gemini_service.answer_operator_question(
        question=request.question,
        system_context=system_context
    )

    return {
        "answer": result["answer"],
        "evidence_used": [
            f"Building Context: {len(rooms)} zones",
            f"Focused Room: {focused_room_name}",
            f"Active Incidents: {len(active_incidents)}",
            f"Historical Incidents: {len(all_recent_incidents)}",
            f"Historical Telemetry Records: {sum(s.cnt for s in stats_rows)}"
        ],
        "confidence": 0.96,
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
