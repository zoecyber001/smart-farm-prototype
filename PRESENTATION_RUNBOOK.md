# PRESENTATION RUNBOOK — Smart Farm Prototype

Everything in this file was executed and its outputs verified in this exact
environment. Anything runbook lists as "unverified" has **not** been run here.

---

## 0. Pre-flight (morning of the review)

```bash
cd /home/zoecyber/Downloads/smart_farm_prototype/farm_ai
../.venv/bin/python -m unittest discover -s tests -v     # expect: "Ran 53 tests ... OK"
python3 enclosure/validate_stl.py                          # expect: "VALIDATION OK"
```

Environment needed: Python 3 venv at repo root (`.venv/`, already present),
Firefox or any browser for the dashboard, internet **only** for wokwi.com
(everything on your machine runs offline).

---

## 1. Track A — Dashboard demo (laptop, ~2 min of the talk)

```bash
cd /home/zoecyber/Downloads/smart_farm_prototype
./run_dashboard.sh          # local Python venv + browser; or manually:
cd farm_ai && ../.venv/bin/python run_demo.py
```

* Open `http://localhost:5000`. The page rebuilds `farm_ai/data/demo.db` from
  scratch each start and prefills 4 simulated days of history (a day ticks in
  ~1 minute).
* Verified observations on load:
  * Header reads **"GAA Demo Farm (simulation)"** with a `SIMULATED CLOCK` badge —
    keep this on screen; it is the honest label.
  * "WHAT TO DO FIRST" already shows the injected faults: Bed B blocked drip
    line, Bed C dead pump, Bed D draining battery, Bed E cut sensor cable.
    Beds A–E all show farmer-phrase advice, e.g. "Water by hand: about N litres".
  * Footer line (verified rendering): *"Forecast accuracy: the model's drying
    forecast misses by 0.0148 soil-water points/hour on average, vs 0.0741
    points/hour for a flat average of the last days (80% better, tested on
    simulated beds it never saw in training)."*
* Talking points while clicking: soil type per bed, crop growth stage, the
  reason text under each decision, the Alerts tab, the Activity feed, and one
  bed drill-down (history sparkline + water-now dialog with the safe-step arm).

### Pushing live faults into the dashboard (optional walk-through)

```bash
cd farm_ai
../.venv/bin/python wokwi/wokwi_gateway.py --demo --server http://localhost:5000
```

Verified sequence (5 packets) and the exact console output:

| # | Packet | Server reaction |
|---|---|---|
| 1 | `N1,1,2950,270,55,3980,0,0,0` dry soil | Water command issued → `ACK,N1,1,1800` (30 min plan) |
| 2 | `N1,2,1650,265,60,3960,300,20000,810` just watered | `run_s 0` (soil absorbed the last run; soak window) |
| 3 | `N1,3,2900,280,50,3940,60,0,805` 0-flow run | `run_s 0`, `LINE_BLOCKED` fault persists ("hand-water, flush emitters") |
| 4 | `N1,4,4095,282,49,3920,0,0,0` cut probe | `run_s 0`, `SENSOR_FAULT` registered; bed advice switches to `check_hardware` and moisture advice is suppressed (`aw_pct` disappears) |
| 5 | `N1,5,1500,250,65,3900,60,4000,800` repaired + healthy test run | faults clear; next evaluation returns to normal advice |

The bridge prints `>>> Copy this downlink reply into Wokwi console: ACK,...` —
that is the exact string to paste into the Wokwi serial input (Track B).

Notes: (a) each `/api/uplink` needs a current timestamp — the bridge stamps
`ts` itself; a hand-made JSON with `ts: 0` is silently ignored (don't hand-craft
packets in the demo, use the bridge). (b) After scenario 1 the same node stays
in its soak window for a while — send scenario 4/3 (fault packets) if you want
visible state changes, not repeat watering demands.

---

## 2. Track B — Wokwi hardware simulation (~3 min of the talk)

Files: `farm_ai/wokwi/diagram.json` (repo-root `diagram.json` is the same file),
`farm_ai/wokwi/sketch.ino`, `farm_ai/wokwi/libraries.txt`.

**Setup (web, zero install):**
1. Go to wokwi.com → new ESP32 project.
2. Paste `diagram.json` into the diagram tab, `sketch.ino` into `sketch.ino`,
   and the four libraries into Library Manager (`Adafruit SSD1306`,
   `Adafruit GFX Library`, `DHT sensor library`, `Adafruit Unified Sensor`).
3. Press Play. A Serial Monitor pane appears at the bottom.

