#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <DHT.h>
#include <Adafruit_Sensor.h>
#include <math.h>

// WiFi Configuration (Wokwi uses Wokwi-GUEST with empty password)
const char* WIFI_SSID = "Wokwi-GUEST";
const char* WIFI_PASSWORD = "";

// NEXUS Backend Telemetry Endpoint
// Multi-Gateway Endpoint Fallback (host.wokwi.internal -> 10.0.2.2 -> LAN IP -> localhost)
const char* SERVER_URLS[] = {
  "http://host.wokwi.internal:8000/api/sensors/batch",
  "http://10.0.2.2:8000/api/sensors/batch",
  "http://192.168.1.207:8000/api/sensors/batch",
  "http://localhost:8000/api/sensors/batch"
};
const int NUM_SERVER_URLS = 4;
int active_url_idx = 0;

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

unsigned long last_transmit_ms = 0;
const unsigned long TRANSMIT_INTERVAL_MS = 2000;

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("[NEXUS-ESP32] Initializing Multimodal Sensor Node with Smoke & LDR Fire Detector...");

  pinMode(PIN_GAS, INPUT);
  pinMode(PIN_SMOKE, INPUT);
  pinMode(PIN_PIR, INPUT);
  pinMode(PIN_LDR, INPUT);
  pinMode(PIN_LED, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);

  dht.begin();

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

    // 2. Read Gas Sensor: knob position 0-1023 == 0-1023 ppm (ADC 0-4095)
    int raw_gas = analogRead(PIN_GAS);
    float gas_ppm = (float)raw_gas * (1023.0 / 4095.0);

    // 2b. Read Smoke Sensor: knob position 0-1023 == 0.0% - 100.0% obscuration
    int raw_smoke = analogRead(PIN_SMOKE);
    float smoke_pct = (float)raw_smoke * (100.0 / 4095.0);

    // 3. Read PIR Motion Sensor
    int motion_detected = digitalRead(PIN_PIR);

    // 4. Read LDR Photoresistor using Wokwi's official GAMMA=0.7, RL10=50k, R_series=10k transfer function
    int raw_ldr = analogRead(PIN_LDR);
    float v_ratio = (float)raw_ldr / 4095.0f;
    if (v_ratio < 0.0005f) v_ratio = 0.0005f;
    if (v_ratio > 0.9995f) v_ratio = 0.9995f;
    float r_ldr_kohm = 10.0f * v_ratio / (1.0f - v_ratio);
    float light_lux = 10.0f * powf(50.0f / r_ldr_kohm, 1.0f / 0.7f);
    if (light_lux < 0.0f) light_lux = 0.0f;
    if (light_lux > 100000.0f) light_lux = 100000.0f;

    // Formulate JSON Batch Payload
    StaticJsonDocument<640> doc;
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
    r_light["calibrated"] = true;

    String json_payload;
    serializeJson(doc, json_payload);

    Serial.println("[NEXUS-ESP32] Telemetry packet: " + json_payload);

    // Multi-Sensor ML Fusion Hazard Evaluation:
    // 1. Fire Conflagration requires 3-sensor corroboration: High Temp (>= 32°C) + Smoke (>= 6%) + High Lux flame light (>= 700 lux).
    //    High Temp + Smoke WITHOUT High Lux (e.g. 500 lux normal light or 20 lux dark) means no flame radiance -> no fire hazard!
    // 2. Gas leak hazard triggers on correlated Temp/Smoke + Gas (>= 160 ppm) or standalone Gas (>= 200 ppm).
    bool ldr_fire_signature = (light_lux >= 700.0);
    bool fire_hazard = (temperature >= 32.0 && smoke_pct >= 6.0 && ldr_fire_signature);
    bool gas_hazard =
        (temperature >= 32.0 && gas_ppm >= 160.0) ||
        (smoke_pct >= 6.0 && gas_ppm >= 160.0) ||
        (gas_ppm >= 200.0);
    bool ml_hazard_concluded = fire_hazard || gas_hazard;

    // Transmit via HTTP POST (tries each gateway URL, remembers the one that works)
    if (WiFi.status() == WL_CONNECTED) {
      bool sent = false;
      for (int i = 0; i < NUM_SERVER_URLS && !sent; i++) {
        int idx = (active_url_idx + i) % NUM_SERVER_URLS;
        HTTPClient http;
        http.begin(SERVER_URLS[idx]);
        http.addHeader("Content-Type", "application/json");
        http.setTimeout(1500);
        int http_code = http.POST(json_payload);
        if (http_code == 200) {
          active_url_idx = idx;
          sent = true;
          String resp = http.getString();
          StaticJsonDocument<256> resp_doc;
          if (deserializeJson(resp_doc, resp) == DeserializationError::Ok) {
            if (resp_doc.containsKey("hazard_detected")) {
              ml_hazard_concluded = resp_doc["hazard_detected"].as<bool>();
            }
          }
          Serial.printf("[NEXUS-ESP32] POST OK via %s\n", SERVER_URLS[idx]);
        }
        http.end();
      }
      if (!sent) {
        Serial.println("[NEXUS-ESP32] POST failed on all gateway URLs (is the backend running on port 8000?)");
      }
    }

    // Hazard Alert: Only activate alarm LED & Buzzer when ML / multi-sensor fusion concludes danger
    if (ml_hazard_concluded) {
      digitalWrite(PIN_LED, HIGH);
      tone(PIN_BUZZER, 1000, 200);
    } else {
      digitalWrite(PIN_LED, LOW);
      noTone(PIN_BUZZER);
    }
  }
}
