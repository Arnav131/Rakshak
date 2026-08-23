# backend/ai_integration/severity.py
"""
Rakshak AI — Centralized Severity Thresholds and Calculations
============================================================
Single Source of Truth (SSOT) for anomaly score thresholds, alert levels,
and ticket priority classifications across the entire platform.
"""

from typing import Dict

# Canonical thresholds for railway anomaly scores
CRITICAL_THRESHOLD = 0.85
WARNING_THRESHOLD = 0.65
CAUTION_THRESHOLD = 0.40

SEVERITY_THRESHOLDS: Dict[str, float] = {
    "critical": CRITICAL_THRESHOLD,
    "warning": WARNING_THRESHOLD,
    "caution": CAUTION_THRESHOLD,
}


def score_to_alert_level(score: float) -> str:
    """
    Map an anomaly/risk score to a standard alert level string.
    Returns: 'critical' | 'warning' | 'caution' | 'none'
    """
    if score >= CRITICAL_THRESHOLD:
        return "critical"
    if score >= WARNING_THRESHOLD:
        return "warning"
    if score >= CAUTION_THRESHOLD:
        return "caution"
    return "none"


def score_to_ticket_priority(score: float, alert_level: str = "") -> str:
    """
    Map score/alert_level to Ticket.Priority (critical | high | medium | low).
    """
    if alert_level == "critical" or score >= CRITICAL_THRESHOLD:
        return "critical"
    if alert_level == "warning" or score >= WARNING_THRESHOLD:
        return "high"
    if score >= CAUTION_THRESHOLD:
        return "medium"
    return "low"
