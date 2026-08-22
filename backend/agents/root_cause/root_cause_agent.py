"""
Rakshak Agent System — Root Cause Agent
==========================================
Identifies the root cause of detected anomalies using the
fault classifier model and historical analysis.
"""

import logging
from typing import Any, Dict, List, Optional

from agents.shared.base_agent import BaseAgent
from agents.shared.events import AnomalyEvent

logger = logging.getLogger("rakshak.agents.root_cause")


class RootCauseAgent(BaseAgent):
    """
    Root cause analysis for detected anomalies.

    Uses:
    - Fault classification model (ResNet-1D) for initial diagnosis
    - Historical pattern matching against past incidents
    - Contextual analysis (weather, maintenance history, track age)

    From agents_README:
        Autonomy: Event-driven
        Target: Top-1 ≥ 0.85, Top-5 ≥ 0.97
    """

    AGENT_NAME = "root_cause"
    AGENT_VERSION = "1.0.0"

    # Fault type → recommended action mapping
    FAULT_ACTIONS = {
        "thermal_buckle": {
            "urgency": "critical",
            "action": "Apply immediate TSR. Dispatch track inspector within 2 hours.",
            "estimated_hours": 4.0,
        },
        "rail_fracture": {
            "urgency": "critical",
            "action": "Emergency TSR (30 km/h). Dispatch welding team immediately.",
            "estimated_hours": 8.0,
        },
        "gauge_widening": {
            "urgency": "high",
            "action": "Schedule gauge correction. Apply TSR (60 km/h) as precaution.",
            "estimated_hours": 6.0,
        },
        "ballast_degradation": {
            "urgency": "medium",
            "action": "Schedule ballast tamping and packing.",
            "estimated_hours": 12.0,
        },
        "joint_wear": {
            "urgency": "medium",
            "action": "Schedule joint inspection and replacement.",
            "estimated_hours": 6.0,
        },
        "corrugation": {
            "urgency": "medium",
            "action": "Schedule rail grinding.",
            "estimated_hours": 8.0,
        },
        "fastener_failure": {
            "urgency": "high",
            "action": "Replace failed fasteners. Inspect adjacent fasteners.",
            "estimated_hours": 3.0,
        },
        "subgrade_settlement": {
            "urgency": "high",
            "action": "Geotechnical assessment required. Apply TSR.",
            "estimated_hours": 24.0,
        },
        "weld_defect": {
            "urgency": "high",
            "action": "Ultrasonic testing on weld. Schedule re-welding if confirmed.",
            "estimated_hours": 6.0,
        },
        "drainage_failure": {
            "urgency": "medium",
            "action": "Clear drainage channels. Inspect for erosion.",
            "estimated_hours": 8.0,
        },
        "vegetation_encroachment": {
            "urgency": "low",
            "action": "Schedule vegetation clearance.",
            "estimated_hours": 4.0,
        },
        "buckle_precursor": {
            "urgency": "high",
            "action": "Monitor closely. Pre-position TSR for activation if temperature exceeds threshold.",
            "estimated_hours": 2.0,
        },
        "normal": {
            "urgency": "none",
            "action": "No action required. Continue monitoring.",
            "estimated_hours": 0,
        },
    }

    def process(self, data: Any) -> Dict:
        """
        Analyse the root cause of an anomaly.

        Args:
            data: AnomalyEvent or dict with fault classification results

        Returns:
            Dict with root cause analysis, recommended actions, and confidence
        """
        if isinstance(data, AnomalyEvent):
            fault_type = data.fault_type
            fault_confidence = data.fault_confidence
            track_section_id = data.track_section_id
            anomaly_score = data.anomaly_score
        else:
            fault_type = data.get("fault_type", "unknown")
            fault_confidence = data.get("fault_confidence", 0.0)
            track_section_id = data.get("track_section_id")
            anomaly_score = data.get("anomaly_score", 0.0)

        # Get recommended action
        action_info = self.FAULT_ACTIONS.get(fault_type, {
            "urgency": "medium",
            "action": f"Investigate anomaly (type: {fault_type}). Schedule inspection.",
            "estimated_hours": 8.0,
        })

        # Historical pattern analysis
        historical = self._analyse_historical(track_section_id, fault_type)

        # Build root cause report
        report = {
            "track_section_id": track_section_id,
            "fault_type": fault_type,
            "confidence": fault_confidence,
            "anomaly_score": anomaly_score,
            "urgency": action_info["urgency"],
            "recommended_action": action_info["action"],
            "estimated_repair_hours": action_info["estimated_hours"],
            "historical_analysis": historical,
            "explanation": self._generate_explanation(
                fault_type, fault_confidence, anomaly_score, historical
            ),
        }

        logger.info(
            f"[{self.AGENT_NAME}] Root cause: {fault_type} "
            f"(confidence={fault_confidence:.2%}, urgency={action_info['urgency']})"
        )

        return report

    def _analyse_historical(self, track_section_id: Optional[int], fault_type: str) -> Dict:
        """
        Check historical incidents for this section and fault type.
        """
        if not track_section_id:
            return {"available": False}

        try:
            from railway.models import Alert
            past_alerts = Alert.objects.filter(
                track_section_id=track_section_id,
                alert_type=Alert.AlertType.ANOMALY,
                status__in=[Alert.Status.RESOLVED, Alert.Status.ACKNOWLEDGED],
            ).order_by("-generated_at")[:10]

            return {
                "available": True,
                "past_incidents": past_alerts.count(),
                "recurrence": past_alerts.count() > 3,
                "last_incident": (
                    past_alerts.first().generated_at.isoformat()
                    if past_alerts.exists() else None
                ),
            }
        except Exception:
            return {"available": False}

    def _generate_explanation(
        self,
        fault_type: str,
        confidence: float,
        anomaly_score: float,
        historical: Dict,
    ) -> str:
        """Generate a human-readable explanation of the root cause analysis."""
        parts = [
            f"Detected {fault_type.replace('_', ' ')} with {confidence:.0%} confidence.",
            f"Anomaly score: {anomaly_score:.2f}.",
        ]

        if historical.get("recurrence"):
            parts.append(
                f"⚠️ This section has {historical['past_incidents']} previous incidents — "
                f"recurring pattern detected."
            )

        if historical.get("last_incident"):
            parts.append(f"Last incident: {historical['last_incident']}.")

        action_info = self.FAULT_ACTIONS.get(fault_type, {})
        if action_info.get("action"):
            parts.append(f"Recommended: {action_info['action']}")

        return " ".join(parts)
