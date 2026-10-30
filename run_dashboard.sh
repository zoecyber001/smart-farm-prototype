#!/usr/bin/env bash
# ==============================================================================
# Smart Farm Dashboard Launcher (Mac / Linux)
# Starts the local dashboard waiting for live Wokwi hardware uplinks.
# To run with pre-filled 5-bed synthetic demo history instead: ./run_dashboard.sh demo
# ==============================================================================

set -e
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "=========================================================="
echo " Starting Smart Farm Operations Dashboard..."
echo "=========================================================="

# Check for Python 3
if command -v python3 &> /dev/null; then
    PY_BIN="python3"
elif command -v python &> /dev/null; then
    PY_BIN="python"
else
    echo "[ERROR] Python 3 is not installed on your system."
    echo "Please download and install Python from https://www.python.org/downloads/"
    exit 1
fi

# Set up virtual environment if not already present
if [ ! -d ".venv" ]; then
    echo "[INFO] Creating lightweight local Python environment..."
    $PY_BIN -m venv .venv
    .venv/bin/pip install --quiet --upgrade pip
    .venv/bin/pip install --quiet -r farm_ai/requirements.txt
fi

# Activate environment
source .venv/bin/activate

# Open browser in the background after 2 seconds
(
    sleep 2
    URL="http://localhost:5000"
    if command -v xdg-open &> /dev/null; then
        xdg-open "$URL" > /dev/null 2>&1 || true
    elif command -v open &> /dev/null; then
        open "$URL" > /dev/null 2>&1 || true
    fi
) &

MODE="${1:-live}"

if [ "$MODE" == "--demo" ] || [ "$MODE" == "demo" ]; then
    echo "[INFO] Mode: PRE-FILLED DEMO (5 simulated beds with historical data)"
    echo "[INFO] Dashboard running at http://localhost:5000"
    echo "[INFO] Press Ctrl+C anytime to stop."
    echo "----------------------------------------------------------"
    python farm_ai/run_demo.py
else
    echo "[INFO] Mode: LIVE HARDWARE (Clean start — waiting for Wokwi node)"
    echo "[INFO] Dashboard running at http://localhost:5000"
    echo "[INFO] Beds will display data the moment your hardware sends an uplink!"
    echo "[INFO] Press Ctrl+C anytime to stop."
    echo "----------------------------------------------------------"
    python farm_ai/server.py --clean
fi
