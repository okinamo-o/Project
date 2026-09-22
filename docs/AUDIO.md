# NEXUS Acoustic Intelligence Subsystem

## 1. Digital Signal Processing Pipeline

The audio subsystem analyzes microphone audio in real time using local physical signal processing before event classification:

```
Microphone Audio Stream
           ↓
Audio Frame Chunk (16 kHz, 0.5s window)
           ↓
Physical DSP Feature Extraction:
  • RMS Energy: Root Mean Square signal amplitude
  • Zero-Crossing Rate (ZCR): High-frequency noise indicator
  • Fast Fourier Transform (FFT): Spectral Centroid calculation
           ↓
Operational Acoustic Event Classification:
  [NORMAL | SPEECH | ALARM | IMPACT | KNOCK | SUDDEN_NOISE]
           ↓
Structured Audio Event Ingestion & Fusion Engine
```

---

## 2. Acoustic Signatures

* **ALARM**: Characterized by sustained high RMS energy ($>0.45$) and high spectral centroid ($>2200$ Hz) corresponding to emergency horns and piezo buzzers.
* **IMPACT / KNOCK**: High transient peak-to-average ratio and steep temporal decay ($>0.60$ RMS, high ZCR).
* **SPEECH**: Mid-band spectral centroid ($300 - 2000$ Hz) corresponding to human vocal formants.
* **SUDDEN_NOISE**: Transient ambient acoustic shift.
* **NORMAL**: Ambient baseline HVAC hum ($<0.05$ RMS).
