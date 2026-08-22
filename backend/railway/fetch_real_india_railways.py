"""
fetch_real_india_railways.py

Fetches complete real OpenStreetMap railway line geometry and station infrastructure across India.
Processes data into GeoJSON format for the RAKSHAK control room map.
"""

import json
import os
import sys
import time
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "frontend", "static", "data")
RAILWAY_DIR = os.path.join(DATA_DIR, "railway")
STATIONS_DIR = os.path.join(DATA_DIR, "stations")
MONITORING_DIR = os.path.join(DATA_DIR, "monitoring")
ZONES_DIR = os.path.join(DATA_DIR, "zones")

os.makedirs(RAILWAY_DIR, exist_ok=True)
os.makedirs(STATIONS_DIR, exist_ok=True)
os.makedirs(MONITORING_DIR, exist_ok=True)
os.makedirs(ZONES_DIR, exist_ok=True)

OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter"
]

def fetch_india_railways():
    # Bounding box for India: [min_lat, min_lng, max_lat, max_lng]
    # Query for ways with railway=rail and nodes with railway in India
    query = """
    [out:json][timeout:120];
    (
      way["railway"="rail"](8.0,68.0,35.5,97.0);
      node["railway"~"station|halt|junction|signal|switch|level_crossing"](8.0,68.0,35.5,97.0);
    );
    out body geom;
    """

    headers = {
        "User-Agent": "RAKSHAK-Railway-Processor/1.0 (RAKSHAK India Rail Ops)"
    }

    for url in OVERPASS_SERVERS:
        print(f"Trying Overpass server: {url}...")
        try:
            resp = requests.post(url, data={"data": query}, headers=headers, timeout=120)
            if resp.status_code == 200:
                data = resp.json()
                print(f"Success! Fetched {len(data.get('elements', []))} elements from {url}")
                return data
            else:
                print(f"Server returned status {resp.status_code}")
        except Exception as e:
            print(f"Failed with server {url}: {e}")

    return None

def safe_prop(val):
    if val is None or val == "" or str(val).strip() == "":
        return "Not available"
    return str(val).strip()

