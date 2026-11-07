# Classroom 01 — Dedicated Wokwi Simulation Node

This folder contains the complete, dedicated Wokwi simulation for **Classroom 01** with its own tailored sensor suite.

## Sensor Suite

1. **DHT22**: Temperature (°C) & Humidity (%) — Pin `GPIO 4`
2. **Gas Detector**: Analog Potentiometer mapped to 50–1000 ppm — Pin `GPIO 34`
3. **Smoke Detector**: Analog Potentiometer mapped to 0.0%–100.0% obscuration — Pin `GPIO 36`
4. **Normal Camera**: PIR presence / motion sensor — Pin `GPIO 13`
5. **Camera Indicator LED**: Blue LED active when subject is in camera view — Pin `GPIO 2`
6. **Hazard Alert LED**: Red LED for threshold breach — Pin `GPIO 12`
7. **Piezo Buzzer**: Tone indicator for critical alarm — Pin `GPIO 15`

## Target Metadata

- **Room ID**: `classroom_01`
- **Device ID**: `esp32_classroom01`

## How to Run in Wokwi

### Option 1: VS Code (with Wokwi Simulator extension)

1. Open this folder `iot/wokwi/classroom_01/` or open `diagram.json`.
2. Press `F1` and select **Wokwi: Start Simulator**.
3. Adjust the sliders on the DHT22, Gas potentiometer, Smoke potentiometer, or click the Camera presence sensor to simulate events in Classroom 01.

### Option 2: Wokwi Online (wokwi.com)

1. Create a new ESP32 project on [wokwi.com](https://wokwi.com).
2. Copy the contents of `diagram.json` into the Diagram tab.
3. Copy `sketch.ino` into the Code tab.
4. Add libraries from `libraries.txt`.
5. Click **Start Simulation**.
