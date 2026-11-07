import csv
import os
import json
import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import precision_score, recall_score, f1_score, accuracy_score

def train_detector(
    dataset_path: str = "ml/datasets/sensor_training_data.csv",
    model_output_path: str = "ml/models/anomaly_detector.joblib",
    meta_output_path: str = "ml/models/model_metadata.json"
):
    print(f"[ML-TRAIN] Loading dataset from {dataset_path}...")
    features = []
    labels = []

    with open(dataset_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            feat = [
                float(row["temperature"]),
                float(row["humidity"]),
                float(row["gas"]),
                float(row.get("smoke", 0.3)),
                float(row.get("light", 450.0)),
                float(row["temp_rate_of_change"]),
                float(row["gas_rate_of_change"])
            ]
            features.append(feat)
            labels.append(int(row["is_anomaly"]))

    X = np.array(features)
    y_true = np.array(labels)

    feature_names = [
        "temperature", "humidity", "gas", "smoke", "light",
        "temp_rate_of_change", "gas_rate_of_change"
    ]

    print(f"[ML-TRAIN] Training Isolation Forest on {X.shape[0]} samples with {X.shape[1]} features...")
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    iso = IsolationForest(n_estimators=200, contamination=0.11, random_state=42)
    iso.fit(X_scaled)

    raw_preds = iso.predict(X_scaled)
    y_pred = np.where(raw_preds == -1, 1, 0)

    acc = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred)
    rec = recall_score(y_true, y_pred)
    f1 = f1_score(y_true, y_pred)

    print(f"==================================================")
    print(f" [ML-EVALUATION] Isolation Forest Metrics:")
    print(f" Accuracy:  {acc * 100:.2f}%")
    print(f" Precision: {prec * 100:.2f}%")
    print(f" Recall:    {rec * 100:.2f}%")
    print(f" F1-Score:  {f1 * 100:.2f}%")
    print(f"==================================================")

    os.makedirs(os.path.dirname(model_output_path), exist_ok=True)

    pipeline = {
        "scaler": scaler,
        "model": iso,
        "feature_names": feature_names
    }
    joblib.dump(pipeline, model_output_path)
    print(f"[ML-TRAIN] Model saved to {model_output_path}")

    metadata = {
        "model_version": "nexus-isoforest-v2.0",
        "algorithm": "IsolationForest",
        "features": feature_names,
        "n_samples": int(X.shape[0]),
        "metrics": {
            "accuracy": round(float(acc), 4),
            "precision": round(float(prec), 4),
            "recall": round(float(rec), 4),
            "f1_score": round(float(f1), 4)
        }
    }
    with open(meta_output_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"[ML-TRAIN] Metadata saved to {meta_output_path}")

if __name__ == "__main__":
    train_detector()
