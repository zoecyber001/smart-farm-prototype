/*
 * ==============================================================================
 * SMART FARM PROTOTYPE: FIELD NODE HARDWARE SIMULATION (WOKWI / ESP32)
 * Designed for Technical & Architectural Review
 *
 * System Role: ESP32 Field Sensor & Actuator Node (Bed A / Node N1)
 *
 * Hardware Pinout:
 *   - GPIO 34 (ADC1_CH6): Capacitive Soil Moisture Sensor (Analog In)
 *   - GPIO 25: Switched VCC for Soil Probe (Anti-corrosion / Deep Sleep gating)
 *   - GPIO 35 (ADC1_CH7): Battery Voltage Divider (100k/100k -> 2:1 attenuation)
 *   - GPIO 27: DHT22 Temperature & Humidity Sensor (Digital Single-Wire)
 *   - GPIO 26: Submersible Pump Actuator (Relay Module + Blue LED Indicator)
 *   - GPIO 33: YF-S201 Flow Sensor Hall Pulse (Interrupt Falling Edge)
 *   - GPIO 21 / 22: I2C Bus (SDA / SCL) -> SSD1306 128x64 OLED Display
 *   - GPIO 4: Manual Instant Wake / Uplink Pushbutton
 *   - GPIO 12: Review Fault Switch 1 (Simulate Jammed Pump / Over-current)
 *   - GPIO 13: Review Fault Switch 2 (Simulate Blocked Drip Line / Zero Flow)
 *   - GPIO 14: Review Fault Switch 3 (Simulate Cut Sensor Wire / Raw 4095)
 *
 * Telemetry Protocol (CSV):
 *   Uplink:   <node>,<seq>,<soil_raw>,<temp_x10>,<hum>,<batt_mV>,<irr_s>,<flow_mL>,<pump_mA>
 *   Downlink: ACK,<node>,<seq>,<run_s>
 * ==============================================================================
 */

#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <DHT.h>

// ---------- Feature Toggles ----------
// Set to true if running with Wokwi IoT Gateway to send HTTP directly to local host
#define ENABLE_WOKWI_WIFI   false

#if ENABLE_WOKWI_WIFI
#include <WiFi.h>
#include <HTTPClient.h>
const char* WIFI_SSID = "Wokwi-GUEST";
const char* WIFI_PASS = "";
const char* SERVER_URL = "http://host.wokwi.internal:5000/api/uplink";
#endif

// ---------- Identity & Agronomic Calibration ----------
#define NODE_ID             "N1"
#define DEMO_SLEEP_SEC      15            // Fast wake cycle for review demos (production = 900s)
#define RATED_PUMP_MA       800           // 12V submersible pump rated current
#define DESIGN_FLOW_LPM     4.0           // Nominal drip line flow rate
#define SOIL_DRY_RAW        3100          // In dry air (0% VWC)
#define SOIL_WET_RAW        1350          // In saturated water (100% capacity)
#define LOCAL_DRY_RAW       2700          // Local fail-safe trigger threshold
#define FLOW_PULSES_PER_L   450.0         // YF-S201 Hall sensor calibration
#define MAX_RUN_S           900           // Max allowable pump run per command

// ---------- Hardware Pin Allocations ----------
#define PIN_SOIL_ADC        34
#define PIN_SOIL_PWR        25
#define PIN_BATT_ADC        35
#define PIN_DHT             27
#define PIN_PUMP            26
#define PIN_FLOW            33
#define PIN_WAKE            4
#define PIN_SW_JAM          18
#define PIN_SW_BLOCK        19
#define PIN_SW_CUT          23

#define SCREEN_WIDTH        128
#define SCREEN_HEIGHT       64
#define OLED_RESET          -1

// ---------- Peripherals ----------
Adafruit_SSD1306 oled(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);
DHT dht(PIN_DHT, DHT22);

// ---------- State Variables ----------
uint32_t seq = 0;
uint16_t lastIrrS = 0;
uint32_t lastFlowMl = 0;
uint16_t lastPumpMa = 0;
uint16_t wakesSinceAck = 0;
bool oledAvailable = false;

