# NEXUS

**Multimodal AI Digital Twin for Intelligent Environmental Monitoring, Prediction and Decision Support**

[![Backend Tests](https://img.shields.io/badge/pytest-12%20passed-10b981.svg)](#testing)
[![Next.js Build](https://img.shields.io/badge/next.js-v14.2%20passing-38bdf8.svg)](#frontend)
[![Python](https://img.shields.io/badge/python-3.11-blue.svg)](#backend)
[![Three.js](https://img.shields.io/badge/three.js-3D%20twin-purple.svg)](#3d-digital-twin)
[![AI Reasoning](https://img.shields.io/badge/Gemini-2.5%20Flash-orange.svg)](#generative-ai)

NEXUS is an educational, local-first multimodal software system that creates an interactive 3D digital twin of a building to perform real-time environmental monitoring, machine learning anomaly detection, predictive trend forecasting, multi-signal evidence fusion, and generative AI decision support.

> **Core Philosophy:**  
> NEXUS does not merely display individual sensor readings. It correlates multiple independent physical signals (IoT telemetry, local computer vision, acoustic DSP, trend forecasting) to understand complex situations, detect anomalous patterns, estimate their future trajectory, explain the underlying evidence, and enable human operators to explore "What If?" alternative scenarios.

---

## Architecture Overview

```
                ┌────────────────────────┐
                │      WOKWI ESP32       │
                │  Temp, Gas, Motion,    │
                │  Light, Vibration IMU  │
                └───────────┬────────────┘
                            │ HTTP / WebSocket / MQTT
                            ▼
                ┌────────────────────────┐
                │     NEXUS BACKEND      │
                │        FastAPI         │
                └───────────┬────────────┘
                            │
            ┌───────────────┼────────────────┐
            │               │                │
            ▼               ▼                ▼
       PostgreSQL/     ML ANOMALY       PREDICTION
         SQLite         DETECTION        ENGINE
            │        (IsolationForest) (+1m, +5m, +15m)
            │               │                │
            └───────────────┼────────────────┘
                            ▼
                ┌────────────────────────┐
                │  MULTIMODAL FUSION     │
                │   • Sensory Evidence   │
                │   • Vision (YOLO/CV)   │
                │   • Audio (DSP/FFT)    │
                │   • Chronology Timeline│
                └───────────┬────────────┘
                            │
                            ▼
                ┌────────────────────────┐
                │    GEMINI REASONING    │
                │  Advisory & Explanatory│
                └───────────┬────────────┘
                            │
                            ▼
                ┌────────────────────────┐
                │     NEXUS FRONTEND     │
                │ Next.js + Three.js 3D  │
                │    Digital Twin Hub    │
                └────────────────────────┘
```

---

## Subsystem Capabilities

1. **3D Digital Twin (Three.js)**: Isometric 2-floor 3D building featuring 9 monitored zones (Main Hall, Classrooms 01 & 02, Labs 01 & 02, Server Room, Chemical Storage, Entrance, Emergency Exit). Rooms react dynamically to state (`NORMAL`, `ATTENTION`, `ANOMALY`, `INCIDENT`, `OFFLINE`) with neon glow shaders and pulsing beacons.
2. **IoT & Embedded Firmware (ESP32 / Wokwi)**: 6-channel sensor node with DHT22 (temp/humidity), MQ-2 gas, PIR motion, photoresistor, and MPU6050 vibration. Supports Wokwi simulation and physical hardware.
3. **Machine Learning Anomaly Detection**: Unsupervised `IsolationForest` pipeline trained on multivariate environmental dynamics, capturing rates of change and cross-sensor correlations with 93.6% accuracy.
4. **Predictive Modeling**: Short-term least-squares trend forecaster calculating instantaneous rates of change (°C/min) and estimating values across +1m, +5m, and +15m horizons with 95% uncertainty intervals.
5. **Edge-First Computer Vision**: Local OpenCV/YOLO pipeline extracting occupancy counts, human presence, and sudden movement vectors. Features dual-mode operation: physical DirectShow webcam capture or real-time synthetic surveillance rendering.
6. **Acoustic Intelligence**: Physical DSP pipeline computing RMS energy, zero-crossing rate (ZCR), and spectral centroid via FFT to classify operational acoustic signatures (`NORMAL`, `SPEECH`, `ALARM`, `IMPACT`, `KNOCK`, `SUDDEN_NOISE`).
7. **Multimodal Fusion Engine**: Centerpiece of NEXUS. Correlates independent signals within a 120s temporal window, attributes proportional weights to contributing evidence, maintains chronological timelines, and elevates facility condition states.
8. **Generative AI Advisory (Gemini)**: Secure server-side integration over structured project data for forensic incident explanations, natural language operator Q&A ("Ask NEXUS..."), and automated HTML technical briefing generation. Includes full **Offline / Degraded Mode** when no API key is supplied.
9. **"What If?" Sensitivity Engine**: Allows operators to inject parameter deltas and disable individual sensors (e.g. Gas or Camera) to demonstrate how NEXUS recalculates confidence without single-point failure.

---

## Quick Start Guide

### 1. Prerequisites
* **Node.js**: v18+ (tested on Node v24.13.1, NPM 11.8)
* **Python**: 3.10+ (tested on Python 3.11.9 64-bit)

### 2. Backend Setup
```powershell
# Navigate to backend and create virtual environment
cd backend
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install opencv-python-headless

# (Optional) Set your Gemini API key in .env or environment
# If omitted, NEXUS operates in local Offline Expert Mode
$env:GEMINI_API_KEY="your-gemini-api-key"

# Launch Backend Server
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
The backend initializes the local database (`nexus.db`), creates all schemas, and seeds default rooms and devices.
* API Documentation: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* Health Endpoint: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

### 3. Frontend Setup
Open a second terminal window:
```powershell
cd frontend
npm install
npm run dev
```
Open your browser at: **[http://localhost:3000](http://localhost:3000)**

---

## Running the Official 10-Stage Demonstration

With the frontend and backend running, open a third terminal and run the interactive demonstration script:

```powershell
python scripts/run_demo.py
```

The script guides you through the complete official scenario:
1. **Normal Baseline**: Reset all rooms and establish healthy telemetry.
2. **Thermal Anomaly**: Ingest rising heat in Laboratory 02.
3. **Second Modality**: MQ-2 gas sensor surges to 390 ppm.
4. **Computer Vision**: Human occupancy detected in hazardous area.
5. **Acoustic Siren**: Emergency 2.5 kHz alarm tone detected by DSP engine.
6. **Central Fusion**: Multi-modal incident created with evidence matrix and 3D twin alarm beacon.
7. **AI Investigation**: Natural-language explanation of why NEXUS triggered the alert.
8. **Prediction Trajectory**: Forecasted +5m and +15m values displayed.
9. **Sensitivity Test**: Disable Gas sensor and observe confidence recalculation.
10. **Official Briefing Report**: Open the generated HTML report.

---

## Testing

Run the automated test suite covering all APIs, fusion logic, machine learning, and simulation:

```powershell
.\backend\venv\Scripts\pytest tests/ -v
```

All 12 test suites pass with 100% verification:
* `test_health_endpoint`: API and system health
* `test_rooms_seeded`: Relational room seeding
* `test_sensor_ingestion`: Telemetry processing
* `test_iot_batch_ingestion`: Hardware parity payload
* `test_anomaly_detector_scoring`: ML Isolation Forest
* `test_prediction_api`: Polynomial trend forecasting
* `test_vision_event_ingestion`: Computer vision pipeline
* `test_audio_event_ingestion`: Acoustic DSP analysis
* `test_multimodal_fusion_incident_generation`: Central fusion engine
* `test_what_if_simulation_full_and_failure`: Sensitivity analysis
* `test_ai_operator_assistant`: Natural language Q&A
* `test_ai_explain_and_report`: Briefing report generation

---

## Technical Documentation Suite

Detailed architectural reports are available in the [`docs/`](docs/) directory:
* [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): System topology and decoupled contracts
* [`docs/API.md`](docs/API.md): REST and WebSocket API specification
* [`docs/DATABASE.md`](docs/DATABASE.md): Entity relationship model and schema
* [`docs/ML.md`](docs/ML.md): Machine learning methodology, features, and metrics
* [`docs/AI.md`](docs/AI.md): Gemini prompt architecture and offline degraded mode
* [`docs/IOT.md`](docs/IOT.md): Wokwi ESP32 pinout, wiring, and firmware
* [`docs/VISION.md`](docs/VISION.md): Computer vision edge processing
* [`docs/AUDIO.md`](docs/AUDIO.md): Acoustic DSP feature extraction and classification
* [`docs/SIMULATION.md`](docs/SIMULATION.md): What-If scenarios and sensor sensitivity
* [`docs/DEMO.md`](docs/DEMO.md): Presentation guide and script
* [`docs/DECISIONS.md`](docs/DECISIONS.md): Architectural Decision Records (ADRs)
* [`docs/ENVIRONMENT_AUDIT.md`](docs/ENVIRONMENT_AUDIT.md): Local environment findings