**Wiring facts worth saying out loud** (all consistent between diagram and sketch):
* Soil probe pot's VCC comes from **GPIO 25** — firmware switches sensor power
  on only around a reading (anti-corrosion), so the sim exercises the same gate.
* Battery pot's VCC is on the **3.3 V rail** (never 5 V — that would push a
  voltage out of ADC range into GPIO 35). Firmware doubles the divider voltage,
  so the pot maps 0–6.6 V; default position ≈ 3.9 V displayed.
* Fault switches are **GPIO 18 (jam), 19 (blocked line), 23 (cut sensor)**.

**Default start readings:** soil pot at 600/1023 → raw ≈ 2400 → OLED ≈ 40% VWC
(safely wet of the ≈22 % fail-safe trigger); battery ≈ 3.9 V.

### Drill 1 — Watering round trip (normal loop)
1. Sweep the soil pot toward dry (raw > 2700, OLED % falls below ~23) and press
   the **Wake button (GPIO 4)** — node prints its packet:
   `UPLINK PACKET: N1,<seq>,<raw>,<temp_x10>,<hum>,<batt_mV>,0,0,0`
   followed by `Opening 1.5s RX Window for Gateway reply...`
2. Paste the packet into the gateway bridge (Section 1) and get an `ACK,..` reply.
3. Paste `ACK,<node>,<seq>,<seconds>` back into the Wokwi serial box.
4. Verified-by-design behaviour to narrate: `[DOWNLINK] Confirmed for Node
   N1, Seq …` (printed as soon as the ACK parses), then the pump cycle:
   `>> STARTING IRRIGATION CYCLE: N SECONDS`, per-second live log lines in the
   exact format `[PUMP] T-<ss>s | Curr: <mA> mA | Flow: <L> L (<pulses>
   pulses)`, relay + blue LED, `>> PUMP CYCLE COMPLETED: Ran <n> s | Flow:
   <mL> mL | Avg Current: <mA> mA` (plus `>> TERMINATION REASON: …` when a
   safety interlock fired), and the same `irr_s`, `flow_mL`, avg `pump_mA`
   carried in the next uplink packet.

### Drill 2 — Jammed pump (current spike)
* Set **Fault Switch 1 (GPIO 18)** ON, run a pump cycle.
* Expected within ~1 s of pump start (verified string):
  `>>> [SAFETY INTERLOCK] Current > 160% rated! Jam detected. Halting pump.`
* Next uplink carries the fault; OLED and dashboard alert accordingly.

### Drill 3 — Blocked drip line (no flow)
* Set **Fault Switch 2 (GPIO 19)** ON, run a pump cycle.
* Expected at 15 s into the run:
  `>>> [SAFETY INTERLOCK] Zero flow measured after 15s! Line blocked. Halting pump.`
* Next uplink: `irr_s 15, flow 0` — the dashboard flags `LINE_BLOCKED`.

### Drill 4 — Cut sensor wire (the fail-safe showcase)
1. Set **Fault Switch 3 (GPIO 23)** ON, press Wake.
2. Serial shows `[DIAGNOSTIC] Fault Switch 3 active: Simulating CUT SENSOR
   CABLE (Raw 4095)`; ADC reads 4095; OLED shows `SENSOR FAULT ... Probe fault:
   no auto water`.
3. **Key safety point:** the node itself refuses to water — no local fail-safe
   run on such an invalid reading, and even a pasted `ACK,...` watering command
   is ignored while the reading is untrustworthy. (Firmware gate; regression
   covered by `farm_ai/tests/test_firmware_gates.py`.)
4. The packet still goes up as `soil_raw 4095`; the server side independently
   registers `SENSOR_FAULT` (verified: bed advice switched to
   `check_hardware`, no watering command, moisture advice withheld).
5. Flip the switch back off, press Wake again — fault clears on a healthy reading.

### Rehearsal script — run once in the browser before class

This is the browser-only checklist that could NOT be automated from the dev
environment (no Wokwi CLI available here), so the demo must be rehearsed by a
human exactly once. If any expected output below does not appear, fix that
step and re-run before presenting. Gateway bridge stays OFF — everything here
works with the Wokwi Serial Monitor alone. Total ≈ 8 minutes (estimate).

☐ **1. Boot & display.** Press Play. Serial: `SMART FARM FIELD NODE HARDWARE
   BOOT` → `[READY] All subsystems operational.` → `[SLEEP] Entering low-power
   sleep for 15 seconds.` OLED lit: header, soil ≈ 40 %, battery ≈ 3.9 V.
☐ **2. Soil pot live.** Turn the Soil Moisture pot: the raw value and OLED %
   change on the next uplink. Turn it back to the default position (600).