volatile uint32_t pulses = 0;
void IRAM_ATTR onFlowPulse() {
  pulses++;
}

// ---------- UI Rendering Helpers ----------
void renderOLED(const char* state, uint16_t soilRaw, int soilPct, float temp, float hum, float battV, const char* alert) {
  if (!oledAvailable) return;

  oled.clearDisplay();
  oled.setTextSize(1);
  oled.setTextColor(SSD1306_WHITE);

  // Header
  oled.setCursor(0, 0);
  oled.print(F("[SMART FARM] "));
  oled.print(NODE_ID);
  oled.print(F(" #"));
  oled.print(seq);
  oled.drawLine(0, 9, 127, 9, SSD1306_WHITE);

  // Line 1: Soil Moisture with graphical bar
  oled.setCursor(0, 13);
  oled.print(F("Soil: "));
  oled.print(soilPct);
  oled.print(F("% ("));
  oled.print(soilRaw);
  oled.print(F(")"));
  
  // Soil moisture mini progress bar
  oled.drawRect(0, 23, 128, 6, SSD1306_WHITE);
  int barW = map(constrain(soilPct, 0, 100), 0, 100, 0, 124);
  if (barW > 0) oled.fillRect(2, 25, barW, 2, SSD1306_WHITE);

  // Line 2: Climate & Battery
  oled.setCursor(0, 32);
  oled.print(F("T:"));
  oled.print(temp, 1);
  oled.print(F("C H:"));
  oled.print((int)hum);
  oled.print(F("% B:"));
  oled.print(battV, 2);
  oled.print(F("V"));

  // Line 3: System State / Actuator
  oled.setCursor(0, 44);
  if (strcmp(state, "PUMPING") == 0) {
    oled.fillRect(0, 42, 128, 10, SSD1306_WHITE);
    oled.setTextColor(SSD1306_BLACK, SSD1306_WHITE);
    oled.print(F(" >> PUMP ACTIVE << "));
    oled.setTextColor(SSD1306_WHITE);
  } else {
    oled.print(F("Mode: "));
    oled.print(state);
  }

  // Line 4: Alerts or Downlink status
  oled.setCursor(0, 54);
  if (alert && strlen(alert) > 0) {
    oled.print(F("! "));
    oled.print(alert);
  } else {
    oled.print(F("LoRa: Ready | RX: 1.5s"));
  }

  oled.display();
}

// ---------- Sensor Acquisition ----------
uint16_t readSoilMoisture() {
  // Check review fault switch: Cut probe wire (GPIO 14 pulled to GND)
  if (digitalRead(PIN_SW_CUT) == LOW) {
    Serial.println(F("[DIAGNOSTIC] Fault Switch 3 active: Simulating CUT SENSOR CABLE (Raw 4095)"));
    return 4095;
  }

  // Switch probe power on, settle, sample 16x, power off
  digitalWrite(PIN_SOIL_PWR, HIGH);
  delay(50);
  uint32_t sum = 0;
  for (int i = 0; i < 16; i++) {
    sum += analogRead(PIN_SOIL_ADC);
    delay(2);
  }
  digitalWrite(PIN_SOIL_PWR, LOW);
  return sum / 16;
}

uint16_t readBatteryMilliVolts() {
  uint32_t sum = 0;
  for (int i = 0; i < 8; i++) {
    sum += analogReadMilliVolts(PIN_BATT_ADC);
    delay(2);
  }
  // 100k/100k voltage divider multiplies by 2
  return (sum / 8) * 2;
}

float measurePumpCurrentmA() {
  if (digitalRead(PIN_PUMP) == LOW) return 0.0;

  // Check review fault switch: Jammed Pump (GPIO 18 pulled to GND)
  if (digitalRead(PIN_SW_JAM) == LOW) {
    return 1650.0; // Stalled/jammed impeller over-current (> 1.6 * RATED_PUMP_MA)
  }

  // Realistic simulated active pump current with slight jitter
  return RATED_PUMP_MA + (random(-15, 15));
}

