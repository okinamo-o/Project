import datetime
import logging
import uuid
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from backend.app.models.schema import Incident, IncidentEvidence, Room
from backend.app.core.events import event_manager
from backend.app.prediction.trend_forecaster import forecaster
from backend.app.db.firebase_client import sync_incident_to_firebase, sync_room_state_to_firebase

logger = logging.getLogger("nexus.fusion")

def utcnow():
    return datetime.datetime.now(datetime.timezone.utc)

class MultimodalFusionEngine:
    """
    Central Multimodal Data Fusion Engine.
    Correlates IoT sensor telemetry, local computer vision events, acoustic signatures,
    and predictive trajectory to formulate unified, evidence-attributed incident hypotheses.
    """
    def __init__(self, correlation_window_seconds: int = 120):
        self.window_seconds = correlation_window_seconds
        # In-memory recent signal buffer per room
        self._room_buffers: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

    def _get_buffer(self, room_id: str) -> Dict[str, List[Dict[str, Any]]]:
        if room_id not in self._room_buffers:
            self._room_buffers[room_id] = {
                "sensors": [],
                "vision": [],
                "audio": [],
                "timeline": []
            }
        return self._room_buffers[room_id]

    def record_signal(self, room_id: str, modality: str, event_data: Dict[str, Any]):
        """Records a new signal into the room's temporal correlation buffer."""
        buf = self._get_buffer(room_id)
        now = utcnow()
        event_entry = {
            "modality": modality,
            "timestamp": now,
            "data": event_data
        }
        
        if modality == "sensor":
            buf["sensors"].append(event_entry)
            desc = f"{event_data.get('sensor_type', 'sensor').capitalize()}: {event_data.get('value')} {event_data.get('unit', '')}"
            buf["timeline"].append({"time": now.isoformat(), "source": "SENSOR", "description": desc})
        elif modality == "vision":
            buf["vision"].append(event_entry)
            desc = f"Vision: {event_data.get('event_type')} (Occupancy: {event_data.get('occupancy', 1)})"
            buf["timeline"].append({"time": now.isoformat(), "source": "VISION", "description": desc})
        elif modality == "audio":
            buf["audio"].append(event_entry)
            desc = f"Audio: {event_data.get('event_type')} signature detected"
            buf["timeline"].append({"time": now.isoformat(), "source": "AUDIO", "description": desc})

        # Trim signals older than correlation window
        cutoff = now - datetime.timedelta(seconds=self.window_seconds)
        for key in ["sensors", "vision", "audio"]:
            buf[key] = [item for item in buf[key] if item["timestamp"] >= cutoff]
        buf["timeline"] = buf["timeline"][-20:] # Keep last 20 timeline events

    async def evaluate_room(
        self,
        room_id: str,
        db: AsyncSession,
        disabled_sensors: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluates the active evidence matrix for a room.
        If conditions warrant an incident, creates/updates the database record,
        updates the room state, and broadcasts the event.
        """
        disabled = set(disabled_sensors or [])
        buf = self._get_buffer(room_id)

        # 1. Analyze Environmental Telemetry
        active_sensors = [s for s in buf["sensors"] if s["data"].get("sensor_type") not in disabled]
        
        # Extract latest sensor values
        temp_val, temp_roc = 22.0, 0.0
        gas_val, gas_roc = 70.0, 0.0
        vib_val = 0.03
        motion_detected = False

        recent_temps_nodes = [s for s in active_sensors if s["data"].get("sensor_type") == "temperature"]
        if recent_temps_nodes:
            temp_val = recent_temps_nodes[-1]["data"]["value"]
            if len(recent_temps_nodes) >= 2:
                delta_val = recent_temps_nodes[-1]["data"]["value"] - recent_temps_nodes[0]["data"]["value"]
                delta_sec = (recent_temps_nodes[-1]["timestamp"] - recent_temps_nodes[0]["timestamp"]).total_seconds()
                temp_roc = (delta_val / max(delta_sec, 1.0)) * 60.0

        recent_gas_nodes = [s for s in active_sensors if s["data"].get("sensor_type") == "gas"]
        if recent_gas_nodes:
            gas_val = recent_gas_nodes[-1]["data"]["value"]
            if len(recent_gas_nodes) >= 2:
                delta_val = recent_gas_nodes[-1]["data"]["value"] - recent_gas_nodes[0]["data"]["value"]
                delta_sec = (recent_gas_nodes[-1]["timestamp"] - recent_gas_nodes[0]["timestamp"]).total_seconds()
                gas_roc = (delta_val / max(delta_sec, 1.0)) * 60.0

        recent_smoke_nodes = [s for s in active_sensors if s["data"].get("sensor_type") == "smoke"]
        smoke_val, smoke_roc = 0.3, 0.0
        if recent_smoke_nodes:
            smoke_val = recent_smoke_nodes[-1]["data"]["value"]
            if len(recent_smoke_nodes) >= 2:
                delta_val = recent_smoke_nodes[-1]["data"]["value"] - recent_smoke_nodes[0]["data"]["value"]
                delta_sec = (recent_smoke_nodes[-1]["timestamp"] - recent_smoke_nodes[0]["timestamp"]).total_seconds()
                smoke_roc = (delta_val / max(delta_sec, 1.0)) * 60.0

        recent_vib = [s["data"] for s in active_sensors if s["data"].get("sensor_type") == "vibration"]
        if recent_vib:
            vib_val = recent_vib[-1]["value"]

        recent_motion = [s["data"] for s in active_sensors if s["data"].get("sensor_type") == "motion"]
        if recent_motion and any(m["value"] == 1 for m in recent_motion):
            motion_detected = True

        # 2. Analyze Vision Evidence
        vision_active = "camera" not in disabled and len(buf["vision"]) > 0
        person_detected = False
        occupancy = 0
        if vision_active:
            latest_vis = buf["vision"][-1]["data"]
            occupancy = latest_vis.get("occupancy", 0)
            person_detected = occupancy > 0 or latest_vis.get("event_type") == "PERSON_DETECTED"

        # 3. Analyze Audio Evidence
        audio_active = "microphone" not in disabled and len(buf["audio"]) > 0
        audio_alarm = False
        audio_impact = False
        if audio_active:
            latest_aud = buf["audio"][-1]["data"]
            audio_alarm = latest_aud.get("event_type") == "ALARM"
            audio_impact = latest_aud.get("event_type") == "IMPACT"

        # 4. Multi-Signal Hypothesis Evaluation
        evidence_list = []
        base_confidence = 0.0
        incident_type = None
        severity = "NORMAL"

        # Check conditions: absolute thresholds or high-rate surge at elevated baselines
        temp_spike = (temp_val > 38.0) or (temp_val > 28.0 and temp_roc > 2.5)
        gas_spike = (gas_val > 280.0) or (gas_val > 150.0 and gas_roc > 30.0)
        smoke_spike = (smoke_val > 15.0) or (smoke_val > 6.0 and smoke_roc > 3.0)

        if temp_spike:
            evidence_list.append({
                "source_type": "SENSOR",
                "source_id": "dht22_temperature",
                "contribution": 0.35,
                "explanation": f"Thermal runaway detected: Temperature reached {temp_val:.1f}°C (Trajectory: +{temp_roc:.1f}°C/min)."
            })
            base_confidence += 0.35

        if gas_spike:
            evidence_list.append({
                "source_type": "SENSOR",
                "source_id": "mq2_gas",
                "contribution": 0.30,
                "explanation": f"Hazardous gas concentration detected: {gas_val:.0f} ppm (Surge rate: +{gas_roc:.1f} ppm/min)."
            })
            base_confidence += 0.30

        if smoke_spike:
            evidence_list.append({
                "source_type": "SENSOR",
                "source_id": "optical_smoke_detector",
                "contribution": 0.35,
                "explanation": f"Optical smoke obscuration detected: {smoke_val:.1f}% (Surge rate: +{smoke_roc:.1f}%/min)."
            })
            base_confidence += 0.35

        if person_detected:
            evidence_list.append({
                "source_type": "VISION",
                "source_id": "surveillance_cam",
                "contribution": 0.20,
                "explanation": f"Occupancy verified: {occupancy} subject(s) detected in hazardous zone."
            })
            base_confidence += 0.20

        if audio_alarm:
            evidence_list.append({
                "source_type": "AUDIO",
                "source_id": "acoustic_sensor",
                "contribution": 0.35 if not (temp_spike or gas_spike or smoke_spike) else 0.15,
                "explanation": "Acoustic alarm siren active in zone."
            })
            base_confidence += 0.35 if not (temp_spike or gas_spike or smoke_spike) else 0.15
        elif audio_impact:
            evidence_list.append({
                "source_type": "AUDIO",
                "source_id": "acoustic_sensor",
                "contribution": 0.25 if not (temp_spike or gas_spike or smoke_spike) else 0.15,
                "explanation": "High-energy acoustic impact impulse detected."
            })
            base_confidence += 0.25 if not (temp_spike or gas_spike or smoke_spike) else 0.15

        # Formulate Incident Hypothesis
        if (temp_spike or smoke_spike) and gas_spike and person_detected and audio_alarm:
            incident_type = "MULTI_SIGNAL_ENVIRONMENTAL_CRISIS"
            severity = "CRITICAL"
            summary = f"Multi-signal cascading emergency in {room_id.upper()}: Thermal runaway, toxic gas surge, verified human occupancy, and audible alarms."
            confidence = min(0.98, base_confidence)
        elif smoke_spike and temp_spike and person_detected:
            incident_type = "STRUCTURAL_FIRE_WITH_OCCUPANTS"
            severity = "CRITICAL"
            summary = f"Critical structural fire conflagration in {room_id.upper()}: Simultaneous thermal surge and optical smoke obscuration with verified human occupants."
            confidence = min(0.98, base_confidence)
        elif smoke_spike and temp_spike:
            incident_type = "STRUCTURAL_FIRE_CONFLAGRATION"
            severity = "CRITICAL"
            summary = f"Structural fire emergency in {room_id.upper()}: Correlated thermal rise and dense smoke obscuration."
            confidence = min(0.95, base_confidence)
        elif smoke_spike and gas_spike:
            incident_type = "TOXIC_SMOKE_AND_FUME_HAZARD"
            severity = "CRITICAL"
            summary = f"Toxic combustion emergency in {room_id.upper()}: Simultaneous volatile gas surge and optical smoke."
            confidence = min(0.92, base_confidence)
        elif temp_spike and gas_spike and person_detected:
            incident_type = "HAZARDOUS_ATMOSPHERE_OCCUPIED"
            severity = "CRITICAL"
            summary = f"Critical environmental hazard with human occupancy in {room_id.upper()}: Simultaneous thermal surge and gas accumulation."
            confidence = min(0.94, base_confidence)
        elif temp_spike and gas_spike:
            incident_type = "MULTI_SIGNAL_ENVIRONMENTAL_ANOMALY"
            severity = "WARNING"
            summary = f"Correlated multi-sensor anomaly in {room_id.upper()}: Temperature and volatile gas rising simultaneously."
            confidence = min(0.89, base_confidence)
        elif audio_alarm and person_detected:
            incident_type = "AUDIBLE_ALARM_OCCUPIED_ZONE"
            severity = "CRITICAL"
            summary = f"Audible emergency alarm siren active in {room_id.upper()} with active human occupancy. Immediate life-safety verification required."
            confidence = min(0.96, base_confidence + 0.45)
        elif audio_alarm:
            incident_type = "ACOUSTIC_ALARM_TRIGGERED"
            severity = "WARNING"
            summary = f"Audible acoustic emergency alarm siren detected in {room_id.upper()}. Zone inspection or evacuation alert recommended."
            confidence = min(0.92, base_confidence + 0.50)
        elif audio_impact:
            incident_type = "STRUCTURAL_IMPACT_DETECTED"
            severity = "WARNING"
            summary = f"High-energy acoustic impact impulse detected in {room_id.upper()}."
            confidence = min(0.85, base_confidence + 0.40)
        elif smoke_spike:
            incident_type = "OPTICAL_SMOKE_DETECTED"
            severity = "CRITICAL" if smoke_val > 35.0 else "WARNING"
            summary = f"Optical smoke detector alert in {room_id.upper()}: Smoke obscuration reached {smoke_val:.1f}%."
            confidence = min(0.90, base_confidence)
        elif temp_spike:
            incident_type = "ELEVATED_THERMAL_RUNAWAY"
            severity = "ATTENTION"
            summary = f"Thermal anomaly in {room_id.upper()}: Temperature exceeds operational safety threshold."
            confidence = min(0.78, base_confidence)
        elif gas_spike:
            incident_type = "GAS_LEAK_ACCUMULATION"
            severity = "WARNING"
            summary = f"Volatile fume hazard in {room_id.upper()}: Gas concentration increasing."
            confidence = min(0.82, base_confidence)
        else:
            return None # Room is healthy

        # Normalize contribution weights so they sum to 1.0
        total_weight = sum(e["contribution"] for e in evidence_list)
        if total_weight > 0:
            for e in evidence_list:
                e["contribution"] = round(e["contribution"] / total_weight, 2)

        # Generate or update Incident in Database
        unique_suffix = uuid.uuid4().hex[:6].upper()
        incident_id = f"INC-{utcnow().strftime('%Y%m%d%H%M%S')}-{room_id[:4].upper()}-{unique_suffix}"
        
        # Check if active incident already exists for this room
        q = select(Incident).where(Incident.room_id == room_id, Incident.status == "ACTIVE")
        existing_res = await db.execute(q)
        active_inc = existing_res.scalars().first()

        timeline_copy = list(buf["timeline"])
        timeline_copy.append({
            "time": utcnow().isoformat(),
            "source": "FUSION",
            "description": f"Fusion engine formulated hypothesis: {incident_type} (Confidence: {confidence:.2f})"
        })

        if active_inc:
            active_inc.type = incident_type
            active_inc.severity = severity
            active_inc.confidence = round(confidence, 2)
            active_inc.summary = summary
            active_inc.timeline = timeline_copy
            incident_id = active_inc.id
            
            # Remove previous evidence rows to refresh with new multimodal evidence
            from sqlalchemy import delete
            await db.execute(delete(IncidentEvidence).where(IncidentEvidence.incident_id == active_inc.id))
        else:
            active_inc = Incident(
                id=incident_id,
                room_id=room_id,
                type=incident_type,
                severity=severity,
                confidence=round(confidence, 2),
                status="ACTIVE",
                summary=summary,
                timeline=timeline_copy
            )
            db.add(active_inc)
            try:
                await db.flush()
            except Exception as flush_err:
                logger.warning(f"[FUSION] Database flush error on incident insert: {flush_err}")
                await db.rollback()
                return None

        # Add refreshed evidence records
        for ev in evidence_list:
            db_ev = IncidentEvidence(
                incident_id=active_inc.id,
                source_type=ev["source_type"],
                source_id=ev["source_id"],
                contribution=ev["contribution"],
                explanation=ev["explanation"]
            )
            db.add(db_ev)

        # Update Room condition state in DB
        room_q = select(Room).where(Room.id == room_id)
        r_res = await db.execute(room_q)
        room = r_res.scalar_one_or_none()
        if room:
            room.state = "INCIDENT" if severity == "CRITICAL" else "ANOMALY"

        await db.commit()

        # Broadcast INCIDENT_CREATED / UPDATED via WebSocket
        payload = {
            "type": "INCIDENT_ALERT",
            "incident_id": incident_id,
            "room_id": room_id,
            "incident_type": incident_type,
            "severity": severity,
            "confidence": round(confidence, 2),
            "summary": summary,
            "evidence": evidence_list,
            "timeline": timeline_copy
        }
        await event_manager.broadcast(payload)
        logger.info(f"[FUSION] Incident {incident_id} active for {room_id}: {incident_type} (Conf: {confidence:.2f})")

        # Push to Firebase Realtime Database
        sync_incident_to_firebase(incident_id, payload)
        sync_room_state_to_firebase(room_id, "INCIDENT" if severity == "CRITICAL" else "ANOMALY", incident_id)

        return payload

# Global fusion engine instance
fusion_engine = MultimodalFusionEngine()
