"""One-command LIVE demonstration, no Wokwi and no serial input required.

    python farm_ai/demo_live.py              # against http://localhost:5000
    python farm_ai/demo_live.py --no-pause   # run straight through (for checks)

Start the dashboard first (./run_dashboard.sh at the repo root), then run
this script in a second terminal. It drives the dashboard through the full
story using the same HTTP contract the Wokwi gateway bridge and the node
firmware speak, so every response you see here is what real hardware would
get over the radio:

  1. healthy heartbeat            -> Bed A refreshes, "no action needed"
  2. dry soil packet              -> the farm's own controller commands irrigation
  3. farmer waters by hand        -> the radio answers: ACK,N1,<seq>,300
  4. water delivered              -> Bed A's last-water stamp updates, no faults
  5. line blocked (flow 0)        -> LINE_BLOCKED critical: "water by hand"
  6. pump jammed (high amps)      -> PUMP_JAMMED critical
  7. probe cable cut (raw 4095)   -> SENSOR_FAULT: no number published, nothing waters
  8. recovery                     -> healthy run clears the fault, advice normal

Wokwi can still share the stage (optional): its browser sim shows the same
firmware logic on the OLED in parallel. This script alone is the complete,
reproducible demo.

Notes on honesty:
- The dashboard runs a background farm simulator, so other beds (B-E) keep
  showing their own simulated faults; they are not produced by this script.
- Beat 7's sensor fault is a last-reading fault, so the dashboard keeps it
  only while the cut reading is the newest one; the terminal capture holds
  the proof. The Wokwi OLED shows the same guard continuously.
"""
import argparse
import json
import time
import urllib.error
import urllib.request

TICK = 900.0          # the dashboard's simulated step: 15 min
SIM_START = 1792540800.0   # matches run_demo.py's prefill start (2026-10-21)

BATT_OK = 3.85
PUMP_OK = 800


def req(url, method='GET', obj=None):
    data = json.dumps(obj).encode() if obj is not None else None
    r = urllib.request.Request(url, data=data, method=method,
                               headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors='replace')[:200]
        raise SystemExit('HTTP {} from {}: {}'.format(e.code, url, body))


def pause(opts):
    if opts.no_pause:
        time.sleep(1.2)
        return
    try:
        input('      \n      [press Enter for the next beat] ')
    except EOFError:
        time.sleep(1.2)


def say(beat, title, body=''):
    print('\n' + '=' * 62)
    print('  BEAT {}  {}'.format(beat, title))
    if body:
        print('  ' + body)
    print('=' * 62)


def uplink(base, node, ts, seq, **fields):
    """Send one telemetry packet exactly like the gateway bridge does."""
    pkt = dict(node=node, ts=ts, seq=seq,
               soil_raw=2500, temp=27.0, hum=55, batt_v=BATT_OK,
               irr_s=0, flow_l=0.0, pump_ma=0, rssi=-62)
    pkt.update(fields)
    return req(base + '/api/uplink', 'POST', pkt)


def csv_line(node, seq, soil=2500, batt_v=BATT_OK, extra='0,0,0'):
    """What this packet would look like on the node's serial console."""
    return '{},{},{},270,55,{}'.format(
        node, seq, soil, int(batt_v * 1000), extra)


def sim_time(base, node):
    """The dashboard runs on a simulated clock; calendar in step with it."""
    try:
        h = req('{}/api/history/{}?hours=2'.format(base, node))
        t = [x for x in (h.get('t') or []) if x]
        if t:
            return float(t[-1])
    except Exception:
        pass
    return time.time() + 6 * 3600


def next_seq(ts):
    """Seq on the simulator's own tick grid, so real and injected packets
    share one counter and no false packet-loss alerts are raised."""
    return int((ts + TICK - SIM_START) / TICK)


def show_node(base, node):
    st = req(base + '/api/state')
    me = next((b for b in st['beds'] if b.get('id') == node), {})
    bed = me.get('bed', node)
    print('  Dashboard says: {} | status: {} | aw: {}% | last_water: {}'.format(
        bed, me.get('status'), me.get('aw_pct'), me.get('last_water')))
    print('  Headline : {}'.format(me.get('headline', '?')))
    fault = next((f for f in st.get('faults') or [] if f.get('node') == node), None)
    print('  Faults   : {}'.format(fault['title'] if fault else 'none'))
    cmds = [c for c in (st.get('commands') or []) if c.get('node') == node][:1]
    for c in cmds:
        print('  Activity : {} -> {} {}s ({} {})'.format(
            c['time'], c['bed'], c['run_s'], c['source'], c['status']))
    return me, st