// ---------- Irrigation & Actuator Control with Live Protection ----------
void executePumpCycle(uint16_t targetSeconds) {
  if (targetSeconds == 0) return;
  if (targetSeconds > MAX_RUN_S) targetSeconds = MAX_RUN_S;

  Serial.println(F("\n=================================================="));
  Serial.printf(">> STARTING IRRIGATION CYCLE: %u SECONDS\n", targetSeconds);
  Serial.println(F("=================================================="));

  pulses = 0;
  uint32_t sumMa = 0, samples = 0;
  uint32_t startTime = millis();
  char faultMsg[32] = "";

  digitalWrite(PIN_PUMP, HIGH);

  while ((millis() - startTime) / 1000 < targetSeconds) {
    uint32_t elapsed = (millis() - startTime) / 1000;
    uint32_t remaining = targetSeconds - elapsed;

    // Simulate flow pulses unless Fault Switch 2 is active (Blocked Line)
    bool isBlocked = (digitalRead(PIN_SW_BLOCK) == LOW);
    if (!isBlocked) {
      // 4 LPM nominal = ~30 pulses per second
      pulses += 30;
    }

    float currentmA = measurePumpCurrentmA();
    sumMa += (currentmA > 0 ? (uint32_t)currentmA : 0);
    samples++;

    // Telemetry log to serial
    float flowL = pulses / FLOW_PULSES_PER_L;
    Serial.printf("[PUMP] T-%02us | Curr: %.0f mA | Flow: %.2f L (%u pulses)\n", remaining, currentmA, flowL, pulses);

    // Live display update
    if (oledAvailable) {
      oled.fillRect(0, 42, 128, 22, SSD1306_BLACK);
      oled.setCursor(0, 44);
      oled.printf("PUMP: %us left", remaining);
      oled.setCursor(0, 54);
      oled.printf("Flow: %.2fL | %03.0fmA", flowL, currentmA);
      oled.display();
    }

    // Safety Limit 1: Pump Over-current / Jam protection (1.6x rated)
    if (currentmA > 1.6 * RATED_PUMP_MA) {
      snprintf(faultMsg, sizeof(faultMsg), "FAULT: Jammed Pump");
      Serial.println(F(">>> [SAFETY INTERLOCK] Current > 160% rated! Jam detected. Halting pump."));
      break;
    }

    // Safety Limit 2: Pump Under-current / Dry run / Dead pump (< 15% rated after 3s)
    if (elapsed >= 3 && currentmA < 0.15 * RATED_PUMP_MA) {
      snprintf(faultMsg, sizeof(faultMsg), "FAULT: Pump Dead/Dry");
      Serial.println(F(">>> [SAFETY INTERLOCK] Current < 15% rated! Dead pump/cut line. Halting pump."));
      break;
    }

    // Safety Limit 3: Zero Flow detection after 15s (Blocked line or dry tank)
    if (elapsed >= 15 && pulses == 0) {
      snprintf(faultMsg, sizeof(faultMsg), "FAULT: Blocked Line");
      Serial.println(F(">>> [SAFETY INTERLOCK] Zero flow measured after 15s! Line blocked. Halting pump."));
      break;
    }

    delay(1000);
  }

  digitalWrite(PIN_PUMP, LOW);
  uint32_t totalDuration = (millis() - startTime) / 1000;
  lastIrrS = totalDuration;
  lastFlowMl = (uint32_t)(pulses / FLOW_PULSES_PER_L * 1000.0);
  lastPumpMa = samples ? (sumMa / samples) : 0;

  Serial.printf(">> PUMP CYCLE COMPLETED: Ran %u s | Flow: %u mL | Avg Current: %u mA\n",
                lastIrrS, lastFlowMl, lastPumpMa);
  if (strlen(faultMsg) > 0) {
    Serial.printf(">> TERMINATION REASON: %s\n\n", faultMsg);
  }
}

// ---------- Telemetry Dispatch & RX Window ----------
String buildTelemetryPacket(uint16_t soilRaw, float temp, float hum, uint16_t battMv) {
  seq++;
  // Format: node,seq,soil_raw,temp_x10,hum,batt_mV,irr_s,flow_mL,pump_mA
  return String(NODE_ID) + "," +
         seq + "," +
         soilRaw + "," +
         (int)(temp * 10) + "," +
         (int)hum + "," +
         battMv + "," +
         lastIrrS + "," +
         lastFlowMl + "," +
         lastPumpMa;
}

