import numpy as np
import csv
import os
import datetime

def generate_sensor_dataset(n_samples: int = 3500, output_path: str = "ml/datasets/sensor_training_data.csv"):
    """
    Generates realistic environmental telemetry for ML training with real-life physics:
    - Normal baseline (18-28°C) AND benign warm summer / localized heat (28-42°C, e.g. 39°C cup of coffee)
      where smoke, gas, and LDR are normal -> labeled 0 (NORMAL).
    - Correlated Fire Anomalies (Temp + Smoke + LDR flame flash or smoke obscuration) -> labeled 1.
    - Correlated Thermal + Gas Anomalies -> labeled 1.
    - Severe Gas Leak (>350 ppm) or Dense Smoke (>25%) or Extreme Heat (>50°C) -> labeled 1.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    np.random.seed(42)

    t = np.linspace(0, 60, n_samples)
    temperature = 22.5 + 3.0 * np.sin(t * 0.2) + np.random.normal(0, 0.4, n_samples)
    humidity = 46.0 + 5.0 * np.cos(t * 0.2) + np.random.normal(0, 1.0, n_samples)
    gas = 80.0 + 12.0 * np.sin(t * 0.1) + np.random.normal(0, 3.0, n_samples)
    smoke = np.clip(0.3 + np.random.normal(0, 0.15, n_samples), 0.0, 3.0)
    light = np.clip(460.0 + 60.0 * np.sin(t * 0.15) + np.random.normal(0, 15.0, n_samples), 150.0, 720.0)
    motion = np.random.binomial(1, 0.20, n_samples)

    labels = np.zeros(n_samples, dtype=int)  # 0: normal, 1: anomaly

    # 1. Benign Summer Heat / Cup of Coffee near sensor (28°C - 42°C alone, normal smoke & gas) -> NORMAL (label 0)
    temperature[150:320] = np.random.uniform(31.0, 41.5, 170)
    humidity[150:320] = np.random.uniform(34.0, 52.0, 170)
    gas[150:320] = np.random.uniform(65.0, 115.0, 170)
    smoke[150:320] = np.random.uniform(0.1, 2.2, 170)
    labels[150:320] = 0

    # 2. Fire Conflagration: Elevated Temp + Smoke + LDR Flame Flash (>750 lux) (Samples 450-540)
    temperature[450:540] = np.random.uniform(34.0, 56.0, 90)
    humidity[450:540] = np.random.uniform(18.0, 32.0, 90)
    smoke[450:540] = np.random.uniform(9.0, 55.0, 90)
    light[450:540] = np.random.uniform(770.0, 980.0, 90)
    labels[450:540] = 1

    # 3. Fire with Dense Smoke Plume Blocking Ambient Light (LDR < 120 lux) (Samples 800-880)
    temperature[800:880] = np.random.uniform(33.0, 50.0, 80)
    smoke[800:880] = np.random.uniform(10.0, 60.0, 80)
    light[800:880] = np.random.uniform(15.0, 110.0, 80)
    labels[800:880] = 1

    # 4. Multi-Sensor Gas + Thermal Anomaly (Samples 1300-1380)
    temperature[1300:1380] = np.random.uniform(34.0, 49.0, 80)
    gas[1300:1380] = np.random.uniform(180.0, 520.0, 80)
    labels[1300:1380] = 1

    # 5. Severe Gas Leak + Smoke Hazard (Samples 1900-1970)
    gas[1900:1970] = np.random.uniform(260.0, 650.0, 70)
    smoke[1900:1970] = np.random.uniform(8.5, 40.0, 70)
    labels[1900:1970] = 1

    # 6. Full Cascading Emergency (Samples 2500-2580)
    temperature[2500:2580] = np.random.uniform(42.0, 62.0, 80)
    gas[2500:2580] = np.random.uniform(300.0, 620.0, 80)
    smoke[2500:2580] = np.random.uniform(15.0, 70.0, 80)
    light[2500:2580] = np.random.uniform(800.0, 995.0, 80)
    motion[2500:2580] = 1
    labels[2500:2580] = 1

    start_date = datetime.datetime(2026, 9, 1, 0, 0, 0)
    rows = []

    for i in range(n_samples):
        ts = (start_date + datetime.timedelta(minutes=i)).isoformat()
        window_start = max(0, i - 4)
        temp_rolling_mean = float(np.mean(temperature[window_start:i+1]))
        temp_roc = float(temperature[i] - temperature[i-1]) if i > 0 else 0.0
        gas_roc = float(gas[i] - gas[i-1]) if i > 0 else 0.0

        rows.append([
            ts,
            round(float(temperature[i]), 2),
            round(float(humidity[i]), 2),
            round(float(gas[i]), 1),
            round(float(smoke[i]), 2),
            round(float(light[i]), 1),
            int(motion[i]),
            round(temp_rolling_mean, 2),
            round(temp_roc, 3),
            round(gas_roc, 2),
            int(labels[i])
        ])

    headers = [
        "timestamp", "temperature", "humidity", "gas", "smoke", "light", "motion",
        "temp_rolling_mean", "temp_rate_of_change", "gas_rate_of_change",
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
