import os
import joblib
import logging
import numpy as np
from typing import Dict, Any, Tuple

logger = logging.getLogger("nexus.anomaly_service")

class AnomalyDetectorService:
    """
    Runtime Machine Learning anomaly scoring using trained scikit-learn IsolationForest pipeline
    coupled with real-life multi-sensor physical validation (Temperature, Humidity, Gas, Smoke, LDR Light).
    Ensures benign single-sensor fluctuations (e.g. 39°C summer heat or coffee cup near DHT22, or
    room lights toggled alone) are classified as normal unless corroborated by companion sensors.
    """
    def __init__(self, model_path: str = "ml/models/anomaly_detector.joblib"):
        self.model_path = model_path
        self.pipeline = None
        self.scaler = None
        self.model = None
        self.feature_names = []
        self._load_model()

    def _load_model(self):
        if os.path.exists(self.model_path):
            try:
                self.pipeline = joblib.load(self.model_path)
                self.scaler = self.pipeline.get("scaler")
                self.model = self.pipeline.get("model")
                self.feature_names = self.pipeline.get("feature_names", [])
                logger.info(f"[ML] Successfully loaded anomaly model from {self.model_path}")
            except Exception as e:
                logger.error(f"[ML] Failed to load model from {self.model_path}: {e}")
        else:
            logger.warning(f"[ML] Model file {self.model_path} not found. Running in baseline heuristic mode.")

    def score_telemetry(self, features: Dict[str, float]) -> Tuple[bool, float, Dict[str, Any]]:
        """
        Scores a set of environmental telemetry features.
        Returns: (is_anomaly, anomaly_score_0_to_1, details)
        """
        temp = float(features.get("temperature", 22.0))
        hum = float(features.get("humidity", 45.0))
        gas = float(features.get("gas", 75.0))
        smoke = float(features.get("smoke", 0.3))
        light = float(features.get("light", 450.0))
        motion = float(features.get("motion", 0.0))
        temp_roc = float(features.get("temp_rate_of_change", 0.0))
        gas_roc = float(features.get("gas_rate_of_change", 0.0))

        # Real-life physical guard:
        # 1. Warm ambient / localized heat (< 45°C, e.g. 39°C summer day or coffee cup) WITHOUT smoke or gas is benign.
        # 2. High temperature + smoke WITHOUT high Lux (< 700 lux, e.g. 20 lux dark or 500 lux normal light) and without
        #    toxic gas (< 160 ppm) means no optical flame radiance is present -> no fire hazard detected.
        ldr_fire = (light >= 700.0) and (smoke >= 6.0)
        is_uncorroborated_fire = (gas < 160.0 and not ldr_fire and (temp < 45.0 or smoke >= 5.0))

        # 1. Model inference if available
        if self.model and self.scaler:
            try:
                if "smoke" in self.feature_names and "light" in self.feature_names:
                    vec = np.array([[temp, hum, gas, smoke, light, temp_roc, gas_roc]])
                else:
                    vec = np.array([[temp, hum, gas, motion, temp_roc, gas_roc]])

                scaled = self.scaler.transform(vec)
                raw_pred = self.model.predict(scaled)[0]  # -1 anomaly, 1 normal
                dec_func = self.model.decision_function(scaled)[0]
                anomaly_score = round(float(np.clip(0.5 - (dec_func * 2.5), 0.0, 1.0)), 2)

                if is_uncorroborated_fire:
                    anomaly_score = min(anomaly_score, 0.32)
                    is_anomaly = False
                else:
                    is_anomaly = bool(raw_pred == -1 or anomaly_score > 0.62)

                return is_anomaly, anomaly_score, {
                    "method": "IsolationForest",
                    "decision_score": round(float(dec_func), 3),
                    "anomaly_score": anomaly_score,
                    "features_evaluated": {
                        "temperature": temp,
                        "humidity": hum,
                        "gas": gas,
                        "smoke": smoke,
                        "light": light,
                        "temp_rate_of_change": temp_roc,
                        "gas_rate_of_change": gas_roc
                    }
                }
            except Exception as e:
                logger.error(f"[ML] Inference error: {e}")

        # 2. Multi-sensor statistical fallback
        is_anomaly = False
        reasons = []
        if (temp >= 33.0 and smoke >= 6.0) or (temp >= 33.0 and gas >= 160.0) or temp >= 45.0:
            is_anomaly = True
            reasons.append(f"Correlated thermal hazard ({temp}°C)")
        if gas >= 220.0 or (gas >= 160.0 and smoke >= 6.0):
            is_anomaly = True
            reasons.append(f"Gas accumulation ({gas} ppm)")
        if smoke >= 10.0:
            is_anomaly = True
            reasons.append(f"Optical smoke density ({smoke}%)")

        score = 0.85 if is_anomaly else 0.15
        return is_anomaly, score, {
            "method": "MultiSensorFallback",
            "anomaly_score": score,
            "reasons": reasons
        }

anomaly_detector = AnomalyDetectorService()
