"""Flask server: LoRa gateway posts packets to /api/uplink; farmer opens / in any browser on the LAN. No internet needed."""
import os
from flask import Flask, jsonify, request, send_from_directory
from farm.engine import Engine
from farm import core


def create_app(engine=None, db_path=None, sim_clock=False):
    eng = engine or Engine(db_path or os.path.join(core.BASE, 'data', 'farm.db'), sim_clock=sim_clock)
    app = Flask(__name__, static_folder='static', static_url_path='/static')
    app.config['engine'] = eng

    @app.route('/')
    def index():
        return send_from_directory(app.static_folder, 'index.html')

    @app.route('/service-worker.js')
    def service_worker():
        resp = send_from_directory(app.static_folder, 'sw.js')
        # registered at '/' scope so the app itself can be cached/installed
        resp.headers['Service-Worker-Allowed'] = '/'
        return resp

    @app.route('/api/state')
    def state():
        return jsonify(eng.state())

    @app.route('/api/history/<nid>')
    def history(nid):
        return jsonify(eng.series(nid, float(request.args.get('hours', 72))))

    @app.route('/api/uplink', methods=['POST'])
    def uplink():
        pkt = request.get_json(force=True, silent=True) or {}
        need = ('node', 'ts', 'seq', 'soil_raw', 'batt_v')
        if any(k not in pkt for k in need):
            return jsonify({'error': 'missing fields: ' + ', '.join(k for k in need if k not in pkt)}), 400
        res = eng.ingest(pkt)
        if 'error' in res:
            return jsonify(res), 404
        return jsonify({'downlink': res['downlink']})     # gateway forwards this to the node inside its RX window

    @app.route('/api/manual', methods=['POST'])
    def manual():
        d = request.get_json(force=True, silent=True) or {}
        ok = eng.manual(d.get('node'), max(30, min(int(d.get('run_s', 300)), 900)))
        return jsonify({'ok': ok}), (200 if ok else 404)

    return app


if __name__ == '__main__':
    create_app().run(host='0.0.0.0', port=5000)
