# NEXUS Official Presentation & Live Demonstration Guide

This guide walks an evaluator or presenter through the official 10-stage live demonstration workflow of NEXUS.

---

## 1. Preparation

1. **Launch NEXUS Core Backend**:
   ```powershell
   cd backend
   .\venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```
2. **Launch NEXUS Operations Dashboard**:
   ```powershell
   cd frontend
   npm run dev
   ```
3. Open browser at: **`http://localhost:3000`**

---

## 2. Running the 10-Stage Demonstration

You can run the demonstration automatically or step-by-step using the controller script:

```powershell
# Interactive step-by-step mode (advance with Enter key):
python scripts/run_demo.py

# Or automated presentation mode:
python scripts/run_demo.py --auto
```

---

## 3. Demonstration Stages & Presentation Script

### Stage 1: Normal Baseline
* **Visual**: All 9 rooms in the 3D Digital Twin show calm emerald green edges. Telemetry gauges indicate nominal levels (23.5°C, 75 ppm gas, 0 occupancy).
* **Explanation**: Explain that NEXUS continuously models a digital twin of the facility across environmental, visual, and acoustic streams.

### Stage 2: Environmental Change (Thermal Anomaly)
* **Visual**: Temperature begins rising rapidly in Laboratory 02. The thermal sparkline updates in real-time.
* **Explanation**: The ESP32 node detects rising heat. The short-term trend forecaster calculates a trajectory of $+2.8^\circ\text{C/min}$.

### Stage 3: Second Modality (Hazardous Gas Accumulation)
* **Visual**: MQ-2 gas concentration surges above 350 ppm.
* **Explanation**: Emphasize that NEXUS does not trigger isolated single-sensor panic; it correlates independent channels to avoid false positives.

### Stage 4: Computer Vision (Occupancy & Movement)
* **Visual**: Vision card indicates 2 occupants detected in Laboratory 02.
* **Explanation**: Local YOLO/OpenCV vision processing confirms human subjects inside the hazard zone, escalating life-safety severity.

### Stage 5: Audio Intelligence (Acoustic Siren)
* **Visual**: Acoustic card detects a 2.5 kHz emergency alarm signature with elevated RMS energy.
* **Explanation**: Local DSP signal processing extracted spectral centroids and classified the sound into an operational alarm class.

### Stage 6: Central Multimodal Fusion
* **Visual**: Laboratory 02 turns into a flashing crimson alarm beacon in the 3D Digital Twin. The incident card displays:
  - Classification: `MULTI_SIGNAL_ENVIRONMENTAL_CRISIS`
  - Severity: `CRITICAL`
  - Confidence: `98%`
  - Evidence Attribution Matrix shows proportional contributions of Temperature (35%), Gas (30%), Vision (20%), and Audio (15%).
* **Explanation**: This is the centerpiece of NEXUS: combining multiple modalities into an explainable, attributed incident hypothesis.

### Stage 7: AI Investigation ("Why did NEXUS create this incident?")
* **Action**: In the AI Operator Assistant drawer, click or type: *"Why is Laboratory 02 highlighted?"*
* **Visual**: NEXUS-AI replies with an evidence-grounded breakdown of the 4 signals and recommended safety actions.

### Stage 8: Predictive Trajectory
* **Visual**: The prediction horizon card displays the projected +5m and +15m trajectories with 95% uncertainty intervals.
* **Explanation**: Demonstrates how decision-makers are provided with future estimates rather than only reactive alerts.

### Stage 9: "What If?" Sensor Sensitivity Analysis
* **Action**: Open the What-If Simulation modal and click **Disable Gas Sensor**.
* **Visual**: The system re-evaluates the active incident. Confidence recalculates from 98% down to 76%. The gas contribution vanishes from the evidence matrix.
* **Explanation**: Demonstrates that the system reasons from multiple independent signals and gracefully handles individual sensor failures.

### Stage 10: Official Safety Incident Briefing
* **Action**: Click **Open Official Briefing Report**.
* **Visual**: A formal HTML incident briefing opens in the browser, with executive summary, timestamped evidence tables, chronological sequence, and CAPA corrective actions.
