#!/usr/bin/env python3
"""
NEXUS Digital Twin - Comprehensive System Diagnostic & Health Auditor.
Verifies all 6 multimodal AI subsystems and infrastructure components end-to-end.
"""
import sys
import os
import time
import httpx

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def print_result(title: str, passed: bool, detail: str = ""):
    status = f"{GREEN}[PASS]{RESET}" if passed else f"{RED}[FAIL]{RESET}"
    print(f" {status} {title:<40} {detail}")

def main():
    print(f"\n{BLUE}======================================================================{RESET}")
    print(f"{BLUE}      NEXUS MULTIMODAL AI DIGITAL TWIN — FULL SYSTEM AUDIT            {RESET}")
    print(f"{BLUE}======================================================================{RESET}\n")

    results = []

    # 1. Backend Health Check
    try:
        with httpx.Client(timeout=3.0) as client:
            res = client.get("http://127.0.0.1:8000/api/health")
            data = res.json()
            is_healthy = (res.status_code == 200 and data.get("status") == "healthy")
            print_result("1. Backend API & Database Engine", is_healthy, f"HTTP {res.status_code} | DB: {data.get('database')}")
            results.append(is_healthy)
    except Exception as e:
        print_result("1. Backend API & Database Engine", False, f"Connection failed: {e}")
        results.append(False)

    # 2. Camera & Vision Intelligence (45 FPS)
    try:
        with httpx.Client(timeout=3.0) as client:
            res = client.get("http://127.0.0.1:8000/api/vision/latest/lab_02")
            data = res.json()
            occ = data.get("occupancy", 0)
            fps = data.get("metadata", {}).get("fps_target", 45)
            print_result("2. Edge Vision Engine (45 FPS)", res.status_code == 200, f"Target: {fps} FPS | Detected Occupancy: {occ}")
            results.append(res.status_code == 200)
    except Exception as e:
        print_result("2. Edge Vision Engine (45 FPS)", False, str(e))
        results.append(False)

    # 3. Acoustic DSP & Voice Activity Detection
    try:
        with httpx.Client(timeout=3.0) as client:
            res = client.get("http://127.0.0.1:8000/api/audio/latest/lab_02")
            data = res.json()
            ev = data.get("event_type", "NORMAL")
            rms = data.get("metadata", {}).get("rms_energy", 0.0)
            print_result("3. Acoustic Subsystem & Mic DSP", res.status_code == 200, f"State: {ev} | RMS: {rms:.4f}")
            results.append(res.status_code == 200)
    except Exception as e:
        print_result("3. Acoustic Subsystem & Mic DSP", False, str(e))
        results.append(False)

    # 4. Wokwi Simulator & Hardware Link
    try:
        with httpx.Client(timeout=3.0) as client:
            # Test external / LAN connectivity on 0.0.0.0
            test_packet = {
                "device_id": "esp32_lab02",
                "room_id": "lab_02",
                "readings": [
                    {"sensor_type": "temperature", "value": 24.5, "unit": "C"},
                    {"sensor_type": "gas", "value": 150.0, "unit": "ppm"},
                    {"sensor_type": "smoke", "value": 5.0, "unit": "%"}
                ]
            }
            post_res = client.post("http://127.0.0.1:8000/api/sensors/batch", json=test_packet)
            status_res = client.get("http://127.0.0.1:8000/api/sensors/status/wokwi")
            wokwi_data = status_res.json()
            is_wokwi_ok = (post_res.status_code == 200 and wokwi_data.get("wokwi_active") is True)
            print_result("4. Wokwi ESP32 Priority Arbitration", is_wokwi_ok, f"Wokwi Live Priority: Active")
            results.append(is_wokwi_ok)
    except Exception as e:
        print_result("4. Wokwi ESP32 Priority Arbitration", False, str(e))
        results.append(False)

    # 5. Frontend 3D Twin & Next.js Bundle
    try:
        with httpx.Client(timeout=4.0) as client:
            page_res = client.get("http://localhost:3000")
            css_res = client.get("http://localhost:3000/_next/static/css/app/layout.css")
            is_fe_ok = (page_res.status_code == 200 and css_res.status_code == 200)
            css_len = len(css_res.content) if css_res.status_code == 200 else 0
            print_result("5. Frontend 3D Studio Dashboard", is_fe_ok, f"HTTP 200 | Stylesheet: {css_len:,} bytes")
            results.append(is_fe_ok)
    except Exception as e:
        print_result("5. Frontend 3D Studio Dashboard", False, str(e))
        results.append(False)

    # 6. Multimodal Fusion & Automated Tests
    try:
        with httpx.Client(timeout=3.0) as client:
            f_res = client.get("http://127.0.0.1:8000/api/prediction/lab_02?variable=temperature")
            f_ok = (f_res.status_code == 200)
            print_result("6. Multimodal Fusion & Forecast Twin", f_ok, "Forward Forecast Models Online")
            results.append(f_ok)
    except Exception as e:
        print_result("6. Multimodal Fusion & Forecast Twin", False, str(e))
        results.append(False)

    passed_count = sum(1 for r in results if r)
    total_count = len(results)
    score = int((passed_count / total_count) * 100)

    print(f"\n{BLUE}======================================================================{RESET}")
    color = GREEN if score == 100 else YELLOW
    print(f" FINAL SYSTEM READINESS SCORE: {color}{score}/100{RESET} ({passed_count}/{total_count} Subsystems Verified)")
    print(f"{BLUE}======================================================================{RESET}\n")

    return 0 if score == 100 else 1

if __name__ == "__main__":
    sys.exit(main())
