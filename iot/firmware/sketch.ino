#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <DHT.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>

// WiFi Configuration (Wokwi uses Wokwi-GUEST with empty password)
const char* WIFI_SSID = "Wokwi-GUEST";
const char* WIFI_PASSWORD = "";

// NEXUS Backend Telemetry Endpoint
// In Wokwi simulation, host machine is accessible via host.wokwi.internal or custom IP
const char* SERVER_URL = "http://host.wokwi.internal:8000/api/sensors/batch";

// Pin Assignments
#define DHTPIN 4
#define DHTTYPE DHT22
#define PIN_GAS 34
#define PIN_SMOKE 36
#define PIN_PIR 13
#define PIN_LDR 35
#define PIN_LED 2
#define PIN_BUZZER 15

DHT dht(DHTPIN, DHTTYPE);
Adafruit_MPU6050 mpu;
bool mpu_available = false;

unsigned long last_transmit_ms = 0;
const unsigned long TRANSMIT_INTERVAL_MS = 2000;

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("[NEXUS-ESP32] Initializing Multimodal Sensor Node with Smoke Detector...");

  pinMode(PIN_GAS, INPUT);
  pinMode(PIN_SMOKE, INPUT);
  pinMode(PIN_PIR, INPUT);
  pinMode(PIN_LDR, INPUT);
  pinMode(PIN_LED, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);

  dht.begin();

  Wire.begin(21, 22);
  if (mpu.begin()) {
    mpu_available = true;
    mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
    mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
    Serial.println("[NEXUS-ESP32] MPU6050 Accelerometer/Vibration Initialized.");
  } else {
    Serial.println("[NEXUS-ESP32] MPU6050 not detected, using synthetic acceleration.");
  }

  // Connect to WiFi
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("[NEXUS-ESP32] Connecting to WiFi");
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[NEXUS-ESP32] WiFi Connected! IP: " + WiFi.localIP().toString());
  } else {
    Serial.println("\n[NEXUS-ESP32] Continuing in standalone mode...");
  }
}

void loop() {
  unsigned long now = millis();
  if (now - last_transmit_ms >= TRANSMIT_INTERVAL_MS) {
    last_transmit_ms = now;

    // 1. Read DHT22
    float temperature = dht.readTemperature();
    float humidity = dht.readHumidity();
    if (isnan(temperature)) temperature = 23.5;
    if (isnan(humidity)) humidity = 45.0;

    // 2. Read Gas Sensor (Mapped from ADC 0-4095 to 50-1000 ppm)
    int raw_gas = analogRead(PIN_GAS);
    float gas_ppm = map(raw_gas, 0, 4095, 50, 1000);

    // 2b. Read Smoke Sensor (Optical Obscuration 0.0% - 100.0%)
    int raw_smoke = analogRead(PIN_SMOKE);
    float smoke_pct = (float)raw_smoke * (100.0 / 4095.0);

    // 3. Read PIR Motion Sensor
    int motion_detected = digitalRead(PIN_PIR);

    // 4. Read LDR Photoresistor (Mapped to Lux 0-1000)
    int raw_ldr = analogRead(PIN_LDR);
    float light_lux = map(raw_ldr, 0, 4095, 0, 1000);

    // 5. Read MPU6050 Vibration
    float vibration_g = 0.05;
    if (mpu_available) {
      sensors_event_t a, g, temp;
      mpu.getEvent(&a, &g, &temp);
      vibration_g = sqrt(sq(a.acceleration.x) + sq(a.acceleration.y) + sq(a.acceleration.z - 9.8));
    }

    // Alarm indicator if gas, temperature, or smoke high
    if (temperature > 40.0 || gas_ppm > 400.0 || smoke_pct > 15.0) {
      digitalWrite(PIN_LED, HIGH);
      tone(PIN_BUZZER, 1000, 200);
    } else {
      digitalWrite(PIN_LED, LOW);
      noTone(PIN_BUZZER);
    }

    // Formulate JSON Batch Payload
    StaticJsonDocument<512> doc;
    doc["device_id"] = "esp32_lab02";
    doc["room_id"] = "lab_02";

    JsonArray readings = doc.createNestedArray("readings");

    JsonObject r_temp = readings.createNestedObject();
    r_temp["sensor_type"] = "temperature";
    r_temp["value"] = round(temperature * 10.0) / 10.0;
    r_temp["unit"] = "C";

    JsonObject r_hum = readings.createNestedObject();
    r_hum["sensor_type"] = "humidity";
    r_hum["value"] = round(humidity * 10.0) / 10.0;
    r_hum["unit"] = "%";

    JsonObject r_gas = readings.createNestedObject();
    r_gas["sensor_type"] = "gas";
    r_gas["value"] = round(gas_ppm);
    r_gas["unit"] = "ppm";

    JsonObject r_smoke = readings.createNestedObject();
    r_smoke["sensor_type"] = "smoke";
    r_smoke["value"] = round(smoke_pct * 10.0) / 10.0;
    r_smoke["unit"] = "%";

    JsonObject r_motion = readings.createNestedObject();
    r_motion["sensor_type"] = "motion";
    r_motion["value"] = motion_detected;
    r_motion["unit"] = "state";

    JsonObject r_light = readings.createNestedObject();
    r_light["sensor_type"] = "light";
    r_light["value"] = round(light_lux);
    r_light["unit"] = "lux";

    JsonObject r_vib = readings.createNestedObject();
    r_vib["sensor_type"] = "vibration";
    r_vib["value"] = round(vibration_g * 100.0) / 100.0;
    r_vib["unit"] = "g";

    String json_payload;
    serializeJson(doc, json_payload);

    Serial.println("[NEXUS-ESP32] Telemetry packet: " + json_payload);

    // Transmit via HTTP POST
    if (WiFi.status() == WL_CONNECTED) {
      HTTPClient http;
      http.begin(SERVER_URL);
      http.addHeader("Content-Type", "application/json");
      int http_code = http.POST(json_payload);
      if (http_code > 0) {
        Serial.printf("[NEXUS-ESP32] POST Status: %d\n", http_code);
      } else {
        Serial.printf("[NEXUS-ESP32] POST Failed: %s\n", http.errorToString(http_code).c_str());
      }
      http.end();
    }
  }
}
