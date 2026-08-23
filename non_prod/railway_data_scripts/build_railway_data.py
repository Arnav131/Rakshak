"""
build_railway_data.py

RAKSHAK India Railway Data Pipeline.
Processes real OpenStreetMap railway geometry for India into web-optimized GeoJSON and JSON files.

Output Structure:
- frontend/static/data/railway/india_railways_full.geojson
- frontend/static/data/railway/india_railways_major.geojson
- frontend/static/data/stations/india_stations.geojson
- frontend/static/data/zones/rakshak_zones.json
- frontend/static/data/monitoring/rakshak_monitoring.json
"""

import json
import os
import math
import random
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

def safe_prop(val):
    if val is None or val == "" or str(val).strip() == "":
        return "Not available"
    return str(val).strip()

def process_overpass_to_geojson(overpass_data):
    """
    Transforms Overpass API elements into GeoJSON FeatureCollections.
    """
    elements = overpass_data.get("elements", [])
    print(f"Processing {len(elements)} OSM elements...")

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
            
            # Determine if this feature is a major corridor line
            is_major = (
                usage in ["main", "branch"] or 
                ref != "Not available" or 
                name != "Not available" or 
                tracks in ["2", "3", "4", "double"]
            )

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
                    "maxspeed": maxspeed,
                    "is_major": is_major
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

    print(f"Extracted {len(rail_features)} railway track features and {len(station_features)} station/node features.")

    # Split into full and major railway datasets
    major_features = [f for f in rail_features if f["properties"]["is_major"]]
    if len(major_features) < len(rail_features) * 0.2:
        major_features = rail_features  # Fallback if tags were light

    full_geojson = {
        "type": "FeatureCollection",
        "features": rail_features
    }
    
    major_geojson = {
        "type": "FeatureCollection",
        "features": major_features
    }

    stations_geojson = {
        "type": "FeatureCollection",
        "features": station_features
    }

    return full_geojson, major_geojson, stations_geojson

def create_zones_dataset():
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
            "center": [21.1702, 72.8311], # Surat / Mumbai / Guj
            "zoom": 7,
            "bounds": [[18.5, 69.5], [24.5, 74.5]]
        },
        {
            "id": "ZONE-03",
            "code": "CR",
            "name": "Central Railway Zone",
            "short_name": "ZONE 03",
            "status": "OPERATIONAL",
            "center": [19.0760, 72.8777], # Mumbai / Pune / Nagpur
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
            "center": [22.5726, 88.3639], # Kolkata
            "zoom": 7,
            "bounds": [[21.5, 86.0], [26.0, 89.5]]
        },
        {
            "id": "ZONE-06",
            "code": "SCR",
            "name": "South Central Railway Zone",
            "short_name": "ZONE 06",
            "status": "OPERATIONAL",
            "center": [17.3850, 78.4867], # Hyderabad
            "zoom": 7,
            "bounds": [[14.0, 77.0], [19.0, 82.5]]
        }
    ]
    return zones

def create_monitoring_dataset(rail_features):
    """
    Creates RAKSHAK operational status overlays linked to real OSM railway segment IDs.
    Includes the specific required Zone 04 demo critical asset VIB-04A.
    """
    # Pick a real OSM segment from Southern region (Zone 04, near Chennai/SR) if available, else pick first valid
    zone04_track_id = None
    zone04_coords = None
    
    for f in rail_features:
        coords = f["geometry"]["coordinates"]
        # Check if coordinates are in Zone 04 region (Lat 8 to 14, Lng 76 to 81)
        if len(coords) >= 2:
            lon, lat = coords[0]
            if 8.0 <= lat <= 14.5 and 76.0 <= lon <= 81.0:
                zone04_track_id = f["id"]
                zone04_coords = coords[len(coords)//2]  # midpoint
                break

    if not zone04_track_id and rail_features:
        f = rail_features[0]
        zone04_track_id = f["id"]
        zone04_coords = f["geometry"]["coordinates"][0]

    monitoring = {
        "critical_asset": {
            "sensor_id": "VIB-04A",
            "zone": "ZONE 04",
            "status": "CRITICAL",
            "reading": "5.8 mm/s",
            "failure_risk": "92%",
            "position": {
                "lat": zone04_coords[1] if zone04_coords else 13.0827,
                "lng": zone04_coords[0] if zone04_coords else 80.2707
            },
            "affected_track_id": zone04_track_id,
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
        "monitored_tracks": {
            # Map of track_id -> status ('warning' | 'critical' | 'healthy')
        },
        "sensors": []
    }

    if zone04_track_id:
        monitoring["monitored_tracks"][zone04_track_id] = "critical"

    # Pick a few warning sections
    for i, f in enumerate(rail_features[:50]):
        if f["id"] != zone04_track_id and i % 12 == 0:
            monitoring["monitored_tracks"][f["id"]] = "warning"
        elif f["id"] != zone04_track_id and i % 5 == 0:
            monitoring["monitored_tracks"][f["id"]] = "healthy"

    return monitoring

def main():
    raw_path = os.path.join(BASE_DIR, "raw_overpass_railway.json")
    if not os.path.exists(raw_path):
        print(f"Error: {raw_path} not found. Please run Overpass query first.")
        return

    with open(raw_path, "r", encoding="utf-8") as f:
        overpass_data = json.load(f)

    full_geo, major_geo, stations_geo = process_overpass_to_geojson(overpass_data)
    zones = create_zones_dataset()
    monitoring = create_monitoring_dataset(full_geo["features"])

    with open(os.path.join(RAILWAY_DIR, "india_railways_full.geojson"), "w", encoding="utf-8") as f:
        json.dump(full_geo, f)
    print("Saved india_railways_full.geojson")

    with open(os.path.join(RAILWAY_DIR, "india_railways_major.geojson"), "w", encoding="utf-8") as f:
        json.dump(major_geo, f)
    print("Saved india_railways_major.geojson")

    with open(os.path.join(STATIONS_DIR, "india_stations.geojson"), "w", encoding="utf-8") as f:
        json.dump(stations_geo, f)
    print("Saved india_stations.geojson")

    with open(os.path.join(ZONES_DIR, "rakshak_zones.json"), "w", encoding="utf-8") as f:
        json.dump(zones, f, indent=2)
    print("Saved rakshak_zones.json")

    with open(os.path.join(MONITORING_DIR, "rakshak_monitoring.json"), "w", encoding="utf-8") as f:
        json.dump(monitoring, f, indent=2)
    print("Saved rakshak_monitoring.json")

    print("Data processing pipeline complete!")

if __name__ == "__main__":
    main()
