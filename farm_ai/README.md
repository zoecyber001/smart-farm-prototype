# Smart Farm Prototype: LoRa + Data/AI, built for field failures

A working prototype of a smart-irrigation system designed around what actually breaks on farms:
**power and network, destroyed hardware, useless raw data, and silent mechanical failure.**

```
 soil sensor + flow sensor + pump current      LoRa (868 MHz)       Raspberry Pi / laptop (offline)
 [ field node: ESP32, deep sleep, battery ] ~~~~~~~~~~~~~~~~~~~~> [ gateway + decision engine + dashboard ]
        ^                                      <~~ watering command in the radio reply         |
        +-- local fail-safe if the gateway is silent                                  farmer's phone/browser (LAN)
```

## How each real-world problem is handled

| Problem from the farm | What this prototype does |
|---|---|
| **WiFi/power don't reach the field** | LoRa radio, ESP32 deep sleep (wakes every 15 min), battery + optional small solar panel. Estimated ~2 years on two 18650 cells (assumptions in `docs/FIELD_GUIDE.md`; **measure it**). Gateway and dashboard work with **no internet**. The dashboard also caches itself and the last server state (service worker), so it opens and reads during network drops, and can be installed on a phone home screen (PWA manifest). |
| **Hardware gets destroyed** | Electronics stay in an IP65+ box above ground; only the probe goes in the soil, cable in armoured conduit. Specs, parts and a bench test plan are in `docs/FIELD_GUIDE.md`. |
| **Raw numbers mean nothing to a farmer** | The engine knows each bed's **soil type** (what it can hold), **crop and growth stage** (what the plant needs now) and the **temperature**. It outputs an instruction: *"Water Bed A (Tomato) for 22 min now"*, with the reason in crop terms. Slow clay soil is split into short cycles. |
| **Pump/drip line fails silently** | Every run reports commanded seconds, **measured flow** and **pump current**. Detects: dead pump, jammed pump, blocked line, clogging filter, burst pipe, "water delivered but soil didn't respond", frozen/cut sensor, flat battery, offline node, weak link. Automation stops on pump faults and the farmer is told to hand-water and what to check. |

The "AI": a gradient-boosted model learns each bed's **drying rate** (from weather, time of day, soil, trend) and forecasts
**hours until the bed needs water**, so the farmer gets a plan, not a late alarm. On beds it never saw (simulated), it cuts the
error by ~80% versus a simple average (`data/drying_model_metrics.json`). Decisions themselves are transparent rules, on purpose.

## Run it (laptop, no hardware)
```bash
pip install -r requirements.txt
python run_demo.py            # open http://localhost:5000 : a simulated farm with failures already happening
python -m unittest tests.test_farm -v     # 31 tests
python -m unittest discover -s tests -v   # 53 tests (adds firmware-gate & uplink-contract regressions)
```
On the first page load the browser installs the offline service worker (scope `/`, served from `/service-worker.js`). From then on, with no network the dashboard still opens and shows the last state it saw, and can be added to a phone home screen via the browser's "Add to Home screen" / install prompt.
```
The simulation injects a **blocked drip line (Bed B)**, a **dead pump (Bed C)**, a **leaking enclosure draining the battery (Bed D)**
and a **cut sensor cable (Bed E)**. Bed A is healthy as the control. Edit `config/farm.json` for your own beds and `config/crops.json` for crops.

## Hardware Simulation (Wokwi) for Technical & Client Reviews
A complete ESP32 Wokwi hardware simulation suite is available in `wokwi/` (`wokwi/diagram.json` and `wokwi/sketch.ino`).
It models the full physical node:
- **Interactive Sensors:** Capacitive Soil Probe potentiometer (ADC GPIO 34, gated by GPIO 25), Battery divider (GPIO 35), and DHT22 Temp/Humidity (GPIO 27).
- **Actuators:** 12V Submersible Pump Relay + High-visibility Blue LED indicator (GPIO 26) with Hall flow meter pulse generator (GPIO 33).
- **Diagnostics & Display:** I2C 128x64 OLED display showing real-time moisture %, battery voltage, and pump status.
- **Review Fault Injection:** Three live slide switches to simulate **Jammed Pump** (GPIO 18), **Blocked Drip Line** (GPIO 19), and **Cut Sensor Wire** (GPIO 23) during demonstrations.
- **Live Bridge:** `wokwi/wokwi_gateway.py` bridges Wokwi serial telemetry straight to the local `server.py` dashboard.
See [`wokwi/README.md`](wokwi/README.md) for full setup instructions and review demonstration drills.

## What is and isn't proven
- **Tested (simulation):** advice logic, all fault detectors, automation halting on pump faults, fault persistence until a healthy
  test run, offline detection, API, dashboard, and the swap-in seams (alternative advice strategy, alternative storage,
  activity feed). 53 automated tests, including regressions for the invalid-reading
  sensor gate (raw 4095 / 0 never waters, even with a silent gateway) and the
  CSV/JSON uplink contract.
- **NOT tested:** `firmware/` (not compiled or run on real boards), `gateway/lora_gateway.py` (no real radio), real sensors, real enclosures.
  Treat them as a careful first draft for your lab trial.
- **Crop numbers** (trigger %, root depth, stages) are generic starting values. Confirm with a local agronomist. The ML model starts trained on
  simulated drying; **retrain on the farm's own logs** after 2 to 4 weeks (`python -c "from farm import ml; print(ml.train())"` after swapping in real data).

## Suggested lab/field trial
1. Bench: one node + gateway on a table, watch packets arrive in the dashboard. 2. Waterproof test (see field guide). 3. One real bed for 2 weeks:
**advice-only mode** (`auto_irrigate: false`), compare advice with what the farmer would do and with a finger test. 4. Deliberately cause each fault
(kink the hose, unplug the pump) and confirm the alert. 5. Only then switch the bed to auto.

## Layout
```
run_demo.py          simulated farm + dashboard          server.py   Flask API + dashboard (LAN, offline)
farm/
  ports.py           the seams: Repository, HealthChecker, AdviceStrategy, ForecastModel
  config_store.py    FarmConfig (beds, soils, crops)     units.py   pure unit conversions
  storage.py         SQLiteRepository (swap for any store)
  ingest.py          packet -> measurement -> storage    evaluation.py   history + health + forecast + strategy
  decisioning.py     the downlink policy                 dashboard.py    view builders (+ activity feed)
  advisory.py        ThresholdAdvisor (swap for any watering policy)   health.py  HardwareHealthChecker
  forecast.py        DryingForecastModel (hours-until-trigger seam)
  ml.py              training + metrics for the drying-rate model   simulator.py  physics + fault injection
  system.py          FarmSystem: composes all ports; engine.py/core.py/advisor.py are compat shims
config/ farm.json (beds, soil, crop)  crops.json  soils.json
static/  dashboard (vanilla ES5, no CDN): index.html, style.css, js/ api.js state.js charts.js views.js main.js
firmware/field_node/field_node.ino   ESP32 node        firmware/lora_bridge/lora_bridge.ino   gateway radio
gateway/lora_gateway.py   serial radio -> server       docs/FIELD_GUIDE.md   hardware, enclosures, tests, maintenance
```
Packet: `node,seq,soil_raw,temp_x10,hum,batt_mV,irr_s,flow_mL,pump_mA`. Reply: `ACK,node,seq,run_s`.
Real gateway: `POST /api/uplink` with the decoded packet as JSON; the response `downlink.run_s` goes back to the node inside its ~1.5 s receive window.
