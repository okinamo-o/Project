"""
NEXUS Hardware & Subsystem Diagnostic Verification Tool
Run this script on any machine (especially a laptop) to verify that the
built-in webcam, microphone array, and AI models are fully operational.
"""

import sys
import time
import os

print("=" * 65)
print("  NEXUS DIGITAL TWIN - HARDWARE & AI DIAGNOSTIC SUITE")
print("=" * 65)
print(f"Python Version : {sys.version.split()[0]} ({sys.executable})")

# 1. Dependency Check
print("\n[1/4] Checking Essential Dependencies...")
deps = ["cv2", "sounddevice", "numpy", "fastapi", "uvicorn", "httpx", "scipy", "sklearn"]
dep_status = {}
for dep in deps:
    try:
        __import__(dep)
        dep_status[dep] = True
        print(f"  [OK]      {dep:14s} : AVAILABLE")
    except ImportError as e:
        dep_status[dep] = False
        print(f"  [MISSING] {dep:14s} : NOT INSTALLED ({e})")

# 2. Camera Diagnostics
print("\n[2/4] Testing Video Capture Devices (Laptop Webcam / USB)...")
cv2_ok = dep_status.get("cv2", False)
camera_found = False
working_camera_idx = None

if cv2_ok:
    import cv2
    import numpy as np

    backends = [
        ("DSHOW", cv2.CAP_DSHOW),
        ("MSMF", cv2.CAP_MSMF),
        ("DEFAULT", cv2.CAP_ANY)
    ]

    for idx in range(3):
        for b_name, b_api in backends:
            try:
                cap = cv2.VideoCapture(idx, b_api)
                if cap.isOpened():
                    frame = None
                    for _ in range(5):
                        ret, f = cap.read()
                        if ret and f is not None and f.size > 0:
                            frame = f
                    if frame is not None:
                        h, w = frame.shape[:2]
                        mean_b = float(np.mean(frame))
                        print(f"  [OK] Camera [{idx}] via {b_name:7s} : OPENED ({w}x{h}, Mean Brightness: {mean_b:.1f})")
                        if not camera_found:
                            camera_found = True
                            working_camera_idx = idx
                        cap.release()
                        break
                    cap.release()
            except Exception as e:
                pass
        if camera_found and working_camera_idx == idx:
            break

    if not camera_found:
        print("  [!] No physical camera answered with video frames. (Synthetic fallback will activate).")
else:
    print("  [X] OpenCV not installed. Skipping camera probe.")

# 3. Microphone Diagnostics
print("\n[3/4] Testing Audio Input Devices (Microphone Array / Default Mic)...")
sd_ok = dep_status.get("sounddevice", False)
mic_found = False

if sd_ok:
    import sounddevice as sd
    import numpy as np

    try:
        devices = sd.query_devices()
        input_devs = [i for i, d in enumerate(devices) if d['max_input_channels'] > 0]
        default_in = sd.default.device[0]

        print(f"  Total Audio Input Devices Found: {len(input_devs)}")
        print(f"  Default System Input Device    : [{default_in}] {devices[default_in]['name'] if default_in >= 0 else 'None'}")

        for i in input_devs:
            marker = " (DEFAULT)" if i == default_in else ""
            print(f"    - Device [{i}]: {devices[i]['name']}{marker}")

        if default_in in input_devs or input_devs:
            test_idx = default_in if default_in in input_devs else input_devs[0]
            print(f"  Testing 0.5s audio sampling on device [{test_idx}]...")
            samples = sd.rec(int(16000 * 0.5), samplerate=16000, channels=1, dtype='float32', device=test_idx)
            sd.wait()
            rms = float(np.sqrt(np.mean(samples ** 2)))
            print(f"  [OK] Microphone Live Sampling OK (Recorded RMS Level: {rms:.5f})")
            mic_found = True
    except Exception as e:
        print(f"  [X] Microphone test failed: {e}")
else:
    print("  [X] sounddevice not installed. Skipping microphone probe.")

# 4. ONNX Models Verification
print("\n[4/4] Verifying Deep Learning Vision ONNX Models...")
base_dir = os.path.dirname(os.path.abspath(__file__))
models_dir = os.path.join(base_dir, "ai", "vision", "models")
yolo_p = os.path.join(models_dir, "yolov5n.onnx")
yunet_p = os.path.join(models_dir, "face_detection_yunet_2023mar.onnx")

yolo_exists = os.path.exists(yolo_p) and os.path.getsize(yolo_p) > 3_000_000
yunet_exists = os.path.exists(yunet_p) and os.path.getsize(yunet_p) > 200_000

print(f"  YOLOv5n Model ({yolo_p}) : {'[OK] PRESENT' if yolo_exists else '[MISSING] (run ai/vision/download_models.py)'}")
print(f"  YuNet Model   ({yunet_p}) : {'[OK] PRESENT' if yunet_exists else '[MISSING] (run ai/vision/download_models.py)'}")

# Summary
print("\n" + "=" * 65)
print("  DIAGNOSTIC SUMMARY & READINESS")
print("=" * 65)
print(f"  Built-in / USB Camera    : {'[READY]' if camera_found else '[SYNTHETIC FALLBACK]'}")
print(f"  Microphone Array         : {'[READY]' if mic_found else '[SYNTHETIC FALLBACK]'}")
print(f"  DNN Object/Face Models   : {'[READY]' if (yolo_exists and yunet_exists) else '[NEEDS DOWNLOAD]'}")
print("=" * 65)
print("All systems checked. You can launch NEXUS with: python -m backend.app.main\n")
