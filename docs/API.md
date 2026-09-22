# NEXUS REST & WebSocket API Specification

## Base URL: `http://127.0.0.1:8000`

---

## 1. System Health & Rooms

### `GET /api/health`
Returns system operational status, database connectivity, and AI engine mode (`ONLINE` vs `DEGRADED_LOCAL_MODE`).

### `GET /api/rooms`
Retrieves all 9 monitored rooms with floor, type, 3D coordinates, and state (`NORMAL`, `ATTENTION`, `ANOMALY`, `INCIDENT`, `OFFLINE`).

### `GET /api/rooms/{room_id}`
Retrieves details for a specific room.

### `PUT /api/rooms/{room_id}/state`
Updates room condition state and broadcasts the update to the 3D digital twin over WebSockets.

---

## 2. Sensor Telemetry & Ingestion

### `POST /api/sensors/reading`
Ingest an individual sensor reading:
```json
{
  "device_id": "esp32_lab02",
  "room_id": "lab_02",
  "sensor_type": "temperature",
  "value": 24.5,
  "unit": "C"
}
```

### `POST /api/sensors/batch`
Ingest multi-channel batch payload from ESP32:
```json
{
  "device_id": "esp32_lab02",
  "room_id": "lab_02",
  "readings": [
    {"sensor_type": "temperature", "value": 25.1, "unit": "C"},
    {"sensor_type": "humidity", "value": 44.0, "unit": "%"},
    {"sensor_type": "gas", "value": 110.0, "unit": "ppm"},
    {"sensor_type": "motion", "value": 1, "unit": "state"},
    {"sensor_type": "vibration", "value": 0.04, "unit": "g"}
  ]
}
```

### `GET /api/sensors/history?sensor_type=temperature&limit=50`
Retrieves historical telemetry for charts and statistical baseline computation.

---

## 3. Multimodal Events (Vision & Audio)

### `POST /api/vision/event`
Dispatches a structured computer vision event:
```json
{
  "room_id": "lab_02",
  "event_type": "PERSON_DETECTED",
  "confidence": 0.94,
  "occupancy_count": 2,
  "bounding_boxes": [{"class": "person", "box": [100, 120, 80, 160]}]
}
```

### `POST /api/audio/event`
Dispatches a structured acoustic event:
```json
{
  "room_id": "lab_02",
  "event_type": "ALARM",
  "confidence": 0.92,
  "rms_energy": 0.55,
  "spectral_centroid": 2500.0
}
```

---

## 4. Multimodal Incidents

### `GET /api/incidents?status=ACTIVE`
Retrieves active incidents with evidence attribution and chronological timeline.

### `POST /api/incidents/{id}/resolve`
Resolves an incident and resets the monitored room state to `NORMAL`.

---

## 5. Predictive Modeling & Simulation

### `GET /api/prediction/{room_id}?variable=temperature`
Returns instantaneous rate of change and forecasted values over +1m, +5m, and +15m horizons with 95% uncertainty bounds.

### `POST /api/simulation/run`
Executes What-If scenario through the production fusion engine:
```json
{
  "scenario": "gas_leak",
  "room_id": "lab_02",
  "temperature_delta": 15.0,
  "gas_delta": 280.0,
  "motion": true,
  "person_present": true,
  "acoustic_anomaly": true,
  "disabled_sensors": ["gas"]
}
```

---

## 6. Generative AI Reasoning

### `POST /api/ai/ask`
Operator Assistant question answering:
```json
{
  "question": "Why is Laboratory 02 highlighted?"
}
```

### `GET /api/ai/explain/{incident_id}`
Returns evidence-grounded incident analysis.

### `GET /api/ai/report/{incident_id}?format=html`
Renders and returns a formal post-incident technical briefing HTML report.

---

## 7. Real-Time WebSocket Endpoint

### `WS /ws/telemetry`
Real-time bi-directional telemetry and event bus streaming:
* `SENSOR_READING` / `SENSOR_BATCH`
* `VISION_EVENT`
* `AUDIO_EVENT`
* `INCIDENT_ALERT`
* `INCIDENT_RESOLVED`
* `ROOM_STATE_CHANGED`
