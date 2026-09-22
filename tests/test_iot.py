import pytest
import httpx
from backend.app.main import app

@pytest.mark.asyncio
async def test_iot_batch_ingestion():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "device_id": "esp32_lab02",
            "room_id": "lab_02",
            "readings": [
                {"sensor_type": "temperature", "value": 26.8, "unit": "C"},
                {"sensor_type": "humidity", "value": 44.0, "unit": "%"},
                {"sensor_type": "gas", "value": 120.0, "unit": "ppm"},
                {"sensor_type": "motion", "value": 1, "unit": "state"},
                {"sensor_type": "light", "value": 520, "unit": "lux"},
                {"sensor_type": "vibration", "value": 0.045, "unit": "g"}
            ]
        }
        res = await client.post("/api/sensors/batch", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "batch_ingested"
        assert data["count"] == 6

        # Verify history retrieval
        hist_res = await client.get("/api/sensors/history?sensor_type=gas&limit=10")
        assert hist_res.status_code == 200
        hist_data = hist_res.json()
        assert len(hist_data) >= 1
        assert any(r["value"] == 120.0 for r in hist_data)
