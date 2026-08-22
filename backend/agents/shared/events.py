"""
Rakshak Agent System — Event Schemas
=======================================
Pydantic event models for inter-agent communication.
"""

from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class SensorValidatedEvent:
    """Emitted by SensorIngestionAgent after validation."""
    sensor_id: int
    track_section_id: int
    reading_id: int
    ambient_temp: float
    humidity: float
    vibration_rms: float
    gauge_width: float
    recorded_at: str
    quality_score: float = 1.0


@dataclass
class AnomalyEvent:
    """Emitted by AnomalyDetectionAgent when anomaly is detected."""
    alert_id: int
    track_section_id: int
    sensor_id: int
    anomaly_score: float
    is_anomaly: bool
    tier_scores: Dict[str, float] = field(default_factory=dict)
    fault_type: str = ""
    fault_confidence: float = 0.0
    detected_at: str = ""


@dataclass
class FailurePredictionEvent:
    """Emitted by FailurePredictionAgent."""
    track_section_id: int
    probabilities: Dict[str, float] = field(default_factory=dict)  # {1h, 6h, 24h}
    uncertainty: Dict[str, float] = field(default_factory=dict)
    alert_level: str = "none"  # none, warning, critical
    predicted_at: str = ""


@dataclass
class MaintenanceDispatchEvent:
    """Emitted by MaintenanceDispatchAgent."""
    ticket_id: int
    alert_id: int
    track_section_id: int
    assigned_team_id: Optional[int] = None
    priority: str = "medium"
    scheduled_for: Optional[str] = None


@dataclass
class SpeedRestrictionEvent:
    """Emitted by SpeedRestrictionAgent."""
    track_section_id: int
    recommended_speed_kmh: float
    reason: str = ""
    risk_score: float = 0.0
    is_emergency: bool = False


@dataclass
class NetworkHealthEvent:
    """Emitted by NetworkHealthAgent."""
    track_section_id: int
    health_index: float  # 0-100
    component_scores: Dict[str, float] = field(default_factory=dict)
    anomaly_cluster_detected: bool = False
