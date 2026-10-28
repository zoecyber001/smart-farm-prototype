"""Evaluation service: judge one bed once -> an Evaluation dict that decisions,
fault handling and the dashboard all read.

Blends: stored history, the health checker, the forecast model (cached per bed,
refreshed hourly) and the injected advice strategy. Strategies never fetch data;
they receive a complete AdviceContext.
"""
from .advisory import BLOCKING, UNRELIABLE
from .ports import AdviceContext


class EvaluationService:
    def __init__(self, config, repository, checker, forecaster, strategy):
        self.config = config
        self.repository = repository
        self.checker = checker
        self.forecaster = forecaster
        self.strategy = strategy
        self._forecast_cache = {}        # node id -> (computed_ts, hours)

    def evaluate(self, node, now, refresh_forecast=False):
        hist = self.repository.readings(node['id'], 96)
        if not hist:
            return None
        latest = hist[-1]
        # keep the most recent pump run in view even if it is older than the last 96 readings,
        # so a pump fault stays flagged until a healthy run replaces it (manual test run after repair)
        last_ev = self.repository.last_irrigation_event(node['id'])
        hh = hist if (last_ev is None or last_ev['ts'] >= hist[0]['ts']) else [dict(last_ev)] + hist
        faults = self.checker.check(node, hh, now)
        codes = {f['code'] for f in faults}
        f_h = None
        if not (codes & set(UNRELIABLE)):
            cached = self._forecast_cache.get(node['id'])
            if refresh_forecast or cached is None or latest['ts'] - cached[0] >= 3600:
                self._forecast_cache[node['id']] = (latest['ts'], self.forecaster.hours_to_trigger(node, hist, latest))
            f_h = self._forecast_cache[node['id']][1]
        soil = self.config.soil(node)
        stage, days = self.config.stage_for(node, latest['ts'])
        ctx = AdviceContext(node=node, soil=soil, crop=self.config.crop(node), stage=stage, days=days,
                            latest=latest, history=hist, forecast_h=f_h, faults=faults,
                            blocking=[f for f in faults if f['code'] in BLOCKING], now=now)
        adv = self.strategy.advise(ctx)
        per_watering = int(round((stage['target_aw'] - stage['trigger_aw']) * (soil['fc'] - soil['wp'])
                                 / 100.0 * stage['root_mm'] * node['area_m2']))
        if 'NODE_OFFLINE' in codes or 'SENSOR_FAULT' in codes or 'SENSOR_STUCK' in codes:
            why = ('no data for {:.0f} h'.format((now - latest['ts']) / 3600.0) if 'NODE_OFFLINE' in codes
                   else 'the soil sensor is not working')
            adv.update(status='check_hardware', urgency='urgent', minutes=0, litres=per_watering,
                       headline='{}: {}. Check the hardware and water by hand.'.format(node['bed'], why),
                       detail='Moisture advice is switched off because the data cannot be trusted. Until it is fixed, '
                              'check the soil with a finger 5 cm deep and give about {} litres when it feels dry. '
                              '{} stage needs: {}'.format(per_watering, adv['stage'].capitalize(), stage['needs']))
        elif adv['status'] == 'water_now' and 'LOW_BATTERY' in codes:
            adv['detail'] += ' (Battery is also low.)'
        return {'node': node, 'latest': latest, 'faults': faults, 'advice': adv, 'forecast_h': f_h, 'hist': hist,
                'blocking': [f for f in faults if f['code'] in BLOCKING], 'stage': stage}
