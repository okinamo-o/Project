import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.db.database import get_db
from backend.app.schemas.schemas import WhatIfSimulationRequest
from backend.app.fusion.engine import fusion_engine
from backend.app.core.events import event_manager

router = APIRouter()
logger = logging.getLogger("nexus.api.simulation")

PRECONFIGURED_SCENARIOS = {
    "normal_baseline": {
        "name": "Normal Operational Baseline",
        "description": "Stable diurnal baseline across all rooms. Low ambient noise, nominal temperature and humidity.",
        "room_id": "lab_02",
        "temperature": 23.5,
        "gas": 65.0,
        "motion": 0,
        "occupancy": 0,
        "audio": "NORMAL"
    },
    "thermal_runaway": {
        "name": "Thermal Runaway in Server Room",
        "description": "Cooling unit failure leads to severe temperature spike (+3.2°C/min) with thermal stress vibration.",
        "room_id": "server_room",
        "temperature": 45.0,
        "gas": 90.0,
        "motion": 0,
        "occupancy": 0,
        "audio": "NORMAL"
    },
    "chemical_gas_leak": {
        "name": "Volatile Solvent Gas Leak",
        "description": "Fume hood damper malfunction causes rapid accumulation of hazardous solvent vapor.",
        "room_id": "lab_02",
        "temperature": 25.0,
        "gas": 420.0,
        "motion": 1,
        "occupancy": 1,
        "audio": "NORMAL"
    },
    "electrical_fire_smoke": {
        "name": "Electrical Conflagration & Smoke Inversion",
        "description": "High-current insulation fault triggers intense optical smoke (>45% obscuration) with thermal flashover.",
        "room_id": "lab_02",
        "temperature": 52.0,
        "gas": 310.0,
        "smoke": 65.0,
        "motion": 1,
        "occupancy": 2,
        "audio": "ALARM"
    },
    "multi_signal_cascade": {
        "name": "Multi-Modal Cascading Crisis",
        "description": "Full-spectrum event: Rapid thermal rise, explosive gas surge, trapped personnel, and acoustic siren.",
        "room_id": "lab_02",
        "temperature": 48.0,
        "gas": 520.0,
        "smoke": 45.0,
        "motion": 1,
        "occupancy": 3,
        "audio": "ALARM"
    },
    "unauthorized_breach": {
        "name": "Off-Hours Facility Intrusion",
        "description": "Unauthorized subject detected at Emergency Exit corridor with acoustic impact impulse.",
        "room_id": "emergency_exit",
        "temperature": 21.0,
        "gas": 60.0,
        "smoke": 0.2,
        "motion": 1,
        "occupancy": 1,
        "audio": "IMPACT"
    }
}

@router.get("/scenarios")
async def list_scenarios():
    """List available preconfigured What-If simulation scenarios."""
    return PRECONFIGURED_SCENARIOS

@router.post("/run")
async def run_simulation_scenario(
    req: WhatIfSimulationRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Executes a 'What If?' simulation through the real multimodal fusion engine.
    Allows injecting synthetic sensor deltas and toggling sensor failures.
    """
    room_id = req.room_id or "lab_02"
    disabled = req.disabled_sensors

    # 1. Feed simulated sensor signals into fusion engine
    base_temp = 23.5 + req.temperature_delta
    base_gas = 75.0 + req.gas_delta
    base_smoke = 0.4 + req.smoke_delta
    
    if "temperature" not in disabled:
        fusion_engine.record_signal(room_id, "sensor", {
            "sensor_type": "temperature",
            "value": round(base_temp, 1),
            "unit": "C"
        })
    if "gas" not in disabled:
        fusion_engine.record_signal(room_id, "sensor", {
            "sensor_type": "gas",
            "value": round(base_gas, 1),
            "unit": "ppm"
        })
    if "smoke" not in disabled:
        fusion_engine.record_signal(room_id, "sensor", {
            "sensor_type": "smoke",
            "value": round(max(0.0, base_smoke), 1),
            "unit": "%"
        })
    if req.motion and "motion" not in disabled:
        fusion_engine.record_signal(room_id, "sensor", {
            "sensor_type": "motion",
            "value": 1,
            "unit": "state"
        })

    # 2. Feed simulated vision if enabled
    if req.person_present and "camera" not in disabled:
        fusion_engine.record_signal(room_id, "vision", {
            "event_type": "PERSON_DETECTED",
            "occupancy": 2,
            "confidence": 0.94
        })

    # 3. Feed simulated audio if enabled
    if req.acoustic_anomaly and "microphone" not in disabled:
        fusion_engine.record_signal(room_id, "audio", {
            "event_type": "ALARM",
            "rms_energy": 0.65,
            "spectral_centroid": 2600.0,
            "confidence": 0.95
        })

    # 4. Evaluate fusion under current active sensor configuration
    fusion_result = await fusion_engine.evaluate_room(room_id, db, disabled_sensors=disabled)

    # 5. Broadcast simulation event
    sim_payload = {
        "type": "SIMULATION_RESULT",
        "scenario": req.scenario,
        "room_id": room_id,
        "disabled_sensors": disabled,
        "fusion_result": fusion_result
    }
    await event_manager.broadcast(sim_payload)

    return {
        "status": "simulation_executed",
        "scenario": req.scenario,
        "room_id": room_id,
        "disabled_sensors": disabled,
        "fusion_output": fusion_result
    }
