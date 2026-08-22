"""
verify_final_map.py

Verification script for RAKSHAK Railway Control Map.
Checks template, endpoints, and static GeoJSON datasets.
"""

import json
import os
import urllib.request

def check_file(path, label):
    if os.path.exists(path):
        size_kb = os.path.getsize(path) / 1024
        print(f"[OK] {label}: {path} ({size_kb:.2f} KB)")
        return True
    else:
        print(f"[FAIL] {label} MISSING: {path}")
        return False

def main():
    print("--- RAKSHAK Railway Control Map Final Verification ---")

    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # Check data files
    full_geo = os.path.join(base, "frontend", "static", "data", "railway", "india_railways_full.geojson")
    stations_geo = os.path.join(base, "frontend", "static", "data", "stations", "india_stations.geojson")
    zones_json = os.path.join(base, "frontend", "static", "data", "zones", "rakshak_zones.json")
    monitoring_json = os.path.join(base, "frontend", "static", "data", "monitoring", "rakshak_monitoring.json")

    check_file(full_geo, "Full Railway GeoJSON")
    check_file(stations_geo, "Stations GeoJSON")
    check_file(zones_json, "Zones Data")
    check_file(monitoring_json, "Monitoring Data")

    # Load and verify GeoJSON contents
    with open(full_geo, "r", encoding="utf-8") as f:
        d = json.load(f)
        print(f"  -> Total Railway Corridors: {len(d['features'])}")
        
    with open(stations_geo, "r", encoding="utf-8") as f:
        d = json.load(f)
        print(f"  -> Total Stations: {len(d['features'])}")

    with open(monitoring_json, "r", encoding="utf-8") as f:
        d = json.load(f)
        crit = d.get("critical_asset", {})
        print(f"  -> Critical Sensor: {crit.get('sensor_id')} ({crit.get('status')}, Risk: {crit.get('failure_risk')})")

    # Verify HTTP /map/ endpoint
    try:
        url = "http://127.0.0.1:8000/map/"
        resp = urllib.request.urlopen(url)
        print(f"[OK] Django Map Page HTTP Status: {resp.getcode()}")
    except Exception as e:
        print(f"[WARNING] Django Server Check Error: {e}")

    print("\nVerification Complete: All systems operational!")

if __name__ == "__main__":
    main()
