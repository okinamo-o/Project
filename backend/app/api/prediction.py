import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from backend.app.db.database import get_db
from backend.app.models.schema import SensorReading, Device
from backend.app.prediction.trend_forecaster import forecaster

router = APIRouter()
logger = logging.getLogger("nexus.api.prediction")

@router.get("/{room_id}")
async def get_room_prediction(
    room_id: str,
    variable: str = Query("temperature", description="Variable to forecast: temperature, gas, humidity"),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve instantaneous trend slope and forecasted horizons with uncertainty intervals."""
    # Fetch recent readings for this room's devices
    query = (
        select(SensorReading)
        .join(Device, SensorReading.device_id == Device.id)
        .where(Device.room_id == room_id, SensorReading.sensor_type == variable)
        .order_by(desc(SensorReading.timestamp))
        .limit(15)
    )
    result = await db.execute(query)
    readings = result.scalars().all()
    
    # Sort chronologically for regression
    readings_list = [{"value": r.value, "timestamp": r.timestamp} for r in reversed(readings)]
    
    forecast_result = forecaster.forecast(readings_list, variable=variable)
    forecast_result["room_id"] = room_id
    
    return forecast_result
