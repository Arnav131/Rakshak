"""
map_view/api_views.py
JSON API endpoints for the Leaflet map frontend.

All endpoints return JsonResponse — no template rendering.
The map.js frontend fetches these via fetch() to populate
stations, routes, tickets, alerts, and train simulation data.

All endpoints require authentication via api_login_required.
Unauthenticated requests receive a 401 JSON response.
"""

import random
import time
from decimal import Decimal

from django.db.models import Count, Q
from django.http import JsonResponse

# Custom decorator that returns 401 JSON instead of redirecting to login page
from core.utils import api_login_required

# Railway models needed for querying map data
from railway.models import (
    Alert,
    Division,
    Station,
    Ticket,
    TrackSection,
    Zone,
)


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def _decimal_to_float(val):
    """
    Convert Decimal to float for JSON serialization.
    
    Django's DecimalField stores values as Decimal objects which aren't
    JSON-serializable by default. This helper converts them to native
    Python floats so they can be serialized to JSON safely.
    
    Args:
        val: A Decimal instance or any other value
        
    Returns:
        float if val is Decimal, otherwise returns val unchanged
    """
    return float(val) if isinstance(val, Decimal) else val


# ---------------------------------------------------------------------------
# API Views — All require authentication
# ---------------------------------------------------------------------------

@api_login_required
def api_stations(request):
    """
    GET /api/stations/
    
    Returns all active railway stations with their geographic coordinates,
    operational metadata, and health status for map marker rendering.
    
    Health status is determined by counting active alerts on connected
    track sections:
        - healthy: 0 active alerts
        - warning: 1-2 active alerts  
        - critical: 3+ active alerts
    
    Authentication: Required
    Response: JSON array of station objects
    """
    # Fetch all active stations with their zone and division data
    # select_related() performs a SQL JOIN to avoid N+1 queries
    # DATABASE TEAM NOTE:
    # Optimization: Replaced N+1 queries with Django ORM annotations.
    # Why: Previously, each station executed 3 additional queries in a loop (2 for alerts, 1 for tracks).
    # Compatibility: Fully compatible with PostgreSQL.
    # Index impact: Uses existing indexes on status and active fields. No new indexes required.
    # Migration required: NO.
    stations = (
        Station.objects
        .filter(is_active=True)  # Only show operational stations
        .select_related("division__zone")  # Eager load division and zone
        .annotate(
            active_alerts_start=Count(
                "track_sections_starting__alerts",
                filter=Q(track_sections_starting__alerts__status="active"),
                distinct=True
            ),
            active_alerts_end=Count(
                "track_sections_ending__alerts",
                filter=Q(track_sections_ending__alerts__status="active"),
                distinct=True
            ),
            tracks_start=Count("track_sections_starting", distinct=True),
            tracks_end=Count("track_sections_ending", distinct=True)
        )
        .order_by("station_name")
    )

    data = []
    for s in stations:
        # Calculate active alerts and monitored tracks from annotations
        # avoiding N+1 queries.
        active_alerts = s.active_alerts_start + s.active_alerts_end

        # Determine station health status based on alert count
        # This drives the color coding on the map (green/yellow/red)
        if active_alerts >= 3:
            status = "critical"
        elif active_alerts >= 1:
            status = "warning"
        else:
            status = "healthy"

        # Calculate track sections connected to this station
        tracks_monitored = s.tracks_start + s.tracks_end
        
        # Generate a stable pseudo-random daily train count
        # Using station PK ensures the same station always gets the same number
        # Formula: multiply PK by 37, modulo 400, then add 50 = range 50-450
        daily_trains = (s.pk * 37 % 400) + 50

        # Build the station data dictionary for JSON serialization
        data.append({
            "code": s.station_code,           # Unique station identifier (e.g., "NDLS")
            "name": s.station_name,           # Human-readable station name
            "lat": _decimal_to_float(s.latitude),   # Latitude for map positioning
            "lng": _decimal_to_float(s.longitude),  # Longitude for map positioning
            "zone": s.division.zone.name,     # Railway zone (e.g., "Northern Railway")
            "division": s.division.name,      # Railway division (e.g., "Delhi")
            "is_junction": s.is_junction,     # True if station is a junction
            "is_terminal": s.is_terminal,     # True if station is a terminal
            "status": status,                 # Health status: healthy/warning/critical
            "active_alerts": active_alerts,   # Number of active alerts
            "tracks_monitored": tracks_monitored,  # Connected track sections
            "daily_trains": daily_trains,     # Estimated daily train traffic
        })

    # safe=False allows returning a list at the top level (not wrapped in dict)
    return JsonResponse(data, safe=False)


