import os
import joblib
import logging
import numpy as np
from typing import Dict, Any, Tuple

logger = logging.getLogger("nexus.anomaly_service")

class AnomalyDetectorService:
    """Runtime anomaly scoring using trained scikit-learn IsolationForest pipeline."""
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
        # Feature vector
        # [temp, humidity, gas, vib, motion, temp_roc, gas_roc, vib_var]
        temp = float(features.get("temperature", 22.0))
        hum = float(features.get("humidity", 45.0))
        gas = float(features.get("gas", 75.0))
        vib = float(features.get("vibration", 0.03))
        motion = float(features.get("motion", 0.0))
        temp_roc = float(features.get("temp_rate_of_change", 0.0))
        gas_roc = float(features.get("gas_rate_of_change", 0.0))
        vib_var = float(features.get("vibration_variance", 0.0))

        # 1. Model inference if available
        if self.model and self.scaler:
            try:
                vec = np.array([[temp, hum, gas, vib, motion, temp_roc, gas_roc, vib_var]])
                scaled = self.scaler.transform(vec)
                raw_pred = self.model.predict(scaled)[0] # -1 anomaly, 1 normal
                # decision_function returns negative for anomalies
                dec_func = self.model.decision_function(scaled)[0]
                # Map decision function to 0.0 - 1.0 anomaly severity score
                anomaly_score = round(float(np.clip(0.5 - (dec_func * 2.5), 0.0, 1.0)), 2)
                is_anomaly = bool(raw_pred == -1 or anomaly_score > 0.65)
                
                return is_anomaly, anomaly_score, {
                    "method": "IsolationForest",
                    "decision_score": round(float(dec_func), 3),
                    "anomaly_score": anomaly_score,
                    "features_evaluated": {
                        "temperature": temp,
                        "gas": gas,
                        "temp_rate_of_change": temp_roc,
                        "gas_rate_of_change": gas_roc
                    }
                }
            except Exception as e:
                logger.error(f"[ML] Inference error: {e}")

        # 2. Rule & statistical baseline fallback
        is_anomaly = False
        reasons = []
        if temp > 38.0 or temp_roc > 1.8:
            is_anomaly = True
            reasons.append(f"Temperature high ({temp}°C) or surging (+{temp_roc}°C/min)")
        if gas > 350.0 or gas_roc > 20.0:
            is_anomaly = True
            reasons.append(f"Gas level dangerous ({gas} ppm) or rising rapidly")
        if vib > 0.5:
            is_anomaly = True
            reasons.append(f"Vibration stress ({vib} g)")

        score = 0.85 if is_anomaly else 0.10
        return is_anomaly, score, {
            "method": "RuleBaselineFallback",
            "anomaly_score": score,
            "reasons": reasons
        }

anomaly_detector = AnomalyDetectorService()
