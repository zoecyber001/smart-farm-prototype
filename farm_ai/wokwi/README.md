# Smart Farm Field Node: Wokwi Hardware Simulation Suite

> **Architectural Status:** Demo-Ready Hardware Simulation for Technical & Client Reviews
> **Target MCU:** Espressif ESP32 DevKit V4 (`board-esp32-devkit-c-v4`)
> **Firmware:** Embedded C++ (Arduino Framework / FreeRTOS compatible)
> **Radio / Telemetry:** Telemetry over the Wokwi serial console (CSV). The "LoRa radio link" is simulated by that serial path — no radio is modelled. An EXPERIMENTAL direct-WiFi HTTP path exists in the sketch but is disabled by default and unverified.

---

## 1. System Overview

This hardware simulation environment faithfully models the **Smart Farm Field Node** described in the system architecture and `docs/FIELD_GUIDE.md`. It allows reviewers to inspect, interact with, and stress-test the field hardware without needing physical soil beds, LoRa transceivers, or 12V submersible pumps on hand.

```
 +-----------------------------------------------------------------------------------+
 |                             WOKWI SIMULATED HARDWARE                              |
 |                                                                                   |
 |  [Soil Potentiometer] ----> GPIO 34 (ADC) <--- Switched VCC (GPIO 25)             |
 |  [Batt Potentiometer] ----> GPIO 35 (ADC) (100k/100k divider)                     |
 |  [DHT22 Temp & Hum]   ----> GPIO 27 (Single-Wire)                                 |
 |  [Flow Sensor Hall]   ----> GPIO 33 (Interrupt Pulses) <--- [Manual Button / Gen] |
 |  [Pump Relay & LED]   <---- GPIO 26 (Relay Module + Blue Indicator)               |
 |  [SSD1306 OLED]       <---> GPIO 21 (SDA), GPIO 22 (SCL) I2C                      |
 |  [Fault Switches]     ----> GPIO 18 (Jam), GPIO 19 (Block), GPIO 23 (Cut)         |
 |  [Wake Pushbutton]    ----> GPIO 4 (Instant Wake / Interrupt)                     |
 +-----------------------------------------------------------------------------------+
                                   |
                     Serial Stream / LoRa Bridge
                                   v
             [ wokwi_gateway.py ]  or  [ Direct WiFi: EXPERIMENTAL, disabled ]
                                   v
             [ Flask Backend: /api/uplink (server.py) ]
                                   v
                [ Real-time Offline PWA Dashboard ]
```

---

## 2. Hardware Pinout & Component Matrix

