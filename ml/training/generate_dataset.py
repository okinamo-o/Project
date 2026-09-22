import numpy as np
import csv
import os
import datetime

def generate_sensor_dataset(n_samples: int = 3000, output_path: str = "ml/datasets/sensor_training_data.csv"):
    """
    Generates realistic environmental telemetry with synthetic anomalies:
    - Normal diurnal cycles
    - Thermal runaway / overheating
    - Hazardous gas spikes
    - Mechanical vibration surges
    - Multi-sensor correlated emergencies
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    np.random.seed(42)

    # 1. Normal baseline with cyclical drift & Gaussian noise
    t = np.linspace(0, 50, n_samples)
    temperature = 22.0 + 2.5 * np.sin(t * 0.2) + np.random.normal(0, 0.2, n_samples)
    humidity = 45.0 + 5.0 * np.cos(t * 0.2) + np.random.normal(0, 0.5, n_samples)
    gas = 75.0 + 10.0 * np.sin(t * 0.1) + np.random.normal(0, 2.0, n_samples)
    vibration = np.abs(np.random.normal(0.03, 0.01, n_samples))
    motion = np.random.binomial(1, 0.15, n_samples)
    
    labels = np.zeros(n_samples, dtype=int)  # 0: normal, 1: anomaly

    # 2. Inject Overheating Anomalies (Samples 400-480, 1500-1550)
    temperature[400:480] += np.linspace(1.0, 25.0, 80)
    labels[400:480] = 1

    temperature[1500:1550] += np.linspace(0.5, 18.0, 50)
    labels[1500:1550] = 1

    # 3. Inject Gas Leak Anomalies (Samples 800-860)
    gas[800:860] += np.linspace(20.0, 350.0, 60)
    labels[800:860] = 1

    # 4. Inject Vibration Spike (Samples 1200-1230)
    vibration[1200:1230] += np.random.uniform(0.5, 1.2, 30)
    labels[1200:1230] = 1

    # 5. Inject Multi-Sensor Emergency (Samples 2200-2280: Temp + Gas + Motion + Vib)
    temperature[2200:2280] += np.linspace(2.0, 30.0, 80)
    gas[2200:2280] += np.linspace(15.0, 420.0, 80)
    motion[2200:2280] = 1
    vibration[2200:2280] += np.random.uniform(0.2, 0.6, 80)
    labels[2200:2280] = 1

    start_date = datetime.datetime(2026, 9, 1, 0, 0, 0)
    rows = []
    
    for i in range(n_samples):
        ts = (start_date + datetime.timedelta(minutes=i)).isoformat()
        
        # Derived rolling features
        window_start = max(0, i - 4)
        temp_rolling_mean = float(np.mean(temperature[window_start:i+1]))
        temp_roc = float(temperature[i] - temperature[i-1]) if i > 0 else 0.0
        gas_roc = float(gas[i] - gas[i-1]) if i > 0 else 0.0
        vib_var = float(np.var(vibration[window_start:i+1])) if i > 0 else 0.0

        rows.append([
            ts,
            round(float(temperature[i]), 2),
            round(float(humidity[i]), 2),
            round(float(gas[i]), 1),
            round(float(vibration[i]), 4),
            int(motion[i]),
            round(temp_rolling_mean, 2),
            round(temp_roc, 3),
            round(gas_roc, 2),
            round(vib_var, 6),
            int(labels[i])
        ])

    headers = [
        "timestamp", "temperature", "humidity", "gas", "vibration", "motion",
        "temp_rolling_mean", "temp_rate_of_change", "gas_rate_of_change", "vibration_variance",
        "is_anomaly"
    ]

    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

    anomaly_count = int(np.sum(labels))
    print(f"[ML-DATASET] Successfully generated {n_samples} samples at {output_path}")
    print(f"[ML-DATASET] Anomalous samples: {anomaly_count} ({(anomaly_count/n_samples)*100:.1f}%)")

if __name__ == "__main__":
    generate_sensor_dataset()
