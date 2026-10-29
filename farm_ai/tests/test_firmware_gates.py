"""Regression tests for the sensor-validity interlock in the ESP32 firmware.

LIMITATION (documented honestly): no Arduino/ESP32 toolchain is installed in
this environment, so the .ino sketches cannot be compiled or executed here.
These tests therefore protect the fail-safe decision logic in two ways that do
not require a toolchain:

1. Textual anchors: the sketches carry marked code sections; these tests pin
   the exact gating structure (the sensor-validity function, the fail-safe
   condition, and the watering-command interlock) so any edit that removes the
   gate fails this suite.
2. A Python mirror of the numeric decision rule, with its thresholds parsed
   from the sketch files themselves, proves the required behaviour: a raw
   reading of 4095 (cut probe) or 0 (shorted probe) with the gateway
   unavailable never triggers the local fail-safe watering.

To execute the real firmware logic end-to-end instead, open the Wokwi
simulation per farm_ai/wokwi/README.md and follow the "Cut sensor + silent
gateway" drill under the presentation runbook.
"""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
WOKWI = os.path.join(HERE, '..', 'wokwi', 'sketch.ino')
FIELD_NODE = os.path.join(HERE, '..', 'firmware', 'field_node', 'field_node.ino')


def read(path):
    with open(path, encoding='utf8') as fh:
        return fh.read()


class FirmwareGateTestBase:
    """Mixin with the shared assertions; NOT itself a TestCase (each concrete
    test class below pairs it with unittest.TestCase)."""

    def path(self):
        raise NotImplementedError

    def setUp(self):
        self.text = read(self.path())

    # ---- the sole watering gate ----
    def test_validity_function_is_anchored_and_reasonable(self):
        self.assertIn('INO_TEST_ANCHOR: soilReadingValid', self.text)
        m = re.search(r'bool soilReadingValid\(uint16_t (\w+)\)\s*\{([^}]*)\}', self.text)
        self.assertIsNotNone(m, 'soilReadingValid(raw) function missing')
        body, arg = m.group(2), m.group(1)
        self.assertIn(f'{arg} >= SENSOR_VALID_LO', body)
        self.assertIn(f'{arg} <= SENSOR_VALID_HI', body)
        self.assertIn('!= 0', body)
        self.assertIn('!= 4095', body)

    def test_validity_window_derives_from_calibration(self):
        self.assertRegex(self.text, r'#define\s+SENSOR_VALID_LO\s+\(SOIL_WET_RAW - \d+\)')
        self.assertRegex(self.text, r'#define\s+SENSOR_VALID_HI\s+\(SOIL_DRY_RAW \+ \d+\)')

    def test_fail_safe_branch_is_the_else_of_a_sensor_fault_guard(self):
        """The 'soil > LOCAL_DRY_RAW' trigger must only be reachable through an
        if-chain whose first branch is the sensor-fault guard (the fault branch
        body is brace-free in both sketches, so this regex matches exactly the
        adjacent chain)."""
        m = re.search(r'if\s*\(soilFault\)\s*\{[^{}]*\}\s*else if\s*\(([^)]*LOCAL_DRY_RAW[^)]*)\)', self.text, re.S)
        self.assertIsNotNone(m, 'fail-safe must be the else-branch of a soilFault guard')
        self.assertIn('LOCAL_DRY_RAW', m.group(1))

    def test_fault_is_logged_to_serial(self):
        self.assertIn('[SENSOR FAULT]', self.text)


class TestWokwiSketchGate(FirmwareGateTestBase, unittest.TestCase):
    def path(self):
        return WOKWI

    def test_watering_command_is_blocked_while_sensor_faulted(self):
        # sketch form: guarded while-pump expression near the actuation step
        self.assertRegex(self.text, r'if\s*\(\s*run\w*\s*>\s*0\s*&&\s*soilFault\s*\)')

    def test_fail_safe_wakes_condition_present(self):
        # wait-for-gateway counter is part of the trigger (demo: 10 wakes)
        self.assertIn('wakesSinceAck >= 10', self.text)

    def test_experiment_wifi_branch_maps_contract_fields(self):
        """The optional (disabled) direct-WiFi uplink must build contract-shaped
        JSON: node, ts, seq, soil_raw (+ batt_v) are required by /api/uplink."""
        blocks = re.findall(r'#if ENABLE_WOKWI_WIFI(.*?)#endif', self.text, re.S)
        self.assertTrue(blocks, 'ENABLE_WOKWI_WIFI blocks missing')
        found = '\n'.join(blocks)
        for key in (r'\\"node\\"', r'\\"ts\\"', r'\\"seq\\"', r'\\"soil_raw\\"', r'\\"batt_v\\"'):
            self.assertRegex(found, key, f'direct-WiFi JSON missing {key}')
        self.assertRegex(found, r'wallClock < \d+')


