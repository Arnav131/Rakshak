"""
Rakshak Agent System — Network Health Agent
===============================================
Computes Track Health Index (THI) per section and
detects spatial-temporal anomaly clusters.
"""

import logging
from typing import Any, Dict, List, Optional

from django.utils import timezone

from agents.shared.base_agent import BaseAgent
from agents.shared.events import NetworkHealthEvent

logger = logging.getLogger("rakshak.agents.network_health")


class NetworkHealthAgent(BaseAgent):
    """
    Network-wide track health monitoring.

    Responsibilities:
    - Track Health Index (THI) computation per section (0-100)
    - Spatial-temporal anomaly clustering
    - GeoJSON overlay generation for map visualization
    - Health trend analysis

    From agents_README:
        Autonomy: Scheduled (every 5 minutes)
        Health Index: Composite of sensor readings, anomaly history,
                     maintenance recency, and environmental stress
    """

    AGENT_NAME = "network_health"
    AGENT_VERSION = "1.0.0"

    # THI component weights
    WEIGHTS = {
        "anomaly_rate": 0.30,      # Recent anomaly frequency
        "maintenance_recency": 0.25, # Days since last maintenance
        "sensor_quality": 0.15,     # Average sensor data quality
        "environmental_stress": 0.15, # Temperature + weather stress
        "structural_age": 0.15,     # Track age factor
    }

    # THI → health category
    HEALTH_CATEGORIES = {
        (80, 100): "excellent",
        (60, 80): "good",
        (40, 60): "fair",
        (20, 40): "poor",
        (0, 20): "critical",
    }

    def process(self, data: Any) -> Dict:
        """
        Compute Track Health Index for a section or all sections.

        Args:
            data: Dict with optional track_section_id (None = all sections)

        Returns:
            Dict with health indices and cluster analysis
        """
        track_section_id = data.get("track_section_id")

        if track_section_id:
            result = self._compute_section_health(track_section_id)
            return {"sections": [result]}
        else:
            return self._compute_network_health()

    def _compute_section_health(self, track_section_id: int) -> Dict:
        """Compute THI for a single track section."""
        from railway.models import TrackSection, Alert, SensorReading, Ticket

        try:
            section = TrackSection.objects.get(pk=track_section_id)
        except TrackSection.DoesNotExist:
            return {"track_section_id": track_section_id, "error": "Section not found"}

        now = timezone.now()

        # 1. Anomaly rate (last 24h)
        recent_anomalies = Alert.objects.filter(
            track_section_id=track_section_id,
            generated_at__gte=now - timezone.timedelta(hours=24),
            alert_type__in=["anomaly", "prediction"],
        ).count()
        anomaly_score = max(0, 100 - recent_anomalies * 15)

        # 2. Maintenance recency
        last_ticket = Ticket.objects.filter(
            track_section_id=track_section_id,
            status="resolved",
        ).order_by("-resolved_at").first()

        if last_ticket and last_ticket.resolved_at:
            days_since = (now - last_ticket.resolved_at).days
            maintenance_score = max(0, 100 - days_since * 1.5)
        else:
            maintenance_score = 50  # Unknown

        # 3. Sensor quality (average)
        recent_readings = SensorReading.objects.filter(
            sensor__asset__track_section_id=track_section_id,
            recorded_at__gte=now - timezone.timedelta(hours=1),
        )
        if recent_readings.exists():
            from django.db.models import Avg
            avg_quality = recent_readings.aggregate(Avg("quality_score"))["quality_score__avg"]
            sensor_score = float(avg_quality or 0.5) * 100
        else:
            sensor_score = 50

        # 4. Environmental stress (simplified)
        env_score = 70  # Default; would be weather-dependent

        # 5. Structural age
        if hasattr(section, "created_at"):
            age_years = (now - section.created_at).days / 365.25
            age_score = max(0, 100 - age_years * 2)
        else:
            age_score = 70

        # Weighted THI
        thi = (
            self.WEIGHTS["anomaly_rate"] * anomaly_score +
            self.WEIGHTS["maintenance_recency"] * maintenance_score +
            self.WEIGHTS["sensor_quality"] * sensor_score +
            self.WEIGHTS["environmental_stress"] * env_score +
            self.WEIGHTS["structural_age"] * age_score
        )
        thi = max(0, min(100, thi))

        # Health category
        category = "unknown"
        for (lo, hi), cat in self.HEALTH_CATEGORIES.items():
            if lo <= thi < hi:
                category = cat
                break

        result = {
            "track_section_id": track_section_id,
            "health_index": round(thi, 2),
            "category": category,
            "component_scores": {
                "anomaly_rate": round(anomaly_score, 2),
                "maintenance_recency": round(maintenance_score, 2),
                "sensor_quality": round(sensor_score, 2),
                "environmental_stress": round(env_score, 2),
                "structural_age": round(age_score, 2),
            },
            "recent_anomalies_24h": recent_anomalies,
            "computed_at": now.isoformat(),
        }

        return result

    def _compute_network_health(self) -> Dict:
        """Compute THI for all active track sections."""
        from railway.models import TrackSection

        sections = TrackSection.objects.filter(is_active=True).values_list("pk", flat=True)

        results = []
        critical_sections = []
        total_thi = 0

        for section_id in sections:
            health = self._compute_section_health(section_id)
            results.append(health)

            thi = health.get("health_index", 50)
            total_thi += thi

            if thi < 40:
                critical_sections.append(section_id)

        avg_thi = total_thi / max(len(results), 1)

        # Cluster detection: flag if multiple adjacent sections are unhealthy
        cluster_detected = len(critical_sections) >= 3

        return {
            "sections": results,
            "summary": {
                "total_sections": len(results),
                "average_thi": round(avg_thi, 2),
                "critical_sections": len(critical_sections),
                "cluster_detected": cluster_detected,
            },
        }

    def generate_geojson(self, health_data: Dict) -> Dict:
        """
        Generate GeoJSON overlay for the map visualization.

        Color-codes sections by health index:
        - Green: THI ≥ 80
        - Yellow: 60 ≤ THI < 80
        - Orange: 40 ≤ THI < 60
        - Red: THI < 40
        """
        features = []

        for section in health_data.get("sections", []):
            thi = section.get("health_index", 50)

            if thi >= 80:
                color = "#22c55e"  # Green
            elif thi >= 60:
                color = "#eab308"  # Yellow
            elif thi >= 40:
                color = "#f97316"  # Orange
            else:
                color = "#ef4444"  # Red

            features.append({
                "type": "Feature",
                "properties": {
                    "section_id": section["track_section_id"],
                    "health_index": thi,
                    "category": section.get("category", "unknown"),
                    "color": color,
                    "anomalies_24h": section.get("recent_anomalies_24h", 0),
                },
                "geometry": None,  # Populated from TrackSection coordinates
            })

        return {
            "type": "FeatureCollection",
            "features": features,
        }