| Component | Wokwi Part Type | ESP32 Pin / Rail | Function / Physics |
|---|---|---|---|
| **Solderless Breadboard** | `wokwi-breadboard` | Rails: `3V3`, `5V`, `GND` | 830-point distribution bus. Top rail (`tp`/`tn`) distributes 3.3V & GND; bottom rail (`bp`/`bn`) distributes 5V & GND. |
| **Soil Probe** | `wokwi-potentiometer` | `GPIO 34` (SIG)<br>`esp:25` (VCC, direct wire), `bb1:bn` (GND) | Stands in for the capacitive probe: raw 3100 = dry air (0%), 1350 = saturated (100%). Its VCC is wired to **GPIO 25**, which the firmware drives HIGH only around a reading (anti-corrosion power gating) — the simulation exercises the same gate as the real sensor. Default pot position (600/1023) ≈ raw 2400 ≈ 40% VWC on the OLED, safely wet of the ~22% fail-safe trigger. |
| **Battery Monitor** | `wokwi-potentiometer` | `GPIO 35` (SIG)<br>`bb1:tp` (3.3 V), `bb1:tn` (GND) | Stands in for the 100k/100k divider on the Li-ion pack: firmware multiplies its ADC mV ×2, so a pot on the 3.3 V rail displays 0–6.6 V equivalents (a real 4.2 V pack ≈ 2.1 V at the pin). Default (600/1023) ≈ 3.9 V shown — a healthy battery. Keep this pot's VCC on the **3.3 V rail**: 5 V on GPIO 35 is outside the ADC's range. |
| **Microclimate** | `wokwi-dht22` | `GPIO 27` (Data)<br>`bb1:tp` (3.3V), `bb1:tn` (GND) | Ambient temperature (-40°C to 80°C) and relative humidity (0–100%). |
| **Pump Actuator** | `wokwi-relay-module` | `GPIO 26` (IN)<br>`bb1:bp` (5V), `bb1:bn` (GND) | 12V submersible pump contactor with audible click & status light. |
| **Pump Active LED**| `wokwi-led` (Blue) | `GPIO 26` (Anode)<br>`bb1:bn` (GND via 220Ω) | High-visibility optical indicator showing when pump motor is energized. |
| **Flow Meter** | `wokwi-pushbutton` | `GPIO 33` (Pulse)<br>`bb1:tn` (GND) | YF-S201 Hall-effect turbine simulator (450 pulses/L). Generates synthetic pulses during normal runs or on manual push. |
| **Local Display** | `board-ssd1306` | `GPIO 21` (SDA), `GPIO 22` (SCL)<br>`bb1:tp` (3.3V), `bb1:tn` (GND) | 128x64 I2C graphical OLED displaying real-time VWC %, battery bar, climate, pump telemetry, and faults. |
| **Wake Trigger** | `wokwi-pushbutton` | `GPIO 4` (Active Low)<br>`bb1:tn` (GND) | Manual interrupt button to immediately wake the node from sleep during presentations. |
| **Fault Switch 1** | `wokwi-slide-switch` | `GPIO 18`<br>`bb1:tn` (GND) | **Simulate Jammed Pump:** Forces current to 1650 mA (>1.6x rated), triggering immediate overcurrent shutdown. |
| **Fault Switch 2** | `wokwi-slide-switch` | `GPIO 19`<br>`bb1:tn` (GND) | **Simulate Blocked Drip Line:** Inhibits water flow pulses, triggering zero-flow cutoff after 15 seconds. |
| **Fault Switch 3** | `wokwi-slide-switch` | `GPIO 23`<br>`bb1:tn` (GND) | **Simulate Cut Probe Wire:** Forces raw ADC to 4095, disabling automatic watering to protect roots. |

---

## 3. How to Launch and Run the Simulation

### Option A: VS Code with Wokwi Extension (Recommended for Development)
1. Install the **Wokwi Simulator** extension in VS Code.
2. Open this repository.
3. Open `farm_ai/wokwi/diagram.json` or press `Ctrl+Shift+P` (or `Cmd+Shift+P`) and choose **Wokwi: Start Simulator**.
4. The simulation canvas will boot up, showing the ESP32, OLED screen, sensors, and actuators.