uint16_t processDownlinkWindow(const String& pkt) {
  Serial.println(F("\n----------------- TELEMETRY UPLINK -----------------"));
  Serial.print(F("UPLINK PACKET: "));
  Serial.println(pkt);
  Serial.println(F("Opening 1.5s RX Window for Gateway reply..."));
  Serial.println(F("Hint: Send 'ACK,N1,<seq>,<run_s>' to command irrigation."));
  Serial.println(F("----------------------------------------------------"));

  uint16_t commandedRunS = 0;
  bool ackReceived = false;
  uint32_t rxStart = millis();

#if ENABLE_WOKWI_WIFI
  // Optional HTTP Uplink when using Wokwi IoT Gateway
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(SERVER_URL);
    http.addHeader("Content-Type", "application/json");

    // Parse packet into JSON object
    String jsonPayload = String("{\"node\":\"") + NODE_ID + "\"," +
                         "\"seq\":" + seq + "," +
                         "\"soil_raw\":" + pkt.substring(pkt.indexOf(',') + 1) + "}";
    int httpCode = http.POST(jsonPayload);
    if (httpCode > 0) {
      String response = http.getString();
      Serial.printf("HTTP Response (%d): %s\n", httpCode, response.c_str());
      // Simple parse of downlink run_s
      int idx = response.indexOf("\"run_s\":");
      if (idx > 0) {
        commandedRunS = response.substring(idx + 8).toInt();
        ackReceived = true;
      }
    }
    http.end();
  }
#endif

  // Serial LoRa RX Window simulation (1500 ms)
  while (millis() - rxStart < 1500) {
    if (Serial.available()) {
      String reply = Serial.readStringUntil('\n');
      reply.trim();
      if (reply.length() > 0) {
        Serial.printf("[RX-WINDOW] Received: '%s'\n", reply.c_str());
        // Expected format: ACK,N1,<seq>,<run_s>
        if (reply.startsWith("ACK")) {
          int c1 = reply.indexOf(',');
          int c2 = reply.indexOf(',', c1 + 1);
          int c3 = reply.indexOf(',', c2 + 1);
          if (c1 > 0 && c2 > 0 && c3 > 0) {
            String ackNode = reply.substring(c1 + 1, c2);
            long ackSeq = reply.substring(c2 + 1, c3).toInt();
            long runS = reply.substring(c3 + 1).toInt();
            if (ackNode == NODE_ID && ackSeq == (long)seq) {
              commandedRunS = (uint16_t)runS;
              ackReceived = true;
              Serial.printf("[DOWNLINK] Confirmed for Node %s, Seq %ld. Commanded Run: %u seconds.\n",
                            ackNode.c_str(), ackSeq, commandedRunS);
              break;
            }
          }
        }
      }
    }
    delay(10);
  }

  // Clear last run metrics after successful reporting
  lastIrrS = 0;
  lastFlowMl = 0;
  lastPumpMa = 0;

  if (ackReceived) {
    wakesSinceAck = 0;
  } else {
    wakesSinceAck++;
    Serial.println(F("[RX-WINDOW] Closed. No gateway ACK received."));
  }

  return commandedRunS;
}

