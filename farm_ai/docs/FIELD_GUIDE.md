# Field Guide: making it survive outside

## 1. Power and network
- **Radio:** LoRa (868 MHz, SF9). Typical farmland range is a few hundred metres to a few km depending on obstructions; **range-test your site**
  before fixing positions. Check local radio rules (Nigeria: NCC) for band and power limits.
- **Gateway:** put the antenna high (pole or roof), ideally with line of sight to the beds. One gateway serves many nodes.
- **Node sleep:** wakes every 15 min: reads soil/temperature/battery, sends one ~45-byte packet, listens 1.5 s for a command, sleeps. Use a low-sleep ESP32 board
  (e.g. FireBeetle 2 ESP32-E, about 10 uA asleep). Plain dev kits can draw 5 to 10 mA asleep and will drain a battery in days.
- **Estimated battery life** (change to your measurements): boot 0.3 s at 60 mA, soil sensor 0.6 s at 25 mA, DHT22, LoRa TX 0.25 s at 120 mA, RX window 1.5 s at 12 mA
  gives 82 mA-s per wake, 96 wakes/day, plus 15 uA sleep: about **2.5 mAh/day**. Two 18650 cells (~4200 mAh usable) is about 4.5 years ideal, **about 2 years after a 50% real-world derate**.
  Verify with a multimeter or power profiler. Add a 2 to 5 W solar panel + charge controller for margin.
- **Pump power** is separate from the node (12 V battery/solar or mains at the tank). The node only switches it and measures its current.
- **Link lost?** After 12 h without gateway contact the node waters a dry bed once per day for 5 min (capped), so plants are not left to die.

## 2. Hardware that survives
| Part | Do this |
|---|---|
| Node electronics | IP65 or better enclosure, mounted on a post **above ground and above flood level**, shaded from direct sun. Cable glands on every entry (cable diameter must match the gland), desiccant packet, breathable vent plug to stop condensation, conformal coating on the PCB. Drip loops on all cables. |
| Soil probe | Capacitive probe only (not resistive: they corrode). Seal the PCB/cable joint with epoxy or heat-shrink with adhesive. Cable in **steel-braid or rigid conduit** where it runs near the ground. Rodents chew plain cable. |
| Cables | Use outdoor UV-rated cable, strain relief at each end, bury or conduit the run, keep away from hoe paths, label both ends. |
| Pump + tank | Lockable, ventilated box; **filter before the pump** and before the flow sensor. Flush valve at the end of each drip line. |
| Flow sensor | After the filter. Mud and sand are what blocks it: inspect weekly at first. |
| Spares | Keep one spare node, probe, fuse and filter on site. |

## 3. Test before anything goes in a field
1. **Spray test:** hose the closed enclosure for 30 min from all sides; open and check for moisture.
2. **Submersion (if you claim IP67):** 10 cm of water for 30 min, with the real cable glands.
3. **Heat test:** closed box in direct sun for a day; check the battery and sensor still read correctly.
4. **Battery profile:** measure real sleep and wake current, then recompute the life estimate.
5. **Range test:** carry a node to each planned bed, check signal (dBm) and packet loss on the dashboard.
6. **Fault drills:** kink the hose, unplug the pump, unplug the probe, remove the battery. Each must show the right alert within a day.

## 4. Calibration
- **Soil probe, two points:** reading in dry air = `dry_raw`, reading in a glass of water (to the line) = `wet_raw`. Put both in `config/farm.json`.
- **Soil type:** pick sand/loam/clay in `config/farm.json`. For better accuracy measure field capacity (soak a bed, cover it for 24 to 48 h, read the sensor) and edit `config/soils.json`.
- **Flow and current:** measure real litres/min with a bucket and timer; set `design_flow_lpm` and `rated_pump_ma` from your pump.

## 5. What the farmer sees when something breaks
| Real failure | Dashboard says |
|---|---|
| Drip line clogged with mud | Drip line is blocked: only 18% of normal flow. Clean filter, flush ends, check emitters. |
| Pump dead / cable chewed | Pump is not drawing current. Check fuse, cable, tank, relay. |
| Pump jammed with sand | Pump current too high: jammed. Check inlet and impeller. |
| Pipe burst or pulled off | Flow 190% of normal: burst pipe or disconnected line. |
| Water delivered, soil not wetter | Sensor outside the wetted zone, a leak, or a failing sensor. |
| Probe cable cut | Reading impossible (raw 4095): advice switched off for that bed, hand-water instead. |
| Water in the enclosure | Battery draining fast, then node offline. |

After repairing a pump or line, press **Water 5 min** on the bed: the alert clears when a healthy run is recorded.

## 6. Weekly checklist (first month, then monthly)
Filters and flush valves, enclosure seals and desiccant, cable damage and rodent signs, battery voltage trend, antenna position, probe depth and contact with soil, dashboard alerts.
