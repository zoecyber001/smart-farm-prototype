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

## 3. How to Launch and Run the Simulation (Step-by-Step Setup)

### Option A: Online Wokwi Web Simulator (easiest — works in any browser, no install)
1. Copy two files from this repo onto your machine first:
   - `farm_ai/wokwi/diagram.json`
   - `farm_ai/wokwi/sketch.ino`
2. In your browser, open [wokwi.com/projects/new/esp32](https://wokwi.com/projects/new/esp32). You may need to sign in with a Google/GitHub account (free).
3. You will see two tabs above the code editor: **sketch.ino** and **diagram.json**.
4. Open `diagram.json` from the repo, select-all (`Ctrl+A`), copy (`Ctrl+C`), then in Wokwi click the **diagram.json** tab, select-all and paste (`Ctrl+V`). It overwrites the default circuit.
5. Do the same for `sketch.ino`: click the **sketch.ino** tab, select-all, paste the repo's `sketch.ino` over it.
6. Next, add the four libraries: click the red **Library Manager** tab (the one with a + shape), search for and click **Add** on each of:
   - `Adafruit SSD1306`
   - `Adafruit GFX Library`
   - `DHT sensor library`
   - `Adafruit Unified Sensor`
7. Click the green **Play button** (▶) at the top of the screen.
8. A panel appears at the bottom of the canvas — this is the **Serial Monitor**. Within ~10 seconds you should see:
   ```
   SMART FARM FIELD NODE HARDWARE BOOT
   [READY] All subsystems operational. Starting main loop.
   ```
   and then telemetry packets like `UPLINK PACKET: N1,1,2402,265,58,4326,0,0,0`.
9. If it doesn't compile: check that **all four** libraries are added (missing `Adafruit Unified Sensor` is the most common miss) and that both tabs were pasted from the repo, not hand-typed.

> **Wiring visuals:** the canvas should show an ESP32 DevKit-C V4 on a breadboard with two potentiometers, a DHT22, an OLED, a relay + blue LED, two push-buttons and three slide-switches, all per `diagram.json`. If wires look wrong, re-paste `diagram.json` — don't try to fix them by hand.

### Option B: VS Code with the Wokwi Extension (needed to run the local files directly)
1. Install [VS Code](https://code.visualstudio.com) if you don't have it.
2. Open VS Code → click the **Extensions** icon on the left toolbar (four squares).
3. Search for `Wokwi Simulator` (publisher: Wokwi) → click **Install**.
4. Clone or download this repository, then in VS Code: **File → Open Folder…** and select the repository folder (the top folder that contains `farm_ai/`).
5. In the Explorer panel (left sidebar), navigate into `farm_ai/wokwi/` and click **once** on `diagram.json` to open it.
6. Press `Ctrl+Shift+P` (Windows/Linux) or `Cmd+Shift+P` (Mac) to open the command palette.
7. Type `Wokwi` and pick **Wokwi: Start Simulator**.
8. A **Wokwi Simulator** tab opens inside VS Code showing the circuit. The serial output appears in the bottom **Terminal** panel under a **Wokwi Simulator** tab.
9. Click the green play button in the Wokwi tab to start the simulation, then watch the serial terminal for the boot banner and packets.
10. If the extension asks for a project folder, choose the folder that contains `diagram.json` (i.e. `farm_ai/wokwi/`).

> **Which option for the presentation?** Option A (browser) is the most reliable on a presentation laptop and needs no tools installed; Option B (VS Code) lets you run the repo files directly without copy-pasting. Both run the identical firmware.

---

## 4. Live Review Demonstration Scenarios

Here is how to showcase the system's fault-tolerance and agronomic intelligence during a review.

> **About typing into Wokwi:** the Serial Monitor input box (needed for the `ACK,…` scenarios below) is a browser feature that is hidden or unavailable on some setups. **Scenarios 1 and 5 need zero typing.** If the input box works for you, Scenarios 2–4 add the gateway round trip on top.

### Scenario 1: Autonomous Fail-Safe Irrigation (ZERO serial input needed — start here)
This is the strongest single demo: the node waters the crop **by itself** when the gateway cannot answer, using its built-in fail-safe.
1. Slide the **Soil Moisture** potentiometer until the OLED shows roughly **5–17 %** (raw 2800–3200 in the uplink's 3rd number). Do NOT slide it to the very end-stop — raw 4095 is interpreted as a cut probe, and the node will correctly refuse to water.
2. Press the yellow **Wake** button repeatedly. The node counts every wake it makes without receiving a gateway ACK. On (and after) the **10th silent wake with dry soil**, the internal fail-safe fires:
   ```
   [FAIL-SAFE] Gateway silent & soil critical! Initiating local fail-safe 60s water.
   >> STARTING IRRIGATION CYCLE: 60 SECONDS
   ```
3. **Watch the hardware respond:**
   - The Relay clicks ON and the Blue LED illuminates.
   - The OLED shows `PUMP: 59s left` and a live flow/current readout.
   - The Serial Monitor prints a `[PUMP] T-59s | Curr: 800 mA | Flow: …` line every second.
   - At 60 s: `>> PUMP CYCLE COMPLETED: Ran 60 s | Flow: 4000 mL | Avg Current: 800 mA`.
4. **Note:** there is no cooldown after a fail-safe run — as long as the soil is still dry and no ACK is received, the next Wake press re-runs the fail-safe, which makes repeats easy in a rehearsal.

### Scenario 2: Gateway-Commanded Irrigation (requires the Wokwi Serial input box)
1. Turn the **Soil Moisture** potentiometer toward the left (dry reading, raw > 2700).
2. Press the yellow **Wake** button (GPIO 4) to send an immediate telemetry uplink.
3. Observe the Serial Monitor: the node outputs its packet (`N1,1,2850,260,55,3950,0,0,0`) and prints `Opening 1.5s RX Window for Gateway reply...`.
4. In the Serial input box, reply with:
   ```
   ACK,N1,1,20
   ```
   (The 1.5 s window is tight — pre-type the line and just swap in the new sequence number.)
5. **Watch the hardware respond:**
   - The Relay clicks ON, the Blue LED illuminates.
   - The OLED shows `>> PUMP ACTIVE <<` with a live countdown timer.
   - The flow meter measures liters delivered while current stays at ~800 mA nominal.
   - After 20 seconds, the pump safely shuts off.
6. If you want the **dashboard** to witness this too, run the server + gateway bridge described in section 5 below.

### Scenario 3: Jammed Pump Protection (Mechanical Failure Drill)
1. Run the pump first — either via **Scenario 1** (fail-safe, no typing) or **Scenario 2** (gateway ACK paste).
2. While the pump is running, flip **Fault Switch 1** (`sw_jam` on GPIO 18) to the active position.
3. **Observation:** Within 1 second, the node measures current > 1600 mA (stalled motor).
4. The safety interlock immediately shuts off the relay to prevent motor burnout, logs:
   `>>> [SAFETY INTERLOCK] Current > 160% rated! Jam detected. Halting pump.`
5. The OLED updates to `FAULT: Jammed Pump`.

### Scenario 4: Blocked Drip Line (Mud / Clog Drill)
1. Run the pump first — either via **Scenario 1** (fail-safe, no typing) or **Scenario 2** (gateway ACK paste).
2. While the pump is running, flip **Fault Switch 2** (`sw_block` on GPIO 19) to the active position.
3. **Observation:** The pump runs, but no flow pulses are detected.
4. Exactly at elapsed $t = 15\,\text{s}$, the node detects zero flow and halts the pump:
   `>>> [SAFETY INTERLOCK] Zero flow measured after 15s! Line blocked. Halting pump.`
5. The next uplink packet reports `irr_s: 15, flow_mL: 0`, and the dashboard triggers the `LINE_BLOCKED` alert instructing the farmer to flush the emitters.

### Scenario 5: Rodent-Chewed Sensor Cable (Electrical Failure Drill)
1. Flip **Fault Switch 3** (`sw_cut` on GPIO 23) to the active position.
2. Press the yellow **Wake** button.
3. **Observation:** Soil ADC reads 4095 (maximum saturated value). The node itself recognises raw 4095 as invalid (outside its validity window) and shows `SENSOR FAULT` on the OLED.
4. **The node refuses to water while the reading is untrustworthy** — no local fail-safe watering, and any `ACK,...` command pasted into the serial console is ignored too (the operator manual says hand-water instead).
5. The uplink still reports `soil_raw 4095`; the backend's own health check flags `SENSOR_FAULT` (a second, independent layer), disables automated irrigation for that bed, and shows the alert.
6. Flip the switch back off and send a healthy reading to clear the fault, then normal operation resumes.

### Scenario 6: Stale/No-ACK Rejection (requires the Serial input box)
1. Press **Wake** and read the printed sequence number on the `UPLINK PACKET: …` line (e.g. `7`).
2. During the next RX window, paste an `ACK,N1,<DIFFERENT-seq>,20` (e.g. `ACK,N1,3,20`).
3. **Observation:** the node prints the received line, then `[RX-WINDOW] Closed. No gateway ACK received.` and **never** starts the pump — a stale or replayed command is silently rejected. This is the security posture: only a command that names the current sequence number is accepted.

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
