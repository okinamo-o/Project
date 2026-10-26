import time
import datetime
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from backend.app.db.database import get_db
from backend.app.models.schema import SensorReading, Device, Room
from backend.app.schemas.schemas import SensorReadingCreate, SensorBatchCreate
from backend.app.core.events import event_manager
from backend.app.fusion.engine import fusion_engine
from backend.app.db.firebase_client import sync_telemetry_to_firebase

router = APIRouter()
logger = logging.getLogger("nexus.api.sensors")

_last_wokwi_timestamp: float = 0.0

@router.get("/status/wokwi")
async def get_wokwi_status():
    """Returns whether an active Wokwi hardware node is currently streaming."""
    active = (time.time() - _last_wokwi_timestamp) < 15.0
    return {"wokwi_active": active, "last_seen_seconds_ago": round(time.time() - _last_wokwi_timestamp, 1)}


@router.post("/reading")
async def ingest_sensor_reading(
    reading: SensorReadingCreate,
    db: AsyncSession = Depends(get_db)
):
    """Ingest a single sensor reading from an IoT device or Wokwi simulator."""
    ts = reading.timestamp or datetime.datetime.now(datetime.timezone.utc)
    room_id = reading.room_id or "lab_02"
    
    # Ensure device exists
    dev_id = reading.device_id or f"esp32_{room_id}"
    dev = await db.get(Device, dev_id)
    if not dev:
        dev = Device(
            id=dev_id,
            room_id=room_id,
            name=f"{room_id.replace('_', ' ').title()} Sensor Node",
            device_type="esp32_multisensor",
            status="ONLINE"
        )
        db.add(dev)
        await db.flush()

    # Store reading
    db_reading = SensorReading(
        device_id=dev_id,
        timestamp=ts,
        sensor_type=reading.sensor_type,
        value=reading.value,
        unit=reading.unit,
        quality="GOOD"
    )
    db.add(db_reading)
    await db.commit()

    # Record signal in Multimodal Fusion Engine
    fusion_engine.record_signal(room_id, "sensor", {
        "sensor_type": reading.sensor_type,
        "value": reading.value,
        "unit": reading.unit
    })

    # Prepare payload for real-time WebSocket stream
    payload = {
        "type": "SENSOR_READING",
        "room_id": room_id,
        "device_id": dev_id,
        "sensor_type": reading.sensor_type,
        "value": reading.value,
        "unit": reading.unit,
        "timestamp": ts.isoformat()
    }
    
    # Broadcast to all connected clients
    await event_manager.broadcast(payload)

    # Push to Firebase Realtime Database
    sync_telemetry_to_firebase(room_id, {
        "room_id": room_id,
        "device_id": dev_id,
        "timestamp": ts.isoformat(),
        reading.sensor_type: reading.value,
        "latest_update": {
            "sensor_type": reading.sensor_type,
            "value": reading.value,
            "unit": reading.unit
        }
    })

    # Trigger fusion evaluation
    await fusion_engine.evaluate_room(room_id, db)
    
    return {"status": "ingested", "id": db_reading.id, "reading": payload}

@router.post("/batch")
async def ingest_sensor_batch(
    batch: SensorBatchCreate,
    db: AsyncSession = Depends(get_db)
):
    """Ingest a batch of sensor readings from an ESP32 multi-sensor payload."""
    global _last_wokwi_timestamp
    now_mono = time.time()
    if batch.device_id == "esp32_lab02" or "wokwi" in str(batch.device_id).lower():
        _last_wokwi_timestamp = now_mono
    elif str(batch.device_id).startswith("sim_esp32_lab"):
        if (now_mono - _last_wokwi_timestamp) < 15.0:
            return {"status": "suppressed_by_live_wokwi", "count": 0}

    ts = batch.timestamp or datetime.datetime.now(datetime.timezone.utc)
    created_ids = []
    broadcast_items = []

    # Ensure device exists
    dev = await db.get(Device, batch.device_id)
    if not dev:
        dev = Device(
            id=batch.device_id,
            room_id=batch.room_id,
            name=f"{batch.room_id.replace('_', ' ').title()} Sensor Node",
            device_type="esp32_multisensor",
            status="ONLINE"
        )
        db.add(dev)
        await db.flush()

    for item in batch.readings:
        db_reading = SensorReading(
            device_id=batch.device_id,
            timestamp=ts,
            sensor_type=item.get("sensor_type", "unknown"),
            value=float(item.get("value", 0.0)),
            unit=item.get("unit", ""),
            quality="GOOD"
        )
        db.add(db_reading)
        await db.flush()
        created_ids.append(db_reading.id)
        broadcast_items.append({
            "sensor_type": item.get("sensor_type"),
            "value": float(item.get("value", 0.0)),
            "unit": item.get("unit", "")
        })

        # Record in fusion engine
        fusion_engine.record_signal(batch.room_id, "sensor", item)

    await db.commit()

    # Broadcast multi-channel event
    is_wokwi_node = (batch.device_id == "esp32_lab02" or "wokwi" in str(batch.device_id).lower())
    payload = {
        "type": "SENSOR_BATCH",
        "room_id": batch.room_id,
        "device_id": batch.device_id,
        "is_wokwi": is_wokwi_node,
        "readings": broadcast_items,
        "timestamp": ts.isoformat()
    }
    await event_manager.broadcast(payload)

    # Push to Firebase Realtime Database
    batch_dict = {
        "room_id": batch.room_id,
        "device_id": batch.device_id,
        "timestamp": ts.isoformat(),
        "readings": broadcast_items
    }
    for item in broadcast_items:
        st = item.get("sensor_type")
        if st:
            batch_dict[st] = item.get("value")
    sync_telemetry_to_firebase(batch.room_id, batch_dict)

    # Evaluate fusion
    await fusion_engine.evaluate_room(batch.room_id, db)

    return {"status": "batch_ingested", "count": len(created_ids)}

