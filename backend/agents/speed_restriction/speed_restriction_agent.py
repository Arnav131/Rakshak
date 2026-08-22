"""
Rakshak Agent System — Speed Restriction Agent
=================================================
Recommends and enforces Temporary Speed Restrictions (TSR)
based on physics-informed risk assessment.
"""

import logging
import math
from typing import Any, Dict, Optional

from agents.shared.base_agent import BaseAgent
from agents.shared.events import SpeedRestrictionEvent

logger = logging.getLogger("rakshak.agents.speed_restriction")


class SpeedRestrictionAgent(BaseAgent):
    """
    Physics-informed speed restriction recommendation engine.

    Calculates risk-adjusted speed limits based on:
    - Anomaly severity and fault type
    - Temperature (thermal expansion risk)
    - Gauge deviation from nominal
    - Vibration levels (ride quality)
    - Track section characteristics

    From agents_README:
        Autonomy: Semi-auto / Emergency Override
        Target: False TSR Rate < 2%
    """

    AGENT_NAME = "speed_restriction"
    AGENT_VERSION = "1.0.0"

    # Indian Railways speed categories (km/h)
    SPEED_LIMITS = {
        "normal": 130,        # Group A route max
        "caution": 75,        # Cautionary speed
        "restricted": 50,     # Restricted running
        "severe": 30,         # Severe restriction
        "emergency_stop": 0,  # Stop all traffic
    }

    # Fault type → base speed restriction
    FAULT_SPEED_LIMITS = {
        "thermal_buckle": 30,
        "rail_fracture": 0,       # Emergency stop
        "gauge_widening": 50,
        "buckle_precursor": 75,
        "subgrade_settlement": 50,
        "weld_defect": 50,
        "fastener_failure": 75,
        "ballast_degradation": 75,
        "joint_wear": 75,
        "corrugation": 75,
        "drainage_failure": 100,
        "vegetation_encroachment": 100,
    }

    # Indian Railways gauge specs (broad gauge, mm)
    NOMINAL_GAUGE = 1676
    GAUGE_TOLERANCE = 6       # ±6mm within spec
    GAUGE_WARNING = 10        # > 10mm deviation → TSR
    GAUGE_CRITICAL = 15       # > 15mm → emergency

    def process(self, data: Any) -> Dict:
        """
        Calculate speed restriction recommendation.

        Args:
            data: Dict with fault_type, anomaly_score, track_section_id,
                  and optionally sensor values (ambient_temp, gauge_width, etc.)

        Returns:
            Dict with recommended speed, risk score, and rationale
        """
        fault_type = data.get("fault_type", "unknown")
        anomaly_score = data.get("anomaly_score", 0.0)
        track_section_id = data.get("track_section_id")
        urgency = data.get("urgency", "medium")

        # Sensor context
        ambient_temp = data.get("ambient_temp", 35.0)
        gauge_width = data.get("gauge_width", self.NOMINAL_GAUGE)
        vibration_rms = data.get("vibration_rms", 0.5)

        # Calculate component risk scores
        fault_risk = self._compute_fault_risk(fault_type, anomaly_score)
        thermal_risk = self._compute_thermal_risk(ambient_temp)
        gauge_risk = self._compute_gauge_risk(gauge_width)
        vibration_risk = self._compute_vibration_risk(vibration_rms)

        # Combined risk score (weighted)
        risk_score = (
            0.40 * fault_risk +
            0.25 * thermal_risk +
            0.25 * gauge_risk +
            0.10 * vibration_risk
        )
        risk_score = min(1.0, max(0.0, risk_score))

        # Determine speed limit
        recommended_speed = self._compute_speed_limit(
            fault_type, risk_score, gauge_width, ambient_temp
        )

        is_emergency = recommended_speed <= 30 or urgency == "critical"

        # Generate rationale
        reasons = []
        if fault_risk > 0.5:
            reasons.append(f"Fault detected: {fault_type.replace('_', ' ')} (score={anomaly_score:.2f})")
        if thermal_risk > 0.5:
            reasons.append(f"High temperature: {ambient_temp}°C (thermal expansion risk)")
        if gauge_risk > 0.5:
            gauge_dev = abs(gauge_width - self.NOMINAL_GAUGE)
            reasons.append(f"Gauge deviation: {gauge_dev:.1f}mm from nominal")
        if vibration_risk > 0.5:
            reasons.append(f"High vibration: {vibration_rms:.2f} mm/s RMS")

        rationale = " | ".join(reasons) if reasons else "Precautionary restriction"

        # Emit event
        event = SpeedRestrictionEvent(
            track_section_id=track_section_id or 0,
            recommended_speed_kmh=recommended_speed,
            reason=rationale,
            risk_score=risk_score,
            is_emergency=is_emergency,
        )

        logger.info(
            f"[{self.AGENT_NAME}] TSR recommendation: {recommended_speed} km/h "
            f"(risk={risk_score:.2f}, emergency={is_emergency})"
        )

        return {
            "track_section_id": track_section_id,
            "recommended_speed_kmh": recommended_speed,
            "risk_score": round(risk_score, 4),
            "is_emergency": is_emergency,
            "component_risks": {
                "fault": round(fault_risk, 4),
                "thermal": round(thermal_risk, 4),
                "gauge": round(gauge_risk, 4),
                "vibration": round(vibration_risk, 4),
            },
            "rationale": rationale,
            "event": event,
        }

    def _compute_fault_risk(self, fault_type: str, anomaly_score: float) -> float:
        """Risk from detected fault type."""
        if fault_type == "normal" or fault_type == "unknown":
            return anomaly_score * 0.3
        if fault_type in ("rail_fracture", "thermal_buckle"):
            return max(0.9, anomaly_score)
        if fault_type in ("gauge_widening", "subgrade_settlement"):
            return max(0.7, anomaly_score * 0.9)
        return anomaly_score * 0.7

    def _compute_thermal_risk(self, temp: float) -> float:
        """Risk from ambient temperature (thermal buckling)."""
        if temp <= 40:
            return 0.0
        elif temp <= 50:
            return (temp - 40) / 10.0 * 0.5
        elif temp <= 55:
            return 0.5 + (temp - 50) / 5.0 * 0.3
        else:
            return min(1.0, 0.8 + (temp - 55) / 10.0 * 0.2)

    def _compute_gauge_risk(self, gauge_width: float) -> float:
        """Risk from gauge deviation."""
        deviation = abs(gauge_width - self.NOMINAL_GAUGE)
        if deviation <= self.GAUGE_TOLERANCE:
            return 0.0
        elif deviation <= self.GAUGE_WARNING:
            return (deviation - self.GAUGE_TOLERANCE) / (self.GAUGE_WARNING - self.GAUGE_TOLERANCE) * 0.5
        elif deviation <= self.GAUGE_CRITICAL:
            return 0.5 + (deviation - self.GAUGE_WARNING) / (self.GAUGE_CRITICAL - self.GAUGE_WARNING) * 0.4
        else:
            return 1.0

    def _compute_vibration_risk(self, vibration_rms: float) -> float:
        """Risk from vibration levels."""
        if vibration_rms <= 2.0:
            return 0.0
        elif vibration_rms <= 5.0:
            return (vibration_rms - 2.0) / 3.0 * 0.5
        elif vibration_rms <= 10.0:
            return 0.5 + (vibration_rms - 5.0) / 5.0 * 0.4
        else:
            return min(1.0, 0.9 + (vibration_rms - 10.0) / 20.0)

    def _compute_speed_limit(
        self,
        fault_type: str,
        risk_score: float,
        gauge_width: float,
        ambient_temp: float,
    ) -> float:
        """Determine the final speed limit."""
        # Start with fault-based limit
        base_speed = self.FAULT_SPEED_LIMITS.get(fault_type, 130)

        # Risk-based reduction
        if risk_score >= 0.9:
            risk_speed = 30
        elif risk_score >= 0.7:
            risk_speed = 50
        elif risk_score >= 0.5:
            risk_speed = 75
        elif risk_score >= 0.3:
            risk_speed = 100
        else:
            risk_speed = 130

        # Gauge-based hard limit
        gauge_dev = abs(gauge_width - self.NOMINAL_GAUGE)
        if gauge_dev > self.GAUGE_CRITICAL:
            gauge_speed = 0  # Emergency stop
        elif gauge_dev > self.GAUGE_WARNING:
            gauge_speed = 30
        elif gauge_dev > self.GAUGE_TOLERANCE:
            gauge_speed = 75
        else:
            gauge_speed = 130

        # Take the most restrictive
        return min(base_speed, risk_speed, gauge_speed)
