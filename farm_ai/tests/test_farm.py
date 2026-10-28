import os, sys, tempfile, time, unittest
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from farm import core, advisor, health, ml, simulator as sim
from farm.engine import Engine
import server

START = 1792540800.0          # 2026-10-21 00:00 UTC


def reading(ts, vwc=22.0, node=None, **kw):
    node = node or core.node_cfg('N1'); soil = core.soil_of(node)
    jitter = int(ts // 900) % 7 - 3                        # a live sensor always shows a little noise
    r = {'node': node['id'], 'ts': ts, 'seq': int(ts // 900), 'soil_raw': int(core.vwc_to_raw(vwc, node, soil)) + jitter, 'temp': 28.0, 'hum': 60,
         'batt_v': 4.0, 'irr_s': 0, 'flow_l': 0.0, 'pump_ma': 0, 'rssi': -95, 'vwc': vwc}
    r.update(kw); return r


def series(n=30, node=None, t0=None, **kw):
    node = node or core.node_cfg('N1'); t0 = t0 or core.planted_ts(node) + 52 * 86400
    return [reading(t0 + i * 900, node=node, **kw) for i in range(n)]


def codes(f): return {x['code'] for x in f}


class TestCore(unittest.TestCase):
    def test_stage_and_conversion(self):
        n = core.node_cfg('N1'); st, d = core.stage_for(n, core.planted_ts(n) + 52 * 86400)
        self.assertEqual(st['name'], 'flowering/fruit set'); self.assertEqual(d, 52)
        s = core.soil_of(n)
        self.assertAlmostEqual(core.raw_to_vwc(core.vwc_to_raw(20.0, n, s), n, s), 20.0, places=3)


class TestAdvisor(unittest.TestCase):
    def adv(self, nid, aw, temp=28, days=None, faults=()):
        n = core.node_cfg(nid); s = core.soil_of(n)
        ts = core.planted_ts(n) + (days if days is not None else 52 if nid == 'N1' else 29) * 86400
        l = reading(ts, core.vwc_from_aw(aw, s), node=n, temp=temp)
        return advisor.advise(n, l, [], None, list(faults), ts)

    def test_water_now_is_specific(self):
        a = self.adv('N1', 0.40)
        self.assertEqual(a['status'], 'water_now'); self.assertGreater(a['minutes'], 0)
        self.assertIn('Bed A', a['headline']); self.assertIn('Tomato', a['detail']); self.assertIn('flowering', a['detail'])
        self.assertIn('blossom-end rot', a['detail'])            # tells the farmer WHY, in crop terms

    def test_ok_and_too_wet(self):
        self.assertEqual(self.adv('N1', 0.95)['status'], 'ok')
        self.assertEqual(self.adv('N1', 1.20)['status'], 'too_wet')

    def test_clay_is_split_into_cycles(self):
        a = self.adv('N5', 0.10)
        self.assertLessEqual(a['minutes'], 15); self.assertIn('repeat in 90 min', a['detail'])

    def test_heat_raises_trigger(self):
        self.assertNotEqual(self.adv('N1', 0.62, temp=28)['status'], 'water_now')
        self.assertEqual(self.adv('N1', 0.62, temp=34)['status'], 'water_now')

    def test_hardware_fault_changes_the_instruction(self):
        f = [{'code': 'LINE_BLOCKED', 'title': 'Drip line is blocked'}]
        a = self.adv('N1', 0.40, faults=f)
        self.assertEqual(a['status'], 'check_hardware'); self.assertIn('by hand', a['headline'])


class TestHealth(unittest.TestCase):
    N = core.node_cfg('N1')

    def chk(self, rs, now=None):
        return health.check(self.N, rs, now or rs[-1]['ts'] + 60)

    def test_healthy_is_silent(self):
        self.assertEqual(self.chk(series()), [])

    def test_battery(self):
        self.assertIn('LOW_BATTERY', codes(self.chk(series(batt_v=3.5))))
        self.assertIn('BATTERY_CRITICAL', codes(self.chk(series(batt_v=3.3))))

    def test_offline_and_weak_link(self):
        rs = series(); self.assertIn('NODE_OFFLINE', codes(self.chk(rs, rs[-1]['ts'] + 8 * 3600)))
        self.assertIn('NODE_LATE', codes(self.chk(rs, rs[-1]['ts'] + 3300)))
        self.assertIn('WEAK_LINK', codes(self.chk(series(rssi=-120))))

    def test_sensor_faults(self):
        self.assertIn('SENSOR_FAULT', codes(self.chk(series(soil_raw=4095))))
        self.assertIn('SENSOR_FAULT', codes(self.chk(series(soil_raw=0))))
        self.assertIn('SENSOR_STUCK', codes(self.chk(series(soil_raw=2500))))

    def with_event(self, flow_factor, ma, rise=4.0):
        rs = series(30, vwc=20.0)
        exp = self.N['design_flow_lpm'] * 600 / 60.0
        rs[10] = dict(rs[10], irr_s=600, flow_l=exp * flow_factor, pump_ma=ma)
        for i in range(10, 14):
            v = 20.0 + rise; rs[i] = dict(rs[i], vwc=v, soil_raw=int(core.vwc_to_raw(v, self.N, core.soil_of(self.N))) + i % 5)
        return rs

    def test_pump_and_line_faults(self):
        R = self.N['rated_pump_ma']
        self.assertIn('LINE_BLOCKED', codes(self.chk(self.with_event(0.2, R))))
        self.assertIn('LINE_PARTIAL', codes(self.chk(self.with_event(0.65, R))))
        self.assertIn('PUMP_NO_CURRENT', codes(self.chk(self.with_event(0.0, 3))))
        self.assertIn('PUMP_JAMMED', codes(self.chk(self.with_event(0.0, int(R * 1.9)))))
        self.assertIn('LEAK', codes(self.chk(self.with_event(1.9, R))))

    def test_healthy_event_and_soil_response(self):
        R = self.N['rated_pump_ma']
        self.assertEqual(self.chk(self.with_event(1.0, R, rise=4.0)), [])
        self.assertIn('NO_SOIL_RESPONSE', codes(self.chk(self.with_event(1.0, R, rise=0.0))))

    def test_fault_clears_after_repair(self):
        R = self.N['rated_pump_ma']; rs = self.with_event(0.2, R)
        exp = self.N['design_flow_lpm'] * 600 / 60.0
        rs[20] = dict(rs[20], irr_s=600, flow_l=exp, pump_ma=R)           # a later, healthy run
        for i in range(20, 24): rs[i] = dict(rs[i], vwc=24.0)
        self.assertNotIn('LINE_BLOCKED', codes(self.chk(rs)))


class TestML(unittest.TestCase):
    def test_model_beats_baseline(self):
        m = ml.metrics()
        if not m: ml.train(); m = ml.metrics()
        self.assertGreater(m['improvement_pct'], 50)

    def test_load_or_train_recovers_from_bad_model_file(self):
        with tempfile.TemporaryDirectory() as d:
            model_path = os.path.join(d, 'drying_model.joblib')
            metrics_path = os.path.join(d, 'drying_model_metrics.json')
            with open(model_path, 'wb') as fh:
                fh.write(b'not a valid joblib pickle')
            with mock.patch.object(ml, '_MODEL', None), \
                 mock.patch.object(ml, 'MODEL_PATH', model_path), \
                 mock.patch.object(ml, 'METRICS_PATH', metrics_path):
                model = ml.load_or_train()
                self.assertIsNotNone(model)
                self.assertTrue(os.path.exists(metrics_path))
                with open(metrics_path, 'r', encoding='utf8') as fh:
                    payload = fh.read()
                self.assertIn('improvement_pct', payload)


class TestEndToEnd(unittest.TestCase):
    """5 simulated days with the failures the farmer described injected on four beds."""
    @classmethod
    def setUpClass(cls):
        cls.db = os.path.join(tempfile.mkdtemp(), 'e2e.db')
        cls.e = Engine(cls.db, sim_clock=True)
        cls.sims = sim.make_sims(START)
        sim.run(cls.e, cls.sims, START, 5 * 96)
        cls.st = cls.e.state()
        cls.f = {}
        for x in cls.st['faults']: cls.f.setdefault(x['node'], set()).add(x['code'])

    def first_bad_event(self, nid, bad):
        for r in self.e.history(nid, 600):
            if r['irr_s'] >= 30 and bad(r): return r['ts']

    def commands_after(self, nid, ts):
        return self.e.db.execute("SELECT COUNT(*) FROM commands WHERE node=? AND source='auto' AND ts>?", (nid, ts + 900)).fetchone()[0]

    def test_blocked_line_found_and_pump_stopped(self):
        self.assertIn('LINE_BLOCKED', self.f['N2'])
        ts = self.first_bad_event('N2', lambda r: r['flow_l'] < 0.5 * 4.0 * r['irr_s'] / 60.0)
        self.assertIsNotNone(ts)
        self.assertLessEqual(self.commands_after('N2', ts), 1)             # at most one more run before automation halts

    def test_dead_pump_found_and_automation_halted(self):
        self.assertIn('PUMP_NO_CURRENT', self.f['N3'])
        ts = self.first_bad_event('N3', lambda r: r['pump_ma'] < 100)
        self.assertIsNotNone(ts); self.assertEqual(self.commands_after('N3', ts), 0)

    def test_battery_drain_found(self):
        self.assertTrue(self.f['N4'] & {'LOW_BATTERY', 'BATTERY_CRITICAL'})

    def test_cut_sensor_found_and_advice_switches_off(self):
        self.assertIn('SENSOR_FAULT', self.f['N5'])
        bed = [b for b in self.st['beds'] if b['id'] == 'N5'][0]
        self.assertIsNone(bed['aw_pct']); self.assertIn('sensor is not working', bed['headline'])

    def test_farmer_told_what_to_do_by_hand(self):
        for nid in ('N2', 'N3'):
            bed = [b for b in self.st['beds'] if b['id'] == nid][0]
            self.assertEqual(bed['status'], 'check_hardware'); self.assertIn('by hand', bed['headline'])

    def test_healthy_bed_has_no_false_alarms_and_no_crop_stress(self):
        self.assertNotIn('N1', self.f)
        rs = self.e.history('N1', 600)
        self.assertGreater(min(r['aw'] for r in rs[96:]), 0.30)
        self.assertGreaterEqual(self.e.db.execute("SELECT COUNT(*) FROM commands WHERE node='N1'").fetchone()[0], 1)

    def test_forecast_and_actions_present(self):
        n1 = [b for b in self.st['beds'] if b['id'] == 'N1'][0]
        self.assertIsNotNone(n1['forecast_h'])
        self.assertEqual(self.st['actions'][0]['urgency'], 'urgent')       # most urgent first


class TestRepair(unittest.TestCase):
    def test_fault_persists_then_clears_after_a_healthy_test_run(self):
        e = Engine(os.path.join(tempfile.mkdtemp(), 'r.db'), sim_clock=True)
        sims = sim.make_sims(START, faults={'N3': {'pump_dead': START}})
        sim.run(e, sims, START, 4 * 96)                                      # 4 days, well past any time window
        st = e.state(); self.assertIn('PUMP_NO_CURRENT', {f['code'] for f in st['faults'] if f['node'] == 'N3'})
        n_cmd = e.db.execute("SELECT COUNT(*) FROM commands WHERE node='N3' AND source='auto'").fetchone()[0]
        sim.run(e, sims, START + 4 * 96 * 900, 96)                           # a 5th day: still no automatic runs
        self.assertEqual(e.db.execute("SELECT COUNT(*) FROM commands WHERE node='N3' AND source='auto'").fetchone()[0], n_cmd)
        sims['N3'].faults = {}                                               # farmer repairs the pump...
        e.manual('N3', 300)                                                  # ...and presses "Water 5 min" as a test
        sim.run(e, sims, START + 5 * 96 * 900, 4)
        st = e.state(); self.assertNotIn('PUMP_NO_CURRENT', {f['code'] for f in st['faults'] if f['node'] == 'N3'})


class TestOffline(unittest.TestCase):
    def test_silent_node_is_reported(self):
        e = Engine(os.path.join(tempfile.mkdtemp(), 'o.db'), sim_clock=True)
        sims = sim.make_sims(START, faults={'N1': {'node_offline': START + 86400}})
        sim.run(e, sims, START, 2 * 96)
        st = e.state(); codes_ = {f['code'] for f in st['faults'] if f['node'] == 'N1'}
        self.assertIn('NODE_OFFLINE', codes_)
        self.assertEqual([b for b in st['beds'] if b['id'] == 'N1'][0]['status'], 'check_hardware')


class TestApi(unittest.TestCase):
    def setUp(self):
        self.e = Engine(os.path.join(tempfile.mkdtemp(), 'a.db')); self.c = server.create_app(engine=self.e).test_client()

    def pkt(self, **kw):
        n = core.node_cfg('N1'); s = core.soil_of(n)
        p = {'node': 'N1', 'ts': time.time(), 'seq': 1, 'soil_raw': int(core.vwc_to_raw(14.0, n, s)), 'batt_v': 4.0, 'temp': 28, 'hum': 60}
        p.update(kw); return p

    def test_pages_and_validation(self):
        self.assertEqual(self.c.get('/').status_code, 200)
        self.assertIn('beds', self.c.get('/api/state').get_json())
        self.assertEqual(self.c.post('/api/uplink', json={'node': 'N1'}).status_code, 400)
        self.assertEqual(self.c.post('/api/uplink', json=self.pkt(node='ZZ')).status_code, 404)

    def test_state_passes_sensor_air_conditions_through(self):
        self.e.ingest(self.pkt(temp=29.4, hum=66))
        b = self.e.state()['beds'][0]
        self.assertEqual(b['temp'], 29.4)                 # what the sensor sent is what the farmer sees
        self.assertEqual(b['hum'], 66)

    def test_dry_soil_returns_watering_command(self):
        r = self.c.post('/api/uplink', json=self.pkt()).get_json()
        self.assertIsNotNone(r['downlink']); self.assertGreater(r['downlink']['run_s'], 0)
        self.assertLessEqual(r['downlink']['run_s'], 30 * 60)               # capped by the soil's safe maximum

    def test_manual_request_is_delivered_and_capped(self):
        self.assertEqual(self.c.post('/api/manual', json={'node': 'N1', 'run_s': 99999}).status_code, 200)
        r = self.c.post('/api/uplink', json=self.pkt(soil_raw=2000)).get_json()
        self.assertTrue(r['downlink']['run_s'] <= 900)
        self.assertEqual(self.c.post('/api/manual', json={'node': 'ZZ'}).status_code, 404)


class TestSeams(unittest.TestCase):
    """The ports are load-bearing: prove each one can be swapped without touching the engine."""

    def pkt(self, vwc=10.0, nid='N1', **kw):
        n = core.node_cfg(nid); s = core.soil_of(n)
        p = {'node': nid, 'ts': time.time(), 'seq': int(time.time() / 900), 'soil_raw': int(core.vwc_to_raw(vwc, n, s)),
             'temp': 28, 'hum': 60, 'batt_v': 4.0, 'rssi': -95}
        p.update(kw); return p

    def test_advice_strategy_is_swappable(self):
        stub = {'status': 'water_now', 'urgency': 'today', 'node': 'N1', 'bed': 'Bed A', 'crop': 'Tomato',
                'stage': 'vegetative', 'day': 50, 'soil': 'loam', 'aw_pct': 30, 'trigger_pct': 60,
                'target_pct': 90, 'minutes': 10, 'litres': 40, 'headline': 'STUB: water Bed A', 'detail': 'stub'}

        class RecordingStrategy(object):
            def __init__(self): self.contexts = []; self.template = dict(stub)
            def advise(self, ctx):
                self.contexts.append(ctx); return dict(self.template)

        strat = RecordingStrategy()
        e = Engine(os.path.join(tempfile.mkdtemp(), 'seam.db'), strategy=strat)
        dl = e.ingest(self.pkt())['downlink']
        self.assertIsNotNone(dl)                              # stub advice drove the real decision
        self.assertGreater(dl['run_s'], 0)
        self.assertEqual(len(strat.contexts), 1)              # engine built the full context for us
        self.assertEqual(strat.contexts[0].soil, core.soil_of(core.node_cfg('N1')))
        self.assertIn('STUB: water Bed A', e.state()['beds'][0]['headline'])

    def test_storage_backend_is_swappable(self):
        class MemoryRepository(object):
            """Smallest possible alternative store: proves the port is real."""
            def __init__(self): self.rows = {}; self.cmds = []; self._cid = 0
            @property
            def connection(self): return None
            def lock(self):
                import contextlib
                return contextlib.nullcontext()
            def insert_reading(self, node, ts, seq, soil_raw, temp, hum, batt_v, irr_s, flow_l, pump_ma, rssi, vwc, aw):
                self.rows.setdefault(node, []).append(dict(ts=ts, seq=seq, soil_raw=soil_raw, temp=temp, hum=hum,
                    batt_v=batt_v, irr_s=irr_s, flow_l=flow_l, pump_ma=pump_ma, rssi=rssi, vwc=vwc, aw=aw))
            def readings(self, node, n=96): return sorted(self.rows.get(node, []), key=lambda r: r['ts'])[-n:]
            def last_irrigation_event(self, node, min_seconds=30):
                ev = [r for r in self.rows.get(node, []) if r['irr_s'] >= min_seconds]
                return ev[-1] if ev else None
            def latest_reading_ts(self): return max((r['ts'] for v in self.rows.values() for r in v), default=None)
            def insert_command(self, node, ts, run_s, reason, source, status):
                self._cid += 1; self.cmds.append(dict(id=self._cid, node=node, ts=ts, run_s=run_s, reason=reason,
                                                      source=source, status=status)); return self._cid
            def pending_command(self, node):
                q = sorted([c for c in self.cmds if c['node'] == node and c['status'] == 'queued'], key=lambda c: c['ts'])
                return q[0] if q else None
            def latest_sent_command(self, node):
                c = [x for x in self.cmds if x['node'] == node and x['status'] != 'queued']
                return sorted(c, key=lambda c: c['ts'])[-1] if c else None
            def mark_command_sent(self, command_id, ts):
                for c in self.cmds:
                    if c['id'] == command_id: c['status'] = 'sent'; c['ts'] = ts
            def recent_commands(self, limit=30): return sorted(self.cmds, key=lambda c: -c['ts'])[:limit]

        mem = MemoryRepository()
        e = Engine(os.path.join(tempfile.mkdtemp(), 'unused.db'), repository=mem, sim_clock=False)
        res = e.ingest(self.pkt())
        self.assertEqual(len(mem.rows['N1']), 1)              # reading went to OUR store
        self.assertIsNotNone(res['downlink'])                 # the decision cycle still ran
        self.assertEqual(len(mem.cmds), 1)
        self.assertEqual(mem.cmds[0]['source'], 'auto')

    def test_state_includes_activity_feed(self):
        e = Engine(os.path.join(tempfile.mkdtemp(), 'act.db'))
        e.ingest(self.pkt())                                  # dry soil -> auto watering decision
        st = e.state()
        self.assertTrue(st['commands'])
        top = st['commands'][0]
        self.assertEqual(top['node'], 'N1'); self.assertEqual(top['bed'], 'Bed A')
        self.assertIn(top['source'], ('auto', 'farmer'))
        self.assertTrue(top.get('time'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
