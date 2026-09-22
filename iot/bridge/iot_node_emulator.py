import time
import math
import random
import argparse
import httpx
import sys

def simulate_node(
    base_url: str = "http://127.0.0.1:8000",
    room_id: str = "lab_02",
    device_id: str = "esp32_lab02",
    interval: float = 2.0,
    scenario: str = "normal",
    duration: int = 0
):
    print(f"==================================================")
    print(f" [NEXUS IoT] Starting ESP32 Node Emulator")
    print(f" Target: {base_url}/api/sensors/batch")
    print(f" Room: {room_id} | Device: {device_id}")
    print(f" Mode: {scenario.upper()} | Interval: {interval}s")
    print(f"==================================================")

    step = 0
    start_time = time.time()

    # Base physics state
    temp = 23.5
    humidity = 45.0
    gas = 85.0
    light = 450.0
    vibration = 0.04

    client = httpx.Client(timeout=5.0)

    try:
        while True:
            step += 1
            now = time.time()
            if duration > 0 and (now - start_time) > duration:
                print(f"[NEXUS IoT] Completed {duration}s run. Exiting.")
                break

            # Natural fluctuations
            noise_temp = random.gauss(0, 0.1)
            noise_gas = random.gauss(0, 2.0)
            noise_light = random.gauss(0, 5.0)
            noise_vib = max(0.01, random.gauss(0.04, 0.01))

            # Scenario modifications
            if scenario == "overheating":
                temp += 0.8 + random.uniform(0.1, 0.3)
                gas += 5.0 + random.uniform(1.0, 3.0)
                motion = 1
                vibration = 0.15 + random.uniform(0.05, 0.1)
            elif scenario == "gas_leak":
                gas += 18.0 + random.uniform(2.0, 6.0)
                motion = random.choice([0, 1])
                vibration = 0.05
            elif scenario == "vibration_anomaly":
                vibration = 0.85 + random.uniform(0.1, 0.3)
                temp += 0.2
                motion = 1
            else: # normal
                temp = 23.5 + math.sin(step * 0.1) * 0.5 + noise_temp
                humidity = 45.0 + math.cos(step * 0.1) * 1.5
                gas = max(40.0, 85.0 + noise_gas)
                light = max(100.0, 450.0 + noise_light)
                vibration = noise_vib
                motion = 1 if random.random() > 0.8 else 0

            payload = {
                "device_id": device_id,
                "room_id": room_id,
                "readings": [
                    {"sensor_type": "temperature", "value": round(temp, 1), "unit": "C"},
                    {"sensor_type": "humidity", "value": round(humidity, 1), "unit": "%"},
                    {"sensor_type": "gas", "value": round(gas, 1), "unit": "ppm"},
                    {"sensor_type": "motion", "value": motion, "unit": "state"},
                    {"sensor_type": "light", "value": round(light, 0), "unit": "lux"},
                    {"sensor_type": "vibration", "value": round(vibration, 3), "unit": "g"}
                ]
            }

            try:
                res = client.post(f"{base_url}/api/sensors/batch", json=payload)
                if res.status_code == 200:
                    print(f"[{step:03d}] TX OK -> Temp: {temp:.1f}°C | Gas: {gas:.0f}ppm | Motion: {motion} | Vib: {vibration:.3f}g")
                else:
                    print(f"[{step:03d}] TX Failed: HTTP {res.status_code}")
            except Exception as e:
                print(f"[{step:03d}] Connection failed: {e}")

            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n[NEXUS IoT] Stopped by operator.")
    finally:
        client.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NEXUS ESP32 IoT Node Emulator")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="Backend base URL")
    parser.add_argument("--room", default="lab_02", help="Monitored Room ID")
    parser.add_argument("--device", default="esp32_lab02", help="Device ID")
    parser.add_argument("--interval", type=float, default=2.0, help="Packet interval in seconds")
    parser.add_argument("--scenario", choices=["normal", "overheating", "gas_leak", "vibration_anomaly"], default="normal", help="Simulation mode")
    parser.add_argument("--duration", type=int, default=0, help="Duration in seconds (0 for infinite)")
    args = parser.parse_args()

    simulate_node(
        base_url=args.url,
        room_id=args.room,
        device_id=args.device,
        interval=args.interval,
        scenario=args.scenario,
        duration=args.duration
    )