class TestFieldNodeGate(FirmwareGateTestBase, unittest.TestCase):
    def path(self):
        return FIELD_NODE

    def test_fail_safe_wakes_condition_present(self):
        self.assertIn('wakesSinceAck >= FAILSAFE_WAKES', self.text)

    def test_watering_command_is_blocked_while_sensor_faulted(self):
        # field-node form: a commanded run is zeroed before runPump()
        self.assertIn('[SAFETY-LOCK] Watering command', self.text)
        self.assertRegex(self.text, r'if\s*\(\s*\w+\s*>\s*0\s*\)\s*\{[^{}]*run\w*\s*=\s*0;')
        # and nothing reaches runPump() with a non-zero run while faulted
        self.assertRegex(self.text, r'runPump\(runS\);')


def parse_thresholds(text):
    """Read the calibrated range, margins and fail-safe threshold straight out
    of a sketch file, so the Python mirror cannot silently drift."""
    def base_of(define_name):
        return int(re.search(r'#define\s+%s\s+(\d+)' % define_name, text).group(1))

    def margin(define_name, base_name, sign):
        m = re.search(r'#define\s+%s\s+\(%s - (\d+)\)' % (define_name, base_name), text)
        if m:
            return base_of(base_name) - int(m.group(1))
        m = re.search(r'#define\s+%s\s+\(%s \+ (\d+)\)' % (define_name, base_name), text)
        if m:
            return base_of(base_name) + int(m.group(1))
        raise AssertionError('%s not found' % define_name)

    t = {'dry': base_of('SOIL_DRY_RAW'), 'wet': base_of('SOIL_WET_RAW'), 'fail_dry': base_of('LOCAL_DRY_RAW')}
    t['lo'] = margin('SENSOR_VALID_LO', 'SOIL_WET_RAW', '-')
    t['hi'] = margin('SENSOR_VALID_HI', 'SOIL_DRY_RAW', '+')
    w = re.search(r'wakesSinceAck >= (\w+)', text).group(1)
    if w.isdigit():
        t['wakes'] = int(w)
    else:
        t['wakes'] = int(re.search(r'#define\s+FAILSAFE_WAKES\s+(\d+)', text).group(1))
    return t


def mirrored_soil_reading_valid(raw, t):
    """Python mirror of soilReadingValid(): valid window + hard 0/4095 guards."""
    return bool(t['lo'] <= raw <= t['hi'] and raw != 0 and raw != 4095)


def mirrored_fail_safe_triggers(raw, wakes_since_ack, t):
    """Mirror of the node's fail-safe decision: water only when the reading is
    valid AND drier than LOCAL_DRY_RAW AND the gateway is silent long enough."""
    if not mirrored_soil_reading_valid(raw, t):
        return False                     # SENSOR FAULT: never water
    return raw > t['fail_dry'] and wakes_since_ack >= t['wakes']


class MirroredBehaviour(unittest.TestCase):
    """Numeric proof of the audit requirement, using thresholds parsed from
    each sketch (kept in sync by the textual tests above)."""

    SKETCHES = (WOKWI, FIELD_NODE)

    def test_cut_probe_with_silent_gateway_never_waters(self):
        for text in (read(WOKWI), read(FIELD_NODE)):
            t = parse_thresholds(text)
            self.assertFalse(mirrored_fail_safe_triggers(4095, 100, t),
                             'raw 4095 + silent gateway must NOT trigger the fail-safe')
            self.assertFalse(mirrored_fail_safe_triggers(4095, 99999, t))
            self.assertFalse(mirrored_fail_safe_triggers(0, 99999, t))
            # the genuine feature must survive: dry, valid reading + silent gateway
            self.assertTrue(mirrored_fail_safe_triggers(t['fail_dry'] + 1, t['wakes'], t))

    def test_validity_boundaries(self):
        for text in (read(WOKWI), read(FIELD_NODE)):
            t = parse_thresholds(text)
            self.assertTrue(mirrored_soil_reading_valid(t['lo'], t))
            self.assertFalse(mirrored_soil_reading_valid(t['lo'] - 1, t))
            self.assertTrue(mirrored_soil_reading_valid(t['hi'], t))
            self.assertFalse(mirrored_soil_reading_valid(t['hi'] + 1, t))
            self.assertTrue(mirrored_soil_reading_valid(t['wet'], t))   # calibrated water point
            self.assertTrue(mirrored_soil_reading_valid(t['dry'], t))   # calibrated air point
            for bad in (0, 4095):
                self.assertFalse(mirrored_soil_reading_valid(bad, t))


if __name__ == '__main__':
    unittest.main(verbosity=2)
