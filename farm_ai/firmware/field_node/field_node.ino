/*
 * Smart Farm field node  (ESP32 + SX1276 LoRa)       *** NOT yet tested on hardware ***
 *
 * Designed around what actually fails on a farm:
 *   - No WiFi, no mains: LoRa radio, deep sleep, battery (+ optional small solar panel).
 *   - Dirt and water: sensor probe is the ONLY thing in the soil; the electronics live in a sealed
 *     weather-protected enclosure (IP65 is the design target: not yet verified on a physical box).
 *   - Silent mechanical failure: pump CURRENT and drip-line FLOW are measured on every run and reported,
 *     and the node protects itself (stops on jam / dry-run / zero flow).
 *   - Lost link: if the gateway is unreachable for 12 h, a capped local fail-safe waters a dry bed
 *     (only when the soil reading is valid; see soilReadingValid below).
 *   - Broken probe: a reading outside the calibrated range is reported as a sensor fault and
 *     blocks every automatic watering decision (raw 4095 is never "dry soil").
 *
 * Libraries (Arduino Library Manager): "LoRa" by Sandeep Mistry, "DHT sensor library" (Adafruit), "Adafruit INA219".
 * Board: use a low-sleep-current ESP32 board (e.g. FireBeetle 2 ESP32-E). Generic dev boards waste 5-10 mA asleep.
 *
 * Packet (CSV, ~45 bytes):  node,seq,soil_raw,temp_x10,hum,batt_mV,irr_s,flow_mL,pump_mA
 * Reply  (CSV, in RX window): ACK,node,seq,run_s      (run_s = seconds to run the pump now, 0 = none)
 */
#include <SPI.h>
#include <LoRa.h>
#include <DHT.h>
#include <Wire.h>
#include <Adafruit_INA219.h>

// ---------- identity & calibration (edit per node) ----------
#define NODE_ID            "N1"
#define SLEEP_SECONDS      900          // 15 min, must match uplink_interval_s in config/farm.json
#define RATED_PUMP_MA      800          // for the local protection limits below
#define DESIGN_FLOW_LPM    4.0
#define SOIL_DRY_RAW       3100         // sensor in air   (calibrate: see docs/FIELD_GUIDE.md)
#define SOIL_WET_RAW       1350         // sensor in water
#define LOCAL_DRY_RAW      2700         // fail-safe: water if drier than this and gateway silent
// Sensor validity window (calibrated range + margin): readings outside it mean
// the probe is cut/shorted/unplugged. They must never be treated as dry soil;
// they raise a sensor fault and inhibit every automatic watering decision.
#define SENSOR_VALID_LO    (SOIL_WET_RAW - 200)   // 1150: wetter than water = broken
#define SENSOR_VALID_HI    (SOIL_DRY_RAW + 300)   // 3400: past dry-air = disconnected
// ---------- pins ----------
#define PIN_SOIL_ADC       34
#define PIN_SOIL_PWR       25           // powers the soil sensor only while measuring
#define PIN_BATT_ADC       35           // via 100k/100k divider
#define PIN_DHT            27
#define PIN_PUMP           26           // logic-level MOSFET or relay module
#define PIN_FLOW           33           // YF-S201 hall pulse output
#define LORA_SS 5
#define LORA_RST 14
#define LORA_DIO0 2
// ---------- safety limits ----------
#define MAX_RUN_S          1800         // hard cap on any single pump run
#define FAILSAFE_WAKES     48           // 48 x 15 min = 12 h without gateway contact
#define FAILSAFE_RUN_S     300          // one capped run per fail-safe day
#define FLOW_PULSES_PER_L  450.0        // YF-S201

DHT dht(PIN_DHT, DHT22);
Adafruit_INA219 ina;

RTC_DATA_ATTR uint32_t seq = 0;
RTC_DATA_ATTR uint16_t lastIrrS = 0;       // result of the previous pump run, reported in the next packet
RTC_DATA_ATTR uint32_t lastFlowMl = 0;
RTC_DATA_ATTR uint16_t lastPumpMa = 0;
RTC_DATA_ATTR uint16_t wakesSinceAck = 0;
RTC_DATA_ATTR uint16_t failsafeCooldown = 0;

