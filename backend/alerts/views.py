# backend/alerts/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from django.utils.timesince import timesince

from railway.models import Alert


@login_required
def alerts_page(request):
    """Display alerts with status and severity filtering."""
    severity_filter = request.GET.get("severity", "all")
    status_filter = request.GET.get("status", "active")

    all_alerts = Alert.objects.select_related(
        "sensor",
        "track_section__start_station__division__zone",
        "track_section__end_station",
    )

    summary = {
        "total": all_alerts.count(),
        "critical": all_alerts.filter(severity=Alert.Severity.CRITICAL).count(),
        "warning": all_alerts.filter(severity=Alert.Severity.WARNING).count(),
        "info": all_alerts.filter(severity=Alert.Severity.INFO).count(),
        "active": all_alerts.filter(status=Alert.Status.ACTIVE).count(),
        "acknowledged": all_alerts.filter(status=Alert.Status.ACKNOWLEDGED).count(),
        "resolved": all_alerts.filter(status=Alert.Status.RESOLVED).count(),
    }

    filtered_qs = all_alerts
    if status_filter != "all":
        filtered_qs = filtered_qs.filter(status=status_filter)
    if severity_filter != "all":
        filtered_qs = filtered_qs.filter(severity=severity_filter)

    alerts = []
    now = timezone.now()
    for alert in filtered_qs:
        generated_at = alert.generated_at or alert.created_at or now
        age = timesince(generated_at, now).split(",")[0]

        # Defensive: track_section and its chain could be None if data is incomplete
        track_section = alert.track_section
        if track_section and track_section.start_station and track_section.start_station.division:
            zone = track_section.start_station.division.zone
            zone_name = zone.name if zone else "Unknown"
            zone_code = zone.code if zone else "?"
            station_name = track_section.start_station.station_name
        else:
            zone_name = "Unknown"
            zone_code = "?"
            station_name = "Unknown"

        section_code = track_section.section_code if track_section else "N/A"
        end_station_name = (
            track_section.end_station.station_name
            if track_section and track_section.end_station
            else "Unknown"
        )
        section_label = (
            f"{station_name} - {end_station_name}"
            if track_section
            else "N/A"
        )
        sensor_code = alert.sensor.sensor_code if alert.sensor else "Sensor network"

        alerts.append(
            {
                "id": alert.alert_code,
                "severity": alert.severity,
                "title": alert.title,
                "description": alert.description,
                "track_id": section_code,
                "section": section_label,
                "station": station_name,
                "zone": zone_name,
                "zone_code": zone_code,
                "sensor": sensor_code,
                "timestamp": generated_at.strftime("%Y-%m-%d %H:%M"),
                "time_ago": f"{age} ago",
                "status": alert.status,
                "type": alert.alert_type.replace("_", " ").title(),
                "confidence": round(float(alert.confidence_score or 0) * 100),
            }
        )

    context = {
        "page_title": "Alerts",
        "alerts": alerts,
        "summary": summary,
        "current_filter": severity_filter,
        "current_status": status_filter,
    }
    return render(request, "alerts.html", context)
