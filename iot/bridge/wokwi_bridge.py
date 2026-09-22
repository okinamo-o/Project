import json
import logging
import asyncio
import time
import httpx
from backend.app.core.config import settings

logger = logging.getLogger("nexus.wokwi_bridge")

class WokwiBridge:
    """Bridges MQTT messages from Mosquitto / Wokwi to the NEXUS HTTP/WebSocket backend."""
    def __init__(self, broker_host: str = "localhost", broker_port: int = 1883, backend_url: str = "http://127.0.0.1:8000"):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.backend_url = backend_url
        self.client = None

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info(f"[WOKWI-MQTT] Connected to MQTT broker at {self.broker_host}:{self.broker_port}")
            client.subscribe(settings.MQTT_TOPIC_SENSORS)
        else:
            logger.warning(f"[WOKWI-MQTT] Connection failed with code {rc}")

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            logger.info(f"[WOKWI-MQTT] Received packet: {payload}")
            # Forward to backend
            with httpx.Client() as http_client:
                http_client.post(f"{self.backend_url}/api/sensors/batch", json=payload, timeout=2.0)
        except Exception as e:
            logger.error(f"[WOKWI-MQTT] Ingestion error: {e}")

    def start(self):
        try:
            import paho.mqtt.client as mqtt
            self.client = mqtt.Client()
            self.client.on_connect = self.on_connect
            self.client.on_message = self.on_message
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start()
            logger.info("[WOKWI-MQTT] MQTT listener started.")
        except Exception as e:
            logger.warning(f"[WOKWI-MQTT] MQTT broker not reachable ({e}). Direct HTTP mode is active.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    bridge = WokwiBridge()
    bridge.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
