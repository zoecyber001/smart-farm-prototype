"""Compatibility shim: advice logic lives in advisory.py (ThresholdAdvisor, a
swappable AdviceStrategy). New code should inject/instantiate strategies there;
this keeps `advisor.advise(...)` working for tests and old call sites.
"""
from .advisory import BLOCKING, UNRELIABLE, ThresholdAdvisor   # noqa: F401
from .config_store import load_default
from .ports import AdviceContext


def _ctx(node, latest, history, forecast_h, faults, now):
    cfg = load_default()
    stage, days = cfg.stage_for(node, latest['ts'])
    faults = list(faults)
    return AdviceContext(node=node, soil=cfg.soil(node), crop=cfg.crop(node), stage=stage, days=days,
                         latest=latest, history=history, forecast_h=forecast_h, faults=faults,
                         blocking=[f for f in faults if f['code'] in BLOCKING], now=now)


def advise(node, latest, history, forecast_h, faults, now):
    return ThresholdAdvisor().advise(_ctx(node, latest, history, forecast_h, faults, now))
