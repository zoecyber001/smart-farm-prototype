#!/usr/bin/env python3
"""Hands-free gateway bridge for a Wokwi CLI simulation.

Spawns `wokwi-cli --interactive` on this project (or reads from nothing if
WOKWI_CLI_TOKEN is missing), watches the simulator's serial output for
telemetry packets (`UPLINK PACKET: N1,...`), POSTs each one to the farm
server's /api/uplink, and writes the returned `ACK,<node>,<seq>,<run_s>`
reply straight back into the simulator's serial input - the exact loop a
human would do by copy-paste, done automatically.

Usage:
  WOKWI_CLI_TOKEN=wok_xxx python3 auto_bridge.py --server http://localhost:5000

Dry-run (no token, no sim): feed sample serial lines through the parser:
  python3 auto_bridge.py --self-test

Serial keyboard is also interactive: type lines on stdin to send manually.
"""
import argparse
import json
import os
import subprocess
import sys
import threading
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)  # so `import wokwi_gateway` resolves next to this file


def mkpost(server):
    def post(pkt):
        data = json.dumps(pkt).encode()
        req = urllib.request.Request(server.rstrip("/") + "/api/uplink", data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            out = json.loads(r.read().decode())
        dl = out.get("downlink") or {}
        run_s = int(dl.get("run_s", 0))
        return f"ACK,{pkt['node']},{pkt['seq']},{run_s}"
    return post


def feed_lines(lines, server):
    """Reuse wokwi_gateway.parse_telemetry to map serial lines to API packets."""
    import wokwi_gateway as gw
    post = mkpost(server)
    n = 0
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        try:
            pkt = gw.parse_telemetry(line)
        except ValueError:
            continue
        ack = post(pkt)
        n += 1
        print(f"[auto-bridge] uplink {pkt['node']} seq={pkt['seq']} -> {ack}", flush=True)
    return n


def self_test(server):
    samples = [
        "UPLINK PACKET: N1,1,2950,270,55,3980,0,0,0",
        "UPLINK PACKET: N1,4,4095,282,49,3920,0,0,0",
        "not telemetry",
    ]
    n = feed_lines(samples, server)
    print(f"[self-test] forwarded {n}-ish (both valid samples parsed & posted)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="http://localhost:5000")
    ap.add_argument("--timeout", default="0", help="sim timeout ms; 0 = run forever")
    ap.add_argument("--manual", action="store_true",
                    help="no sim: read pasted serial lines from stdin, print the ACK")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        self_test(a.server)
        return

    if a.manual:
        print("[manual-bridge] paste a UPLINK line, get the ACK back (Ctrl-C to exit):",
              flush=True)
        for line in sys.stdin:
            line = line.strip()
            if "UPLINK PACKET:" not in line and not line.startswith("N"):
                continue
            try:
                import wokwi_gateway as gw
                pkt = gw.parse_telemetry(line)
                print(mkpost(a.server)(pkt), flush=True)
            except Exception as e:
                print(f"[manual-bridge] skipped ({type(e).__name__})", flush=True)
        return

    token = os.environ.get("WOKWI_CLI_TOKEN")
    if not token:
        print("Missing WOKWI_CLI_TOKEN. Get one at https://wokwi.com/dashboard/ci "
              "(needs only wokwi.com - reachable here) and export it, e.g.:")
        print("  WOKWI_CLI_TOKEN=$(cat ~/.wokwi/cli_token) python3 auto_bridge.py")
        sys.exit(2)

    env = dict(os.environ, WOKWI_CLI_TOKEN=token)
    cmd = ["wokwi-cli", "--interactive", "--timeout", a.timeout, "."]
    child = subprocess.Popen(cmd, cwd=HERE, env=env,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=None, text=True, bufsize=1)
    print(f"[auto-bridge] sim pid {child.pid}; watching serial...", flush=True)

    import wokwi_gateway as gw
    post = mkpost(a.server)

    def reader():
        for line in child.stdout:
            sys.stdout.write(line)              # mirror serial to terminal
            line = line.strip()
            if "UPLINK PACKET:" in line or ("," in line and line.split(",")[0].startswith("N")):
                try:
                    pkt = gw.parse_telemetry(line)
                    ack = post(pkt)
                    child.stdin.write(ack + "\n")
                    child.stdin.flush()
                    print(f">>> auto-bridge replied {ack}", flush=True)
                except Exception as e:
                    print(f"[auto-bridge] skipped line ({type(e).__name__}): {e}", flush=True)

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    try:                                        # forward manual serial input
        for line in sys.stdin:
            child.stdin.write(line)
            child.stdin.flush()
    except KeyboardInterrupt:
        pass
    finally:
        child.terminate()


if __name__ == "__main__":
    main()
