"""Farm simulator: weather, soil physics, pumps, batteries, radio, and injected hardware failures.
Used to (1) train the ML model, (2) run the demo, (3) test that the system catches real-world failures."""
import math, random
from . import core

TICK = 900   # 15 minutes


class Weather:
    def at(self, ts):
        day = int(ts // 86400)
        r = random.Random(day)
        tmean = 26 + r.uniform(-2.5, 5.0)
        h = core.local_hour(ts)
        temp = tmean + 6.0 * math.sin(2 * math.pi * (h - 9) / 24.0)
        hum = max(25, min(95, 100 - 2.0 * (temp - 14)))
        rain = 0.0
        if r.random() < 0.10:                       # ~1 rainy day in 10
            start = r.uniform(15, 18)
            if start <= h < start + 2:
                rain = r.uniform(5, 15) / 8.0       # mm per 15 min tick
        return temp, hum, rain


class Bed:
    """Soil-water physics for one bed (volumetric water content in %)."""
    def __init__(self, node, et_scale=1.0, rng=None, vwc=None):
        self.node, self.soil, self.et_scale = node, core.soil_of(node), et_scale
        self.rng = rng or random.Random(1)
        self.vwc = vwc if vwc is not None else core.vwc_from_aw(0.95, self.soil)
        self.pending = []                           # irrigation water arriving over the next ticks
        self.rain_mm = 0.0

    def step(self, ts, weather):
        temp, hum, rain = weather.at(ts)
        stage, _ = core.stage_for(self.node, ts)
        h = core.local_hour(ts)
        et0_day = 5.0 * self.et_scale * (max(temp, 10) / 28.0) ** 1.3
        f = max(0.0, math.sin(math.pi * (h - 6) / 12.0))
        et_mm = et0_day * f / 7.64 * 0.25 * stage['kc']
        aw = core.aw_from_vwc(self.vwc, self.soil)
        if aw < 0.5:
            et_mm *= max(0.0, aw / 0.5)
        self.vwc -= et_mm / stage['root_mm'] * 100.0
        self.rain_mm = rain
        self.vwc += rain / stage['root_mm'] * 100.0 * 0.8
        if self.pending:
            self.vwc += self.pending.pop(0)
        if self.vwc > self.soil['fc']:               # free drainage above field capacity
            self.vwc -= (self.vwc - self.soil['fc']) * self.soil['drain']
        self.vwc = max(1.0, min(self.soil['sat'], self.vwc))
        return temp, hum

    def irrigate(self, litres, ts, efficiency=0.85):
        stage, _ = core.stage_for(self.node, ts)
        pts = litres / self.node['area_m2'] / stage['root_mm'] * 100.0 * efficiency
        self.pending += [pts * 0.6, pts * 0.4]


class SimNode:
    def __init__(self, node, start_ts, et_scale=1.0, faults=None, seed=0):
        self.n = node
        self.rng = random.Random(seed)
        self.bed = Bed(node, et_scale, self.rng)
        self.faults = faults or {}                   # {'type': 'blocked_line', 'from_ts': ...}
        self.seq = 0
        self.batt = 4.05 + self.rng.uniform(-0.03, 0.03)
        self.last_irr = {'irr_s': 0, 'flow_l': 0.0, 'pump_ma': 0}
        self.frozen_raw = None
        self.silent = False

    def active(self, ts, kind):
        f = self.faults.get(kind)
        return f is not None and ts >= f

    def packet(self, ts, weather):
        temp, hum = self.bed.step(ts, weather)
        soil = core.soil_of(self.n)
        raw = int(round(core.vwc_to_raw(self.bed.vwc, self.n, soil) + self.rng.gauss(0, 6)))
        if self.active(ts, 'sensor_disconnected'):
            raw = 4095
        if self.active(ts, 'sensor_stuck'):
            if self.frozen_raw is None:
                self.frozen_raw = raw
            raw = self.frozen_raw
        drain = 0.0015 if self.active(ts, 'battery_leak') else 0.00004
        self.batt = max(3.0, self.batt - drain)
        if self.active(ts, 'node_offline'):
            return None
        self.seq += 1
        pkt = {'node': self.n['id'], 'ts': ts, 'seq': self.seq, 'soil_raw': raw, 'temp': round(temp, 1), 'hum': round(hum),
               'batt_v': round(self.batt + self.rng.gauss(0, 0.004), 3),
               'rssi': int(-98 + self.rng.gauss(0, 3)), 'irr_s': self.last_irr['irr_s'],
               'flow_l': round(self.last_irr['flow_l'], 2), 'pump_ma': self.last_irr['pump_ma']}
        self.last_irr = {'irr_s': 0, 'flow_l': 0.0, 'pump_ma': 0}
        return pkt

    def run_pump(self, run_s, ts):
        """Executes a downlink command and records what a flow sensor + current sensor would measure."""
        if not run_s:
            return
        rated, design = self.n['rated_pump_ma'], self.n['design_flow_lpm']
        flow_factor, gain_factor, ma = 1.0, 1.0, rated * self.rng.uniform(0.92, 1.08)
        if self.active(ts, 'pump_dead'):
            flow_factor, ma = 0.0, self.rng.uniform(0, 4)
        elif self.active(ts, 'pump_jammed'):
            flow_factor, ma = 0.0, rated * 1.9
        elif self.active(ts, 'blocked_line'):
            flow_factor, ma = 0.18, rated * 0.95
        elif self.active(ts, 'leak'):
            flow_factor, gain_factor = 1.9, 0.25
        elif self.active(ts, 'partial_clog'):
            flow_factor = 0.65
        litres = design / 60.0 * run_s * flow_factor * self.rng.uniform(0.96, 1.04)
        self.bed.irrigate(litres * gain_factor, ts)
        self.last_irr = {'irr_s': int(run_s), 'flow_l': litres, 'pump_ma': int(ma)}


# ---------------------------------------------------------------- scenario helpers
def default_faults(start_ts):
    """The real-world failures a farmer described, scheduled so the demo and tests can prove they are caught."""
    d = 86400
    return {
        'N2': {'blocked_line': start_ts + 1.0 * d},          # mud clogs the drip line
        'N3': {'pump_dead': start_ts + 1.5 * d},             # chewed cable / dead pump
        'N4': {'battery_leak': start_ts + 0.0 * d},          # water in the enclosure drains the battery
        'N5': {'sensor_disconnected': start_ts + 2.5 * d},   # sensor cable cut by a hoe
    }


def make_sims(start_ts, faults=None, et_scale=2.0, seed=7):
    faults = default_faults(start_ts) if faults is None else faults
    return {n['id']: SimNode(n, start_ts, et_scale=et_scale, faults=faults.get(n['id'], {}), seed=seed + i)
            for i, n in enumerate(core.nodes())}


def tick_all(engine, sims, ts, weather, refresh_forecast=True):
    for sim in sims.values():
        pkt = sim.packet(ts, weather)
        if pkt is None:
            continue
        res = engine.ingest(pkt, refresh_forecast=refresh_forecast)
        dl = res.get('downlink')
        sim.run_pump(dl['run_s'] if dl else 0, ts)


def run(engine, sims, start_ts, ticks, weather=None, refresh_every=4):
    weather = weather or Weather()
    for k in range(ticks):
        tick_all(engine, sims, start_ts + k * TICK, weather, refresh_forecast=(k % refresh_every == 0 or k == ticks - 1))
