"""Hardware and link health, as a swappable checker (implements the HealthChecker port).

Detects the failures that make a computer 'throw an error' while plants die:
pump/line checks compare what the node COMMANDED (run seconds) with what it
MEASURED (flow litres, pump current). Soil-sensor and battery/link checks watch
the raw values a live system always jitters.
"""
from . import units
from .config_store import load_default

INTERVAL = 900


class HardwareHealthChecker:
    """Returns a list of fault dicts; never raises on bad data."""

    @staticmethod
    def _fault(code, sev, title, steps, evidence):
        return {'code': code, 'severity': sev, 'title': title, 'what_to_check': steps, 'evidence': evidence}

    def check(self, node, readings, now, interval=INTERVAL):
        """readings: oldest -> newest (up to ~96). Returns a list of faults."""
        f = []
        if not readings:
            return f
        last = readings[-1]
        soil = load_default().soil(node)
        age = now - last['ts']

        # ---- link / power ----
        if age > 6 * interval:
            f.append(self._fault('NODE_OFFLINE', 'critical', 'Node offline for {:.0f} h'.format(age / 3600.0),
                                 ['Check the node battery and fuse.', 'Look for water inside the enclosure (condensation, bad gland).',
                                  'Check the antenna and its cable (rodents, broken connector).', 'Check the gateway is powered and the link is clear.'],
                                 'last message {}'.format(units.fmt_time(last['ts']))))
        elif age > 3 * interval:
            f.append(self._fault('NODE_LATE', 'warning', 'Node has missed messages ({:.0f} min silent)'.format(age / 60.0),
                                 ['Usually a weak radio link or a flat battery starting.', 'Check the signal level and battery on this bed.'],
                                 'last message {}'.format(units.fmt_time(last['ts']))))
        v = last['batt_v']
        if v < 3.40:
            f.append(self._fault('BATTERY_CRITICAL', 'critical', 'Battery critically low ({:.2f} V)'.format(v),
                                 ['Replace or recharge the battery now; the node will stop soon.', 'If it drained fast, check for water ingress or a leaking cell.'],
                                 '{:.2f} V'.format(v)))
        elif v < 3.60:
            days_txt = ''
            old = [r for r in readings if last['ts'] - r['ts'] >= 86400]
            if old:
                drop_per_day = (old[-1]['batt_v'] - v) / ((last['ts'] - old[-1]['ts']) / 86400.0)
                if drop_per_day > 0.001:
                    days_txt = ', about {:.0f} day(s) left at the current rate'.format(max(0, (v - 3.30) / drop_per_day))
            f.append(self._fault('LOW_BATTERY', 'warning', 'Battery low ({:.2f} V){}'.format(v, days_txt),
                                 ['Plan a battery swap or check the solar panel and charge controller.'], '{:.2f} V'.format(v)))
        if last.get('rssi', 0) and last['rssi'] < -115:
            f.append(self._fault('WEAK_LINK', 'warning', 'Weak radio signal ({} dBm)'.format(last['rssi']),
                                 ['Raise the node antenna above the crop canopy.', 'Move or raise the gateway antenna, or add a repeater.'],
                                 '{} dBm'.format(last['rssi'])))
        seqs = [r['seq'] for r in readings[-12:]]
        if len(seqs) >= 6:
            gaps = sum(max(0, (b - a - 1)) for a, b in zip(seqs, seqs[1:]) if b > a)
            if gaps >= 4 and not any(x['code'] == 'WEAK_LINK' for x in f):
                f.append(self._fault('LOSSY_LINK', 'warning', 'Radio messages are being lost ({} missed in the last hour-ish)'.format(gaps),
                                     ['Check antenna orientation and obstructions.', 'Move the gateway higher.'], 'sequence gaps: {}'.format(gaps)))

        # ---- soil sensor ----
        lo, hi = node['wet_raw'] - 250, node['dry_raw'] + 250
        if last['soil_raw'] <= lo or last['soil_raw'] >= hi or last['soil_raw'] in (0, 4095):
            f.append(self._fault('SENSOR_FAULT', 'critical', 'Soil sensor reading is impossible (raw {})'.format(last['soil_raw']),
                                 ['Sensor cable is probably cut, chewed or disconnected (reads 0/4095).', 'Check the connector for corrosion and water.',
                                  'Do not trust moisture advice for this bed until the sensor is fixed; water by hand.'], 'raw {}'.format(last['soil_raw'])))
        else:
            tail = readings[-12:]
            if len(tail) >= 12 and len(set(r['soil_raw'] for r in tail)) == 1:
                f.append(self._fault('SENSOR_STUCK', 'warning', 'Soil sensor value has not changed for 3 h',
                                     ['A live sensor always shows small noise; a frozen value means a failed sensor or board.',
                                      'Re-seat the sensor, test in a glass of water, replace if needed.'], 'raw {} repeated'.format(last['soil_raw'])))

        # ---- pump / drip line: compare commanded vs measured on the latest irrigation event ----
        ev_idx = None
        for i in range(len(readings) - 1, -1, -1):
            if readings[i].get('irr_s', 0) >= 30:
                ev_idx = i
                break
        if ev_idx is not None and now - readings[ev_idx]['ts'] < 30 * 86400:   # persists until a healthy run replaces it
            ev = readings[ev_idx]
            expected_l = node['design_flow_lpm'] * ev['irr_s'] / 60.0
            ratio = ev.get('flow_l', 0) / expected_l if expected_l > 0 else 1
            rated = node['rated_pump_ma']
            when = units.fmt_time(ev['ts'])
            ev_txt = 'run {} s at {}: flow {:.1f} L of {:.1f} L expected, pump {} mA'.format(ev['irr_s'], when, ev.get('flow_l', 0), expected_l, ev.get('pump_ma', 0))
            if ev.get('pump_ma', 0) < 0.15 * rated:
                f.append(self._fault('PUMP_NO_CURRENT', 'critical', 'Pump is not drawing current: it did not run',
                                     ['Check the pump fuse and the relay/valve driver.', 'Check the pump power cable for cuts (rodents, hoes).',
                                      'Check the tank is not empty (some pumps cut out dry).', 'Test the pump directly from the battery.',
                                      'After repairing, press "Water 5 min" on this bed. The alert clears when a healthy run is recorded.'], ev_txt))
            elif ev.get('pump_ma', 0) > 1.5 * rated:
                f.append(self._fault('PUMP_JAMMED', 'critical', 'Pump current is too high: pump is jammed or stalled',
                                     ['Switch off. Check the pump inlet for sand, mud or debris.', 'Check the impeller turns freely.',
                                      'Check the inlet filter and the water source.', 'After repairing, press "Water 5 min" on this bed. The alert clears when a healthy run is recorded.'], ev_txt))
            elif ratio < 0.5:
                f.append(self._fault('LINE_BLOCKED', 'critical', 'Drip line is blocked: only {:.0f}% of normal flow'.format(ratio * 100),
                                     ['Clean or replace the inlet and line filter.', 'Open the flush valves at the line ends and flush with water.',
                                      'Check emitters for mud, insects and salt crust.', 'Check the hose is not kinked or crushed.',
                                      'After repairing, press "Water 5 min" on this bed. The alert clears when a healthy run is recorded.'], ev_txt))
            elif ratio < 0.8:
                f.append(self._fault('LINE_PARTIAL', 'warning', 'Flow is down to {:.0f}% of normal: filter or emitters clogging'.format(ratio * 100),
                                     ['Clean the filter this week.', 'Flush the line ends.'], ev_txt))
            elif ratio > 1.4:
                f.append(self._fault('LEAK', 'critical', 'Flow is {:.0f}% of normal: burst pipe or a disconnected line'.format(ratio * 100),
                                     ['Walk the line and look for wet patches or a pipe pulled off a fitting.', 'Close the valve until it is repaired.',
                                      'After repairing, press "Water 5 min" on this bed. The alert clears when a healthy run is recorded.'], ev_txt))
            else:
                # flow looks healthy: did the soil respond?
                stage, _ = load_default().stage_for(node, ev['ts'])
                after = readings[ev_idx:ev_idx + 4]
                if ev_idx >= 1 and len(after) >= 3:
                    base = readings[ev_idx - 1]['vwc']
                    rise = max(r['vwc'] for r in after) - base
                    gain = ev.get('flow_l', 0) / node['area_m2'] / stage['root_mm'] * 100 * 0.85
                    if gain > 1.5 and rise < 0.25 * gain:
                        f.append(self._fault('NO_SOIL_RESPONSE', 'warning', 'Water was delivered but the soil did not get wetter',
                                             ['The sensor may be outside the wetted zone: move it next to an emitter.', 'Or water is going somewhere else (leak, runoff).',
                                              'Or the sensor is failing: test it in water.'], '{}; expected about +{:.1f} points, saw +{:.1f}'.format(ev_txt, gain, rise)))
        return f


def check(node, readings, now, interval=INTERVAL):
    """Compatibility for the old module-level API."""
    return HardwareHealthChecker().check(node, readings, now, interval)
