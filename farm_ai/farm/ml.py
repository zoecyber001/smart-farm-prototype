"""AI component: learns how fast each bed dries (points of soil water per hour) from weather, time of day,
soil and recent trend, then converts that into 'hours until this bed needs water'.
Trained on simulated drying behaviour at first; retrain on the farm's own logs after a few weeks."""
import math, os, json, random
import numpy as np
import joblib
from sklearn.ensemble import HistGradientBoostingRegressor
from . import core
from .simulator import Weather, Bed, TICK

MODEL_PATH = os.path.join(core.BASE, 'data', 'drying_model.joblib')
METRICS_PATH = os.path.join(core.BASE, 'data', 'drying_model_metrics.json')
AHEAD = 24     # 6 hours of 15-minute ticks


def features(vwc_now, vwc_1h, vwc_3h, temp, hum, hour, root_mm, soil):
    aw = core.aw_from_vwc(vwc_now, soil)
    return [vwc_now, aw, vwc_now - vwc_1h, vwc_now - vwc_3h, temp, hum,
            math.sin(2 * math.pi * hour / 24), math.cos(2 * math.pi * hour / 24), root_mm]


def _gen_bed(seed, days=25):
    rng = random.Random(seed)
    node = dict(rng.choice(core.nodes()))
    node['soil'] = rng.choice(list(core.cfg()['soils'].keys()))
    node['crop'] = rng.choice(list(core.cfg()['crops'].keys()))
    node['planted'] = '2026-09-01'
    soil = core.soil_of(node)
    start = core.planted_ts(node) + rng.uniform(5, 50) * 86400
    bed = Bed(node, et_scale=rng.uniform(0.7, 1.6), rng=rng)
    w = Weather()
    rows = []
    for k in range(days * 96):
        ts = start + k * TICK
        temp, hum = bed.step(ts, w)
        stage, _ = core.stage_for(node, ts)
        aw = core.aw_from_vwc(bed.vwc, soil)
        irrigated = 0
        if aw < stage['trigger_aw'] + rng.uniform(-0.05, 0.02):       # a farmer who waters roughly at the trigger
            bed.irrigate((stage['target_aw'] - aw) * (soil['fc'] - soil['wp']) / 100.0 * stage['root_mm'] * node['area_m2'], ts)
            irrigated = 1
        rows.append((ts, bed.vwc, temp, hum, stage['root_mm'], bed.rain_mm, irrigated))
    return soil, rows


def build_dataset(seeds):
    X, y = [], []
    for sd in seeds:
        soil, rows = _gen_bed(sd)
        for i in range(12, len(rows) - AHEAD):
            fut = rows[i + 1: i + 1 + AHEAD + 2]
            if any(r[6] or r[5] > 0 for r in fut) or rows[i][5] > 0:    # keep only clean drying windows
                continue
            ts, vwc, temp, hum, root, _, _ = rows[i]
            target = (vwc - rows[i + AHEAD][1]) / (AHEAD * TICK / 3600.0)   # points per hour (positive = drying)
            X.append(features(vwc, rows[i - 4][1], rows[i - 12][1], temp, hum, core.local_hour(ts), root, soil))
            y.append(target)
    return np.array(X), np.array(y)


def train(seed_train=range(40), seed_test=range(100, 108)):
    Xtr, ytr = build_dataset(seed_train)
    Xte, yte = build_dataset(seed_test)
    model = HistGradientBoostingRegressor(max_iter=200, learning_rate=0.08, max_depth=4, random_state=0)
    model.fit(Xtr, ytr)
    mae = float(np.mean(np.abs(model.predict(Xte) - yte)))
    base = float(np.mean(np.abs(np.mean(ytr) - yte)))
    metrics = {'mae_pts_per_h': round(mae, 4), 'baseline_mae_pts_per_h': round(base, 4),
               'improvement_pct': round((1 - mae / base) * 100, 1), 'train_rows': int(len(ytr)), 'test_rows': int(len(yte))}
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    with open(METRICS_PATH, 'w') as f:
        json.dump(metrics, f)
    return model, metrics


_MODEL = None

def load_or_train():
    global _MODEL
    if _MODEL is None:
        if os.path.exists(MODEL_PATH):
            try:
                _MODEL = joblib.load(MODEL_PATH)
            except Exception:
                _MODEL = None
        if _MODEL is None:
            _MODEL, _ = train()
    return _MODEL


def metrics():
    if os.path.exists(METRICS_PATH):
        with open(METRICS_PATH) as f:
            return json.load(f)
    return {}


def hours_to_trigger(node, history, latest):
    """Compatibility: the forecast recipe lives in forecast.py (DryingForecastModel,
    swappable behind the ForecastModel port)."""
    from .forecast import DryingForecastModel
    return DryingForecastModel().hours_to_trigger(node, history, latest)
