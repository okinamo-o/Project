# NEXUS "What If?" Scenario Simulation & Sensor Sensitivity Engine

## 1. Concept & Purpose

NEXUS does not treat simulation as a disconnected mockup. Instead:
> **The simulation runs directly through the identical production multimodal fusion engine.**

When an operator modulates environmental sliders or triggers failure flags, the backend processes the inputs through the exact same feature engineering, correlation matrices, and incident generation pipelines used for real IoT hardware.

---

## 2. Sensor Failure Simulation (Sensitivity Analysis)

One of the signature capabilities of NEXUS is demonstrating that **conclusions are not based on fragile single-sensor thresholds**.

### Example Scenario:
1. **Full Sensor Cluster Active**:
   - Temperature: $45^\circ\text{C}$
   - Gas Concentration: $380\text{ ppm}$
   - Vision: 2 occupants detected
   - Audio: $2.4\text{ kHz}$ siren
   - **Result**: `MULTI_SIGNAL_ENVIRONMENTAL_CRISIS` (Severity: CRITICAL, Confidence: 98%)
2. **Operator Disables Gas Sensor**:
   - Gas signal is marked OFFLINE / UNTRUSTED.
   - Fusion Engine re-evaluates the active matrix.
   - **Result**: `HAZARDOUS_ATMOSPHERE_OCCUPIED` (Confidence drops to 76%).
   - Evidence attribution dynamically updates, showing the gas contribution has vanished.
3. **Operator Disables Camera**:
   - Visual confirmation disappears.
   - **Result**: `ELEVATED_THERMAL_RUNAWAY` (Severity drops to ATTENTION, Confidence: 65%).

This demonstrates to academic evaluators that the system rigorously correlates independent modalities.
