import pytest
import httpx
from backend.app.main import app
from backend.app.prediction.anomaly_service import anomaly_detector

def test_anomaly_detector_scoring():
    # 1. Test normal readings
    normal_features = {
        "temperature": 23.0,
        "humidity": 45.0,
        "gas": 70.0,
        "vibration": 0.03,
        "motion": 0,
        "temp_rate_of_change": 0.0,
        "gas_rate_of_change": 0.0,
        "vibration_variance": 0.0001
    }
    is_anomaly, score, details = anomaly_detector.score_telemetry(normal_features)
    assert score < 0.60, f"Normal reading scored too high: {score}"

    # 2. Test thermal runaway anomaly
    hazard_features = {
        "temperature": 48.5,
        "humidity": 30.0,
        "gas": 480.0,
        "vibration": 0.25,
        "motion": 1,
        "temp_rate_of_change": 3.5,
        "gas_rate_of_change": 45.0,
        "vibration_variance": 0.05
    }
    is_anomaly, score, details = anomaly_detector.score_telemetry(hazard_features)
    assert is_anomaly is True
    assert score > 0.60

@pytest.mark.asyncio
async def test_prediction_api():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Seed 10 consecutive rising temperature readings for server_room
        for temp_val in [20.0, 21.0, 22.0, 23.0, 24.0, 25.0, 26.5, 28.0, 29.5, 31.0]:
            await client.post("/api/sensors/reading", json={
                "device_id": "esp32_server",
                "room_id": "server_room",
                "sensor_type": "temperature",
                "value": temp_val,
                "unit": "C"
            })
        
        response = await client.get("/api/prediction/server_room?variable=temperature")
        assert response.status_code == 200
        data = response.json()
        assert data["variable"] == "temperature"
        assert "horizons" in data
        assert "+5m" in data["horizons"]
        assert data["trend_slope"] > 0
        assert data["horizons"]["+5m"]["predicted"] > data["current_value"]
