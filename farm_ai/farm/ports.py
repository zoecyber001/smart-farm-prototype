"""Ports: the interfaces the system is built against.

Every service below server.py depends on these protocols, not on concrete classes.
That gives the system four seams you can swap at construction time without touching
anything else:

    Engine(db_path, repository=..., checker=..., forecaster=..., strategy=...)

- Repository      where readings and commands live (SQLite today, anything tomorrow)
- HealthChecker   judges hardware state from raw readings
- AdviceStrategy  turns one evaluated bed into farmer-facing advice
- ForecastModel   predicts hours until a bed needs water
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

Advice = Dict[str, Any]
Fault = Dict[str, Any]
Reading = Dict[str, Any]


@dataclass
class AdviceContext:
    """Everything a strategy needs to judge one bed. Built once by the evaluation
    service so strategies never reach back into config, storage or the clock."""
    node: Dict[str, Any]
    soil: Dict[str, Any]
    crop: Dict[str, Any]
    stage: Dict[str, Any]
    days: int
    latest: Reading
    history: List[Reading]
    forecast_h: Optional[float]
    faults: List[Fault]
    blocking: List[Fault]
    now: float


@runtime_checkable
class AdviceStrategy(Protocol):
    def advise(self, context: AdviceContext) -> Advice: ...


@runtime_checkable
class HealthChecker(Protocol):
    def check(self, node: Dict[str, Any], readings: List[Reading], now: float,
              interval: int = 900) -> List[Fault]: ...


@runtime_checkable
class ForecastModel(Protocol):
    def warm_up(self) -> None: ...
    def metrics(self) -> Dict[str, Any]: ...
    def hours_to_trigger(self, node: Dict[str, Any], history: List[Reading],
                         latest: Reading) -> Optional[float]: ...


@runtime_checkable
class Repository(Protocol):
    """Storage of readings + watering commands. Implementations own their
    connection, locking and schema; return rows as plain dicts."""
    connection: Any

    def lock(self): ...                                             # context manager serialising write+read runs
    def insert_reading(self, node: str, ts: float, seq: int, soil_raw: int, temp: float, hum: float,
                       batt_v: float, irr_s: int, flow_l: float, pump_ma: int, rssi: int,
                       vwc: float, aw: float) -> None: ...
    def readings(self, node: str, n: int = 96) -> List[Reading]: ...  # oldest -> newest, last n
    def last_irrigation_event(self, node: str, min_seconds: int = 30) -> Optional[Reading]: ...
    def latest_reading_ts(self) -> Optional[float]: ...

    def insert_command(self, node: str, ts: float, run_s: int, reason: str, source: str,
                       status: str) -> int: ...
    def pending_command(self, node: str) -> Optional[Dict[str, Any]]: ...
    def latest_sent_command(self, node: str) -> Optional[Dict[str, Any]]: ...
    def mark_command_sent(self, command_id: int, ts: float) -> None: ...
    def recent_commands(self, limit: int = 30) -> List[Dict[str, Any]]: ...