@router.get("/room/{room_id}/latest")
async def get_room_latest_readings(
    room_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Fetch the latest reading for each sensor type in a specific room."""
    # Query devices for this room
    dev_query = select(Device.id).where(Device.room_id == room_id)
    dev_res = await db.execute(dev_query)
    device_ids = dev_res.scalars().all()
    if not device_ids:
        device_ids = [f"esp32_{room_id}"]

    query = (
        select(SensorReading)
        .where(SensorReading.device_id.in_(device_ids))
        .order_by(desc(SensorReading.timestamp))
        .limit(40)
    )
    result = await db.execute(query)
    readings = result.scalars().all()

    latest: dict = {}
    for r in readings:
        if r.sensor_type not in latest:
            latest[r.sensor_type] = {
                "sensor_type": r.sensor_type,
                "value": r.value,
                "unit": r.unit,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                "device_id": r.device_id
            }

    # Distinct baseline fallbacks per room type if not yet ingested
    room_baselines = {
        "server_room": {"temperature": 18.5, "humidity": 35.0, "gas": 35.0, "smoke": 0.1, "vibration": 0.075, "motion": 0, "light": 150},
        "classroom_01": {"temperature": 21.8, "humidity": 48.0, "gas": 240.0, "smoke": 0.3, "vibration": 0.015, "motion": 1, "light": 450},
        "classroom_02": {"temperature": 22.2, "humidity": 47.0, "gas": 260.0, "smoke": 0.3, "vibration": 0.018, "motion": 1, "light": 480},
        "lab_01": {"temperature": 21.5, "humidity": 44.0, "gas": 80.0, "smoke": 0.2, "vibration": 0.020, "motion": 1, "light": 520},
        "lab_02": {"temperature": 23.5, "humidity": 45.0, "gas": 75.0, "smoke": 0.4, "vibration": 0.035, "motion": 0, "light": 500},
        "storage_room": {"temperature": 19.8, "humidity": 40.0, "gas": 125.0, "smoke": 0.5, "vibration": 0.012, "motion": 0, "light": 80},
        "main_hall": {"temperature": 21.0, "humidity": 50.0, "gas": 180.0, "smoke": 0.3, "vibration": 0.028, "motion": 1, "light": 650},
        "entrance": {"temperature": 20.5, "humidity": 52.0, "gas": 160.0, "smoke": 0.2, "vibration": 0.024, "motion": 1, "light": 700},
        "emergency_exit": {"temperature": 19.2, "humidity": 46.0, "gas": 65.0, "smoke": 0.1, "vibration": 0.010, "motion": 0, "light": 200}
    }
    baseline = room_baselines.get(room_id, {"temperature": 22.0, "humidity": 45.0, "gas": 90.0, "smoke": 0.3, "vibration": 0.02, "motion": 0, "light": 400})

    for stype, default_val in baseline.items():
        if stype not in latest:
            latest[stype] = {
                "sensor_type": stype,
                "value": default_val,
                "unit": "C" if stype == "temperature" else "%" if stype in ["humidity", "smoke"] else "ppm" if stype == "gas" else "g" if stype == "vibration" else "lux" if stype == "light" else "state",
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "device_id": f"esp32_{room_id}"
            }

    return {"room_id": room_id, "readings": latest}

@router.get("/latest")
async def get_latest_readings(
    device_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Fetch the latest reading for each sensor type."""
    query = select(SensorReading).order_by(desc(SensorReading.timestamp)).limit(20)
    if device_id:
        query = query.where(SensorReading.device_id == device_id)
    result = await db.execute(query)
    readings = result.scalars().all()
    return readings

@router.get("/history")
async def get_sensor_history(
    sensor_type: str = Query(..., description="temperature, humidity, gas, motion, light, vibration"),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve historical telemetry for charting and trend evaluation."""
    query = (
        select(SensorReading)
        .where(SensorReading.sensor_type == sensor_type)
        .order_by(desc(SensorReading.timestamp))
        .limit(limit)
    )
    result = await db.execute(query)
    readings = result.scalars().all()
    # Return in chronological order
    readings.reverse()
    return readings
