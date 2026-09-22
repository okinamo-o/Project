import pytest
import httpx
from backend.app.main import app

@pytest.mark.asyncio
async def test_multimodal_fusion_incident_generation():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. First environmental signal: Temperature surge
        await client.post("/api/sensors/reading", json={
            "device_id": "esp32_lab02",
            "room_id": "lab_02",
            "sensor_type": "temperature",
            "value": 44.5,
            "unit": "C"
        })

        # 2. Second environmental signal: Gas leak spike
        await client.post("/api/sensors/reading", json={
            "device_id": "esp32_lab02",
            "room_id": "lab_02",
            "sensor_type": "gas",
            "value": 380.0,
            "unit": "ppm"
        })

        # 3. Third modality: Vision person detection
        await client.post("/api/vision/event", json={
            "room_id": "lab_02",
            "event_type": "PERSON_DETECTED",
            "confidence": 0.95,
            "occupancy_count": 2,
            "bounding_boxes": [{"class": "person", "box": [100, 100, 80, 160]}]
        })

        # 4. Fourth modality: Acoustic alarm
        await client.post("/api/audio/event", json={
            "room_id": "lab_02",
            "event_type": "ALARM",
            "confidence": 0.92,
            "rms_energy": 0.58,
            "spectral_centroid": 2500.0
        })

        # 5. Fetch Active Incidents
        res = await client.get("/api/incidents?status=ACTIVE")
        assert res.status_code == 200
        incidents = res.json()
        assert len(incidents) >= 1
        
        target_inc = next((i for i in incidents if i["room_id"] == "lab_02"), None)
        assert target_inc is not None
        assert target_inc["type"] == "MULTI_SIGNAL_ENVIRONMENTAL_CRISIS"
        assert target_inc["severity"] == "CRITICAL"
        assert target_inc["confidence"] >= 0.90
        
        # Verify evidence matrix
        evidence_sources = [e["source_type"] for e in target_inc["evidence"]]
        assert "SENSOR" in evidence_sources
        assert "VISION" in evidence_sources
        assert "AUDIO" in evidence_sources
        
        # Verify timeline sequence
        timeline_sources = [t["source"] for t in target_inc["timeline"]]
        assert "SENSOR" in timeline_sources
        assert "VISION" in timeline_sources
        assert "AUDIO" in timeline_sources
        assert "FUSION" in timeline_sources

        # Verify room state updated to INCIDENT
        room_res = await client.get("/api/rooms/lab_02")
        assert room_res.status_code == 200
        assert room_res.json()["state"] == "INCIDENT"


@pytest.mark.asyncio
async def test_smoke_detector_structural_fire_fusion():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. Optical Smoke Surge
        await client.post("/api/sensors/reading", json={
            "device_id": "esp32_storage",
            "room_id": "storage_room",
            "sensor_type": "smoke",
            "value": 28.5,
            "unit": "%"
        })

        # 2. Correlated Thermal Spike
        await client.post("/api/sensors/reading", json={
            "device_id": "esp32_storage",
            "room_id": "storage_room",
            "sensor_type": "temperature",
            "value": 47.0,
            "unit": "C"
        })

        # 3. Check incident creation
        res = await client.get("/api/incidents?status=ACTIVE")
        assert res.status_code == 200
        incidents = res.json()
        target_inc = next((i for i in incidents if i["room_id"] == "storage_room"), None)
        assert target_inc is not None
        assert target_inc["type"] == "STRUCTURAL_FIRE_CONFLAGRATION"
        assert target_inc["severity"] == "CRITICAL"
        
        # Verify smoke evidence attribution
        smoke_ev = next((e for e in target_inc["evidence"] if e["source_id"] == "optical_smoke_detector"), None)
        assert smoke_ev is not None
        assert smoke_ev["source_type"] == "SENSOR"
        assert "Optical smoke obscuration" in smoke_ev["explanation"]
