import urllib.request
import json
data = json.dumps({"sensor_id":"S1", "ambient_temp": 30.0, "humidity": 50.0, "vibration_rms": 2.5, "gauge_width": 1676.0}).encode('utf-8')
req = urllib.request.Request('http://localhost:8765/api/ai/predict/', data=data, headers={'Content-Type': 'application/json'})
try:
    res = urllib.request.urlopen(req)
    print("STATUS:", res.status)
    print(res.read().decode())
except urllib.error.HTTPError as e:
    print("STATUS:", e.code)
    print(e.read().decode())