def report(base, node, seq, r, extra_note=''):
    if r.get('downlink'):
        d = r['downlink']
        print('  Radio downlink : ACK,{},{},{}  ({})'.format(
            node, seq, d.get('run_s'), d.get('reason')))
    else:
        print('  Radio downlink : none accepted (the gateway replays silence)'.format())
    if extra_note:
        print('  ' + extra_note)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--server', default='http://localhost:5000')
    ap.add_argument('--node', default='N1')
    ap.add_argument('--no-pause', action='store_true')
    opts = ap.parse_args()
    base = opts.server.rstrip('/')
    node = opts.node

    st = req(base + '/api/state')
    print('=' * 62)
    print("  SMART FARM LIVE DEMO -- farm '{}' on {}".format(st['farm'], base))
    print('  Watch http://localhost:5000 between beats (it auto-refreshes).')
    print('=' * 62)

    # ---- 1. healthy heartbeat ------------------------------------------
    say(1, 'HEALTHY HEARTBEAT',
        'A normal node reports in; the dashboard shows Bed A is fine.')
    ts = sim_time(base, node)
    seq0 = next_seq(ts)
    r = uplink(base, node, ts + TICK, seq0, soil_raw=2500)
    print('  Serial would print : {}'.format(csv_line(node, seq0)))
    report(base, node, seq0, r)
    show_node(base, node)
    pause(opts)

    # ---- 2. dry soil -> autonomous irrigation --------------------------
    say(2, 'DRY SOIL -> THE FARM ITSELF DECIDES TO IRRIGATE',
        'Soil raw 2950 (usable water ~0%): no human in the loop.')
    ts = sim_time(base, node)
    seq0 = next_seq(ts)
    r = uplink(base, node, ts + TICK, seq0, soil_raw=2950)
    print('  Serial would print : {}'.format(csv_line(node, seq0, soil=2950)))
    report(base, node, seq0, r)
    show_node(base, node)
    pause(opts)

    # ---- 3. farmer waters by hand --------------------------------------
    say(3, 'THE FARMER ORDERS WATER -- AND THE RADIO CONFIRMS',
        'Remote command: 5 min on this bed. The next packet carries the ACK.',
        )
    ok = req(base + '/api/manual', 'POST', {'node': node, 'run_s': 300})
    print('  /api/manual -> ok: {}'.format(ok.get('ok')))
    ts = sim_time(base, node)
    seq0 = next_seq(ts)
    r = uplink(base, node, ts + TICK, seq0, soil_raw=2500)
    print('  Serial would print : {}'.format(csv_line(node, seq0)))
    report(base, node, seq0, r, '(a real node would now run its pump for 300 s)')
    show_node(base, node)
    pause(opts)

    # ---- 4. water delivered --------------------------------------------
    say(4, 'WATER IS DELIVERED',
        'Completion report: 300 s run, 20.0 L measured, pump 800 mA. All healthy.')
    ts = sim_time(base, node)
    seq0 = next_seq(ts)
    r = uplink(base, node, ts + TICK, seq0,
               soil_raw=2450, irr_s=300, flow_l=20.0, pump_ma=PUMP_OK)
    print('  Serial would print : {}'.format(
        csv_line(node, seq0, soil=2450, extra='300,20000,810')))
    report(base, node, seq0, r)
    show_node(base, node)
    pause(opts)

    # ---- 5. blocked drip line ------------------------------------------
    say(5, 'HARDWARE FAULT: THE LINE BLOCKS',
        'Same 300 s run, but the flow meter says 0.0 L: commanded vs measured.')
    ts = sim_time(base, node)
    seq0 = next_seq(ts)
    r = uplink(base, node, ts + TICK, seq0,
               soil_raw=2950, irr_s=300, flow_l=0.0, pump_ma=PUMP_OK)
    print('  Serial would print : {}'.format(
        csv_line(node, seq0, soil=2950, extra='300,0,810')))
    report(base, node, seq0, r)
    show_node(base, node)
    pause(opts)

    # ---- 6. jammed pump --------------------------------------------------
    say(6, 'HARDWARE FAULT: THE PUMP JAMS',
        'Current spikes to 1350 mA (> 1.6x rated 800 mA): impeller stalled.')
    ts = sim_time(base, node)
    seq0 = next_seq(ts)
    r = uplink(base, node, ts + TICK, seq0,
               soil_raw=2950, irr_s=300, flow_l=20.0, pump_ma=1350)
    print('  Serial would print : {}'.format(
        csv_line(node, seq0, soil=2950, extra='300,20000,1350')))
    report(base, node, seq0, r)
    show_node(base, node)
    pause(opts)

    # ---- 7. cut probe ----------------------------------------------------
    say(7, 'HARDWARE FAULT: THE PROBE IS CUT',
        'Cut cable reads raw 4095. The system must refuse: garbage data, not drought.')
    ts = sim_time(base, node)
    seq0 = next_seq(ts)
    r = uplink(base, node, ts + TICK, seq0, soil_raw=4095)
    print('  Serial would print : {}'.format(csv_line(node, seq0, soil=4095)))
    report(base, node, seq0, r)
    me, _ = show_node(base, node)
    if me.get('aw_pct') is None:
        print('  Evidence : no moisture percentage is published for this bed --')
        print('             the dashboard refuses to trust the broken probe.')
    print('  (The fault shows while the broken reading is newest; the terminal')
    print('   capture above is the proof. Wokwi\'s OLED shows it continuously.)')
    pause(opts)

    # ---- 8. recovery ------------------------------------------------------
    say(8, 'RECOVERY',
        'Healthy run recorded; the fault clears and advice returns to normal.')
    ts = sim_time(base, node)
    seq0 = next_seq(ts)
    r = uplink(base, node, ts + TICK, seq0,
               soil_raw=2500, irr_s=300, flow_l=20.0, pump_ma=PUMP_OK)
    print('  Serial would print : {}'.format(
        csv_line(node, seq0, extra='300,20000,810')))
    report(base, node, seq0, r)
    show_node(base, node)

    print('\n' + '=' * 62)
    print('  DEMO COMPLETE.')
    print('  Story: node reports -> controller decides -> radio command ->')
    print('  water measured -> machine faults -> refuse-on-bad-data -> repair.')
    print('=' * 62)


if __name__ == '__main__':
    main()
