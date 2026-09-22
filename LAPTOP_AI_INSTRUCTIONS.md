# 🚀 NEXUS AI Handover & Deployment Guide (Laptop Environment)

> **Message for the AI Assistant / Developer on the Laptop:**
> Welcome! This codebase is **NEXUS**, a complete Multimodal AI Digital Twin platform for Real-Time Environmental Surveillance, Acoustic Threat Intelligence, Predictive Maintenance, and 3D Spatial Monitoring.
>
> The project has been refactored and optimized specifically for a **laptop environment** with a built-in webcam and integrated microphone array.
> Follow this guide to set up the environment, install all dependencies, verify the hardware, and run the system.

---

## ⚡ 1. Rapid Setup (One-Time Initialization)

### Step 1.1: Set up Python Virtual Environment & Dependencies
Open PowerShell or Command Prompt at the project root (`Nexus/`):

```powershell
# 1. Create a Python 3.10+ virtual environment
python -m venv backend/venv

# 2. Activate the virtual environment
.\backend\venv\Scripts\activate

# 3. Upgrade pip and install all backend requirements
pip install --upgrade pip
pip install -r backend/requirements.txt
```

### Step 1.2: Set up Next.js Frontend Dependencies
```powershell
cd frontend
npm install
cd ..
```

### Step 1.3: Verify Deep Learning Models & Laptop Hardware
Run the automated diagnostic suite to verify that the built-in webcam, microphone array, and ONNX models are operational:

```powershell
# In root directory with venv activated:
python verify_hardware.py
```

> **Note on Vision ONNX Models:**
> If `yolov5n.onnx` or `face_detection_yunet_2023mar.onnx` are missing in `ai/vision/models/`, run:
> ```powershell
> python ai/vision/download_models.py
> ```
> This script automatically downloads the verified lightweight ONNX models directly from official GitHub releases.

---

## 🎮 2. Running the System

### Option A: One-Click Automated Launch (Recommended)
Simply double-click or execute the launcher script:
```powershell
.\start_nexus.bat
# or in PowerShell:
.\start_nexus.ps1
```
This automatically:
1. Verifies the virtual environment and vision models.
2. Runs hardware diagnostics for laptop camera and mic.
3. Launches the FastAPI backend on `http://127.0.0.1:8000` (which auto-spawns the vision, audio, and IoT background services).
4. Launches the Next.js frontend on `http://localhost:3000`.
5. Opens your default web browser to the 3D Digital Twin dashboard.

### Option B: Manual Two-Terminal Launch

**Terminal 1 (Backend API & AI Subsystems):**
```powershell
.\backend\venv\Scripts\activate
python -m backend.app.main
```
*Backend runs on `http://127.0.0.1:8000`*
*Interactive API Docs: `http://127.0.0.1:8000/docs`*

**Terminal 2 (Frontend Dashboard & 3D Twin):**
```powershell
cd frontend
npm run dev
```
*Frontend runs on `http://localhost:3000`*

---

## 💻 3. Laptop Hardware Details & Auto-Discovery

### 📷 Built-in Webcam
* **Auto-Discovery**: [ai/vision/vision_service.py](ai/vision/vision_service.py) automatically probes Camera Index `0` across modern Windows Media Foundation (`MSMF`) and DirectShow (`DSHOW`) backends.
* **Deep Learning Pipeline**: Combines **YOLOv5n ONNX** (body detection) with **YuNet ONNX** (close-up facial detection) to compute room occupancy and draw bounding boxes.
* **Troubleshooting**: If the camera feed is black, check that the laptop's **physical privacy shutter** is slid open, and ensure Windows camera permissions are enabled under `Settings > Privacy & security > Camera`.

### 🎙️ Built-in Microphone Array
* **Auto-Discovery**: [ai/audio/audio_service.py](ai/audio/audio_service.py) queries PortAudio and defaults to the OS primary recording device (`sd.default.device[0]`), which is the laptop's internal microphone array.
* **Acoustic Intelligence**: Continuously streams audio into a 1.0s rolling buffer, applying smooth soft-knee dynamic saturation and physical DSP feature extraction (Spectral Centroid, RMS, Zero-Crossing Rate) with a 1.5s VAD hangover filter for speech.

---

## 🧪 4. Testing & Verification

The project includes an end-to-end pytest test suite covering all APIs, AI models, DSP filters, sensor generation, and fusion engine:

```powershell
.\backend\venv\Scripts\activate
pytest tests/ -v
```
*(Expected result: 17/17 tests passing)*

---

## 🗺️ 5. Codebase Architecture Map

| Directory / File | Description |
| :--- | :--- |
| `backend/app/main.py` | FastAPI application entrypoint; handles lifespan management and auto-spawns vision, audio, and IoT background loops. |
| `backend/app/api/` | REST & WebSocket routes (`health`, `rooms`, `sensors`, `incidents`, `prediction`, `vision`, `audio`, `ai`, `simulation`). |
| `backend/app/fusion/engine.py` | Multimodal sensor fusion engine; cross-correlates vision, audio, and environmental IoT signals into incident states. |
| `backend/app/prediction/` | Anomaly detection and trend forecasting models (IsolationForest, OneClassSVM). |
| `ai/vision/vision_service.py` | Computer vision service with YOLOv5n + YuNet ONNX detection, occupancy tracking, and HUD overlay. |
| `ai/audio/audio_service.py` | Real-time acoustic intelligence with continuous rolling buffer, DSP feature extraction, and speech classification. |
| `iot/emulator/telemetry_generator.py` | Real-time IoT sensor generator (temperature, humidity, air quality, gas, vibration). |
| `frontend/app/page.tsx` | Next.js 14 interactive UI dashboard with Three.js 3D Digital Twin, live camera snapshot, audio telemetry, and AI Assistant. |
| `verify_hardware.py` | Standalone diagnostic tool to test laptop webcam, microphone, and models. |
| `start_nexus.bat` | 1-click Windows launcher for backend, frontend, and browser. |
