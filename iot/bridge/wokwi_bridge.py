import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
sys.path.insert(0, os.path.abspath('.'))
import json
import logging
import time
import socket
import threading
import httpx
from backend.app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [WOKWI-BRIDGE] %(message)s")
logger = logging.getLogger("nexus.wokwi_bridge")

class WokwiBridge:
    """
    Bridges Wokwi simulator signals to the NEXUS backend.
    Supports dual ingestion pathways:
    1. Direct TCP Serial streaming on port 4000 (extracts JSON telemetry printed by sketch.ino).
    2. MQTT broker messages (topic: settings.MQTT_TOPIC_SENSORS).
    """
    def __init__(self, broker_host: str = "localhost", broker_port: int = 1883, backend_url: str = "http://127.0.0.1:8000"):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.backend_url = backend_url
        self.mqtt_client = None
        self.running = True

    def forward_batch(self, payload: dict):
        try:
            with httpx.Client(timeout=2.0) as client:
                res = client.post(f"{self.backend_url}/api/sensors/batch", json=payload)
                if res.status_code == 200:
                    readings = payload.get("readings", [])
                    summary = ", ".join(f"{r.get('sensor_type')}:{r.get('value')}" for r in readings[:3])
                    logger.info(f"Ingested live Wokwi packet -> {summary} (Status: 200)")
        except Exception as e:
            logger.debug(f"Forward error: {e}")

    # --- MQTT INGESTION ---
    def on_mqtt_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info(f"Connected to MQTT broker at {self.broker_host}:{self.broker_port}")
            client.subscribe(settings.MQTT_TOPIC_SENSORS)
        else:
            logger.warning(f"MQTT connection failed with code {rc}")

    def on_mqtt_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            self.forward_batch(payload)
        except Exception as e:
            logger.error(f"MQTT packet error: {e}")

    def start_mqtt(self):
        try:
            import paho.mqtt.client as mqtt
            self.mqtt_client = mqtt.Client()
            self.mqtt_client.on_connect = self.on_mqtt_connect
            self.mqtt_client.on_message = self.on_mqtt_message
            self.mqtt_client.connect(self.broker_host, self.broker_port, 60)
            self.mqtt_client.loop_start()
            logger.info("MQTT listener active on port 1883.")
        except Exception as e:
            logger.debug(f"MQTT broker not accessible: {e}")

    # --- TCP SERIAL INGESTION (Port 4000) ---
    def start_serial_server(self, port: int = 4000):
        def _server_loop():
            while self.running:
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        s.bind(("0.0.0.0", port))
                        s.listen(2)
                        s.settimeout(2.0)
                        logger.info(f"Listening for Wokwi TCP serial monitor on port {port}...")
                        while self.running:
                            try:
                                conn, addr = s.accept()
                            except socket.timeout:
                                continue
                            logger.info(f"Wokwi serial simulator connected from {addr}!")
                            with conn:
                                buf = ""
                                while self.running:
                                    data = conn.recv(1024)
                                    if not data:
                                        break
                                    buf += data.decode("utf-8", errors="ignore")
                                    while "\n" in buf:
                                        line, buf = buf.split("\n", 1)
                                        line = line.strip()
                                        if "[NEXUS-ESP32] Telemetry packet:" in line:
                                            try:
                                                json_str = line.split("[NEXUS-ESP32] Telemetry packet:", 1)[1].strip()
                                                payload = json.loads(json_str)
                                                self.forward_batch(payload)
                                            except Exception as ex:
                                                logger.debug(f"Serial JSON parse error: {ex}")
                except Exception as ex:
                    logger.debug(f"Serial server loop error: {ex}")
                    time.sleep(2.0)

        t = threading.Thread(target=_server_loop, daemon=True)
        t.start()

    def start(self):
        self.start_mqtt()
        self.start_serial_server(port=4000)

if __name__ == "__main__":
    bridge = WokwiBridge()
    bridge.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        bridge.running = False
