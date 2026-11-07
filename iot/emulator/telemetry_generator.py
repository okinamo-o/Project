import time
import random
import httpx
import logging
import argparse
import json
import os
from typing import Dict, Any, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [NEXUS-IOT] %(message)s")
logger = logging.getLogger("nexus.iot_generator")

ROOM_PROFILES: Dict[str, Dict[str, Any]] = {
    "server_room": {
        "name": "Central Server & Telecom Room",
        "device_id": "esp32_server",
        "temp_base": 18.5,
        "temp_var": 0.4,
        "humidity_base": 35.0,
        "humidity_var": 1.0,
        "gas_base": 35.0,
        "gas_var": 3.0,
        "smoke_base": 0.1,
        "smoke_var": 0.05,
        "motion_prob": 0.02,
        "light_base": 150
    },
    "classroom_01": {
        "name": "Classroom 01",
        "device_id": "esp32_classroom01",
        "temp_base": 21.8,
        "temp_var": 0.5,
        "humidity_base": 48.0,
        "humidity_var": 1.5,
        "gas_base": 85.0,
        "gas_var": 5.0,
        "smoke_base": 0.3,
        "smoke_var": 0.1,
        "motion_prob": 0.75,
        "light_base": 450
    },
    "classroom_02": {
        "name": "Classroom 02",
        "device_id": "esp32_classroom02",
        "temp_base": 22.2,
        "temp_var": 0.5,
        "humidity_base": 47.0,
        "humidity_var": 1.5,
        "gas_base": 90.0,
        "gas_var": 5.0,
        "smoke_base": 0.3,
        "smoke_var": 0.1,
        "motion_prob": 0.70,
        "light_base": 480
    },
    "lab_01": {
        "name": "Computer Science Lab 01",
        "device_id": "esp32_lab01",
        "temp_base": 21.5,
        "temp_var": 0.4,
        "humidity_base": 44.0,
        "humidity_var": 1.2,
        "gas_base": 80.0,
        "gas_var": 6.0,
        "smoke_base": 0.2,
        "smoke_var": 0.08,
        "motion_prob": 0.60,
        "light_base": 520
    },
    "lab_02": {
        "name": "Chemistry & Physics Lab 02",
        "device_id": "esp32_lab02",
        "temp_base": 23.5,
        "temp_var": 0.6,
        "humidity_base": 45.0,
        "humidity_var": 1.5,
        "gas_base": 75.0,
        "gas_var": 8.0,
        "smoke_base": 0.4,
        "smoke_var": 0.15,
        "motion_prob": 0.40,
        "light_base": 500
    },
    "storage_room": {
        "name": "Chemical Storage Room",
        "device_id": "esp32_storage",
        "temp_base": 19.8,
        "temp_var": 0.3,
        "humidity_base": 40.0,
        "humidity_var": 1.0,
        "gas_base": 95.0,
        "gas_var": 5.0,
        "smoke_base": 0.5,
        "smoke_var": 0.2,
        "motion_prob": 0.02,
        "light_base": 80
    },
    "main_hall": {
        "name": "Main Atrium & Hall",
        "device_id": "esp32_main_hall",
        "temp_base": 21.0,
        "temp_var": 0.7,
        "humidity_base": 50.0,
        "humidity_var": 2.0,
        "gas_base": 85.0,
        "gas_var": 5.0,
        "smoke_base": 0.3,
        "smoke_var": 0.1,
        "motion_prob": 0.85,
        "light_base": 650
    },
    "entrance": {
        "name": "Main Entrance",
        "device_id": "esp32_entrance",
        "temp_base": 20.5,
        "temp_var": 0.8,
        "humidity_base": 52.0,
        "humidity_var": 2.0,
        "gas_base": 75.0,
        "gas_var": 5.0,
        "smoke_base": 0.2,
        "smoke_var": 0.08,
        "motion_prob": 0.90,
        "light_base": 700
    },
    "emergency_exit": {
        "name": "Emergency Exit & Stairwell",
        "device_id": "esp32_emergency_exit",
        "temp_base": 19.2,
        "temp_var": 0.4,
        "humidity_base": 46.0,
        "humidity_var": 1.0,
        "gas_base": 65.0,
        "gas_var": 5.0,
        "smoke_base": 0.1,
        "smoke_var": 0.05,
        "motion_prob": 0.05,
        "light_base": 200
    }
}

