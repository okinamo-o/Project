import pytest
import httpx
from backend.app.main import app

@pytest.mark.asyncio
async def test_vision_event_ingestion():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "room_id": "lab_02",
            "event_type": "PERSON_DETECTED",
            "confidence": 0.94,
            "occupancy_count": 2,
            "bounding_boxes": [{"class": "person", "box": [100, 100, 50, 120]}],
            "snapshot_base64": "data:image/jpeg;base64,/9j/4AAQSkZJRg==",
            "metadata": {"source": "test_cam"}
        }
        res = await client.post("/api/vision/event", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ingested"
        assert data["event"]["occupancy"] == 2

        # Verify latest retrieval
        latest_res = await client.get("/api/vision/latest/lab_02")
        assert latest_res.status_code == 200
        assert latest_res.json()["event_type"] == "PERSON_DETECTED"

@pytest.mark.asyncio
async def test_audio_event_ingestion():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "room_id": "lab_02",
            "event_type": "ALARM",
            "confidence": 0.92,
            "rms_energy": 0.55,
            "spectral_centroid": 2600.0,
            "zero_crossing_rate": 0.12,
            "metadata": {"source": "test_mic"}
        }
        res = await client.post("/api/audio/event", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ingested"
        assert data["event"]["event_type"] == "ALARM"

        # Verify latest retrieval
        latest_res = await client.get("/api/audio/latest/lab_02")
        assert latest_res.status_code == 200
        assert latest_res.json()["event_type"] == "ALARM"
