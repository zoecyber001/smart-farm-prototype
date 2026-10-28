"""Configuration layer: the farm's beds, soils and crops, loaded once from config/*.json.

Everything above this file asks a FarmConfig instance; nothing re-reads JSON from
disk per query. Swap in another FarmConfig (e.g. built from a database or remote
sync) and the engine, simulator and strategies keep working unchanged.
"""
import json
import os
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DIR = os.path.join(BASE, 'config')


class FarmConfig:
    """Read-only view over the three configuration documents."""

    def __init__(self, farm_doc, crops_doc, soils_doc):
        self._farm = farm_doc
        self._crops = crops_doc
        self._soils = soils_doc
        self._by_id = {n['id']: n for n in farm_doc['nodes']}

    @classmethod
    def from_dir(cls, directory):
        docs = {}
        for name in ('farm', 'crops', 'soils'):
            with open(os.path.join(directory, name + '.json'), encoding='utf8') as f:
                docs[name] = json.load(f)
        return cls(docs['farm'], docs['crops'], docs['soils'])

    # ---- farm ----
    @property
    def farm_name(self):
        return self._farm['farm_name']

    @property
    def uplink_interval_s(self):
        return self._farm.get('uplink_interval_s', 900)

    def nodes(self):
        return self._farm['nodes']

    def node(self, nid):
        return self._by_id.get(nid)

    # ---- domain lookups ----
    def soil(self, node):
        return self._soils[node['soil']]

    def crop(self, node):
        return self._crops[node['crop']]

    # ---- time in the crop calendar ----
    def planted_ts(self, node):
        return datetime.strptime(node['planted'], '%Y-%m-%d') \
            .replace(tzinfo=timezone.utc).timestamp()

    def stage_for(self, node, ts):
        """Current growth stage for a reading timestamp; returns (stage, day_number)."""
        crop = self.crop(node)
        days = (ts - self.planted_ts(node)) / 86400.0
        stage = crop['stages'][0] if days < 0 else crop['stages'][-1]
        for s in crop['stages']:
            if s['from_day'] <= days <= s['to_day']:
                stage = s
                break
        return stage, int(days)

    def as_legacy_dict(self):
        """The old cfg() shape, for code that still wants the raw documents."""
        return {'farm': self._farm, 'crops': self._crops, 'soils': self._soils}


_default = None


def load_default():
    """The farm on this machine, loaded once from config/. Tests can construct
    their own FarmConfig instead and inject it."""
    global _default
    if _default is None:
        _default = FarmConfig.from_dir(DEFAULT_DIR)
    return _default