volatile uint32_t pulses = 0;
void IRAM_ATTR onPulse() { pulses++; }

// INO_TEST_ANCHOR: soilReadingValid
// Sole authority on whether a soil reading may be used for ANY watering decision.
bool soilReadingValid(uint16_t raw) {
  return raw >= SENSOR_VALID_LO && raw <= SENSOR_VALID_HI && raw != 0 && raw != 4095;
}

uint16_t readSoilRaw() {
  digitalWrite(PIN_SOIL_PWR, HIGH); delay(400);               // let the sensor settle
  uint32_t sum = 0; for (int i = 0; i < 16; i++) { sum += analogRead(PIN_SOIL_ADC); delay(5); }
  digitalWrite(PIN_SOIL_PWR, LOW);
  return sum / 16;
}
uint16_t readBattMv() {
  uint32_t sum = 0; for (int i = 0; i < 8; i++) { sum += analogReadMilliVolts(PIN_BATT_ADC); delay(2); }
  return (sum / 8) * 2;                                        // x2 for the divider
}

// Runs the pump with live protection. Records seconds, litres and mean current for the next uplink.
void runPump(uint16_t runS) {
  if (runS == 0) return;
  if (runS > MAX_RUN_S) runS = MAX_RUN_S;
  pulses = 0; uint32_t sumMa = 0, n = 0, t0 = millis();
  digitalWrite(PIN_PUMP, HIGH);
  while ((millis() - t0) / 1000 < runS) {
    delay(1000);
    float ma = ina.getCurrent_mA(); sumMa += (ma > 0 ? ma : 0); n++;
    uint32_t el = (millis() - t0) / 1000;
    if (el >= 3 && ma < 0.15 * RATED_PUMP_MA) break;           // dry run / dead pump / cut cable: stop, report 0 mA
    if (ma > 1.6 * RATED_PUMP_MA) break;                       // jammed or stalled: stop before it burns out
    if (el >= 15 && pulses == 0) break;                        // pump runs but nothing flows: blocked line
  }
  digitalWrite(PIN_PUMP, LOW);
  lastIrrS = (millis() - t0) / 1000;
  lastFlowMl = (uint32_t)(pulses / FLOW_PULSES_PER_L * 1000.0);
  lastPumpMa = n ? sumMa / n : 0;
}