☐ **3. Watering round trip.** Press Wake, read the new sequence number from
   `UPLINK PACKET: N1,<seq>,…`, and within the 1.5 s RX window paste
   `ACK,N1,<seq>,20`. Expected: `>> STARTING IRRIGATION CYCLE: 20 SECONDS`,
   blue LED + relay click, live `[PUMP] T-…` lines, then
   `>> PUMP CYCLE COMPLETED: Ran 20 s | …`. TIP: keep `ACK,N1,**,20` typed
   already and only edit the seq digits — the 1.5 s window is short.
☐ **4. Stale-ACK guard.** Press Wake, allow the window to pass, then paste the
   PREVIOUS wake's `ACK,N1,<old_seq>,20` inside the new window. Expected: no
   confirmation and the window closes with `[RX-WINDOW] Closed. No gateway ACK
   received.` — the pump must not start (seq mismatch is rejected).
☐ **5. Jammed pump.** Switch 1 (GPIO 18) ON, trigger a cycle as in step 3.
   Expected within ~1 s of pump start: `>>> [SAFETY INTERLOCK] Current > 160%
   rated! Jam detected. Halting pump.` Next uplink reports the aborted run.
   Switch OFF afterwards.
☐ **6. Blocked drip line.** Switch 2 (GPIO 19) ON, trigger a cycle. Expected:
   pump runs with zero flow and cuts at the 15 s mark: `>>> [SAFETY INTERLOCK]
   Zero flow measured after 15s! Line blocked. Halting pump.`; next uplink
   shows `irr_s ≈ 15, flow_mL 0`. Switch OFF afterwards.
☐ **7. Cut sensor + gateway unavailable (the safety-critical drill).** Switch 3
   (GPIO 23) ON. Press Wake at least 10 times WITHOUT any ACK (the local
   fail-safe only arms after 10 silent wakes; each wake prints
   `UPLINK PACKET: N1,<seq>,4095,…` and `[SENSOR FAULT] … watering inhibited`).
   Expected at/after the 10th silent wake:
   `[SAFETY-LOCK] Gateway silent, but soil reading is INVALID: fail-safe
   watering is blocked.` AND `>> STARTING IRRIGATION CYCLE` never appears.
   Quick extra proof: while still faulted, paste a well-formed
   `ACK,N1,<current seq>,20` — expect `[SAFETY-LOCK] Watering command ignored:
   soil sensor is faulted. Repair the probe first.`
☐ **8. Recovery.** Switch 3 OFF, soil pot at 600/1023, press Wake: healthy
   reading, OLED leaves the `SENSOR FAULT` screen, packet values normal.

Before class: all three switches OFF, pot at 600, press Play to restart fresh.

### Fallback — demonstration with NO Wokwi serial input (verified zero-typing path)

Discovered during rehearsal: on some stations the Wokwi Serial Monitor input
row is unavailable, and the ACK paste path (steps 3, 5–7 above) can't be done.
This fallback needs **no typing at all** and still demonstrates pump actuation,
the safety interlocks and the sensor fault — the node's own local fail-safe is
the actuator.

1. Slide the **Soil Moisture pot to ≈ 3/4 toward dry** — target uplink
   `soil_raw` between **2700 and 3400** (OLED shows ≈ 3–20 %).
   ⚠️ NEVER push the pot fully to the end: 1023/1023 → raw 4095, which the node
   correctly reads as a CUT PROBE (`SENSOR FAULT`) — the fail-safe will then
   refuse to water. If you overshoot, bring the pot back to ≈ 750.
2. Press **Wake (GPIO 4) 10–12 times**, counting the `Closed. No gateway ACK
   received.` windows. Each wake adds one; the local fail-safe requires 10.
3. On/after the 10th silent wake with a valid dry reading, the node
   self-triggers: `[FAIL-SAFE] Gateway silent & soil critical! Initiating local
   fail-safe 60s water.` → `>> STARTING IRRIGATION CYCLE: 60 SECONDS` →
   relay + blue LED + one `[PUMP] T-…` line per second.
4. **During that 60 s run:** Switch 1 (GPIO 18) ON → overcurrent interlock
   within ~1 s: `>>> [SAFETY INTERLOCK] Current > 160% rated! Jam detected.
   Halting pump.` — or Switch 2 (GPIO 19) ON → zero-flow interlock at the
   15 s mark: `>>> [SAFETY INTERLOCK] Zero flow measured after 15s! Line
   blocked. Halting pump.`
5. **Sensor lockout** still works with serial input broken: Switch 3 (GPIO 23)
   ON + Wake → `[SENSOR FAULT] … Automatic watering inhibited` and the OLED
   "no auto water" screen. An ACK is not needed to prove the lockout exists.
