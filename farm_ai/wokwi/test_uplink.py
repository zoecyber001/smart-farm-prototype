#!/usr/bin/env python3
"""End-to-end verification script for Wokwi hardware telemetry ingest."""

import os
import sys
import time

# Ensure farm_ai root is in sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)

from farm import core
from farm.engine import Engine
import server

def test_hardware_uplink():
    print("[TEST] Initializing Farm Engine test instance...")
    test_db = os.path.join(BASE_DIR, "data", "test_wokwi.db")
    if os.path.exists(test_db):
        os.remove(test_db)

    app = server.create_app(db_path=test_db, sim_clock=False)
    client = app.test_client()

    now = time.time()
    # 1. Send dry soil packet (Raw 2950 -> requires irrigation)
    dry_pkt = {
        "node": "N1",
        "ts": now - 900,
        "seq": 1,
        "soil_raw": 2950,
        "temp": 28.5,
        "hum": 50,
        "batt_v": 3.95,
        "irr_s": 0,
        "flow_l": 0.0,
        "pump_ma": 0,
        "rssi": -65
    }
    print("[TEST] Sending dry soil packet from Wokwi node N1...")
    res = client.post("/api/uplink", json=dry_pkt)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.data}"
    data = res.get_json()
    downlink = data.get("downlink", {})
    run_s = downlink.get("run_s", 0)
    print(f"       Server response: HTTP 200 | Downlink run_s: {run_s}s")
    assert run_s > 0, f"Expected positive watering seconds for dry soil, got {run_s}"

    # 2. Send watering execution report with 0 flow (simulating blocked line with run_s >= 30)
    blocked_pkt = {
        "node": "N1",
        "ts": now,
        "seq": 2,
        "soil_raw": 2950,
        "temp": 28.5,
        "hum": 50,
        "batt_v": 3.93,
        "irr_s": 60,
        "flow_l": 0.0,
        "pump_ma": 805,
        "rssi": -65
    }
    print("[TEST] Sending blocked line execution report (0 flow for 60s run)...")
    res2 = client.post("/api/uplink", json=blocked_pkt)
    assert res2.status_code == 200

    # 3. Verify server state flags fault
    state_res = client.get("/api/state")
    assert state_res.status_code == 200
    state = state_res.get_json()
    faults = [f["title"] for f in state.get("faults", []) if f["node"] == "N1"]
    print(f"       Bed A reported faults: {faults}")
    assert any("blocked" in f.lower() for f in faults), "Expected blocked line fault to be registered!"

    print("\n[SUCCESS] All Wokwi hardware packet tests passed successfully!")
    if os.path.exists(test_db):
        os.remove(test_db)

if __name__ == "__main__":
    test_hardware_uplink()
