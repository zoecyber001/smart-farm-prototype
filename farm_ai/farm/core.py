"""Compatibility shim: core.py moved into config_store.py (configuration) and
units.py (conversions). New code should import from those; this keeps the old
`from farm import core` path working for tests, the simulator and scripts.
"""
from .config_store import BASE, FarmConfig, load_default          # noqa: F401
from .units import (aw_from_vwc, batt_pct, fmt_time, local_hour,    # noqa: F401
                    raw_to_vwc, vwc_from_aw, vwc_to_raw)


def cfg():
    """The old shape: {'farm': ..., 'crops': ..., 'soils': ...}."""
    return load_default().as_legacy_dict()


def nodes():
    return load_default().nodes()


def node_cfg(nid):
    return load_default().node(nid)


def soil_of(node):
    return load_default().soil(node)


def crop_of(node):
    return load_default().crop(node)


def planted_ts(node):
    return load_default().planted_ts(node)


def stage_for(node, ts):
    return load_default().stage_for(node, ts)