void setup() {
  Serial.begin(115200);
  delay(1000); // Safety delay to prevent rapid boot loops and allow Serial stabilization
  Serial.println(F("\n=================================================="));
  Serial.println(F("     SMART FARM FIELD NODE BOOT (ESP32)"));
  Serial.println(F("=================================================="));

  pinMode(PIN_SOIL_PWR, OUTPUT); digitalWrite(PIN_SOIL_PWR, LOW);
  pinMode(PIN_PUMP, OUTPUT);     digitalWrite(PIN_PUMP, LOW);    // pump always OFF at boot
  pinMode(PIN_FLOW, INPUT_PULLUP); attachInterrupt(digitalPinToInterrupt(PIN_FLOW), onPulse, FALLING);
  analogReadResolution(12);
  dht.begin();
  Wire.begin();
  Wire.setTimeOut(50); // Prevent I2C bus hang if INA219 is not connected
  bool hasIna = ina.begin();
  if (hasIna) {
    Serial.println(F("[HW] INA219 sensor detected."));
  } else {
    Serial.println(F("[HW] INA219 sensor not found on I2C (using fallback)."));
  }

  uint16_t soil = readSoilRaw();
  bool soilFault = !soilReadingValid(soil);
  float t = dht.readTemperature(), h = dht.readHumidity();
  if (isnan(t)) t = 0; if (isnan(h)) h = 0;
  uint16_t battMv = readBattMv();
  seq++;

  String pkt = String(NODE_ID) + "," + seq + "," + soil + "," + (int)(t * 10) + "," + (int)h + "," + battMv + "," +
               lastIrrS + "," + lastFlowMl + "," + lastPumpMa;
  lastIrrS = 0; lastFlowMl = 0; lastPumpMa = 0;                // reported once

  Serial.print(F("[TELEMETRY] Uplink Packet: "));
  Serial.println(pkt);

  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);
  uint16_t runS = 0; bool acked = false;
  bool hasLoRa = LoRa.begin(868E6);                             // 868 MHz band
  if (hasLoRa) {
    Serial.println(F("[LORA] Radio initialized. Transmitting packet..."));
    LoRa.setSpreadingFactor(9); LoRa.setSignalBandwidth(125E3); LoRa.setCodingRate4(5);
    LoRa.setTxPower(14); LoRa.enableCrc();
    LoRa.beginPacket(); LoRa.print(pkt); LoRa.endPacket();
    uint32_t t0 = millis();                                    // RX window: gateway answers within ~1.5 s
    while (millis() - t0 < 1500) {
      int sz = LoRa.parsePacket();
      if (sz) {
        String r = ""; while (LoRa.available()) r += (char)LoRa.read();
        // expected: ACK,N1,<seq>,<run_s>
        int a = r.indexOf(','), b = r.indexOf(',', a + 1), c = r.indexOf(',', b + 1);
        if (r.startsWith("ACK") && r.substring(a + 1, b) == NODE_ID && r.substring(b + 1, c).toInt() == (long)seq) {
          runS = r.substring(c + 1).toInt(); acked = true; break;
        }
      }
    }
    LoRa.sleep();
  } else {
    Serial.println(F("[LORA] Radio not detected (Bench/Simulation mode). Listening on Serial for downlink..."));
    // Fallback serial RX window for lab / Wokwi testing
    uint32_t t0 = millis();
    while (millis() - t0 < 1500) {
      if (Serial.available()) {
        String r = Serial.readStringUntil('\n'); r.trim();
        int a = r.indexOf(','), b = r.indexOf(',', a + 1), c = r.indexOf(',', b + 1);
        if (r.startsWith("ACK") && r.substring(a + 1, b) == NODE_ID && r.substring(b + 1, c).toInt() == (long)seq) {
          runS = r.substring(c + 1).toInt(); acked = true;
          Serial.printf("[DOWNLINK] Received ACK: Run pump for %u s\n", runS);
          break;
        }
      }
      delay(10);
    }
  }

  if (acked) wakesSinceAck = 0; else if (wakesSinceAck < 65000) wakesSinceAck++;
  if (failsafeCooldown) failsafeCooldown--;

  // Local fail-safe: gateway silent for 12 h + soil dry + valid reading ->
  // one short, capped watering per day. soilReadingValid() is the gate that
  // keeps a raw 4095 (cut probe) or a shorted probe from being mistaken for
  // dry soil (regression-tested; do not remove it from this condition).
  if (soilFault) {
    Serial.printf("[SENSOR FAULT] Reading %u is outside the calibrated range (%d-%d): probe cut, shorted or unplugged.\n",
                  soil, SENSOR_VALID_LO, SENSOR_VALID_HI);
    Serial.println(F("[SENSOR FAULT] Automatic watering inhibited; water this bed by hand until the probe is repaired."));
  } else if (!acked && wakesSinceAck >= FAILSAFE_WAKES && soil > LOCAL_DRY_RAW && failsafeCooldown == 0) {
    runS = FAILSAFE_RUN_S; failsafeCooldown = 96;
    Serial.println(F("[FAIL-SAFE] Triggering local emergency watering."));
  }
  // An invalid reading also blocks a watering command: the node will not actuate
  // the pump on a decision that was based on data it can see is impossible.
  if (soilFault) {
    if (runS > 0) {
      Serial.printf("[SAFETY-LOCK] Watering command for %u s ignored: soil sensor reading is invalid.\n", runS);
      runS = 0;
    }
  }
  runPump(runS);

  Serial.printf("[SLEEP] Entering sleep for %u s...\n", SLEEP_SECONDS);
  Serial.flush();
  esp_sleep_enable_timer_wakeup((uint64_t)SLEEP_SECONDS * 1000000ULL);
  esp_deep_sleep_start();
}
void loop() {}
