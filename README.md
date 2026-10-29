# 🌾 Smart Farm Prototype: IoT Hardware Simulation & AI Operations

> **Team & Review Guide:** A complete, working prototype of a smart-irrigation system engineered for the real world—addressing power loss, severed cables, jammed pumps, and zero internet connectivity.

---

## 📖 Table of Contents
1. [The 30-Second Summary: What Does This Project Actually Do?](#-the-30-second-summary-what-does-this-project-actually-do)
2. [How the Whole System Works (The Big Picture)](#-how-the-whole-system-works-the-big-picture)
3. [Quick Start: Run the Simulation in Your Web Browser (Wokwi Online)](#-quick-start-run-the-simulation-in-your-web-browser-wokwi-online)
4. [Interactive Review Checklist (What to Click & What Happens)](#-interactive-review-checklist-what-to-click--what-happens)
5. [📦 The 3D Enclosure: TinkerCad & Physical Case Explained](#-the-3d-enclosure-tinkercad--physical-case-explained)
6. [🖥️ The Operations Dashboard (Optional Local Web App)](#-the-operations-dashboard-optional-local-web-app)
7. [🎓 Presentation Cheat Sheet: What to Say During Your Review](#-presentation-cheat-sheet-what-to-say-during-your-review)

---

## 💡 The 30-Second Summary: What Does This Project Actually Do?

Most "smart irrigation" systems in the market fail because of three real-world farm problems:
1. **Dumb Timers:** Sprinklers water on a clock (e.g. 7:00 AM every day) even if it rained all night or if soil is already saturated, rotting plant roots and wasting water.
2. **Silent Mechanical Failures:** Pumps get clogged with sand, drip lines get sliced by farm tools, and rodents chew cables. The farmer thinks plants are being watered, but nothing is coming out until the crop dies.
3. **No Wi-Fi in the Field:** Farm fields don't have Wi-Fi 500 meters away from the house.

### Our Solution
* **Smart Sensing:** An outdoor computer node (ESP32) measures actual soil moisture, battery voltage, temperature, and humidity.
* **Long-Range Radio (LoRa):** Sends data up to 5 km with **zero Wi-Fi or cellular needed**, sleeping 99% of the time so two small batteries last **~2 years**.
* **Agronomic AI:** The system calculates exact water needs based on soil type (clay vs sand) and crop growth stage.
* **Self-Defense Hardware:** If sand jams the pump or a pipe clogs, **the node kills the pump automatically in under 1 second** so the motor doesn't catch fire, and sends an alert to the farmer's dashboard.

---

## 🔄 How the Whole System Works (The Big Picture)

```
[ OUT IN THE CROP BED ]
  1. Soil Probe reads moisture in the dirt.
  2. ESP32 Node wakes up every 15 min, reads sensors, and sleeps to save power.
  3. Transmits an encrypted packet over long-range radio (LoRa, 868 MHz).
            │
            │ Long-Range Radio Signal (2 - 5 km, No Internet Required)
            ▼
[ AT THE FARMHOUSE / BASE STATION ]
  4. Base Station Laptop / Raspberry Pi receives the packet.
  5. The AI Decision Engine checks:
     • Crop: "Tomato in Flowering Stage" (needs moisture between 20% and 35%)
     • Soil: "Clay Loam" (absorbs water slowly)
     • Prediction: "Soil is at 14%—needs 20 seconds of water right now."
  6. Sends a radio command back to the field: "ACK: Pump ON for 20s".
            │
            ▼
[ BACK IN THE CROP BED ]
  7. The Relay clicks ON -> The Water Pump spins -> Blue LED lights up.
  8. A flow meter counts water drops; an ammeter checks electrical current.
  9. If anything jams or leaks, safety interlocks shut down the pump immediately!
```

---

## ⚡ Quick Start: Run the Simulation in Your Web Browser (Wokwi Online)

Your teammates do **not** need to install Python, Arduino, or any software. The entire hardware simulation runs in Google Chrome, Edge, Firefox, or Safari via **Wokwi Online**.

```
                +-------------------------------------------------------+
                |                   WOKWI ONLINE (BROWSER)              |
                |                                                       |
                |   [OLED Screen]       [ESP32 Microcontroller]         |
                |   • Soil VWC %        • Safety Interlocks             |
                |   • Battery Gauge     • Deep Sleep Cycle              |
                |                                                       |
                |   [SOLDERLESS BREADBOARD]                             |
                |   • Yellow Button  ---> Manual Wake & Send            |
                |   • Green Button   ---> Water Flow Meter Pulse        |
                |   • Blue LED       ---> Pump Motor Active             |
                |   • 3 Slide Switches -> Mechanical Fault Drills       |
                |                                                       |
                |   [KNOBS]                                             |
                |   • Soil Moisture Dial (Dry <-> Wet)                  |
                |   • Battery Level Dial (Flat <-> Full)                |
                +-------------------------------------------------------+
```

### 3-Step Setup on Wokwi Online (Takes ~2 Minutes)

#### Step 1: Open Wokwi in your browser
Go to: **[https://wokwi.com/projects/new/esp32](https://wokwi.com/projects/new/esp32)** (free, no sign-in required).

#### Step 2: Paste the 3 project files
In the Wokwi web editor, you will see tabs above the code area:

1. **Paste Firmware (`sketch.ino`):**
   * Open [`farm_ai/wokwi/sketch.ino`](farm_ai/wokwi/sketch.ino) in Notepad, TextEdit, or VS Code.
   * Select All (`Ctrl+A` or `Cmd+A`), Copy.
   * In Wokwi, click the **`sketch.ino`** tab, delete everything, and Paste.

2. **Paste Circuit Diagram (`diagram.json`):**
   * Open [`diagram.json`](diagram.json).
   * Select All, Copy.
   * In Wokwi, click the **`diagram.json`** tab, delete everything, and Paste.
   * *(You will immediately see the ESP32, breadboard, OLED screen, LED, switches, and knobs appear cleanly!)*

3. **Add the 4 Libraries:**
   * In Wokwi, click the **Library Manager** tab (or the little books icon on the left).
   * Add these 4 libraries:
     ```text
     Adafruit SSD1306
     Adafruit GFX Library
     DHT sensor library
     Adafruit Unified Sensor
     ```

#### Step 3: Click the Green Play Button (▶)
* Click the round green **Play** button at the top of the canvas.
* **The hardware starts immediately!**
  * The **ESP32 boots up** and outputs diagnostic logs to the Serial Monitor.
  * The **OLED screen illuminates**, displaying Bed A's live soil moisture bar, battery gauge, temperature, and humidity.

---

## 🎮 Interactive Review Checklist (What to Click & What Happens)

Use this table during presentations to demonstrate the system's intelligence:

| Test Drill | What You Click in Wokwi | What Happens on the Screen (OLED & LED) |
|---|---|---|
| **1. Change Soil Moisture** | Turn the **Soil Moisture dial** (bottom-left knob). | The OLED screen shows the moisture percentage update in real-time (**Dry < 15%**, **Optimal 20–35%**, **Wet > 40%**). |
| **2. Manual Wake / Send** | Click the yellow **Wake / Send** button on the breadboard. | The node immediately wakes up, samples the sensors, and sends an uplink packet over the serial monitor. |
| **3. Trigger Watering** | In the Serial Monitor input box at the bottom, type:<br>`ACK,N1,1,20`<br>and press Enter. | • **Relay clicks ON** and the **Blue LED illuminates**.<br>• OLED shows `>> PUMP ACTIVE <<` with a live countdown timer.<br>• Water flow meter counts liters delivered. |
| **4. Drill: Jammed Pump** | Flip **Switch 1** (`Fault: Jam Pump`) to the right, then trigger a watering run. | **Safety Interlock activates in <1 second!**<br>Motor current exceeds 1600 mA (stalled pump). The system cuts the relay instantly to prevent the motor from burning out. OLED flags `FAULT: Jammed Pump`. |
| **5. Drill: Blocked Pipe** | Flip **Switch 2** (`Fault: Block Line`) to the right, then trigger a watering run. | **Dry-Run Interlock activates!**<br>Pump is running but 0 water flow is measured. After 15 seconds, power is killed. OLED flags `FAULT: Zero Flow`. |
| **6. Drill: Cut Sensor Wire** | Flip **Switch 3** (`Fault: Cut Sensor`) to the right. | **Agronomic Protection activates!**<br>Sensor reads 4095 (broken wire). Automatic irrigation is locked out so crops aren't flooded. OLED flags `FAULT: Broken Probe`. |

---

## 📦 The 3D Enclosure: TinkerCad & Physical Case Explained

If a teammate or teacher asks about **TinkerCad** or the **Enclosure**, here is what it is:

### The "Lunchbox" Analogy
Think of a smartphone:
* **The Circuit (Wokwi):** Is the phone's computer chip and screen.
* **The Enclosure (TinkerCad / STL):** Is the rugged waterproof OtterBox plastic case you put it in so mud and rain don't destroy it on a farm.

```
+-----------------------------------------------------------------------------+
|                           ENCLOSURE INTERIOR LAYOUT                         |
|                                                                             |
|   +-----------------------+     +--------------------+   [SMA Antenna]      |
|   | 2x 18650 Battery Pack |     | 1-Ch Relay Module  |      (Side)          |
|   | (75mm x 40mm x 20mm)  |     | (50mm x 26mm x 18) |        O             |
|   +-----------------------+     +--------------------+                      |
|                                                                             |
|   +--------------------------------------------------+                      |
|   |         ESP32 DevKit V4 Carrier Board            |                      |
|   |         (51mm x 28mm x 12mm)                     |                      |
|   +--------------------------------------------------+                      |
|                                                                             |
|            [Gland 1]             [Gland 2]            [Gland 3]             |
|          Soil Probe In          Flow Pulse In        12V Pump Out           |
+-----------------------------------------------------------------------------+
```

### What are the Features in the 3D Model?
* **The 4 Corner Pillars:** Screw posts. When you close the lid, you screw 4 bolts into these pillars to clamp the box watertight.
* **The 4 Little Floor Bumps / Pegs:** Mounting pedestals (standoffs). The green ESP32 board sits on these pegs so it is elevated 6 mm off the floor and doesn't rattle or touch condensation.
* **The 3 Holes on the Bottom Wall:** Waterproof cable entry ports (PG7 cable glands). Wires poke out to the soil probe, water pipe, and pump. They are on the **bottom wall** so gravity pulls rainwater down and away.
* **The Rectangular Window on the Lid:** A clear acrylic window for the OLED screen so anyone walking past can read moisture and battery levels without opening the box.

### Dimensions for TinkerCad
* **Outer Size:** $130\text{ mm Long} \times 90\text{ mm Wide} \times 45\text{ mm Deep}$ (about the size of a small sandwich box).
* **Wall Thickness:** $3.0\text{ mm}$ (heavy-duty outdoor plastic).

### How to Open It in TinkerCad
1. Go to **[tinkercad.com](https://www.tinkercad.com)** and create a new 3D design.
2. Click **Import** (top right).
3. Select [`farm_ai/enclosure/enclosure_base.stl`](farm_ai/enclosure/enclosure_base.stl) and [`farm_ai/enclosure/enclosure_lid.stl`](farm_ai/enclosure/enclosure_lid.stl).
4. Both 3D parts will appear on your canvas at exact 1:1 real-world scale!

---

## 🖥️ The Operations Dashboard (Optional Local Web App)

If your teammates or reviewers want to see the farmer's web dashboard (showing live soil moisture graphs, weather forecasts, and AI recommendations):

### Windows (1-Click)
* Double-click **[`run_dashboard.bat`](run_dashboard.bat)**.
* It automatically starts the local engine and opens `http://localhost:5000` in your web browser.

### Mac / Linux (1-Click)
* In your terminal, run:
  ```bash
  ./run_dashboard.sh
  ```
* Your browser will automatically open `http://localhost:5000`.

---

## 🎓 Presentation Cheat Sheet: What to Say During Your Review

If an evaluator asks you these questions, here are your answers:

1. **"Why not just use Wi-Fi or Cellular?"**  
   *Answer:* *"Wi-Fi doesn't reach hundreds of meters into crop fields, and cellular SIM cards require monthly subscriptions and drain batteries quickly. We used 868 MHz LoRa, which covers 2 to 5 km with zero subscription cost and allows our node to sleep 99% of the time, lasting up to 2 years on two 18650 cells."*

2. **"What happens if the pump gets clogged with sand or mud?"**  
   *Answer:* *"Our firmware continuously samples pump current and flow rate. If the motor jams, current exceeds 160% of rated value, and our safety interlock shuts off the relay in under 1 second. If emitters clog, it detects 0 flow and shuts down after 15 seconds to prevent dry-running."*

3. **"How does the system survive outdoor weather?"**  
   *Answer:* *"The electronics are housed in an IP65 weatherproof enclosure with downward-facing cable glands and drip loops to prevent water ingress, an internal desiccant pack for condensation control, and an acrylic inspection window for the OLED display. Our CAD models and 3D STL files are documented in our repository."*

---

## 📂 Repository File Index

```
smart_farm_prototype/
├── README.md               # Master team guide & presentation overview
├── diagram.json            # Wokwi breadboard schematic
├── libraries.txt           # Arduino library dependencies for Wokwi
├── wokwi.toml              # VS Code Wokwi configuration
├── run_dashboard.bat       # 1-click dashboard launcher for Windows
├── run_dashboard.sh        # 1-click dashboard launcher for Mac/Linux
│
└── farm_ai/
    ├── enclosure/          # 3D Enclosure CAD Suite
    │   ├── enclosure_base.stl    # 3D Base model (TinkerCad ready)
    │   ├── enclosure_lid.stl     # 3D Lid model with OLED window
    │   ├── TINKERCAD_GUIDE.md    # Step-by-step TinkerCad manual
    │   └── generate_enclosure.py # Python parametric STL generator
    │
    ├── wokwi/              # Embedded Simulation Suite
    │   ├── sketch.ino      # ESP32 C++ firmware with safety interlocks
    │   ├── diagram.json    # Full breadboard schematic
    │   ├── wokwi_gateway.py# Serial-to-dashboard gateway bridge
    │   └── test_uplink.py  # Automated integration test suite
    │
    ├── server.py           # Flask REST API & Offline PWA Dashboard backend
    ├── run_demo.py         # Multi-bed farm simulation with live failures
    ├── requirements.txt    # Python dependencies
    ├── static/             # Offline PWA web UI (HTML, CSS, JS, Service Worker)
    └── farm/               # Agronomic decision engine, ML drying model, SQLite
```
