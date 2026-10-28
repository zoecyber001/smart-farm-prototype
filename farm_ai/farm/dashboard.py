"""Dashboard service: view builders. Shapes the system's state for the screen,
not the database — the server only serialises whatever this returns.
"""
from . import units
from .config_store import load_default

URGENCY_ORDER = {'urgent': 0, 'today': 1, 'soon': 2, 'none': 3}
SEVERITY_ORDER = {'critical': 0, 'warning': 1, 'info': 2}


class DashboardService:
    def __init__(self, config, repository, evaluator, now_fn=None, sim_clock=False):
        self.config = config
        self.repository = repository
        self.evaluator = evaluator
        self.now_fn = now_fn
        self.sim_clock = sim_clock

    def state(self):
        with self.repository.lock():
            now = self.now_fn() if self.now_fn else wall_time()
            beds, actions, faults = [], [], []
            for node in self.config.nodes():
                ev = self.evaluator.evaluate(node, now)
                if ev is None:
                    beds.append({'id': node['id'], 'bed': node['bed'], 'no_data': True})
                    continue
                l, a = ev['latest'], ev['advice']
                lastcmd = self.repository.latest_sent_command(node['id'])
                bad_sensor = any(f['code'] in ('SENSOR_FAULT', 'SENSOR_STUCK') for f in ev['faults'])
                beds.append({
                    'id': node['id'], 'bed': node['bed'], 'crop': a['crop'], 'stage': a['stage'], 'day': a['day'],
                    'soil': a['soil'], 'aw_pct': None if bad_sensor else a['aw_pct'],
                    'trigger_pct': a['trigger_pct'], 'target_pct': a['target_pct'],
                    'temp': l['temp'], 'hum': l['hum'], 'batt_v': l['batt_v'], 'batt_pct': int(round(units.batt_pct(l['batt_v']))),
                    'rssi': l['rssi'], 'age_min': int(round((now - l['ts']) / 60.0)),
                    'auto': bool(node.get('auto_irrigate')),
                    'forecast_h': None if ev['forecast_h'] is None else round(ev['forecast_h'], 1),
                    'status': a['status'],
                    'last_water': None if not lastcmd else '{} min at {}'.format(int(lastcmd['run_s'] / 60), units.fmt_time(lastcmd['ts'])),
                    'headline': a['headline'], 'detail': a['detail']})
                actions.append(a)
                for f in ev['faults']:
                    faults.append(dict(f, node=node['id'], bed=node['bed']))
            actions.sort(key=lambda a: URGENCY_ORDER.get(a['urgency'], 3))
            faults.sort(key=lambda f: SEVERITY_ORDER.get(f['severity'], 2))
            bed_of = {n['id']: n['bed'] for n in self.config.nodes()}
            commands = [{'ts': c['ts'], 'time': units.fmt_time(c['ts']), 'node': c['node'],
                         'bed': bed_of.get(c['node'], c['node']), 'run_s': int(c['run_s']),
                         'source': c['source'], 'status': c['status'], 'reason': c['reason']}
                        for c in self.repository.recent_commands(30)]
            return {'farm': self.config.farm_name, 'now': units.fmt_time(now), 'sim': self.sim_clock,
                    'beds': beds, 'actions': actions, 'faults': faults, 'commands': commands,
                    'model': self.evaluator.forecaster.metrics()}

    def series(self, nid, hours=72):
        node = self.config.node(nid)
        if not node:
            return {}
        with self.repository.lock():
            hist = self.repository.readings(nid, int(hours * 4))
            if not hist:
                return {}
            soil = self.config.soil(node)
            stage, _ = self.config.stage_for(node, hist[-1]['ts'])
            ok = [h for h in hist if node['wet_raw'] - 250 < h['soil_raw'] < node['dry_raw'] + 250]  # drop impossible readings
            return {'t': [h['ts'] for h in ok], 'vwc': [round(h['vwc'], 2) for h in ok],
                    'irr': [h['ts'] for h in hist if h['irr_s'] > 0],
                    'trigger': round(units.vwc_from_aw(stage['trigger_aw'], soil), 2),
                    'target': round(units.vwc_from_aw(stage['target_aw'], soil), 2),
                    'wp': soil['wp'], 'fc': soil['fc']}


def wall_time():
    """Fallback when no now_fn is injected along with #sim_clock (clock only)."""
    import time
    return time.time()
