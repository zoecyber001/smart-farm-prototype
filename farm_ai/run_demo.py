"""Run the whole prototype on your laptop: simulated farm + gateway brain + dashboard (offline).
    python run_demo.py                 # then open http://localhost:5000
    python run_demo.py --prefill-days 4 --tick-seconds 0.4
"""
import argparse, os, threading, time
from werkzeug.serving import make_server
from farm.engine import Engine
from farm import core, simulator as sim
import server

ap = argparse.ArgumentParser()
ap.add_argument('--port', type=int, default=5000)
ap.add_argument('--prefill-days', type=float, default=4.0, help='simulated days generated instantly so the dashboard starts with history')
ap.add_argument('--tick-seconds', type=float, default=0.6, help='real seconds per simulated 15-minute step (0.6 = a day in ~1 minute)')
a = ap.parse_args()

db = os.path.join(core.BASE, 'data', 'demo.db')
if os.path.exists(db):
    os.remove(db)
eng = Engine(db, sim_clock=True)
start = 1792540800.0                              # 2026-10-21 00:00 UTC
sims = sim.make_sims(start)
weather = sim.Weather()
n_pre = int(a.prefill_days * 96)
print('Generating {} simulated days of farm history...'.format(a.prefill_days))
sim.run(eng, sims, start, n_pre, weather)

app = server.create_app(engine=eng)
srv = make_server('0.0.0.0', a.port, app, threaded=True)
threading.Thread(target=srv.serve_forever, daemon=True).start()
print('Dashboard: http://localhost:{}   (Ctrl+C to stop)'.format(a.port))

k = n_pre
try:
    while True:
        sim.tick_all(eng, sims, start + k * sim.TICK, weather)
        k += 1
        time.sleep(a.tick_seconds)
except KeyboardInterrupt:
    srv.shutdown()