def build_datasets(overpass_data):
    elements = overpass_data.get("elements", [])
    print(f"Processing {len(elements)} raw OSM elements into GeoJSON...")

    rail_features = []
    station_features = []

    for el in elements:
        el_type = el.get("type")
        tags = el.get("tags", {})

        name = safe_prop(tags.get("name"))
        ref = safe_prop(tags.get("ref"))
        operator = safe_prop(tags.get("operator", "Indian Railways"))
        railway_type = safe_prop(tags.get("railway"))
        gauge = safe_prop(tags.get("gauge"))
        electrified = safe_prop(tags.get("electrified"))
        tracks = safe_prop(tags.get("tracks"))
        usage = safe_prop(tags.get("usage"))
        service = safe_prop(tags.get("service"))
        maxspeed = safe_prop(tags.get("maxspeed"))

        if el_type == "way" and tags.get("railway") == "rail":
            geometry = el.get("geometry", [])
            if len(geometry) < 2:
                continue

            coordinates = [[pt["lon"], pt["lat"]] for pt in geometry]

            feature = {
                "type": "Feature",
                "id": f"osm-way-{el['id']}",
                "geometry": {
                    "type": "LineString",
                    "coordinates": coordinates
                },
                "properties": {
                    "osm_id": el["id"],
                    "name": name,
                    "ref": ref,
                    "operator": operator,
                    "railway": railway_type,
                    "gauge": gauge,
                    "electrified": electrified,
                    "tracks": tracks,
                    "usage": usage,
                    "service": service,
                    "maxspeed": maxspeed
                }
            }
            rail_features.append(feature)

        elif el_type == "node" and "railway" in tags:
            lat = el.get("lat")
            lon = el.get("lon")
            if lat is None or lon is None:
                continue

            rw_tag = tags.get("railway")
            feature = {
                "type": "Feature",
                "id": f"osm-node-{el['id']}",
                "geometry": {
                    "type": "Point",
                    "coordinates": [lon, lat]
                },
                "properties": {
                    "osm_id": el["id"],
                    "name": name,
                    "ref": ref,
                    "operator": operator,
                    "railway": rw_tag,
                    "gauge": gauge,
                    "electrified": electrified,
                    "tracks": tracks,
                    "usage": usage,
                    "service": service,
                    "maxspeed": maxspeed
                }
            }
            station_features.append(feature)

    print(f"Built {len(rail_features)} track features and {len(station_features)} station features.")

    # Write GeoJSON files
    full_geojson = {"type": "FeatureCollection", "features": rail_features}
    stations_geojson = {"type": "FeatureCollection", "features": station_features}

    with open(os.path.join(RAILWAY_DIR, "india_railways_full.geojson"), "w", encoding="utf-8") as f:
        json.dump(full_geojson, f)

    with open(os.path.join(RAILWAY_DIR, "india_railways_major.geojson"), "w", encoding="utf-8") as f:
        json.dump(full_geojson, f)  # Full or filtered

    with open(os.path.join(STATIONS_DIR, "india_stations.geojson"), "w", encoding="utf-8") as f:
        json.dump(stations_geojson, f)

    # Build zones
    zones = [
        {
            "id": "ZONE-01",
            "code": "NR",
            "name": "Northern Railway Zone",
            "short_name": "ZONE 01",
            "status": "OPERATIONAL",
            "center": [28.6139, 77.2090], # Delhi
            "zoom": 7,
            "bounds": [[26.0, 74.0], [32.5, 79.5]]
        },
        {
            "id": "ZONE-02",
            "code": "WR",
            "name": "Western Railway Zone",
            "short_name": "ZONE 02",
            "status": "WARNING",
            "center": [21.1702, 72.8311], # Gujarat / Mumbai
            "zoom": 7,
            "bounds": [[18.5, 69.5], [24.5, 74.5]]
        },
        {
            "id": "ZONE-03",
            "code": "CR",
            "name": "Central Railway Zone",
            "short_name": "ZONE 03",
            "status": "OPERATIONAL",
            "center": [19.0760, 72.8777], # Maharashtra
            "zoom": 7,
            "bounds": [[17.0, 72.5], [21.5, 79.5]]
        },
        {
            "id": "ZONE-04",
            "code": "SR",
            "name": "Southern Railway Zone",
            "short_name": "ZONE 04",
            "status": "CRITICAL",
            "center": [13.0827, 80.2707], # Chennai / TN
            "zoom": 8,
            "bounds": [[8.0, 76.0], [14.0, 80.5]]
        },
        {
            "id": "ZONE-05",
            "code": "ER",
            "name": "Eastern Railway Zone",
            "short_name": "ZONE 05",
            "status": "OPERATIONAL",
            "center": [22.5726, 88.3639], # West Bengal
            "zoom": 7,
            "bounds": [[21.5, 86.0], [26.0, 89.5]]
        },
        {
            "id": "ZONE-06",
            "code": "SCR",
            "name": "South Central Railway Zone",
            "short_name": "ZONE 06",
            "status": "OPERATIONAL",
            "center": [17.3850, 78.4867], # Telangana / AP
            "zoom": 7,
            "bounds": [[14.0, 77.0], [19.0, 82.5]]
        }
    ]

    with open(os.path.join(ZONES_DIR, "rakshak_zones.json"), "w", encoding="utf-8") as f:
        json.dump(zones, f, indent=2)

    # Find a real OSM track segment in Zone 04 for critical asset VIB-04A
    z4_track_id = None
    z4_coords = [80.2707, 13.0827]
    for feat in rail_features:
        coords = feat["geometry"]["coordinates"]
        if coords:
            lon, lat = coords[0]
            if 8.0 <= lat <= 14.5 and 76.0 <= lon <= 81.0:
                z4_track_id = feat["id"]
                z4_coords = coords[len(coords)//2]
                break
    if not z4_track_id and rail_features:
        z4_track_id = rail_features[0]["id"]
        z4_coords = rail_features[0]["geometry"]["coordinates"][0]

    monitored_tracks = {}
    if z4_track_id:
        monitored_tracks[z4_track_id] = "critical"

    # Add warning and healthy track designations on real OSM segments
    for idx, feat in enumerate(rail_features):
        tid = feat["id"]
        if tid == z4_track_id:
            continue
        if idx % 15 == 0:
            monitored_tracks[tid] = "warning"
        elif idx % 8 == 0:
            monitored_tracks[tid] = "healthy"

    monitoring = {
        "critical_asset": {
            "sensor_id": "VIB-04A",
            "zone": "ZONE 04",
            "status": "CRITICAL",
            "reading": "5.8 mm/s",
            "failure_risk": "92%",
            "position": {
                "lat": z4_coords[1],
                "lng": z4_coords[0]
            },
            "affected_track_id": z4_track_id,
            "waveform": [
                1.2, 1.1, 1.3, 1.2, 1.4, 1.2, 1.1, 1.5, 3.8, 5.8, 5.4, 4.9, 3.2, 1.8, 1.3, 1.2
            ],
            "maintenance_history": [
                "• Inspection completed (2026-07-28)",
                "• Sensor calibrated (2026-07-15)",
                "• Fastening checked (2026-06-30)"
            ],
            "action_required": "IMMEDIATE INSPECTION"
        },
        "monitored_tracks": monitored_tracks
    }

    with open(os.path.join(MONITORING_DIR, "rakshak_monitoring.json"), "w", encoding="utf-8") as f:
        json.dump(monitoring, f, indent=2)

    print("All datasets generated successfully!")

if __name__ == "__main__":
    data = fetch_india_railways()
    if data:
        build_datasets(data)
    else:
        print("Failed to fetch Overpass data.")
