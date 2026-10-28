# Smart Farm Prototype: IoT Hardware Simulation & AI Operations

> **Review & Demo Bundle:** This package contains the complete working prototype of the **Smart Farm Field Node** and **Offline Operations Dashboard**, ready for technical reviews, client demonstrations, and team evaluations.

---

## ⚡ Quick Start for Teammates (Wokwi Online — No Installation Required)

Your teammates do **not** need to install Python, Arduino, or any software. The entire embedded hardware simulation runs directly in Google Chrome, Microsoft Edge, Safari, or Firefox via **Wokwi Online**.

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
1. Go to: **[https://wokwi.com/projects/new/esp32](https://wokwi.com/projects/new/esp32)** (free, no sign-in required).

#### Step 2: Paste the 3 project files
In the Wokwi editor, you will see tabs above the code area:

1. **Paste Firmware (`sketch.ino`):**
   * Open the file `farm_ai/wokwi/sketch.ino` in any text editor (Notepad, TextEdit, or VS Code).
   * Copy all text (`Ctrl+A` or `Cmd+A`, then `Copy`).
   * In Wokwi, click the **`sketch.ino`** tab, select all, delete, and paste.

2. **Paste Circuit Diagram (`diagram.json`):**
   * Open the file `diagram.json` (or `farm_ai/wokwi/diagram.json`).
   * Copy all text.
   * In Wokwi, click the **`diagram.json`** tab, select all, delete, and paste.
   * *(You will immediately see the ESP32, breadboard, OLED, buttons, switches, and knobs appear on the canvas!)*

3. **Add the 4 Libraries:**
   * In Wokwi, click the **Library Manager** tab (or the little library/books icon on the left).
   * Click **Add a new library** (or edit `libraries.txt`) and add these 4 items:
     ```text
     Adafruit SSD1306
     Adafruit GFX Library
     DHT sensor library
     Adafruit Unified Sensor
     ```

#### Step 3: Click the Green Play Button (▶)
* Click the round green **Play** button at the top of the canvas.
* **That's it!** The simulated hardware will boot:
  * The **ESP32 boots up** and prints diagnostic logs to the Serial Monitor.
  * The **OLED screen illuminates**, displaying the Bed A soil moisture bar, battery voltage, temperature, and humidity.

---

## 🎮 Interactive Review Checklist (What to Test)

Hand this checklist to reviewers or teammates during demonstrations:

| Test Drill | What You Do in Wokwi | What the Hardware Does (Look at OLED & LED) |
|---|---|---|
| **1. Adjust Soil Moisture** | Turn the **Soil Moisture dial** (bottom left knob) left or right. | The OLED displays the real-time VWC % update (Dry < 15%, Optimal 20–35%, Wet > 40%). |
| **2. Manual Telemetry Send** | Click the yellow **Wake / Send** button on the breadboard. | The node wakes up, takes immediate sensor readings, and outputs an uplink packet to the Serial Monitor. |
| **3. Trigger Irrigation** | In the Wokwi Serial Monitor input box, type:<br>`ACK,N1,1,20`<br>and press Enter. | • **Relay clicks ON** and the **Blue LED lights up**.<br>• OLED shows `>> PUMP ACTIVE <<` with a live countdown timer.<br>• Simulated water flows at ~4.0 Liters/min. |
| **4. Drill: Jammed Pump** | Flip **Fault Switch 1** (labeled `Fault: Jam Pump`) to the right, then trigger a watering run. | **Safety Interlock halts pump in <1 sec!**<br>Current spikes >1600 mA (stalled motor). The system kills the relay to protect the motor from burning out. OLED shows `FAULT: Jammed Pump`. |
| **5. Drill: Blocked Pipe** | Flip **Fault Switch 2** (`Fault: Block Line`) to the right, then trigger a watering run. | **Dry-Run Interlock activates!**<br>The flow sensor detects 0 pulses despite the pump being on. After 15 seconds, the pump shuts off. OLED shows `FAULT: Zero Flow`. |
| **6. Drill: Cut Probe Wire** | Flip **Fault Switch 3** (`Fault: Cut Sensor`) to the right. | **Agronomic Protection activates!**<br>ADC saturates to 4095 (open-circuit broken wire). Automatic watering is inhibited so crops aren't over-watered. OLED shows `FAULT: Broken Probe`. |

---

## 🖥️ Running the Operations Dashboard (Optional)

If your teammates want to see the **Farmer's Web Dashboard** (the offline-capable PWA with soil moisture graphs, weather forecasts, and automated AI irrigation recommendations):

### Windows (1-Click)
* Double-click **`run_dashboard.bat`**.
* It automatically starts the server and opens `http://localhost:5000` in your browser.

### Mac / Linux (1-Click)
* In your terminal, run:
  ```bash
  ./run_dashboard.sh
  ```
* Your browser will automatically open to `http://localhost:5000`.

---

## 📂 Project Structure

```
smart_farm_prototype/
├── README.md               # This guide (overview & quick start)
├── diagram.json            # Wokwi breadboard schematic (drag & drop into Wokwi)
├── libraries.txt           # Arduino library dependencies for Wokwi
├── wokwi.toml              # VS Code Wokwi extension configuration
├── run_dashboard.bat       # 1-click dashboard launcher for Windows
├── run_dashboard.sh        # 1-click dashboard launcher for Mac/Linux
│
└── farm_ai/
    ├── wokwi/
    │   ├── diagram.json    # Master hardware schematic
    │   ├── sketch.ino      # ESP32 C++ firmware (safety interlocks, OLED UI)
    │   ├── libraries.txt   # Library list
    │   ├── wokwi_gateway.py# Live serial-to-dashboard bridge
    │   └── test_uplink.py  # Automated integration test suite
    │
    ├── server.py           # Flask REST API & Offline PWA Dashboard backend
    ├── run_demo.py         # Multi-bed farm simulation with live failures
    ├── requirements.txt    # Python dependencies (Flask, NumPy, Scikit-learn)
    ├── static/             # Offline PWA web UI (HTML, CSS, JS, Service Worker)
    └── farm/               # Agronomic decision engine, ML drying model, SQLite
```

---

## 🔬 System Specifications

* **Target MCU:** Espressif ESP32 DevKit V4 (`board-esp32-devkit-c-v4`)
* **Display:** 128x64 Monochrome I2C OLED (SSD1306, Address `0x3C`)
* **Soil Sensor:** Capacitive frequency probe, gated via GPIO 25 (prevents galvanic soil corrosion)
* **Battery Sensing:** 100kΩ/100kΩ voltage divider (2:1 attenuation) for 3.7V Li-ion cells
* **Actuation:** 12V 800mA submersible pump relay with status LED on GPIO 26
* **Telemetry Protocol:** Bidirectional compact CSV LoRa frames (Uplink & Downlink ACK)
* **Agronomic AI:** Gradient-boosted drying forecaster predicting hours until moisture threshold
