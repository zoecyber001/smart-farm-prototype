"""FarmSystem: composes the ports into one working system.

    FarmSystem(config=?, repository=?, checker=?, forecaster=?, strategy=?, sim_clock=?)

Every dependency is keyword-injectable; omitted ones get the production default
(JSON config from config/, SQLite storage, rule-based checker, gradient-boosted
forecast, threshold strategy). server.py and run_demo.py only need this construct.
"""
import os
import time

from .advisory import ThresholdAdvisor
from .config_store import BASE, load_default
from .dashboard import DashboardService
from .decisioning import DecisionService
from .evaluation import EvaluationService
from .forecast import DryingForecastModel
from .health import HardwareHealthChecker
from .ingest import IngestService
from .storage import SQLiteRepository


class FarmSystem:
    def __init__(self, config=None, repository=None, db_path=None, checker=None,
                 forecaster=None, strategy=None, sim_clock=False):
        self.config = config or load_default()
        self.sim_clock = sim_clock
        self.repository = repository or SQLiteRepository(db_path or os.path.join(BASE, 'data', 'farm.db'))
        self.checker = checker or HardwareHealthChecker()
        self.forecaster = forecaster or DryingForecastModel(self.config)
        self.strategy = strategy or ThresholdAdvisor()
        self.evaluator = EvaluationService(self.config, self.repository, self.checker,
                                           self.forecaster, self.strategy)
        self.decisions = DecisionService(self.config, self.repository)
        self.ingester = IngestService(self.config, self.repository, self.evaluator,
                                      self.decisions, sim_clock=sim_clock)
        self.dashboard = DashboardService(self.config, self.repository, self.evaluator,
                                          now_fn=self.now, sim_clock=sim_clock)
        self.forecaster.warm_up()

    # ---------------- clock ----------------
    def now(self):
        if self.sim_clock:
            return self.repository.latest_reading_ts() or time.time()
        return time.time()

    # ---------------- API used by server.py / the simulator ----------------
    def ingest(self, pkt, refresh_forecast=True):
        return self.ingester.ingest(pkt, refresh_forecast=refresh_forecast)

    def evaluate(self, node, now=None, refresh_forecast=False):
        return self.evaluator.evaluate(node, self.now() if now is None else now,
                                       refresh_forecast=refresh_forecast)

    def manual(self, nid, run_s):
        node = self.config.node(nid)
        if not node:
            return False
        with self.repository.lock():
            self.repository.insert_command(nid, self.now(), int(run_s), 'manual', 'farmer', 'queued')
        return True

    def state(self):
        return self.dashboard.state()

    def series(self, nid, hours=72):
        return self.dashboard.series(nid, hours)

    def history(self, nid, n=96):
        return self.repository.readings(nid, n)

    @property
    def db(self):
        """Raw sqlite connection, for scripts that already specialise with SQL."""
        return self.repository.connection
