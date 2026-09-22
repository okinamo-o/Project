import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.db.database import get_db
from backend.app.models.schema import Room
from backend.app.schemas.schemas import RoomResponse, RoomStateUpdate
from backend.app.core.events import event_manager

router = APIRouter()
logger = logging.getLogger("nexus.api.rooms")

@router.get("", response_model=List[RoomResponse])
async def get_all_rooms(db: AsyncSession = Depends(get_db)):
    """Retrieve all rooms with current state, coordinates, and metadata."""
    result = await db.execute(select(Room).order_by(Room.floor, Room.name))
    rooms = result.scalars().all()
    return rooms

@router.get("/{room_id}", response_model=RoomResponse)
async def get_room(room_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieve a specific room by identifier."""
    result = await db.execute(select(Room).where(Room.id == room_id))
    room = result.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=404, detail=f"Room '{room_id}' not found")
    return room

@router.put("/{room_id}/state", response_model=RoomResponse)
async def update_room_state(room_id: str, update: RoomStateUpdate, db: AsyncSession = Depends(get_db)):
    """Update a room's dynamic condition state and broadcast to 3D Digital Twin."""
    result = await db.execute(select(Room).where(Room.id == room_id))
    room = result.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=404, detail=f"Room '{room_id}' not found")
    
    room.state = update.state
    await db.commit()
    await db.refresh(room)

    # Broadcast event to frontend 3D twin
    await event_manager.broadcast({
        "type": "ROOM_STATE_CHANGED",
        "room_id": room.id,
        "state": room.state,
        "name": room.name
    })

    return room
