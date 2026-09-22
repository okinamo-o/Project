import pytest
import httpx
from backend.app.main import app

@pytest.mark.asyncio
async def test_health_endpoint():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["system"] == "NEXUS"
        assert "ai_engine" in data

@pytest.mark.asyncio
async def test_rooms_seeded():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Trigger startup lifespan by calling endpoint
        response = await client.get("/api/rooms")
        assert response.status_code == 200
        rooms = response.json()
        assert len(rooms) >= 9
        room_ids = [r["id"] for r in rooms]
        assert "lab_02" in room_ids
        assert "server_room" in room_ids
        assert "main_hall" in room_ids

@pytest.mark.asyncio
async def test_sensor_ingestion():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "device_id": "esp32_lab02",
            "room_id": "lab_02",
            "sensor_type": "temperature",
            "value": 24.5,
            "unit": "C"
        }
        response = await client.post("/api/sensors/reading", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ingested"
        assert data["reading"]["value"] == 24.5
