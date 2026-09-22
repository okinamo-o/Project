# NEXUS Architectural Decision Records (ADR)

This document records the foundational and ongoing architectural decisions for the NEXUS system.

---

## ADR-001: Local-First Multi-Tier Architecture

* **Context**: NEXUS is designed to run reliably on a student's Windows PC without hard external cloud requirements.
* **Decision**: Implement a decoupled monorepo containing:
  1. Next.js App Router (TypeScript, Three.js, Tailwind CSS) for 3D visualization and dashboard.
  2. FastAPI async backend for high-throughput sensor telemetry, WebSocket distribution, and orchestration.
  3. Local ML & signal processing modules (scikit-learn, OpenCV, SciPy).
  4. Google GenAI (Gemini) strictly as an advisory reasoning layer over structured data.
* **Consequence**: The system functions completely even during network disconnection or API rate limits.

---

## ADR-002: Dual Database Engine (SQLite & PostgreSQL)

* **Context**: Docker Desktop may be stopped or unavailable on student machines, yet PostgreSQL is preferred for production.
* **Decision**: Use SQLAlchemy with `aiosqlite` as the default zero-config local database engine. When `DATABASE_URL` specifies `postgresql+asyncpg://...`, the backend automatically connects to PostgreSQL.
* **Consequence**: Zero configuration needed to launch the project out-of-the-box, while fully preserving migration compatibility with PostgreSQL.

---

## ADR-003: Edge-First Computer Vision & Audio Processing

* **Context**: Sending high-frequency raw video frames and audio streams to cloud LLMs introduces prohibitive latency, privacy concerns, and costs.
* **Decision**:
  - Run continuous local computer vision using Ultralytics YOLOv8n and OpenCV to extract structured events (`person_detected`, `occupancy_count`, `movement_velocity`).
  - Run continuous local acoustic signal processing using SciPy/NumPy to detect acoustic changes and classify sound classes.
  - Forward only structured telemetry and selective event keyframes to Gemini for high-level semantic investigation.
* **Consequence**: Sub-50ms local event detection and deterministic offline capabilities.

---

## ADR-004: Explicit Multimodal Fusion Engine

* **Context**: Single-sensor alarms suffer from high false-positive rates (e.g. temporary temperature drift or a harmless noise).
* **Decision**: Build an explicit fusion engine that scores incidents across 4 independent dimensions:
  1. Environmental telemetry (Temperature, Gas, Humidity, Light, Vibration).
  2. Visual evidence (Occupancy, unauthorized presence, rapid movement).
  3. Acoustic signatures (Alarm frequency, sudden impact, acoustic stress).
  4. Predictive trajectory (Forecasted sensor thresholds over +1m, +5m horizons).
* **Consequence**: Every incident retains an auditable evidence chain explaining which sensor contributed and at what time.

---

## ADR-005: Wokwi ESP32 + Direct Bridge Architecture

* **Context**: Physical ESP32 microcontrollers are not always plugged in, but realistic embedded firmware behavior is required.
* **Decision**: Provide standard ESP32 firmware with Wokwi project files (`diagram.json`, `wokwi.toml`, `sketch.ino`) alongside a bidirectional software IoT node emulator that transmits identical JSON payloads over HTTP/MQTT to the backend.
* **Consequence**: Allows instant runtime testing in the browser and CLI while maintaining exact firmware parity.
