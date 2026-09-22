import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models.schema import Room, Device

logger = logging.getLogger("nexus.seed")

DEFAULT_ROOMS = [
    {
        "id": "entrance",
        "name": "Main Entrance",
        "floor": 1,
        "type": "entrance",
        "coordinates": {"x": 0, "y": 0, "z": 0, "w": 8, "h": 3.5, "d": 6},
        "metadata": {"capacity": 50, "security_level": "standard", "sensors": ["motion", "camera", "light"]}
    },
    {
        "id": "main_hall",
        "name": "Main Atrium & Hall",
        "floor": 1,
        "type": "hall",
        "coordinates": {"x": 0, "y": 0, "z": -8, "w": 14, "h": 4.0, "d": 8},
        "metadata": {"capacity": 120, "security_level": "standard", "sensors": ["motion", "temp", "audio"]}
    },
    {
        "id": "classroom_01",
        "name": "Classroom 01",
        "floor": 1,
        "type": "classroom",
        "coordinates": {"x": -9, "y": 0, "z": -8, "w": 8, "h": 3.5, "d": 7},
        "metadata": {"capacity": 30, "security_level": "standard", "sensors": ["temp", "humidity", "co2", "motion"]}
    },
    {
        "id": "classroom_02",
        "name": "Classroom 02",
        "floor": 1,
        "type": "classroom",
        "coordinates": {"x": 9, "y": 0, "z": -8, "w": 8, "h": 3.5, "d": 7},
        "metadata": {"capacity": 30, "security_level": "standard", "sensors": ["temp", "humidity", "co2", "motion"]}
    },
    {
        "id": "lab_01",
        "name": "Computer Science Lab 01",
        "floor": 2,
        "type": "lab",
        "coordinates": {"x": -9, "y": 4.5, "z": -8, "w": 8, "h": 3.5, "d": 7},
        "metadata": {"capacity": 25, "security_level": "elevated", "sensors": ["temp", "power", "smoke", "motion"]}
    },
    {
        "id": "lab_02",
        "name": "Chemistry & Physics Lab 02",
        "floor": 2,
        "type": "lab",
        "coordinates": {"x": 9, "y": 4.5, "z": -8, "w": 8, "h": 3.5, "d": 7},
        "metadata": {"capacity": 25, "security_level": "high", "sensors": ["temp", "gas", "motion", "vibration", "camera", "audio"]}
    },
    {
        "id": "server_room",
        "name": "Central Server & Telecom Room",
        "floor": 1,
        "type": "server_room",
        "coordinates": {"x": -9, "y": 0, "z": 0, "w": 6, "h": 3.5, "d": 5},
        "metadata": {"capacity": 4, "security_level": "critical", "sensors": ["temp", "humidity", "vibration", "airflow"]}
    },
    {
        "id": "storage_room",
        "name": "Chemical Storage Room",
        "floor": 2,
        "type": "storage_room",
        "coordinates": {"x": 0, "y": 4.5, "z": -12, "w": 6, "h": 3.5, "d": 5},
        "metadata": {"capacity": 5, "security_level": "high", "sensors": ["gas", "temp", "motion"]}
    },
    {
        "id": "emergency_exit",
        "name": "Emergency Exit & Stairwell",
        "floor": 1,
        "type": "exit",
        "coordinates": {"x": 9, "y": 0, "z": 0, "w": 5, "h": 3.5, "d": 5},
        "metadata": {"capacity": 20, "security_level": "emergency", "sensors": ["motion", "door_contact", "camera"]}
    }
]

DEFAULT_DEVICES = [
    {"id": "esp32_lab02", "room_id": "lab_02", "name": "Lab 02 Multi-Sensor ESP32 Node", "device_type": "esp32_multisensor"},
    {"id": "esp32_server", "room_id": "server_room", "name": "Server Room Climate Node", "device_type": "esp32_climate"},
    {"id": "esp32_storage", "room_id": "storage_room", "name": "Storage Fume Monitor", "device_type": "esp32_gas"},
    {"id": "cam_lab02", "room_id": "lab_02", "name": "Lab 02 AI Vision Cam", "device_type": "webcam_ai"},
    {"id": "cam_entrance", "room_id": "entrance", "name": "Entrance Vision Cam", "device_type": "webcam_ai"},
    {"id": "mic_lab02", "room_id": "lab_02", "name": "Lab 02 Acoustic Sensor Node", "device_type": "acoustic_node"}
]

async def seed_initial_data(session: AsyncSession):
    """Seed building rooms and monitoring devices if not already present."""
    # Check if rooms exist
    result = await session.execute(select(Room))
    existing_rooms = result.scalars().all()
    if not existing_rooms:
        logger.info("[SEED] Seeding 9 default rooms...")
        for r_data in DEFAULT_ROOMS:
            room = Room(
                id=r_data["id"],
                name=r_data["name"],
                floor=r_data["floor"],
                type=r_data["type"],
                coordinates=r_data["coordinates"],
                state="NORMAL",
                room_metadata=r_data["metadata"]
            )
            session.add(room)
        await session.flush()

        logger.info("[SEED] Seeding initial IoT and sensor devices...")
        for d_data in DEFAULT_DEVICES:
            device = Device(
                id=d_data["id"],
                room_id=d_data["room_id"],
                name=d_data["name"],
                device_type=d_data["device_type"],
                status="ONLINE"
            )
            session.add(device)
        await session.commit()
        logger.info("[SEED] Seeding completed successfully.")
    else:
        logger.info("[SEED] Database already populated with rooms.")
