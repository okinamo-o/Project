import os
import asyncio
import datetime
import logging
import uuid
from typing import Dict, Any, List, Optional, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from backend.app.models.schema import Incident, IncidentEvidence, Room
from backend.app.core.events import event_manager
from backend.app.prediction.anomaly_service import anomaly_detector
from backend.app.services.email_service import email_service
from backend.app.db.firebase_client import (
    sync_incident_to_firebase,
    sync_room_state_to_firebase,
    remove_incident_from_firebase,
)

logger = logging.getLogger("nexus.fusion")

def utcnow():
    return datetime.datetime.now(datetime.timezone.utc)

class MultimodalFusionEngine:
    """
    Central Multimodal Data Fusion Engine.
    Correlates IoT sensor telemetry, local computer vision events, acoustic signatures,
    and predictive trajectory to formulate unified, evidence-attributed incident hypotheses.
    Maintains deterministic per-sensor deadband hysteresis and state-change latching so
    alerts remain completely steady until conditions genuinely escalate, de-escalate, or clear.
    """
    def __init__(self, correlation_window_seconds: int = 120):
        self.window_seconds = correlation_window_seconds
        # In-memory recent signal buffer per room
        self._room_buffers: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        # Persistent latest sensor values per room (does not expire after 120s window)
        self._latest_sensors: Dict[str, Dict[str, float]] = {}
        # Per-room active sensor spike states for deadband hysteresis
        self._active_spikes: Dict[str, Set[str]] = {}

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
        """Records a new signal into the room's temporal correlation buffer and persistent state."""
        buf = self._get_buffer(room_id)
        now = utcnow()
        event_entry = {
            "modality": modality,
            "timestamp": now,
            "data": event_data
        }
        
        if modality == "sensor":
            buf["sensors"].append(event_entry)
            stype = event_data.get("sensor_type")
            sval = event_data.get("value")
            if stype is not None and sval is not None:
                if room_id not in self._latest_sensors:
                    self._latest_sensors[room_id] = {}
                try:
                    self._latest_sensors[room_id][stype] = float(sval)
                except (ValueError, TypeError):
                    pass
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
        buf["timeline"] = buf["timeline"][-20:]  # Keep last 20 timeline events

    async def evaluate_room(
        self,
        room_id: str,
        db: AsyncSession,
        disabled_sensors: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluates the active evidence matrix for a room.
        Only mutates DB / broadcasts / updates Firebase when an incident state transition
        genuinely occurs (Normal <-> Warning <-> Critical or hypothesis type change).
        """
        is_simulation = disabled_sensors is not None
        disabled = set(disabled_sensors or [])
        # Classrooms enforce student audio privacy: disable acoustic/microphone analysis
        if room_id == "classroom_01":
            disabled.add("microphone")
        buf = self._get_buffer(room_id)
        latest_map = self._latest_sensors.get(room_id, {})

        # 1. Analyze Environmental Telemetry
        active_sensors = [s for s in buf["sensors"] if s["data"].get("sensor_type") not in disabled]
        
        temp_val = latest_map.get("temperature", 22.0) if "temperature" not in disabled else 22.0
        humidity_val = latest_map.get("humidity", 45.0) if "humidity" not in disabled else 45.0
        gas_val = latest_map.get("gas", 75.0) if "gas" not in disabled else 75.0
        smoke_val = latest_map.get("smoke", 0.3) if "smoke" not in disabled else 0.3
        light_val = latest_map.get("light", 450.0) if "light" not in disabled else 450.0
        temp_roc, gas_roc, smoke_roc = 0.0, 0.0, 0.0

        recent_temps_nodes = [s for s in active_sensors if s["data"].get("sensor_type") == "temperature"]
        if recent_temps_nodes:
            temp_val = float(recent_temps_nodes[-1]["data"]["value"])
            if len(recent_temps_nodes) >= 2:
                delta_val = recent_temps_nodes[-1]["data"]["value"] - recent_temps_nodes[0]["data"]["value"]
                delta_sec = (recent_temps_nodes[-1]["timestamp"] - recent_temps_nodes[0]["timestamp"]).total_seconds()
                temp_roc = (delta_val / max(delta_sec, 1.0)) * 60.0

        recent_hum_nodes = [s for s in active_sensors if s["data"].get("sensor_type") == "humidity"]
        if recent_hum_nodes:
            humidity_val = float(recent_hum_nodes[-1]["data"]["value"])

        recent_gas_nodes = [s for s in active_sensors if s["data"].get("sensor_type") == "gas"]
        if recent_gas_nodes:
            gas_val = float(recent_gas_nodes[-1]["data"]["value"])
            if len(recent_gas_nodes) >= 2:
                delta_val = recent_gas_nodes[-1]["data"]["value"] - recent_gas_nodes[0]["data"]["value"]
                delta_sec = (recent_gas_nodes[-1]["timestamp"] - recent_gas_nodes[0]["timestamp"]).total_seconds()
                gas_roc = (delta_val / max(delta_sec, 1.0)) * 60.0

        recent_smoke_nodes = [s for s in active_sensors if s["data"].get("sensor_type") == "smoke"]
        if recent_smoke_nodes:
            smoke_val = float(recent_smoke_nodes[-1]["data"]["value"])
            if len(recent_smoke_nodes) >= 2:
                delta_val = recent_smoke_nodes[-1]["data"]["value"] - recent_smoke_nodes[0]["data"]["value"]
                delta_sec = (recent_smoke_nodes[-1]["timestamp"] - recent_smoke_nodes[0]["timestamp"]).total_seconds()
                smoke_roc = (delta_val / max(delta_sec, 1.0)) * 60.0

        recent_light_nodes = [s for s in active_sensors if s["data"].get("sensor_type") == "light"]
        if recent_light_nodes:
            light_val = float(recent_light_nodes[-1]["data"]["value"])

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

        # 4. Real-Life Multi-Sensor Deadband Hysteresis & ML Anomaly Scoring
        spikes = set(self._active_spikes.get(room_id, set()))
        has_ldr_sensor = ("light" not in disabled) and ("light" in latest_map or len(recent_light_nodes) > 0)

        # LDR Photoresistor fire correlation:
        # Detects optical flame radiance / fire flash ONLY via HIGH Lux (>= 700 lux, hysteresis >= 650 lux).
        # Low Lux (e.g. 20 lux dark) or normal room lighting (500 lux) is NEVER a fire signature.
        ldr_high_lux = ("light" not in disabled) and (
            light_val >= (650.0 if "ldr" in spikes else 700.0)
        )

        # Optical smoke detector:
        # When an LDR fire/light sensor is present in the room, fire smoke requires High Lux flame corroboration
        # (>= 700 lux) or toxic gas corroboration (>= 160 ppm). High temp + smoke WITHOUT high Lux (e.g. 20 lux dark
        # or 500 lux normal light) is filtered out by the ML engine as non-fire (no optical flame detected).
        if "smoke" in disabled:
            smoke_spike = False
        elif has_ldr_sensor:
            has_flame_or_gas_corroboration = ldr_high_lux or ("gas" not in disabled and gas_val >= 160.0)
            if not has_flame_or_gas_corroboration:
                smoke_spike = False
            elif "smoke" in spikes:
                smoke_spike = smoke_val >= 4.5
            else:
                smoke_spike = smoke_val >= 6.0
        else:
            has_thermal_or_gas_corroboration = (
                ("temperature" not in disabled and temp_val >= 32.0)
                or ("gas" not in disabled and gas_val >= 160.0)
            )
            if "smoke" in spikes:
                smoke_spike = smoke_val >= 4.5
            elif has_thermal_or_gas_corroboration:
                smoke_spike = smoke_val >= 6.0
            else:
                smoke_spike = smoke_val >= 8.0

        # Gas sensor (MQ-2): >= 160 ppm when corroborated by heat/smoke, >= 200 ppm standalone
        has_thermal_or_smoke_corroboration = (
            ("temperature" not in disabled and temp_val >= 32.0)
            or smoke_spike
            or ("smoke" not in disabled and smoke_val >= 6.0)
        )
        if "gas" in disabled:
            gas_spike = False
        elif "gas" in spikes:
            gas_spike = gas_val >= 145.0
        elif has_thermal_or_smoke_corroboration:
            gas_spike = gas_val >= 160.0
        else:
            gas_spike = gas_val >= 200.0

        has_fire_precursor = (
            smoke_spike
            or ("smoke" not in disabled and smoke_val >= 6.0)
        )
        ldr_fire_anomaly = ldr_high_lux and has_fire_precursor

        # Temperature (DHT22):
        #  - If elevated smoke is present alongside high temp in a room with an LDR sensor, but there is NO High Lux
        #    (< 700 lux, e.g. 20 lux dark or 500 lux normal) and no gas leak, the ML concludes NO fire hazard detected.
        #  - Corroborated by confirmed fire (smoke + high Lux) or gas: activates at >= 32.0°C (clears < 30.0°C).
        #  - Standalone (no smoke, no gas): only activates at extreme heat >= 45.0°C (clears < 42.5°C).
        is_uncorroborated_smoke_temp = (
            has_ldr_sensor
            and ("smoke" not in disabled and smoke_val >= 5.0)
            and not ldr_high_lux
            and not gas_spike
        )
        is_temp_corroborated = smoke_spike or gas_spike or ldr_fire_anomaly
        if "temperature" in disabled or is_uncorroborated_smoke_temp:
            temp_spike = False
        elif is_temp_corroborated:
            temp_spike = temp_val >= (30.0 if "temp" in spikes else 32.0)
        else:
            temp_spike = temp_val >= (42.5 if "temp" in spikes else 45.0)

        # Evaluate trained IsolationForest ML model across all room telemetry features
        ml_is_anomaly, ml_score, _ = anomaly_detector.score_telemetry({
            "temperature": temp_val,
            "humidity": humidity_val,
            "gas": gas_val,
            "smoke": smoke_val,
            "light": light_val,
            "temp_rate_of_change": temp_roc,
            "gas_rate_of_change": gas_roc,
        })

        if not is_simulation:
            new_spikes: Set[str] = set()
            if temp_spike:
                new_spikes.add("temp")
            if gas_spike:
                new_spikes.add("gas")
            if smoke_spike:
                new_spikes.add("smoke")
            if ldr_fire_anomaly:
                new_spikes.add("ldr")
            self._active_spikes[room_id] = new_spikes

        # 5. Multi-Signal Evidence & Hypothesis Formulation
        evidence_list = []
        base_confidence = 0.0
        incident_type = None
        severity = "NORMAL"

        if temp_spike:
            evidence_list.append({
                "source_type": "SENSOR",
                "source_id": "dht22_temperature",
                "contribution": 0.30,
                "explanation": f"Thermal anomaly detected: Temperature reached {temp_val:.1f}°C."
            })
            base_confidence += 0.35

        if gas_spike:
            evidence_list.append({
                "source_type": "SENSOR",
                "source_id": "mq2_gas",
                "contribution": 0.30,
                "explanation": f"Hazardous gas concentration detected: {gas_val:.0f} ppm."
            })
            base_confidence += 0.30

        if smoke_spike:
            evidence_list.append({
                "source_type": "SENSOR",
                "source_id": "optical_smoke_detector",
                "contribution": 0.35,
                "explanation": f"Optical smoke obscuration detected: {smoke_val:.1f}%."
            })
            base_confidence += 0.35

        if ldr_fire_anomaly:
            ldr_desc = f"Optical flame flash / radiant spike detected ({light_val:.0f} lux)."
            evidence_list.append({
                "source_type": "SENSOR",
                "source_id": "ldr_photoresistor",
                "contribution": 0.25,
                "explanation": ldr_desc
            })
            base_confidence += 0.25

        if ml_is_anomaly and (temp_spike or gas_spike or smoke_spike or ldr_fire_anomaly):
            evidence_list.append({
                "source_type": "SENSOR",
                "source_id": "isolation_forest_ml",
                "contribution": 0.20,
                "explanation": f"ML Multi-Sensor Fusion concluded hazard signature (Anomaly Score: {int(ml_score * 100)}%)."
            })
            base_confidence += 0.15

        if person_detected and (temp_spike or gas_spike or smoke_spike or audio_alarm):
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

        # Query existing active incidents for this room
        q = select(Incident).where(Incident.room_id == room_id, Incident.status == "ACTIVE").order_by(Incident.created_at.desc())
        existing_res = await db.execute(q)
        all_active = list(existing_res.scalars().all())
        active_inc = all_active[0] if all_active else None

        # Clean up any duplicate active incidents for this room
        if len(all_active) > 1:
            for dup_inc in all_active[1:]:
                dup_inc.status = "RESOLVED"
                remove_incident_from_firebase(dup_inc.id)
            await db.commit()

        # Helper for CRITICAL <-> WARNING hysteresis when active_inc is already CRITICAL
        was_critical = active_inc is not None and active_inc.severity == "CRITICAL"
        if is_temp_corroborated:
            temp_crit = temp_val >= 37.0 if was_critical else temp_val >= 39.0
        else:
            temp_crit = temp_val >= 48.0 if was_critical else temp_val >= 50.0
        gas_crit = gas_val >= 320.0 if was_critical else gas_val >= 350.0
        smoke_crit = smoke_val >= 20.0 if was_critical else smoke_val >= 25.0

        # Formulate Incident Hypothesis (immune to transient webcam/microphone frame jitter)
        if (temp_spike or smoke_spike) and gas_spike and person_detected and audio_alarm:
            incident_type = "MULTI_SIGNAL_ENVIRONMENTAL_CRISIS"
            severity = "CRITICAL"
            summary = f"Multi-signal cascading emergency in {room_id.upper()}: Thermal runaway, toxic gas surge, verified human occupancy, and audible alarms."
            confidence = min(0.98, base_confidence)
        elif (smoke_spike and temp_spike) or (smoke_spike and ldr_fire_anomaly) or (temp_spike and ldr_fire_anomaly and (smoke_spike or gas_spike)):
            incident_type = "STRUCTURAL_FIRE_CONFLAGRATION"
            severity = "CRITICAL"
            ldr_note = f", LDR optical reading ({light_val:.0f} lux)" if ldr_fire_anomaly else ""
            summary = f"Structural fire emergency in {room_id.upper()}: ML correlated thermal rise ({temp_val:.1f}°C), smoke ({smoke_val:.1f}%){ldr_note}."
            confidence = min(0.97, max(0.90, base_confidence))
        elif smoke_spike and gas_spike:
            incident_type = "TOXIC_SMOKE_AND_FUME_HAZARD"
            severity = "CRITICAL"
            summary = f"Toxic combustion emergency in {room_id.upper()}: Simultaneous volatile gas surge ({gas_val:.0f} ppm) and optical smoke ({smoke_val:.1f}%)."
            confidence = min(0.94, max(0.88, base_confidence))
        elif temp_spike and gas_spike:
            incident_type = "MULTI_SIGNAL_ENVIRONMENTAL_ANOMALY"
            severity = "CRITICAL" if (temp_crit or gas_crit) else "WARNING"
            summary = f"Correlated multi-sensor anomaly in {room_id.upper()}: Temperature ({temp_val:.1f}°C) and volatile gas ({gas_val:.0f} ppm) elevated simultaneously."
            confidence = min(0.92, max(0.65, base_confidence))
        elif smoke_spike:
            incident_type = "OPTICAL_SMOKE_DETECTED"
            severity = "CRITICAL" if smoke_crit else "WARNING"
            summary = f"Optical smoke detector alert in {room_id.upper()}: Smoke obscuration reached {smoke_val:.1f}%."
            confidence = min(0.90, max(0.65, base_confidence))
        elif temp_spike:
            incident_type = "ELEVATED_THERMAL_RUNAWAY"
            severity = "CRITICAL" if temp_crit else "WARNING"
            summary = f"Extreme standalone thermal hazard in {room_id.upper()}: Temperature reached {temp_val:.1f}°C."
            confidence = min(0.82, max(0.65, base_confidence))
        elif gas_spike:
            incident_type = "GAS_LEAK_ACCUMULATION"
            severity = "CRITICAL" if gas_crit else "WARNING"
            summary = f"Volatile fume hazard in {room_id.upper()}: Gas concentration elevated ({gas_val:.0f} ppm)."
            confidence = min(0.88, max(0.65, base_confidence))
        elif is_simulation and audio_alarm and person_detected:
            incident_type = "AUDIBLE_ALARM_OCCUPIED_ZONE"
            severity = "CRITICAL"
            summary = f"Audible emergency alarm siren active in {room_id.upper()} with active human occupancy."
            confidence = min(0.96, base_confidence + 0.45)
        elif is_simulation and audio_alarm:
            incident_type = "ACOUSTIC_ALARM_TRIGGERED"
            severity = "WARNING"
            summary = f"Audible acoustic emergency alarm siren detected in {room_id.upper()}."
            confidence = min(0.92, base_confidence + 0.50)
        elif is_simulation and audio_impact:
            incident_type = "STRUCTURAL_IMPACT_DETECTED"
            severity = "WARNING"
            summary = f"High-energy acoustic impact impulse detected in {room_id.upper()}."
            confidence = min(0.85, base_confidence + 0.40)
        else:
            # All signals have cleared below safe deadband thresholds -> resolve active incident(s)
            if all_active:
                for inc in all_active:
                    inc.status = "RESOLVED"
                    inc.resolved_at = utcnow()
                room_q = select(Room).where(Room.id == room_id)
                r_res = await db.execute(room_q)
                room = r_res.scalar_one_or_none()
                if room:
                    room.state = "NORMAL"
                await db.commit()
                for inc in all_active:
                    await event_manager.broadcast({
                        "type": "INCIDENT_RESOLVED",
                        "incident_id": inc.id,
                        "room_id": room_id
                    })
                    remove_incident_from_firebase(inc.id)
                sync_room_state_to_firebase(room_id, "NORMAL", None)
                logger.info(f"[FUSION] Incident {all_active[0].id} RESOLVED for {room_id} (All signals nominal)")
            return None

        # Normalize contribution weights so they sum to 1.0
        total_weight = sum(e["contribution"] for e in evidence_list)
        if total_weight > 0:
            for e in evidence_list:
                e["contribution"] = round(e["contribution"] / total_weight, 2)

        # STATE LATCHING: If an active incident already exists with the exact same type and severity,
        # keep the alert steady without creating duplicate incidents or sending duplicate emails,
        # but sync updated summary text if live telemetry numbers changed.
        if active_inc and active_inc.type == incident_type and active_inc.severity == severity and not is_simulation:
            if active_inc.summary != summary:
                active_inc.summary = summary
                active_inc.confidence = round(confidence, 2)
                await db.commit()
                ws_update = {
                    "type": "INCIDENT_ALERT",
                    "id": active_inc.id,
                    "incident_id": active_inc.id,
                    "room_id": room_id,
                    "incident_type": incident_type,
                    "severity": severity,
                    "status": "ACTIVE",
                    "confidence": round(confidence, 2),
                    "summary": summary,
                    "evidence": evidence_list,
                    "timeline": active_inc.timeline or [],
                    "created_at": active_inc.created_at.isoformat() if active_inc.created_at else utcnow().isoformat(),
                }
                await event_manager.broadcast(ws_update)
                sync_incident_to_firebase(active_inc.id, {**ws_update, "type": incident_type})
            return None

        unique_suffix = uuid.uuid4().hex[:6].upper()
        incident_id = f"INC-{utcnow().strftime('%Y%m%d%H%M%S')}-{room_id[:4].upper()}-{unique_suffix}"

        timeline_copy = list(buf["timeline"])
        timeline_copy.append({
            "time": utcnow().isoformat(),
            "source": "FUSION",
            "description": f"Fusion engine formulated hypothesis: {incident_type} (Severity: {severity}, Confidence: {confidence:.2f})"
        })

        if active_inc:
            active_inc.type = incident_type
            active_inc.severity = severity
            active_inc.confidence = round(confidence, 2)
            active_inc.summary = summary
            active_inc.timeline = timeline_copy
            incident_id = active_inc.id
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

        for ev in evidence_list:
            db_ev = IncidentEvidence(
                incident_id=active_inc.id,
                source_type=ev["source_type"],
                source_id=ev["source_id"],
                contribution=ev["contribution"],
                explanation=ev["explanation"]
            )
            db.add(db_ev)

        room_q = select(Room).where(Room.id == room_id)
        r_res = await db.execute(room_q)
        room = r_res.scalar_one_or_none()
        if room:
            room.state = "INCIDENT" if severity == "CRITICAL" else "ANOMALY"

        await db.commit()

        created_time = utcnow().isoformat()
        ws_payload = {
            "type": "INCIDENT_ALERT",
            "id": incident_id,
            "incident_id": incident_id,
            "room_id": room_id,
            "incident_type": incident_type,
            "severity": severity,
            "status": "ACTIVE",
            "confidence": round(confidence, 2),
            "summary": summary,
            "evidence": evidence_list,
            "timeline": timeline_copy,
            "created_at": created_time
        }
        fb_payload = {
            **ws_payload,
            "type": incident_type,
        }
        await event_manager.broadcast(ws_payload)
        logger.info(f"[FUSION] Incident {incident_id} STATE CHANGED for {room_id}: {incident_type} [{severity}] (Conf: {confidence:.2f})")

        sync_incident_to_firebase(incident_id, fb_payload)
        sync_room_state_to_firebase(room_id, "INCIDENT" if severity == "CRITICAL" else "ANOMALY", incident_id)

        # Automatically dispatch Warning / Critical Alert email report for this room
        if not is_simulation and os.environ.get("TESTING") != "1" and email_service.auto_send:
            telem_snapshot = {
                "temperature": temp_val,
                "humidity": humidity_val,
                "gas": gas_val,
                "smoke": smoke_val,
                "light": light_val,
                "occupancy": occupancy,
            }
            asyncio.create_task(
                email_service.send_room_report(
                    room_id=room_id,
                    severity=severity,
                    incident=fb_payload,
                    telemetry=telem_snapshot,
                    trigger_source="AUTO_ALERT",
                )
            )

        return ws_payload

# Global fusion engine instance
fusion_engine = MultimodalFusionEngine()
