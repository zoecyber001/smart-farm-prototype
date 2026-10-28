#!/usr/bin/env python3
"""Wokwi Gateway Bridge & Live Review Harness.

Bridges the Wokwi ESP32 hardware simulation to the Smart Farm backend and
dashboard. Uses standard library (zero external dependencies) to forward packets
to /api/uplink and compute downlinks.

Usage:
    1. Standard Pipe / Interactive Terminal Mode:
       python wokwi/wokwi_gateway.py --server http://localhost:5000

    2. Automated Review Demo Mode (Injects live Wokwi packets):
       python wokwi/wokwi_gateway.py --demo
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request


def parse_telemetry(line: str) -> dict:
  """Parses CSV telemetry line: node,seq,soil_raw,temp_x10,hum,batt_mV,irr_s,flow_mL,pump_mA."""
  # Strip any prefix like 'UPLINK PACKET: ' or 'UPLINK:' if copied from Wokwi console
  if "UPLINK PACKET:" in line:
    line = line.split("UPLINK PACKET:")[1].strip()
  elif "UPLINK:" in line:
    line = line.split("UPLINK:")[1].strip()

  parts = [p.strip() for p in line.split(",") if p.strip()]
  if len(parts) < 9:
    raise ValueError(f"Expected 9 CSV fields, got {len(parts)}: {line}")

  node = parts[0]
  seq = int(parts[1])
  soil_raw = int(parts[2])
  temp = int(parts[3]) / 10.0
  hum = int(parts[4])
  batt_v = int(parts[5]) / 1000.0
  irr_s = int(parts[6])
  flow_l = int(parts[7]) / 1000.0
  pump_ma = int(parts[8])

  return {
      "node": node,
      "ts": time.time(),
      "seq": seq,
      "soil_raw": soil_raw,
      "temp": temp,
      "hum": hum,
      "batt_v": batt_v,
      "irr_s": irr_s,
      "flow_l": flow_l,
      "pump_ma": pump_ma,
      "rssi": -65,
  }


def send_uplink(server_url: str, pkt: dict):
  """Dispatches packet to Flask server via urllib and retrieves downlink decision."""
  endpoint = f"{server_url.rstrip('/')}/api/uplink"
  data = json.dumps(pkt).encode("utf-8")
  req = urllib.request.Request(
      endpoint, data=data, headers={"Content-Type": "application/json"}
  )

  for attempt in range(2):
    try:
      with urllib.request.urlopen(req, timeout=2.5) as resp:
        if resp.status != 200:
          print(f"[ERROR] Server responded with HTTP {resp.status}")
          return None

        payload = json.loads(resp.read().decode("utf-8"))
        downlink = payload.get("downlink") or {}
        run_s = int(downlink.get("run_s", 0))
        ack_str = f"ACK,{pkt['node']},{pkt['seq']},{run_s}"

        print("\n----------------- GATEWAY DISPATCH -----------------")
        print(
            f" [->] Ingested Node: {pkt['node']} | Seq: {pkt['seq']} | Soil:"
            f" {pkt['soil_raw']} | Batt: {pkt['batt_v']:.2f}V"
        )
        print(
            f" [<-] Server AI Decision: Water for {run_s}s (Downlink: '{ack_str}')"
        )
        print("----------------------------------------------------\n")
        return ack_str
    except urllib.error.HTTPError as he:
      print(
          f"[ERROR] HTTP Error {he.code}:"
          f" {he.read().decode('utf-8', errors='ignore')}"
      )
      return None
    except Exception as e:
      if attempt == 0:
        time.sleep(0.5)
        continue
      print(f"[ERROR] Failed to reach server at {endpoint}: {e}")
      return None


def run_interactive(server_url: str):
  """Interactive gateway loop reading lines from standard input."""
  print(f"[GATEWAY] Listening for Wokwi telemetry packets...")
  print(f"[GATEWAY] Target Server: {server_url}")
  print(
      "[GATEWAY] Paste or pipe raw CSV packets (e.g."
      " 'N1,1,2850,265,58,3950,0,0,0'):\n"
  )

  while True:
    try:
      line = sys.stdin.readline()
      if not line:
        break
      line = line.strip()
      if not line or line.startswith("#") or line.startswith("="):
        continue

      # Check if this line contains telemetry
      if any(
          line.startswith(prefix)
          for prefix in ("N1,", "N2,", "N3,", "N4,", "N5,")
      ) or ("," in line and len(line.split(",")) >= 9):
        try:
          pkt = parse_telemetry(line)
          ack = send_uplink(server_url, pkt)
          if ack:
            print(f">>> Copy this downlink reply into Wokwi console:  {ack}\n")
        except Exception as err:
          print(f"[WARN] Could not parse packet: {err}")
    except KeyboardInterrupt:
      print("\n[GATEWAY] Shutting down.")
      break


def run_demo(server_url: str):
  """Automated review demonstration simulating live Wokwi hardware states."""
  print(f"[DEMO] Starting Wokwi Hardware Review Sequence...")
  print(f"[DEMO] Server: {server_url}\n")

  scenarios = [
      (
          "Healthy telemetry: Soil dry (needs water)",
          "N1,1,2950,270,55,3980,0,0,0",
      ),
      (
          "Post-watering report: 300s delivered, 20L flow, 810mA pump",
          "N1,2,1650,265,60,3960,300,20000,810",
      ),
      (
          "Fault demo 1: Blocked Drip Line (0L flow during 60s attempt)",
          "N1,3,2900,280,50,3940,60,0,805",
      ),
      (
          "Fault demo 2: Cut Probe Sensor (Raw ADC 4095)",
          "N1,4,4095,282,49,3920,0,0,0",
      ),
      (
          "Recovery: Repaired line & sensor, healthy test run",
          "N1,5,1500,250,65,3900,60,4000,800",
      ),
  ]

  for desc, raw in scenarios:
    print(f"\n>>> SCENARIO: {desc}")
    print(f"    Raw Hardware Packet: {raw}")
    pkt = parse_telemetry(raw)
    send_uplink(server_url, pkt)
    time.sleep(1.0)

  print(
      "\n[DEMO] Review sequence complete. Refresh dashboard at"
      f" {server_url} to inspect state."
  )


if __name__ == "__main__":
  parser = argparse.ArgumentParser(
      description="Wokwi Hardware Simulation Gateway Bridge"
  )
  parser.add_argument(
      "--server",
      default="http://localhost:5000",
      help="Farm AI Server URL (default: http://localhost:5000)",
  )
  parser.add_argument(
      "--demo",
      action="store_true",
      help="Run automated review scenarios against server",
  )
  args = parser.parse_args()

  if args.demo:
    run_demo(args.server)
  else:
    run_interactive(args.server)
