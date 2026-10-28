"""Ingest service: one radio packet in, one decision out.

Conversions live in units.py; storage in the repository; judgement in the
evaluation service; the reply in the decision service. The lock is the
repository's, so ingest and the dashboard never interleave on the same bed.
"""
import time

from . import units


class IngestService:
    def __init__(self, config, repository, evaluator, decisions, sim_clock=False):
        self.config = config
        self.repository = repository
        self.evaluator = evaluator
        self.decisions = decisions
        self.sim_clock = sim_clock

    def _now(self):
        if self.sim_clock:
            return self.repository.latest_reading_ts() or time.time()
        return time.time()

    def ingest(self, pkt, refresh_forecast=True):
        node = self.config.node(pkt['node'])
        if node is None:
            return {'error': 'unknown node'}
        with self.repository.lock():
            soil = self.config.soil(node)
            vwc = units.raw_to_vwc(pkt['soil_raw'], node, soil)
            aw = units.aw_from_vwc(vwc, soil)
            self.repository.insert_reading(pkt['node'], pkt['ts'], pkt['seq'], pkt['soil_raw'],
                                           pkt.get('temp', 25), pkt.get('hum', 60), pkt['batt_v'],
                                           pkt.get('irr_s', 0), pkt.get('flow_l', 0), pkt.get('pump_ma', 0),
                                           pkt.get('rssi', 0), vwc, aw)
            now = self._now() if self.sim_clock else pkt['ts']
            ev = self.evaluator.evaluate(node, now, refresh_forecast=refresh_forecast)
            return {'downlink': self.decisions.decide(node, ev, pkt['ts']),
                    'advice': ev['advice'], 'faults': ev['faults']}