@api_login_required
def api_routes(request):
    """
    GET /api/routes/
    
    Returns all track sections with their polyline geometry for rendering
    as colored polylines on the Leaflet map. Each route connects two stations.
    
    Route status colors:
        - green: active (healthy)
        - yellow: under maintenance (warning)
        - red: closed or decommissioned (critical)
    
    If a track section has no stored geometry, a straight line is generated
    between its start and end station coordinates as a fallback.
    
    Authentication: Required
    Response: JSON array of route objects with coordinates
    """
    # Fetch all track sections with their connected station data
    sections = (
        TrackSection.objects
        .select_related("start_station", "end_station")  # Eager load stations
        .order_by("section_code")
    )

    data = []
    
    # Map database status values to map display colors
    status_map = {
        "active": "healthy",             # Normal operations
        "under_maintenance": "warning",  # Maintenance in progress
        "closed": "critical",            # Route is closed
        "decommissioned": "critical",    # Route permanently closed
    }

    for ts in sections:
        # Use the stored polyline geometry if it exists
        # Otherwise create a straight line between the two stations
        coords = ts.geometry
        if not coords or len(coords) < 2:
            # Fallback: generate a simple 2-point line segment
            coords = [
                [
                    _decimal_to_float(ts.start_station.latitude),
                    _decimal_to_float(ts.start_station.longitude),
                ],
                [
                    _decimal_to_float(ts.end_station.latitude),
                    _decimal_to_float(ts.end_station.longitude),
                ],
            ]

        # Build the route data dictionary
        data.append({
            "id": ts.section_code,       # Unique section identifier
            "name": (                     # Human-readable route name
                f"{ts.start_station.station_name} — "
                f"{ts.end_station.station_name}"
            ),
            "train": "Indian Railways",   # Operator name (constant for now)
            "source": ts.start_station.station_code,     # Origin station code
            "destination": ts.end_station.station_code,  # Destination station code
            "distance_km": _decimal_to_float(ts.length_km) if ts.length_km else None,
            "coordinates": coords,        # Array of [lat, lng] pairs
            "status": status_map.get(ts.status, "healthy"),  # Mapped to color status
        })

    return JsonResponse(data, safe=False)


@api_login_required
def api_tickets(request):
    """
    GET /api/tickets/
    
    Returns active maintenance tickets with location data for map markers.
    Ticket positions are derived from the start station of their track section,
    with a slight deterministic random offset to prevent overlapping markers.
    
    The offset is seeded with a fixed value (99) to ensure tickets render
    at consistent positions across page reloads.
    
    Authentication: Required
    Response: JSON array of ticket objects (max 200 for performance)
    """
    # Fetch non-closed tickets with related station, zone, and team data
    # DATABASE TEAM NOTE:
    # Optimization: Added track_section__end_station to select_related to eliminate N+1 query.
    # Why: The loop accesses t.track_section.end_station.station_name, which previously triggered a query per ticket.
    # Compatibility: Fully compatible with PostgreSQL.
    # Migration required: NO.
    tickets = (
        Ticket.objects
        .exclude(status="closed")  # Don't show resolved/closed tickets
        .select_related(
            "track_section__start_station__division__zone",  # For location
            "track_section__end_station",  # Eager load to prevent N+1
            "assigned_team",  # For team name
        )
        .order_by("-created_at")[:200]  # Limit to 200 newest tickets for map performance
    )

    # Use a LOCAL Random instance seeded with a fixed value for deterministic offsets.
    # IMPORTANT: Do NOT use random.seed() on the global instance — it corrupts random
    # state for all other code in this process (simulation generator, etc.).
    rng = random.Random(99)

    data = []
    for t in tickets:
        # Get the start station of the affected track section
        sta = t.track_section.start_station
        div = sta.division
        zone = div.zone

        # Apply small random offset so overlapping tickets are visually distinct
        # Offset range: ±0.05 degrees (~5.5 km at equator)
        lat = _decimal_to_float(sta.latitude) + rng.uniform(-0.05, 0.05)
        lng = _decimal_to_float(sta.longitude) + rng.uniform(-0.05, 0.05)

        # Build the ticket data dictionary
        data.append({
            "id": t.ticket_code,           # Unique ticket identifier
            "title": t.title,               # Ticket title/description
            "lat": round(lat, 6),           # Latitude (6 decimal places = ~11cm precision)
            "lng": round(lng, 6),           # Longitude
            "status": t.status,             # open/in_progress/pending/resolved
            "priority": t.priority,         # low/medium/high/critical
            "zone": zone.name,              # Railway zone
            "division": div.name,           # Railway division
            "station": sta.station_name,    # Nearest station
            "team": t.assigned_team.team_name if t.assigned_team else "Unassigned",
            "section": (                    # Affected track section
                f"{t.track_section.start_station.station_name} — "
                f"{t.track_section.end_station.station_name}"
            ),
        })

    return JsonResponse(data, safe=False)


