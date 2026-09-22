# NEXUS IoT Subsystem Documentation

## 1. Architecture Overview

The NEXUS IoT subsystem provides continuous real-time environmental telemetry across 6 sensor channels:

```
┌────────────────────────────────────────┐
│           ESP32 Microcontroller        │
│                                        │
│  [DHT22]       Temperature & Humidity  │
│  [Pot/MQ-2]    Gas Concentration (ppm) │
│  [PIR]         Motion Detection        │
│  [LDR]         Ambient Illumination    │
│  [MPU6050]     Vibration & Kinetic (g) │
│  [LED & Tone]  Local Audio/Visual Alarm│
└───────────────────┬────────────────────┘
                    │
           WiFi (HTTP / MQTT)
                    │
                    ▼
┌────────────────────────────────────────┐
│             NEXUS Backend              │
│       /api/sensors/batch & WebSocket   │
└────────────────────────────────────────┘
```

---

## 2. Hardware Pinout & Wiring

| Sensor / Actuator | Type | ESP32 GPIO | Channel Details |
| :--- | :--- | :--- | :--- |
| **DHT22** | Digital 1-Wire | `GPIO 4` | Temperature (°C), Humidity (%) |
| **Gas Potentiometer / MQ-2** | Analog ADC | `GPIO 34` | Gas concentration (50 - 1000 ppm) |
| **PIR Motion Sensor** | Digital Input | `GPIO 13` | Binary presence (0 = none, 1 = motion) |
| **Photoresistor (LDR)** | Analog ADC | `GPIO 35` | Ambient light intensity (0 - 1000 lux) |
| **MPU6050 IMU** | I2C (`0x68`) | `GPIO 21` (SDA), `GPIO 22` (SCL) | 3-axis accelerometer/gyroscope ($g$) |
| **Status LED** | Digital Output | `GPIO 2` | Active high visual alarm |
| **Piezo Buzzer** | PWM / Tone | `GPIO 15` | Acoustic alarm indicator |

---

## 3. Running in Wokwi

1. In VS Code with the Wokwi extension or at [wokwi.com](https://wokwi.com):
   - Open `iot/wokwi/diagram.json`
   - Target firmware: `iot/firmware/sketch.ino`
2. The simulated ESP32 automatically connects to `Wokwi-GUEST` and dispatches batches to `http://host.wokwi.internal:8000/api/sensors/batch`.

---

## 4. Software Node Emulator

For rapid local testing and automated pipelines without opening a browser:
```powershell
python iot/bridge/iot_node_emulator.py --scenario normal --interval 2.0
```
Scenarios supported:
* `--scenario normal`: Diurnal drift with Gaussian physical noise.
* `--scenario overheating`: Rapid thermal runaway with secondary gas and vibration rise.
* `--scenario gas_leak`: Progressive volatile gas accumulation.
* `--scenario vibration_anomaly`: Mechanical stress and sudden kinetic surge.
