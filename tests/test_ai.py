import pytest
import httpx
from backend.app.main import app

@pytest.mark.asyncio
async def test_ai_operator_assistant():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Ask question
        res = await client.post("/api/ai/ask", json={
            "question": "Why is Laboratory 02 highlighted?"
        })
        assert res.status_code == 200
        data = res.json()
        assert "answer" in data
        assert len(data["answer"]) > 10
        assert "is_offline_mode" in data

@pytest.mark.asyncio
async def test_ai_explain_and_report():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Trigger an incident first
        await client.post("/api/sensors/reading", json={
            "device_id": "esp32_lab02",
            "room_id": "lab_02",
            "sensor_type": "temperature",
            "value": 46.0,
            "unit": "C"
        })
        await client.post("/api/sensors/reading", json={
            "device_id": "esp32_lab02",
            "room_id": "lab_02",
            "sensor_type": "gas",
            "value": 390.0,
            "unit": "ppm"
        })

        inc_res = await client.get("/api/incidents?status=ACTIVE")
        incidents = inc_res.json()
        assert len(incidents) > 0
        inc_id = incidents[0]["id"]

        # Test Explanation
        exp_res = await client.get(f"/api/ai/explain/{inc_id}")
        assert exp_res.status_code == 200
        exp_data = exp_res.json()
        assert "explanation" in exp_data
        assert len(exp_data["explanation"]) > 20

        # Test HTML Report Generation
        rep_res = await client.get(f"/api/ai/report/{inc_id}?format=html")
        assert rep_res.status_code == 200
        assert "NEXUS INCIDENT INVESTIGATION REPORT" in rep_res.text
        assert "Multimodal Evidence Attribution" in rep_res.text