# Rooms that have a dedicated Wokwi ESP32 simulation (live device IDs: esp32_lab02 / esp32_classroom01)
WOKWI_ROOMS = ("lab_02", "classroom_01")

def get_wokwi_overrides(room_id: str = "lab_02") -> Dict[str, float]:
    """
    Dynamically inspects Wokwi schematic files (diagram.json) for either lab_02 or classroom_01
    and extracts interactive sensor attributes (DHT22, gas pot, smoke pot, etc.).
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(base_dir, "../.."))
    if room_id == "classroom_01":
        possible_paths = [
            os.path.join(project_root, "iot", "wokwi", "classroom_01", "diagram.json"),
        ]
    else:
        possible_paths = [
            os.path.join(project_root, "iot", "wokwi", "diagram.json"),
            os.path.join(project_root, "iot", "wokwi", "lab_02", "diagram.json"),
            os.path.join(project_root, "wokwi", "diagram.json"),
            os.path.join(project_root, "diagram.json"),
            "iot/wokwi/diagram.json",
            "wokwi/diagram.json",
            "diagram.json",
            "iot/wokwi/diagram.jason",
            "wokwi/diagram.jason",
            "diagram.jason"
        ]
    overrides: Dict[str, float] = {}
    for path in possible_paths:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            for part in data.get("parts", []):
                pid = str(part.get("id", "")).lower()
                ptype = str(part.get("type", "")).lower()
                attrs = part.get("attrs", {})
                if pid == "dht" or ptype == "wokwi-dht22":
                    if "temperature" in attrs:
                        try: overrides["temperature"] = float(attrs["temperature"])
                        except (ValueError, TypeError): pass
                    if "humidity" in attrs:
                        try: overrides["humidity"] = float(attrs["humidity"])
                        except (ValueError, TypeError): pass
                elif pid == "gas_pot" or ("potentiometer" in ptype and "gas" in str(attrs.get("label", "")).lower()):
                    # Same mapping as the firmware: knob 0-1023 == 0-1023 ppm
                    if "value" in attrs:
                        try: overrides["gas"] = float(attrs["value"])
                        except (ValueError, TypeError): pass
                elif pid == "smoke_pot" or ("potentiometer" in ptype and "smoke" in str(attrs.get("label", "")).lower()):
                    # Same mapping as the firmware: knob 0-1023 == 0-100 % obscuration
                    if "value" in attrs:
                        try: overrides["smoke"] = round(float(attrs["value"]) * 100.0 / 1023.0, 2)
                        except (ValueError, TypeError): pass
                elif pid in ["pir", "cam_pir"] or ptype == "wokwi-pir-motion-sensor":
                    if "motion" in attrs:
                        try: overrides["motion"] = float(attrs["motion"])
                        except (ValueError, TypeError): pass
                elif pid == "ldr" or ptype == "wokwi-photoresistor-sensor":
                    for key in ["lux", "value", "light"]:
                        if key in attrs:
                            try:
                                overrides["light"] = float(attrs[key])
                                break
                            except (ValueError, TypeError): pass
            if overrides:
                break
        except Exception as e:
            logger.debug(f"Failed to parse Wokwi diagram from {path}: {e}")
    return overrides


_last_wokwi_check_ts = 0.0
_live_wokwi_rooms: set = set()

def get_live_wokwi_rooms(client: httpx.Client, backend_url: str = "http://127.0.0.1:8000") -> set:
    """Returns the set of room_ids that currently have a running Wokwi simulation posting data."""
    global _last_wokwi_check_ts, _live_wokwi_rooms
    now = time.time()
    if now - _last_wokwi_check_ts < 2.0:
        return _live_wokwi_rooms
    _last_wokwi_check_ts = now
    try:
        res = client.get(f"{backend_url}/api/sensors/status/wokwi", timeout=1.5)
        if res.status_code == 200:
            _live_wokwi_rooms = set(res.json().get("active_rooms", []))
            return _live_wokwi_rooms
    except Exception:
        return _live_wokwi_rooms
    return _live_wokwi_rooms

class TelemetryGenerator:
    """
    Simulates an ESP32 edge node streaming multi-sensor telemetry to NEXUS.
    Implements physical simulation profiles:
    - NORMAL: Standard ambient room baseline (tailored by room profile)
    - THERMAL_RUNAWAY: Rapid heater runaway (temp > 45°C) with smoke development
    - GAS_LEAK: Hazardous volatile concentration surge (gas > 400 ppm)
    - SMOKE_INVERSION: Rapid optical smoke density surge (>35% obscuration)
    - CASCADE_EMERGENCY: Multi-signal crisis (elevated temp + gas + smoke + motion)
    """
    def __init__(self, backend_url: str = "http://127.0.0.1:8000", room_id: str = "lab_02", device_id: str = None):
        self.backend_url = backend_url
        self.room_id = room_id
        profile = ROOM_PROFILES.get(room_id, {})
        self.device_id = device_id or (f"sim_esp32_{room_id}" if room_id in WOKWI_ROOMS else profile.get("device_id", f"esp32_{room_id}"))
        self.step_count = 0

    def generate_packet(self, scenario: str = "NORMAL") -> Dict[str, Any]:
        self.step_count += 1
        prof = ROOM_PROFILES.get(self.room_id, {
            "temp_base": 22.5, "temp_var": 0.8,
            "humidity_base": 45.0, "humidity_var": 1.5,
            "gas_base": 85.0, "gas_var": 8.0,
            "smoke_base": 0.3, "smoke_var": 0.1,
            "motion_prob": 0.35, "light_base": 500
        })

        if scenario == "THERMAL_RUNAWAY":
            temp = min(65.0, 24.0 + self.step_count * 1.8 + random.uniform(-0.3, 0.3))
            humidity = max(20.0, 45.0 - self.step_count * 0.8)
            gas = 110.0 + random.uniform(-5, 5)
            smoke = min(60.0, 1.2 + self.step_count * 5.0 + random.uniform(-0.4, 0.4))
            motion = 1
            light = 480
        elif scenario == "GAS_LEAK":
            temp = 23.5 + random.uniform(-0.4, 0.4)
            humidity = 42.0 + random.uniform(-1, 1)
            gas = min(800.0, 95.0 + self.step_count * 35.0 + random.uniform(-10, 10))
            smoke = 2.0 + random.uniform(-0.3, 0.3)
            motion = 1
            light = 510
        elif scenario == "SMOKE_INVERSION":
            temp = 28.0 + min(20.0, self.step_count * 1.5)
            humidity = 38.0 + random.uniform(-1, 1)
            gas = 160.0 + self.step_count * 12.0
            smoke = min(90.0, 5.0 + self.step_count * 12.5 + random.uniform(-1, 1))
            motion = 1
            light = 320
        elif scenario == "CASCADE_EMERGENCY":
            temp = min(58.0, 26.0 + self.step_count * 2.2)
            humidity = 35.0 + random.uniform(-2, 2)
            gas = min(650.0, 120.0 + self.step_count * 28.0)
            smoke = min(85.0, 6.0 + self.step_count * 11.0)
            motion = 1
            light = 550
        else: # NORMAL Baseline (fixed default values without random fluctuations)
            temp = float(prof["temp_base"])
            humidity = float(prof["humidity_base"])
            gas = float(prof["gas_base"])
            smoke = float(prof["smoke_base"])
            motion = 0
            light = int(prof["light_base"])

            # Dynamically apply Wokwi diagram.json edits for lab_02 and classroom_01
            if self.room_id in WOKWI_ROOMS:
                wokwi_vals = get_wokwi_overrides(self.room_id)
                if "temperature" in wokwi_vals:
                    temp = float(wokwi_vals["temperature"])
                if "humidity" in wokwi_vals:
                    humidity = float(wokwi_vals["humidity"])
                if "gas" in wokwi_vals:
                    gas = max(0.0, float(wokwi_vals["gas"]))
                if "smoke" in wokwi_vals:
                    smoke = max(0.0, float(wokwi_vals["smoke"]))
                if "motion" in wokwi_vals:
                    motion = int(wokwi_vals["motion"])
                if "light" in wokwi_vals:
                    light = int(wokwi_vals["light"])

        readings = [
            {"sensor_type": "temperature", "value": round(temp, 2), "unit": "C"},
            {"sensor_type": "humidity", "value": round(humidity, 1), "unit": "%"},
            {"sensor_type": "gas", "value": round(gas, 1), "unit": "ppm"},
            {"sensor_type": "smoke", "value": round(smoke, 2), "unit": "%"},
            {"sensor_type": "motion", "value": int(motion), "unit": "state"},
            {"sensor_type": "light", "value": int(light), "unit": "lux"}
        ]

        return {
            "device_id": self.device_id,
            "room_id": self.room_id,
            "readings": readings
        }

    def dispatch(self, client: httpx.Client = None, scenario: str = "NORMAL") -> bool:
        packet = self.generate_packet(scenario)
        try:
            if client:
                res = client.post(f"{self.backend_url}/api/sensors/batch", json=packet)
            else:
                with httpx.Client(timeout=3.0) as c:
                    res = c.post(f"{self.backend_url}/api/sensors/batch", json=packet)
            if res.status_code == 200:
                return True
        except Exception as e:
            logger.debug(f"Could not dispatch telemetry packet for {self.room_id}: {e}")
        return False


def run_multi_room_network(backend_url: str = "http://127.0.0.1:8000", interval: float = 1.0):
    """
    Simulates the entire distributed building sensor mesh network.
    Streams continuous independent environmental telemetry for all 9 zones.
    """
    generators = [TelemetryGenerator(backend_url=backend_url, room_id=rid) for rid in ROOM_PROFILES.keys()]
    print(f"\n=======================================================")
    print(f" NEXUS Multi-Zone Building IoT Network Simulator Active")
    print(f" Monitored Zones : {len(generators)} distinct spatial nodes")
    print(f" Target Backend  : {backend_url}/api/sensors/batch")
    print(f" Refresh Rate    : {interval}s")
    print(f" Press Ctrl+C to stop.")
    print(f"=======================================================\n")

    with httpx.Client(timeout=5.0) as client:
        while True:
            success_count = 0
            live_rooms = get_live_wokwi_rooms(client, backend_url)
            for gen in generators:
                # A running Wokwi simulation owns its room: never overwrite its values
                if gen.room_id in live_rooms:
                    continue
                if gen.dispatch(client=client, scenario="NORMAL"):
                    success_count += 1
            logger.info(f"[NETWORK MESH] Broadcasted live microclimates across {success_count}/{len(generators)} zones.")
            time.sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NEXUS ESP32 Telemetry Generator")
    parser.add_argument("--room", default="all", help="Target room ID (or 'all' for full building mesh simulation)")
    parser.add_argument("--scenario", choices=["NORMAL", "THERMAL_RUNAWAY", "GAS_LEAK", "CASCADE_EMERGENCY"], default="NORMAL", help="Simulation scenario")
    parser.add_argument("--interval", type=float, default=2.5, help="Transmission interval in seconds")
    args = parser.parse_args()

    try:
        if args.room.lower() == "all":
            run_multi_room_network(interval=args.interval)
        else:
            generator = TelemetryGenerator(room_id=args.room)
            print(f"\n=======================================================")
            print(f" NEXUS IoT Telemetry Simulator: Node '{generator.device_id}'")
            print(f" Target Room: {args.room} | Scenario: {args.scenario}")
            print(f" Streaming to: {generator.backend_url}/api/sensors/batch")
            print(f" Press Ctrl+C to stop.")
            print(f"=======================================================\n")
            with httpx.Client(timeout=4.0) as client:
                while True:
                    generator.dispatch(client=client, scenario=args.scenario)
                    time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n[NEXUS-IOT] Generator stopped.")
