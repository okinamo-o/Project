import pytest
import httpx
from backend.app.main import app

@pytest.mark.asyncio
async def test_what_if_simulation_full_and_failure():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. Run full multimodal crisis
        full_payload = {
            "scenario": "chemical_gas_fire",
            "room_id": "lab_02",
            "temperature_delta": 22.0, # 23.5 + 22.0 = 45.5 C
            "gas_delta": 350.0,        # 75.0 + 350.0 = 425 ppm
            "motion": True,
            "person_present": True,
            "acoustic_anomaly": True,
            "disabled_sensors": []
        }
        res_full = await client.post("/api/simulation/run", json=full_payload)
        assert res_full.status_code == 200
        data_full = res_full.json()
        assert data_full["status"] == "simulation_executed"
        output_full = data_full["fusion_output"]
        assert output_full is not None
        assert output_full["severity"] == "CRITICAL"
        conf_full = output_full["confidence"]
        assert conf_full >= 0.90

        # 2. Simulate Sensor Failure: Disable Gas Sensor & Camera
        failure_payload = {
            "scenario": "degraded_sensor_failure",
            "room_id": "lab_02",
            "temperature_delta": 22.0,
            "gas_delta": 350.0,
            "motion": True,
            "person_present": True,
            "acoustic_anomaly": False,
            "disabled_sensors": ["gas", "camera"]
        }
        res_fail = await client.post("/api/simulation/run", json=failure_payload)
        assert res_fail.status_code == 200
        data_fail = res_fail.json()
        output_fail = data_fail["fusion_output"]
        assert output_fail is not None
        
        # Verify evidence matrix no longer contains GAS or VISION
        evidence_sources = [e["source_type"] for e in output_fail["evidence"]]
        evidence_ids = [e["source_id"] for e in output_fail["evidence"]]
        assert "mq2_gas" not in evidence_ids
        assert "surveillance_cam" not in evidence_ids
        
        # Verify confidence decreased due to sensor failure
        assert output_fail["confidence"] < conf_full
