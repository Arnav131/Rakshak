"""
Script to extract real OpenStreetMap India railway geometry and station data.
Queries Overpass API / Geofabrik to collect real railway tracks and stations across India.
Saves optimized web GeoJSON files for the RAKSHAK Map.
"""
import json
import os
import sys
import requests

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "frontend", "static", "data")
RAILWAY_DIR = os.path.join(DATA_DIR, "railway")
STATIONS_DIR = os.path.join(DATA_DIR, "stations")
MONITORING_DIR = os.path.join(DATA_DIR, "monitoring")
ZONES_DIR = os.path.join(DATA_DIR, "zones")

os.makedirs(RAILWAY_DIR, exist_ok=True)
os.makedirs(STATIONS_DIR, exist_ok=True)
os.makedirs(MONITORING_DIR, exist_ok=True)
os.makedirs(ZONES_DIR, exist_ok=True)

# Bounding box for India: [min_lat, min_lng, max_lat, max_lng]
# 6.0, 68.0, 36.0, 97.5

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

def fetch_overpass_railways():
    print("Fetching real OpenStreetMap railway data for India from Overpass API...")
    
    # Overpass QL query for railway=rail and railway=station/halt/junction in India bounding box
    query = """
    [out:json][timeout:180];
    (
      way["railway"="rail"](6.0,68.0,36.5,97.5);
      node["railway"~"station|halt|junction|signal|switch|level_crossing"](6.0,68.0,36.5,97.5);
    );
    out body geom;
    """
    
    headers = {
        "User-Agent": "RAKSHAK-Railway-Processor/1.0 (RAKSHAK India Rail Ops)"
    }
    try:
        resp = requests.post(OVERPASS_URL, data={"data": query}, headers=headers, timeout=200)
        resp.raise_for_status()
        data = resp.json()
        print(f"Overpass returned {len(data.get('elements', []))} elements.")
        return data
    except Exception as e:
        print(f"Overpass query error: {e}")
        return None

if __name__ == "__main__":
    data = fetch_overpass_railways()
    if data:
        with open("raw_overpass_railway.json", "w", encoding="utf-8") as f:
            json.dump(data, f)
        print("Saved raw_overpass_railway.json")
