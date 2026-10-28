"""Forecast seam: hours-until-the-bed-needs-water, behind the ForecastModel port.

The current engine of the prediction lives in ml.py (a gradient-boosted drying-rate
model). This wrapper isolates the *recipe* — pull the recent trend, one batched
prediction of the next 48 hourly drying rates, accumulate until the trigger level
is reached — so the model can be swapped (different algorithm, a retrained
production model, or a stub in tests) without touching evaluation or advice.
"""
import numpy as np

from . import ml, units
from .config_store import load_default


class DryingForecastModel:
    def __init__(self, config=None, model=None):
        self._config = config or load_default()
        self._model = model          # optional injected predict-function for tests

    def warm_up(self):
        if self._model is None:
            self._model = ml.load_or_train()

    def metrics(self):
        return ml.metrics()

    def hours_to_trigger(self, node, history, latest):
        """history oldest->newest, 15-min spacing. Returns hours until the bed reaches
        its irrigation trigger, or None when the model cannot say."""
        if self._model is None:
            self.warm_up()
        if len(history) < 13:
            return None            # the trend features need at least ~3 h of readings
        soil = self._config.soil(node)
        stage, _ = self._config.stage_for(node, latest['ts'])
        trigger = stage['trigger_aw'] + (0.05 if latest.get('temp', 25) >= 32 else 0)
        trig_vwc = units.vwc_from_aw(trigger, soil)
        if latest['vwc'] <= trig_vwc:
            return 0.0
        # One batched prediction of the drying rate for each of the next 48 hours
        # (hour-of-day and weather vary), then add up the drop until the trigger level.
        vwc0 = latest['vwc']
        h = [x['vwc'] for x in history[-13:]]
        d1, d3 = vwc0 - h[-5], vwc0 - h[-13]
        X = [ml.features(vwc0, vwc0 - d1, vwc0 - d3, latest.get('temp', 26), latest.get('hum', 60),
                         units.local_hour(latest['ts'] + k * 3600), stage['root_mm'], soil) for k in range(1, 49)]
        rates = np.maximum(0.0, self._model.predict(np.array(X)))
        drop = np.cumsum(rates)                      # points of soil water lost after k hours
        need = vwc0 - trig_vwc
        idx = np.nonzero(drop >= need)[0]
        return float(idx[0] + 1) if len(idx) else None
