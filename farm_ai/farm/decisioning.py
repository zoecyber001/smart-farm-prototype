"""Decision service: the downlink. What the gateway replies inside the node's
~1.5 s radio receive window.

A farmer's manual request wins (still capped by the soil's safe maximum run);
otherwise the auto policy waters when the advice says water_now, no blocking
fault, and enough time has passed since the last run for the soil to absorb it.
"""
import time


class DecisionService:
    def __init__(self, config, repository):
        self.config = config
        self.repository = repository

    def decide(self, node, ev, ts=None):
        ts = ts if ts is not None else time.time()
        nid = node['id']
        soil = self.config.soil(node)
        # a farmer's manual request wins (still capped by the safety limit)
        q = self.repository.pending_command(nid)
        if q:
            run_s = min(int(q['run_s']), soil['max_run_min'] * 60)
            self.repository.mark_command_sent(q['id'], ts)
            return {'run_s': run_s, 'reason': 'manual request'}
        adv = ev['advice']
        if not node.get('auto_irrigate') or adv['status'] != 'water_now' or ev['blocking']:
            return None
        last = self.repository.latest_sent_command(nid)
        if last and ts - last['ts'] < soil['soak_min'] * 60:
            return None                                    # let the soil absorb the last watering first
        run_s = int(min(adv['minutes'], soil['max_run_min']) * 60)
        if run_s < 60:
            return None
        self.repository.insert_command(nid, ts, run_s, adv['headline'], 'auto', 'sent')
        return {'run_s': run_s, 'reason': adv['headline']}