### Option B: Online Wokwi Web Simulator (Zero-Install Review)
1. Go to [wokwi.com/projects/new/esp32](https://wokwi.com/projects/new/esp32).
2. Copy and paste the contents of:
   - `diagram.json` into the web editor's `diagram.json` tab.
   - `sketch.ino` into the main `sketch.ino` code tab.
   - `libraries.txt` into the Library Manager tab (or add `Adafruit SSD1306`, `Adafruit GFX Library`, `DHT sensor library`, `Adafruit Unified Sensor`).
3. Click the green **Play / Start Simulation** button.

---

## 4. Live Review Demonstration Scenarios

Here is how to showcase the system's fault-tolerance and agronomic intelligence during a review:

### Scenario 1: Normal Healthy Irrigation
1. Turn the **Soil Moisture** potentiometer toward the left (dry reading, raw > 2700).
2. Press the yellow **Wake** button (GPIO 4) to send an immediate telemetry uplink.
3. Observe the Serial Monitor: the node outputs its packet (`N1,1,2850,260,55,3950,0,0,0`).
4. In the Serial input box, reply with:
   ```
   ACK,N1,1,20
   ```
5. **Watch the hardware respond:**
   - The Relay clicks ON, the Blue LED illuminates.
   - The OLED shows `>> PUMP ACTIVE <<` with a live countdown timer.
   - The flow meter measures liters delivered while current stays at ~800 mA nominal.
   - After 20 seconds, the pump safely shuts off.

### Scenario 2: Jammed Pump Protection (Mechanical Failure Drill)
1. Flip **Fault Switch 1** (`sw_jam` on GPIO 18) to the active position.
2. Command a pump run (`ACK,N1,2,30`).
3. **Observation:** Within 1 second, the node measures current > 1600 mA (stalled motor).
4. The safety interlock immediately shuts off the relay to prevent motor burnout, logs:
   `>>> [SAFETY INTERLOCK] Current > 160% rated! Jam detected. Halting pump.`
5. The OLED updates to `FAULT: Jammed Pump`.

### Scenario 3: Blocked Drip Line (Mud / Clog Drill)
1. Flip **Fault Switch 2** (`sw_block` on GPIO 19) to the active position.
2. Command a pump run (`ACK,N1,3,30`).
3. **Observation:** The pump runs, but no flow pulses are detected.
4. Exactly at elapsed $t = 15\,\text{s}$, the node detects zero flow and halts the pump:
   `>>> [SAFETY INTERLOCK] Zero flow measured after 15s! Line blocked. Halting pump.`
5. The next uplink packet reports `irr_s: 15, flow_mL: 0`, and the dashboard triggers the `LINE_BLOCKED` alert instructing the farmer to flush the emitters.

### Scenario 4: Rodent-Chewed Sensor Cable (Electrical Failure Drill)
1. Flip **Fault Switch 3** (`sw_cut` on GPIO 23) to the active position.
2. Press the yellow **Wake** button.
3. **Observation:** Soil ADC reads 4095 (maximum saturated value). The node itself recognises raw 4095 as invalid (outside its validity window) and shows `SENSOR FAULT` on the OLED.
4. **The node refuses to water while the reading is untrustworthy** — no local fail-safe watering, and any `ACK,...` command pasted into the serial console is ignored too (the operator manual says hand-water instead).
5. The uplink still reports `soil_raw 4095`; the backend's own health check flags `SENSOR_FAULT` (a second, independent layer), disables automated irrigation for that bed, and shows the alert.
6. Flip the switch back off and send a healthy reading to clear the fault, then normal operation resumes.

---

## 5. Live Integration with the Farm Server & Dashboard

To connect the Wokwi simulation to the real Flask API and web dashboard:

1. **Start the local server:**
   ```bash
   cd farm_ai
   ../.venv/bin/python server.py
   ```
   Open `http://localhost:5000` in your browser.

2. **Run the Wokwi Gateway Bridge:**
   ```bash
   cd farm_ai
   ../.venv/bin/python wokwi/wokwi_gateway.py --server http://localhost:5000
   ```
3. Whenever Wokwi emits an uplink packet in the serial terminal, paste it into the gateway terminal. The gateway immediately forwards it to `/api/uplink`, obtains the AI watering decision, and generates the downlink ACK string ready to paste back into Wokwi!

4. **Or run the automated review sequence:**
   ```bash
   cd farm_ai
   ../.venv/bin/python wokwi/wokwi_gateway.py --demo
   ```
   This automatically streams a live sequence of Wokwi hardware states (dry soil, post-watering, blocked line, cut cable, repair recovery) directly to the dashboard so reviewers can watch the live state updates, charts, and alert resolutions in real time.

> **About "Direct WiFi":** `sketch.ino` contains an EXPERIMENTAL `ENABLE_WOKWI_WIFI` branch that skips the serial bridge and POSTs telemetry JSON straight to `/api/uplink`. It is built to the same contract as the CSV path (`node, ts, seq, soil_raw, …`), but in this demo environment there is no real radio or WiFi stack involved; the branch is compiled out (`#define ENABLE_WOKWI_WIFI 0`) and has not been verified end-to-end. Treat the serial bridge above as the supported path.

---

## 6. Verification Test Suite

To verify that all Wokwi telemetry packets, safety thresholds, and fault detectors conform to the server specification, run:
```bash
cd farm_ai
../.venv/bin/python wokwi/test_uplink.py
```
Expected output:
```
[TEST] Initializing Farm Engine test instance...
[TEST] Sending dry soil packet from Wokwi node N1...
       Server response: HTTP 200 | Downlink run_s: 1800s
[TEST] Sending blocked line execution report (0 flow for 60s run)...
       Bed A reported faults: ['Drip line is blocked: only 0% of normal flow']

[SUCCESS] All Wokwi hardware packet tests passed successfully!
```
