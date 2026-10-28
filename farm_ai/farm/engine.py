"""Compatibility: `Engine` is now FarmSystem (system.py) with the old constructor
signature. The god-class is gone: storage -> storage.py, evaluation -> evaluation.py,
decisions -> decisioning.py, ingest -> ingest.py, dashboard views -> dashboard.py.
New code should use FarmSystem directly; server.py and the tests keep working.
"""
from .advisory import BLOCKING, UNRELIABLE                     # noqa: F401
from .system import FarmSystem


class Engine(FarmSystem):
    def __init__(self, db_path=None, sim_clock=False, config=None, repository=None,
                 checker=None, forecaster=None, strategy=None):
        super(Engine, self).__init__(config=config, repository=repository, db_path=db_path,
                                     checker=checker, forecaster=forecaster, strategy=strategy,
                                     sim_clock=sim_clock)
