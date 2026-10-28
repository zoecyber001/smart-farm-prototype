"""Gateway process (Raspberry Pi or laptop next to the LoRa bridge).  *** Not yet tested with real radio hardware ***
Reads packets from the bridge, forwards them to the farm server, and sends the server's watering decision straight back.

    pip install pyserial requests
    python gateway/lora_gateway.py --port /dev/ttyUSB0 --server http://localhost:5000
"""
import argparse, time
import requests, serial


def parse(payload, rssi):
    # node,seq,soil_raw,temp_x10,hum,batt_mV,irr_s,flow_mL,pump_mA
    p = payload.split(',')
    return {'node': p[0], 'ts': time.time(), 'seq': int(p[1]), 'soil_raw': int(p[2]), 'temp': int(p[3]) / 10.0, 'hum': int(p[4]),
            'batt_v': int(p[5]) / 1000.0, 'irr_s': int(p[6]), 'flow_l': int(p[7]) / 1000.0, 'pump_ma': int(p[8]), 'rssi': rssi}


ap = argparse.ArgumentParser()
ap.add_argument('--port', required=True)
ap.add_argument('--server', default='http://localhost:5000')
a = ap.parse_args()
ser = serial.Serial(a.port, 115200, timeout=1)
print('Gateway listening on', a.port)
while True:
    line = ser.readline().decode('utf8', 'ignore').strip()
    if not line.startswith('RX,'):
        continue
    try:
        _, rssi, payload = line.split(',', 2)
        pkt = parse(payload, int(rssi))
        r = requests.post(a.server + '/api/uplink', json=pkt, timeout=1.0)       # must answer inside the node's ~1.5 s window
        dl = (r.json() or {}).get('downlink')
        run_s = int(dl['run_s']) if dl else 0
        ser.write('TX,ACK,{},{},{}\n'.format(pkt['node'], pkt['seq'], run_s).encode())
        print(time.strftime('%H:%M:%S'), pkt['node'], 'raw', pkt['soil_raw'], 'batt', pkt['batt_v'], '-> run', run_s, 's')
    except Exception as e:
        print('bad packet or server error:', e, '|', line)
