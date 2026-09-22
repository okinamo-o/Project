# NEXUS Computer Vision Subsystem

## 1. Architectural Strategy

To maintain low latency, data privacy, and zero API costs during continuous operation, NEXUS adheres strictly to the **Edge-First Computer Vision Pattern**:

```
Webcam / Video Stream
        ↓
Local Computer Vision (OpenCV & YOLO)
        ↓
Feature & Event Extraction (BBoxes, Occupancy, Motion Vectors)
        ↓
Structured Vision Event (JSON)
        ↓
Multimodal Fusion Engine & 3D Digital Twin
        ↓
(Only on critical incidents / Operator request) → Gemini Vision Reasoning
```

Continuous raw video frames are NEVER streamed into LLMs. Gemini is only invoked for higher-level forensic interpretation of selected event keyframes.

---

## 2. Event Classes & Extraction

The subsystem detects and publishes:
* `PERSON_DETECTED`: Subject present in zone with bounding box coordinates.
* `OCCUPANCY_CHANGE`: Real-time room count tracking ($N$).
* `SUDDEN_MOVEMENT`: Rapid pixel displacement indicating panic or swift egress.
* `OBJECT_UNATTENDED`: Stationary object anomaly.

---

## 3. Physical & Synthetic Operation

* **Physical Mode**: Directly accesses local DirectShow/MediaFoundation webcams (`cv2.VideoCapture(0)`).
* **Synthetic Mode**: When no physical camera is attached, the subsystem renders a real-time 640x480 surveillance simulation with dynamic silhouettes, realistic motion vectors, timestamp OSD, and bounding boxes, providing full functional parity for presentations.
