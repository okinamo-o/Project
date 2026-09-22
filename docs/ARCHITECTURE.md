# NEXUS System Architecture

## 1. High-Level Topology

NEXUS is designed as a local-first, modular, event-driven multimodal digital twin system:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        PHYSICAL / IOT LAYER                            │
│  [Wokwi ESP32 / Physical Node] DHT22, MQ-2 Gas, PIR, LDR, MPU6050 IMU   │
│  [Vision Pipeline] DirectShow Webcam / Real-time Synthetic Generator   │
│  [Audio Pipeline] Microphone DSP / Spectral Centroid Classifier        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP / WebSocket / MQTT
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                       NEXUS CORE ENGINE (FASTAPI)                      │
│  ┌───────────────────────┐  ┌────────────────────────────────────────┐ │
│  │ Ingestion Handlers    │  │ Real-Time WebSocket Broadcaster        │ │
│  │ /api/sensors/batch    │  │ /ws/telemetry                          │ │
│  └───────────┬───────────┘  └────────────────────────────────────────┘ │
│              │                                                         │
│              ▼                                                         │
│  ┌───────────────────────┐  ┌────────────────────────────────────────┐ │
│  │ ML Anomaly Detector   │  │ Trend Forecaster Engine                │ │
│  │ (IsolationForest)     │  │ (+1m, +5m, +15m Horizons & CI)         │ │
│  └───────────┬───────────┘  └──────────────────┬─────────────────────┘ │
│              │                                 │                       │
│              └────────────────┬────────────────┘                       │
│                               ▼                                        │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │               CENTRAL MULTIMODAL FUSION ENGINE                    │ │
│  │ • Temporal correlation window (120s)                              │ │
│  │ • Multi-signal hypothesis synthesis                               │ │
│  │ • Dynamic evidence weighting & attribution                        │ │
│  └────────────────────────────┬──────────────────────────────────────┘ │
│                               │                                        │
│                               ▼                                        │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                   SQLAlchemy Database Layer                       │ │
│  │ Default: SQLite (nexus.db) | Optional: PostgreSQL 15 Container    │ │
│  └────────────────────────────┬──────────────────────────────────────┘ │
└───────────────────────────────┼────────────────────────────────────────┘
                                │ Structured Context & Keyframes
                                ▼
┌────────────────────────────────────────────────────────────────────────┐
│                 GENERATIVE AI REASONING LAYER (GEMINI)                 │
│  • Evidence-Grounded Forensic Explanations                             │
│  │ • Natural Language Operator Assistant ("Ask NEXUS...")              │
│  │ • Automated Technical Incident Briefing Reports                     │
│  │ • Offline/Degraded Mode Guarantee                                   │
└───────────────────────────────┬────────────────────────────────────────┘
                                │ Real-Time WebSocket Telemetry
                                ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   NEXUS OPERATIONS CENTER (NEXT.JS)                    │
│  • Interactive 3D Digital Twin (Three.js Building Model)               │
│  • Dynamic Glow States (NORMAL, ATTENTION, ANOMALY, INCIDENT, OFFLINE)  │
│  • Telemetry Gauge Needles, Occupancy & Acoustic Monitors              │
│  • Multimodal Evidence Attribution Matrix & Chronological Timeline     │
│  • "What If?" Scenario Simulation & Sensor Failure Sensitivity Panel   │
│  • Voice Command Interface (Web Speech API)                            │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Decoupled Subsystems & Contracts

| Subsystem | Folder | Key Interface / Protocol | Primary Output |
| :--- | :--- | :--- | :--- |
| **IoT Node** | `iot/` | JSON over HTTP POST / MQTT | 6-channel sensor telemetry batch |
| **Vision** | `ai/vision/` | JSON + JPEG base64 snapshot | Structured vision event (`occupancy`, `bboxes`) |
| **Audio** | `ai/audio/` | JSON with DSP descriptors | Acoustic event (`rms`, `spectral_centroid`) |
| **ML Models** | `ml/` | `joblib` model pipeline | Normalized anomaly score $[0.0, 1.0]$ |
| **Forecasting** | `backend/app/prediction/` | Least-squares polynomial | Predicted values with 95% confidence intervals |
| **Fusion Engine** | `backend/app/fusion/` | Internal Event Bus | Attributed Incident + Chronological Timeline |
| **Generative AI**| `backend/app/services/` | Google GenAI SDK / Local Expert | Contextual natural language explanations |
| **Digital Twin** | `frontend/components/` | Three.js Raycasting & Materials | Responsive 3D physical representation |