// ---------- Arduino Lifecycle ----------
void setup() {
  Serial.begin(115200);
  delay(100);

  Serial.println(F("\n=================================================="));
  Serial.println(F("     SMART FARM FIELD NODE HARDWARE BOOT"));
  Serial.println(F("     Architecture: ESP32 + LoRa + Deep Sleep"));
  Serial.println(F("=================================================="));

  pinMode(PIN_SOIL_PWR, OUTPUT);
  digitalWrite(PIN_SOIL_PWR, LOW);

  pinMode(PIN_PUMP, OUTPUT);
  digitalWrite(PIN_PUMP, LOW);

  pinMode(PIN_FLOW, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PIN_FLOW), onFlowPulse, FALLING);

  pinMode(PIN_WAKE, INPUT_PULLUP);
  pinMode(PIN_SW_JAM, INPUT_PULLUP);
  pinMode(PIN_SW_BLOCK, INPUT_PULLUP);
  pinMode(PIN_SW_CUT, INPUT_PULLUP);

  analogReadResolution(12);

  // Initialize I2C Bus & OLED Display
  Wire.begin(21, 22);
  Wire.setTimeOut(50);
  if (oled.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    oledAvailable = true;
    oled.clearDisplay();
    oled.setTextSize(1);
    oled.setTextColor(SSD1306_WHITE);
    oled.setCursor(10, 20);
    oled.println(F("Smart Farm ESP32"));
    oled.setCursor(10, 35);
    oled.println(F("Initializing..."));
    oled.display();
  } else {
    Serial.println(F("[WARN] SSD1306 OLED not found at 0x3C (proceeding headless)."));
  }

  dht.begin();

#if ENABLE_WOKWI_WIFI
  Serial.print(F("[WIFI] Connecting to Wokwi-GUEST..."));
  WiFi.begin(WIFI_SSID, WIFI_PASS, 6);
  uint32_t t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 4000) {
    delay(200);
    Serial.print(".");
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println(F(" Connected!"));
  } else {
    Serial.println(F(" Timeout. Proceeding in LoRa/Serial mode."));
  }
#endif

  Serial.println(F("[READY] All subsystems operational. Starting main loop.\n"));
}

void loop() {
  // 1. Acquire telemetry
  uint16_t soilRaw = readSoilMoisture();
  int soilPct = constrain(map(soilRaw, SOIL_DRY_RAW, SOIL_WET_RAW, 0, 100), 0, 100);

  float temp = dht.readTemperature();
  float hum = dht.readHumidity();
  if (isnan(temp)) temp = 25.0;
  if (isnan(hum)) hum = 60.0;

  uint16_t battMv = readBatteryMilliVolts();
  float battV = battMv / 1000.0;

  // 2. Build packet & send
  String pkt = buildTelemetryPacket(soilRaw, temp, hum, battMv);
  renderOLED("UPLINK", soilRaw, soilPct, temp, hum, battV, "Sending packet...");

  // 3. Process RX window for downlink command
  uint16_t runSeconds = processDownlinkWindow(pkt);

  // 4. Local Fail-Safe Logic
  // If gateway is silent for multiple wakes and soil is dry, perform one emergency capped run
  if (runSeconds == 0 && wakesSinceAck >= 10 && soilRaw > LOCAL_DRY_RAW) {
    Serial.println(F("[FAIL-SAFE] Gateway silent & soil critical! Initiating local fail-safe 60s water."));
    runSeconds = 60;
    renderOLED("FAIL-SAFE", soilRaw, soilPct, temp, hum, battV, "Fail-safe Watering");
  }

  // 5. Actuate Pump if commanded
  if (runSeconds > 0) {
    renderOLED("PUMPING", soilRaw, soilPct, temp, hum, battV, "Irrigation Active");
    executePumpCycle(runSeconds);
  }

  // 6. Enter Simulated Sleep / Countdown
  Serial.printf("\n[SLEEP] Entering low-power sleep for %u seconds.\n", DEMO_SLEEP_SEC);
  Serial.println(F("        (Press Yellow 'Wake' button on GPIO 4 to trigger instant wake)\n"));

  uint32_t sleepStart = millis();
  while ((millis() - sleepStart) / 1000 < DEMO_SLEEP_SEC) {
    uint32_t remaining = DEMO_SLEEP_SEC - ((millis() - sleepStart) / 1000);
    char sleepBuf[32];
    snprintf(sleepBuf, sizeof(sleepBuf), "Sleep: %02us (Btn wake)", remaining);
    renderOLED("SLEEPING", soilRaw, soilPct, temp, hum, battV, sleepBuf);

    // Check manual wake button (GPIO 4 active LOW)
    if (digitalRead(PIN_WAKE) == LOW) {
      Serial.println(F("\n[INTERRUPT] Manual Wake Button pressed!"));
      delay(300); // Debounce
      break;
    }
    delay(500);
  }
}