@api_login_required
def api_alerts(request):
    """
    GET /api/alerts/
    
    Returns active and acknowledged alerts with location data for map markers.
    Alerts are positioned at the start station of their affected track section.
    Limited to 100 most recent alerts for map performance.
    
    Authentication: Required
    Response: JSON array of alert objects
    """
    # Fetch alerts that need attention (active or acknowledged but not resolved)
    alerts = (
        Alert.objects
        .filter(status__in=["active", "acknowledged"])  # Only show actionable alerts
        .select_related(
            "track_section__start_station__division__zone",  # For location hierarchy
        )
        .order_by("-generated_at")[:100]  # Most recent first, capped at 100
    )

    data = []
    for a in alerts:
        # Alerts are positioned at the start station of their track section
        sta = a.track_section.start_station
        
        # Build the alert data dictionary
        data.append({
            "id": a.alert_code,             # Unique alert identifier (e.g., "ALT-2024...")
            "title": a.title,               # Alert title
            "description": a.description,   # Detailed alert description
            "severity": a.severity,         # critical/warning/info
            "status": a.status,             # active/acknowledged/resolved
            "lat": _decimal_to_float(sta.latitude),   # Alert location
            "lng": _decimal_to_float(sta.longitude),  # Alert location
            "zone": sta.division.zone.name, # Responsible railway zone
            "station": sta.station_name,    # Nearest station
            "generated_at": a.generated_at.isoformat(),  # ISO 8601 timestamp
        })

    return JsonResponse(data, safe=False)


@api_login_required
def api_summary(request):
    """
    GET /api/summary/
    
    Returns aggregate statistics for the map dashboard stats bar.
    Provides a quick overview of the railway network's operational status.
    
    Metrics returned:
        - Total active stations
        - Total track sections
        - Active (operational) routes
        - Railway zones
        - Active maintenance tickets
        - Active alerts
    
    Authentication: Required
    Response: JSON object with aggregate counts
    """
    # Calculate all statistics with efficient COUNT queries
    data = {
        "stations": Station.objects.filter(is_active=True).count(),
        "track_sections": TrackSection.objects.count(),
        "active_routes": TrackSection.objects.filter(status="active").count(),
        "railway_zones": Zone.objects.filter(is_active=True).count(),
        # Exclude closed AND resolved tickets (both are finished states)
        "active_tickets": Ticket.objects.exclude(
            status__in=["closed", "resolved"]
        ).count(),
        "active_alerts": Alert.objects.filter(status="active").count(),
    }
    return JsonResponse(data)


@api_login_required
def api_trains(request):
    """
    GET /api/trains/
    
    Returns simulated train positions along active routes for map animation.
    
    This is purely a simulation — no real GPS data. Trains move along their
    routes at varying speeds based on time. Positions are interpolated along
    the route's polyline geometry.
    
    Simulation mechanics:
        - 20 random active routes are selected every 10 seconds
        - Each train moves at a different speed (based on its index)
        - Position is calculated by interpolating along the route's geometry
        - Speed is randomly assigned between 60-160 km/h
    
    The random seed changes every 10 seconds, so train positions update
    smoothly when the frontend polls this endpoint.
    
    Authentication: Required
    Response: JSON array of train objects with position and speed
    """
    # Fetch all active track sections that have geometry data
    # values() is more efficient than model instances for this use case
    sections = list(
        TrackSection.objects
        .filter(status="active")    # Only active routes have trains
        .exclude(geometry=[])       # Must have geometry for interpolation
        .values("section_code", "geometry", "length_km")  # Only needed fields
        .order_by("section_code")
    )

    # If no active routes with geometry, return empty array
    if not sections:
        return JsonResponse([], safe=False)

    # Pick ~20 random routes to simulate trains on
    # Seed changes every 10 seconds for smooth animation
    # Use a LOCAL Random instance — do NOT call random.seed() on the global instance.
    rng = random.Random(int(time.time()) // 10)
    train_routes = rng.sample(sections, k=min(20, len(sections)))

    trains = []
    for i, route in enumerate(train_routes):
        coords = route["geometry"]
        # Skip routes with insufficient geometry data
        if not coords or len(coords) < 2:
            continue

        # Calculate train position along the route based on current time
        # Each train moves at a different speed for visual variety
        t = time.time()  # Current Unix timestamp (seconds)
        speed_factor = 0.0001 * (i + 1)  # Each train has unique speed
        progress = (t * speed_factor) % 1.0  # Progress from 0.0 (start) to 1.0 (end)

        # Interpolate position along the polyline geometry
        # This creates smooth movement along multi-point routes
        total_segments = len(coords) - 1
        segment_idx = int(progress * total_segments)
        segment_idx = min(segment_idx, total_segments - 1)  # Clamp to valid range
        local_t = (progress * total_segments) - segment_idx  # Position within segment

        # Linear interpolation between two consecutive points
        # Formula: point1 + t * (point2 - point1)
        lat = coords[segment_idx][0] + local_t * (
            coords[segment_idx + 1][0] - coords[segment_idx][0]
        )
        lng = coords[segment_idx][1] + local_t * (
            coords[segment_idx + 1][1] - coords[segment_idx][1]
        )

        # Build the train data dictionary
        trains.append({
            "id": f"TRN-{i+1:03d}",           # Train identifier (zero-padded)
            "route_id": route["section_code"],  # Which route this train is on
            "lat": round(lat, 6),             # Current latitude
            "lng": round(lng, 6),             # Current longitude
            "progress": round(progress, 3),   # How far along the route (0.0-1.0)
            "speed_kmph": rng.randint(60, 160),  # Current speed in km/h
        })

    return JsonResponse(trains, safe=False)