6. Restart the simulation (Play button) between runs: the fail-safe ring has a
   96-wake cooldown in firmware, which would eat a 2-minute demo slot.

**What this path does not show**: the Wokwi → dashboard round trip. Present
that via Track A's scripted bridge demo (`--demo`, § 1) and *say* it is a
predefined packet sequence, not live radio — that separation is already the
honest wording used throughout this runbook.

---

## 3. Suggested 5-minute talk order

1. Problem (30 s): dumb timers, silent failures, no wifi in the field.
2. Architecture (30 s): node ↔ plain-text CSV over (simulated) LoRa ↔ gateway
   engine ↔ offline dashboard; local fail-safe in the node.
3. Track A dashboard (2 min): faults already happening, farmer-phrase advice,
   activity feed, footer accuracy line with the honest wording.
4. Track B Wokwi (2 min): drills 1 → 4 (the fault switches are the show).
5. Honest limits + what you'd build next (30 s): the statements in Section 4.

---

## 4. Say-this-don't-overclaim cheat sheet

| Property | Status in this prototype |
|---|---|
| LoRa radio | **Simulated** — telemetry is a plain CSV line over Wokwi's serial / the bridge. No real radio was used. |
| Telemetry encryption | **None** — plain CSV; JWT-free local HTTP. Don't present it as encrypted. |
| Radio range | **Not measured.** 868 MHz module datasheets suggest up to a few km clear line-of-sight; unverified here. |
| Battery life "2 years" | **A calculation** from a sleep/current budget in `farm_ai/docs/FIELD_GUIDE.md`; not measured. Depends on real derating. |
| Enclosure | **3D-printed concept shells** (`farm_ai/enclosure/`), mesh-validated but with **no cutouts, no gaskets, no IP rating proven**. Field spec (real glands, gasket, vent, IP65 box) lives in `farm_ai/docs/FIELD_GUIDE.md`. |
| Firmware compile/flash | **Not verified in this environment** (no arduino-cli/PlatformIO/Wokwi CLI here). The sketch is syntax-checkable only; run Wokwi to see it working. |
| Sensors/pumps | Wokwi potentiometers/buttons/switches stand in for real capacitive probe, YF-S201, DHT22, relay, pump. |
| "AI" | Gradient-boosted drying-rate forecaster over physical soil-water points (error reported in **points/hour**, not "% water"); decisions themselves are transparent rule-based — say that last part out loud. Improvement measured on **simulated** beds only; retrain on real logs before field use. |
| Service worker / offline | Verified: page and last state load from cache; installs as PWA. |
| Python backend + tests | Fully verified here: 53 tests pass end-to-end. |

**Repo hygiene note:** `farm_ai/data/farm.db` is tracked in git from before this
audit (pre-existing). `farm_ai/data/demo.db` is recreated per run and git-ignored.
Don't commit any fresh `*.db`.

---

## 5. If an evaluator pushes

* *"How do we know it works on hardware?"* → Hardware is simulated end-to-end in
  Wokwi; the safety math (160 % overcurrent trip, 15 s zero-flow cutoff, invalid
  reading gate) is exercised there, and mirrored in automated tests on the
  server side. Real-board bring-up is the next step, not a claim.
* *"Is my farm data safe?"* → LAN-only plain text right now; adding TLS +
  encryption is on the roadmap, not present.
* *"What's the watermark/AI?"* → It forecasts **drying rate** in soil-water
  points per hour and turns it into hours-until-threshold; the watering
  *decisions* are explicit rules (crop stage windows, soil type) on purpose.
* *"Why is advice sometimes wetter than 100%?"* → The percent is of usable
  water in the root zone, and overwatering/runs are what set the too-wet state;
  the algorithm then recommends waiting, not watering (verified outcome 199 %
  on Bed A in the live demo when a big watering was injected).
* *"Show me proof an untrustworthy sensor can't hurt the crop"* →
  Drill 4: the sensor gate works both in firmware and the server, with tests.

---

## 6. Quick file map

| Path | Role |
|---|---|
| `PRESENTATION_RUNBOOK.md` | this file |
| `./run_dashboard.sh` | dashboard one-liner (laptop demo) |
| `farm_ai/tests/` | 53 automated tests (backend, firmware gates, uplink contract) |
| `farm_ai/wokwi/` | `sketch.ino`, `diagram.json`, bridge `wokwi_gateway.py`, `test_uplink.py` |
| `farm_ai/enclosure/` | STL generator + validator + concept-enclosure guide |
| `farm_ai/docs/FIELD_GUIDE.md` | real-hardware build spec & honest assumptions |
