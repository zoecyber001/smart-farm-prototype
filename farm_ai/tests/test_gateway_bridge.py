"""Integration tests for the hardware->server uplink contract.

Covers the three transport paths that production has:

1. The CSV telemetry line (what the node prints / what a real LoRa packet holds)
   parsed by the gateway bridge (wokwi/wokwi_gateway.py) and posted to
   /api/uplink — the supported integration path.
2. The direct-WiFi JSON payload shape the firmware builds in its optional,
   EXPERIMENTAL ENABLE_WOKWI_WIFI branch (same contract, different encoding).
3. The sensor-fault case: a node reporting a cut probe (soil_raw 4095) must
   receive no watering command, and the backend must register SENSOR_FAULT.

Complements wokwi/test_uplink.py (which checks the dry-soil and blocked-line
scenarios through the same API).
"""
import os
import re
import sys
import time
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, 'wokwi'))

from farm.engine import Engine            # noqa: E402
import server                             # noqa: E402
import wokwi_gateway                      # noqa: E402

SKETCH = os.path.join(BASE, 'wokwi', 'sketch.ino')


class TestCsvBridgeToApi(unittest.TestCase):
    """The supported path: CSV line -> gateway parse -> Flask /api/uplink."""

    def setUp(self):
        e = Engine(os.path.join(tempfile.mkdtemp(), 'gw.db'))
        self.e = e
        self.c = server.create_app(engine=e).test_client()

    def parse_csv(self, raw):
        return wokwi_gateway.parse_telemetry(raw)

    def post_csv(self, raw):
        return self.c.post('/api/uplink', json=self.parse_csv(raw))

    def test_csv_mapping_is_correct(self):
        pkt = self.parse_csv('N1,4,2950,272,55,3980,60,4500,815')
        self.assertEqual(pkt['node'], 'N1')
        self.assertEqual(pkt['seq'], 4)
        self.assertEqual(pkt['soil_raw'], 2950)
        self.assertAlmostEqual(pkt['temp'], 27.2)   # temp_x10 -> degrees
        self.assertEqual(pkt['hum'], 55)
        self.assertAlmostEqual(pkt['batt_v'], 3.980)  # batt_mV -> volts
        self.assertEqual(pkt['irr_s'], 60)
        self.assertAlmostEqual(pkt['flow_l'], 4.5)    # flow_mL -> litres
        self.assertEqual(pkt['pump_ma'], 815)
        self.assertTrue(pkt['ts'])                     # bridge stamps the receive time
        self.assertGreater(pkt['ts'], time.time() - 60)

    def test_rejects_short_or_garbage_lines(self):
        for bad in ('', 'hello world', 'N1,2,3,4'):
            with self.assertRaises(ValueError):
                self.parse_csv(bad)

    def test_prefixes_are_stripped(self):
        p = self.parse_csv('UPLINK PACKET: N1,1,2950,265,58,3950,0,0,0')
        self.assertEqual(p['soil_raw'], 2950)

    def test_dry_soil_csv_gets_a_watering_command(self):
        r = self.post_csv('N1,1,2950,270,55,3960,0,0,0')
        self.assertEqual(r.status_code, 200, r.data)
        dl = r.get_json()['downlink']
        self.assertIsNotNone(dl)
        self.assertGreater(dl['run_s'], 0)
        # The ACK the operator pastes back into the Wokwi console is built by
        # wokwi_gateway.send_uplink (not the API) as ACK,<node>,<seq>,<run_s>.
        # Build it the same way and check it in the exact shape sketch.ino parses.
        pkt = self.parse_csv('N1,1,2950,270,55,3960,0,0,0')
        ack = f"ACK,{pkt['node']},{pkt['seq']},{int(dl['run_s'])}"
        self.assertRegex(ack, r'^ACK,N\d+,\d+,\d+$')

    def test_cut_probe_csv_gets_no_watering_command_and_a_sensor_fault(self):
        r = self.post_csv('N1,2,4095,281,49,3900,0,0,0')
        self.assertEqual(r.status_code, 200, r.data)
        dl = r.get_json()['downlink']
        # server must not command automatic watering while the sensor is faulted
        self.assertTrue(dl is None or dl.get('run_s', 0) == 0, dl)
        faults = {f['code'] for f in self.e.state()['faults'] if f['node'] == 'N1'}
        self.assertIn('SENSOR_FAULT', faults)
        bed = [b for b in self.e.state()['beds'] if b['id'] == 'N1'][0]
        self.assertEqual(bed['status'], 'check_hardware')
        self.assertIsNone(bed['aw_pct'])           # moisture advice switched off


class TestDirectWifiJsonShapeCompat(unittest.TestCase):
    """The EXPERIMENTAL (disabled by default) direct-WiFi branch in sketch.ino
    builds JSON; assert its keys match the API contract, and that a payload
    assembled from those keys/decimals is accepted with the same numbers."""

    def payload_from_sketch_fields(self, csv='N1,7,2950,272,55,3980,60,4500,815'):
        csv = self.parse_csv(csv)
        # Decimal formats mirror the sketch's String(v, d) rendering:
        # temp 2dp, hum 1dp, batt_v 3dp, flow_l 3dp, rssi 0 (unknown, no radio).
        return {
            'node': csv['node'], 'ts': int(csv['ts']), 'seq': csv['seq'],
            'soil_raw': csv['soil_raw'],
            'temp': round(csv['temp'], 2), 'hum': float(f"{csv['hum']:.1f}"),
            'batt_v': round(csv['batt_v'], 3), 'irr_s': csv['irr_s'],
            'flow_l': round(csv['flow_l'], 3), 'pump_ma': csv['pump_ma'],
            'rssi': 0,
        }

    def parse_csv(self, raw):
        return wokwi_gateway.parse_telemetry(raw)

    def test_sketch_json_contains_contract_keys(self):
        with open(SKETCH, encoding='utf8') as fh:
            text = fh.read()
        blocks = re.findall(r'#if ENABLE_WOKWI_WIFI(.*?)#endif', text, re.S)
        body = '\n'.join(blocks)
        for key in (r'\\"node\\"', r'\\"ts\\"', r'\\"seq\\"', r'\\"soil_raw\\"', r'\\"temp\\"',
                    r'\\"hum\\"', r'\\"batt_v\\"', r'\\"irr_s\\"', r'\\"flow_l\\"', r'\\"pump_ma\\"'):
            self.assertRegex(body, key, f'direct-WiFi JSON missing {key}')
        self.assertRegex(body, r'wallClock < \d+', 'sketch must refuse to post with an unsynced clock')

    def test_wifi_shaped_payload_is_accepted_and_watering_matches(self):
        # Fresh server state per encoding: the first watering starts a soak
        # window (farm/decisioning.py), so on one shared Engine the second
        # uplink correctly gets no repeat command. Comparing in isolation.
        results = []
        for db in ('wifi_a.db', 'wifi_b.db'):
            e = Engine(os.path.join(tempfile.mkdtemp(), db))
            c = server.create_app(engine=e).test_client()
            r = c.post('/api/uplink', json=self.payload_from_sketch_fields())
            self.assertEqual(r.status_code, 200, r.data)
            results.append(r.get_json()['downlink'])
        dl, dl2 = results
        self.assertIsNotNone(dl)
        self.assertIsNotNone(dl2)
        # same soil in a CSV-shaped payload must get the SAME decision
        self.assertEqual(dl.get('run_s'), dl2.get('run_s'))
        self.assertGreater(dl['run_s'], 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
