# NEXUS Machine Learning & Predictive Modeling

## 1. Overview

NEXUS employs a two-tier machine learning architecture:
1. **Multivariate Anomaly Detection**: An unsupervised `IsolationForest` model trained to detect multi-sensor anomalies, thermal runaways, and dangerous chemical drifts without relying strictly on static threshold rules.
2. **Trend Forecasting Engine**: A transparent autoregressive and weighted polynomial regression pipeline predicting telemetry trajectories over +1m, +5m, and +15m horizons with 95% uncertainty intervals.

---

## 2. Feature Engineering

The feature vector captures both instantaneous readings and temporal dynamics:

| Feature | Description | Engineering Details |
| :--- | :--- | :--- |
| `temperature` | Instantaneous temperature (°C) | Raw DHT22 reading |
| `humidity` | Instantaneous relative humidity (%) | Raw DHT22 reading |
| `gas` | Gas concentration (ppm) | Mapped MQ-2 / potentiometer reading |
| `vibration` | Total kinetic acceleration ($g$) | Vector magnitude $\sqrt{a_x^2 + a_y^2 + (a_z - 9.8)^2}$ |
| `motion` | Binary presence state | PIR sensor output |
| `temp_rate_of_change` | 1st derivative of temperature | $\Delta T / \Delta t$ (°C/min) |
| `gas_rate_of_change` | 1st derivative of gas | $\Delta G / \Delta t$ (ppm/min) |
| `vibration_variance` | Rolling kinetic instability | 5-step rolling window variance |

---

## 3. Anomaly Model Architecture

* **Algorithm**: `sklearn.ensemble.IsolationForest`
* **Estimators**: 150 decision trees
* **Contamination**: 0.10 (10% anomaly assumption)
* **Preprocessing**: `sklearn.preprocessing.StandardScaler`
* **Evaluation Metrics (Tested on 3,000 synthetic multi-modal samples)**:
  - **Accuracy**: 93.60%
  - **Precision**: 68.00%
  - **Recall**: 68.00%
  - **F1-Score**: 68.00%
* **Model Artifact**: [`ml/models/anomaly_detector.joblib`](file:///c:/Users/Louay/Documents/Nexus/ml/models/anomaly_detector.joblib)
* **Metadata**: [`ml/models/model_metadata.json`](file:///c:/Users/Louay/Documents/Nexus/ml/models/model_metadata.json)

---

## 4. Short-Term Predictive Modeling

The trend forecaster uses a weighted linear polynomial fit ($w_i \in [0.5, 1.0]$) to project future environmental parameters:

$$\hat{y}_{t+h} = y_t + m \cdot h$$

Where $m$ is the estimated slope and $h$ is the horizon in minutes.

### Horizons Provided
* **+1 minute**: Immediate trajectory alert.
* **+5 minutes**: Operational intervention window.
* **+15 minutes**: Worst-case threshold estimation.

Uncertainty intervals are computed using the residual standard error scaled by $1.96 \cdot \sigma_{\text{res}} \cdot \sqrt{1 + \frac{h}{h_0}}$.
