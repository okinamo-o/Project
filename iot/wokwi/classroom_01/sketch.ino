#include <Adafruit_Sensor.h>
#include <ArduinoJson.h>
#include <DHT.h>
#include <HTTPClient.h>
#include <WiFi.h>
#include <math.h>

// WiFi Configuration (Wokwi uses Wokwi-GUEST with empty password)
const char *WIFI_SSID = "Wokwi-GUEST";
const char *WIFI_PASSWORD = "";

// NEXUS Backend Telemetry Endpoints (with gateway fallback)
const char *SERVER_URLS[] = {
    "http://host.wokwi.internal:8000/api/sensors/batch",
    "http://10.0.2.2:8000/api/sensors/batch",
    "http://192.168.1.207:8000/api/sensors/batch",
    "http://localhost:8000/api/sensors/batch"};
const int NUM_SERVER_URLS = 4;
int active_url_idx = 0;

// Vision Event Endpoints (for Normal Camera presence sync)
const char *VISION_URLS[] = {"http://host.wokwi.internal:8000/api/vision/event",
                             "http://10.0.2.2:8000/api/vision/event",
                             "http://192.168.1.207:8000/api/vision/event",
                             "http://localhost:8000/api/vision/event"};

// Classroom 01 Hardware Pin Assignments
#define DHTPIN 4
#define DHTTYPE DHT22
#define PIN_GAS 34
#define PIN_SMOKE 36
#define PIN_LDR 35
#define PIN_CAM_PIR 13
#define PIN_CAM_LED 2
#define PIN_ALARM_LED 12
#define PIN_BUZZER 15

DHT dht(DHTPIN, DHTTYPE);

unsigned long last_transmit_ms = 0;
const unsigned long TRANSMIT_INTERVAL_MS = 2000;
int last_cam_state = -1;

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n========================================================");
  Serial.println(" [NEXUS-ESP32] Classroom 1 Unique Sensor Node Online");
  Serial.println(" Dedicated Sensors: DHT22, Smoke, Gas, LDR, Normal Camera");
  Serial.println(" Target Room: classroom_01 | Device ID: esp32_classroom01");
  Serial.println("========================================================\n");

  pinMode(PIN_GAS, INPUT);
  pinMode(PIN_SMOKE, INPUT);
  pinMode(PIN_LDR, INPUT);
  pinMode(PIN_CAM_PIR, INPUT);
  pinMode(PIN_CAM_LED, OUTPUT);
  pinMode(PIN_ALARM_LED, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);

  dht.begin();

  // Connect to WiFi
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("[NEXUS-ESP32-CLASSROOM01] Connecting to WiFi");
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[NEXUS-ESP32-CLASSROOM01] WiFi Connected! IP: " +
                   WiFi.localIP().toString());
  } else {
    Serial.println("\n[NEXUS-ESP32-CLASSROOM01] Continuing in standalone TCP "
                   "serial mode...");
  }
}

void loop() {
  unsigned long now = millis();
  if (now - last_transmit_ms >= TRANSMIT_INTERVAL_MS) {
    last_transmit_ms = now;

    // 1. Read DHT22 Temperature & Humidity
    float temperature = dht.readTemperature();
    float humidity = dht.readHumidity();
    if (isnan(temperature))
      temperature = 21.8;
    if (isnan(humidity))
      humidity = 48.0;

    // 2. Read Gas Detector (knob 0-1023 == 0-1023 ppm)
    int raw_gas = analogRead(PIN_GAS);
    float gas_ppm = (float)raw_gas * (1023.0 / 4095.0);

    // 3. Read Smoke Detector (Optical Obscuration 0.0% - 100.0%)
    int raw_smoke = analogRead(PIN_SMOKE);
    float smoke_pct = (float)raw_smoke * (100.0 / 4095.0);

    // 4. Read LDR Photoresistor using Wokwi's official GAMMA=0.7, RL10=50k, R_series=10k transfer function
    int raw_ldr = analogRead(PIN_LDR);
    float v_ratio = (float)raw_ldr / 4095.0f;
    if (v_ratio < 0.0005f) v_ratio = 0.0005f;
    if (v_ratio > 0.9995f) v_ratio = 0.9995f;
    float r_ldr_kohm = 10.0f * v_ratio / (1.0f - v_ratio);
    float light_lux = 10.0f * powf(50.0f / r_ldr_kohm, 1.0f / 0.7f);
    if (light_lux < 0.0f) light_lux = 0.0f;
    if (light_lux > 100000.0f) light_lux = 100000.0f;

    // 5. Read Normal Camera Presence / Motion
    int cam_motion = digitalRead(PIN_CAM_PIR);

    // Camera Active Indicator: Blue LED illuminates when subject is detected
    digitalWrite(PIN_CAM_LED, cam_motion ? HIGH : LOW);

    // Formulate JSON Batch Payload for Classroom 01
    StaticJsonDocument<640> doc;
    doc["device_id"] = "esp32_classroom01";
    doc["room_id"] = "classroom_01";

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

    JsonObject r_light = readings.createNestedObject();
    r_light["sensor_type"] = "light";
    r_light["value"] = round(light_lux);
    r_light["unit"] = "lux";
    r_light["calibrated"] = true;

    JsonObject r_motion = readings.createNestedObject();
    r_motion["sensor_type"] = "motion";
    r_motion["value"] = cam_motion;
    r_motion["unit"] = "state";

    String json_payload;
    serializeJson(doc, json_payload);

    // Print for TCP Serial monitor bridge (port 4001 or 4000)
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

    // Transmit via HTTP POST with gateway fallback & check backend ML response
    if (WiFi.status() == WL_CONNECTED) {
      bool sent = false;
      for (int i = 0; i < NUM_SERVER_URLS; i++) {
        int idx = (active_url_idx + i) % NUM_SERVER_URLS;
        HTTPClient http;
        http.begin(SERVER_URLS[idx]);
        http.addHeader("Content-Type", "application/json");
        http.setTimeout(1200);
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
          http.end();
          break;
        }
        http.end();
      }
      if (!sent) {
        Serial.println(
            "[NEXUS-ESP32-CLASSROOM01] POST attempted on all gateway URLs");
      }

      // Sync camera presence to /api/vision/event if camera state changed
      if (cam_motion != last_cam_state) {
        last_cam_state = cam_motion;
        StaticJsonDocument<256> vdoc;
        vdoc["room_id"] = "classroom_01";
        vdoc["event_type"] = cam_motion ? "PERSON_DETECTED" : "NO_SUBJECT";
        vdoc["confidence"] = 0.95;
        vdoc["occupancy_count"] = cam_motion ? 1 : 0;
        String vpayload;
        serializeJson(vdoc, vpayload);

        HTTPClient vhttp;
        vhttp.begin(VISION_URLS[active_url_idx]);
        vhttp.addHeader("Content-Type", "application/json");
        vhttp.setTimeout(1000);
        vhttp.POST(vpayload);
        vhttp.end();
      }
    }

    // Hazard Alert: Only activate alarm LED & Buzzer when ML / multi-sensor fusion concludes danger
    if (ml_hazard_concluded) {
      digitalWrite(PIN_ALARM_LED, HIGH);
      tone(PIN_BUZZER, 1200, 200);
    } else {
      digitalWrite(PIN_ALARM_LED, LOW);
      noTone(PIN_BUZZER);
    }
  }
}
