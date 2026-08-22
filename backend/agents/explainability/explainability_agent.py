"""
Rakshak Agent System — Explainability Agent
===============================================
Generates human-readable explanations for every ML decision
and maintains a cryptographic audit trail.
"""

import logging
import hashlib
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from django.utils import timezone

from agents.shared.base_agent import BaseAgent

logger = logging.getLogger("rakshak.agents.explainability")


class ExplainabilityAgent(BaseAgent):
    """
    Provides transparent explanations for all AI decisions.

    Responsibilities:
    - Generate natural language rationale for anomaly detections
    - Provide feature attribution explanations (SHAP-style)
    - Create structured audit records
    - Format explanations for dashboard display

    From agents_README:
        Autonomy: Event-driven (triggered by any agent decision)
        Output: NLG rationale + SHAP attributions + audit record
    """

    AGENT_NAME = "explainability"
    AGENT_VERSION = "1.0.0"

    # Feature importance labels (human-readable)
    FEATURE_LABELS = {
        "ambient_temp": "Ambient Temperature",
        "humidity": "Relative Humidity",
        "vibration_rms": "Vibration (RMS)",
        "gauge_width": "Track Gauge Width",
        "tier1_zscore": "Statistical Z-Score",
        "tier1_iqr": "IQR Outlier Score",
        "tier2_iforest": "Isolation Forest Score",
        "tier3_vae": "VAE Reconstruction Error",
    }

    def process(self, data: Any) -> Dict:
        """
        Generate explanation for an AI decision.

        Args:
            data: Dict with decision_type, results, and context

        Returns:
            Dict with explanation text, attributions, and audit hash
        """
        decision_type = data.get("decision_type", "anomaly_detection")

        if decision_type == "anomaly_detection":
            explanation = self._explain_anomaly(data)
        elif decision_type == "failure_prediction":
            explanation = self._explain_failure_prediction(data)
        elif decision_type == "speed_restriction":
            explanation = self._explain_speed_restriction(data)
        elif decision_type == "maintenance_dispatch":
            explanation = self._explain_dispatch(data)
        else:
            explanation = self._explain_generic(data)

        # Create audit record with cryptographic hash
        audit = self._create_audit_record(data, explanation)

        return {
            "explanation": explanation,
            "audit": audit,
        }

    def _explain_anomaly(self, data: Dict) -> Dict:
        """Generate explanation for anomaly detection."""
        anomaly_score = data.get("anomaly_score", 0)
        tier_scores = data.get("tier_scores", {})
        fault_type = data.get("fault_type", "unknown")
        fault_confidence = data.get("fault_confidence", 0)
        track_section_id = data.get("track_section_id")

        # Determine which tiers contributed most
        top_tiers = sorted(tier_scores.items(), key=lambda x: x[1], reverse=True)

        # Build narrative
        narrative_parts = []

        if anomaly_score >= 0.9:
            narrative_parts.append(
                f"**HIGH CONFIDENCE ANOMALY** detected on section {track_section_id}."
            )
        elif anomaly_score >= 0.7:
            narrative_parts.append(
                f"Anomaly detected on section {track_section_id} with moderate-to-high confidence."
            )
        else:
            narrative_parts.append(
                f"Potential anomaly detected on section {track_section_id}."
            )

        # Tier contributions
        for tier_name, score in top_tiers[:3]:
            label = self.FEATURE_LABELS.get(tier_name, tier_name)
            if score > 0.5:
                narrative_parts.append(f"{label} flagged abnormal behavior (score: {score:.2f}).")

        # Fault classification
        if fault_type != "unknown" and fault_confidence > 0.5:
            narrative_parts.append(
                f"Root cause analysis identifies **{fault_type.replace('_', ' ')}** "
                f"as the most likely fault ({fault_confidence:.0%} confidence)."
            )

        narrative = " ".join(narrative_parts)

        # Feature attributions (simplified SHAP-style)
        attributions = {}
        total = sum(abs(v) for v in tier_scores.values()) or 1
        for feature, score in tier_scores.items():
            attributions[self.FEATURE_LABELS.get(feature, feature)] = round(score / total, 4)

        return {
            "type": "anomaly_detection",
            "narrative": narrative,
            "attributions": attributions,
            "severity": "high" if anomaly_score >= 0.8 else ("medium" if anomaly_score >= 0.5 else "low"),
            "confidence": round(anomaly_score, 4),
        }

    def _explain_failure_prediction(self, data: Dict) -> Dict:
        """Generate explanation for failure prediction."""
        probabilities = data.get("probabilities", {})
        track_section_id = data.get("track_section_id")
        alert_level = data.get("alert_level", "none")

        parts = []

        if alert_level == "critical":
            parts.append(f"⚠️ **CRITICAL FAILURE WARNING** for section {track_section_id}.")
        elif alert_level == "warning":
            parts.append(f"Elevated failure risk detected for section {track_section_id}.")
        else:
            parts.append(f"Routine failure assessment for section {track_section_id}.")

        for horizon, prob in sorted(probabilities.items()):
            if prob >= 0.5:
                parts.append(f"Failure within **{horizon}**: {prob:.0%} probability.")
            elif prob >= 0.2:
                parts.append(f"Failure within {horizon}: {prob:.0%} probability (monitoring).")

        return {
            "type": "failure_prediction",
            "narrative": " ".join(parts),
            "alert_level": alert_level,
            "probabilities": probabilities,
        }

    def _explain_speed_restriction(self, data: Dict) -> Dict:
        """Generate explanation for speed restriction."""
        speed = data.get("recommended_speed_kmh", 130)
        risk_score = data.get("risk_score", 0)
        rationale = data.get("rationale", "")
        component_risks = data.get("component_risks", {})

        narrative = (
            f"Speed restriction recommended: **{speed} km/h** "
            f"(risk score: {risk_score:.2f}). {rationale}"
        )

        return {
            "type": "speed_restriction",
            "narrative": narrative,
            "component_risks": component_risks,
        }

    def _explain_dispatch(self, data: Dict) -> Dict:
        """Generate explanation for maintenance dispatch."""
        ticket_code = data.get("ticket_code", "")
        priority = data.get("priority", "medium")
        fault_type = data.get("fault_type", "unknown")

        narrative = (
            f"Maintenance ticket **{ticket_code}** created with "
            f"**{priority}** priority for {fault_type.replace('_', ' ')}."
        )

        return {
            "type": "maintenance_dispatch",
            "narrative": narrative,
        }

    def _explain_generic(self, data: Dict) -> Dict:
        return {
            "type": data.get("decision_type", "unknown"),
            "narrative": f"AI decision recorded: {json.dumps(data, default=str)[:500]}",
        }

    def _create_audit_record(self, data: Dict, explanation: Dict) -> Dict:
        """
        Create a tamper-evident audit record.

        Uses SHA-256 hash of decision data + explanation for integrity.
        """
        now = timezone.now()

        record = {
            "agent": self.AGENT_NAME,
            "timestamp": now.isoformat(),
            "decision_type": data.get("decision_type", "unknown"),
            "input_summary": {k: str(v)[:100] for k, v in data.items()},
            "explanation_type": explanation.get("type", "unknown"),
        }

        # Cryptographic hash for tamper detection
        record_str = json.dumps(record, sort_keys=True, default=str)
        record["integrity_hash"] = hashlib.sha256(record_str.encode()).hexdigest()

        # Write to Django AuditLog
        try:
            from railway.models import AuditLog
            AuditLog.objects.create(
                event_type=AuditLog.EventType.SYSTEM,
                entity_type="ai_decision",
                entity_id=data.get("track_section_id", 0) or 0,
                actor_type=AuditLog.ActorType.ML_PIPELINE,
                actor_identifier=self.AGENT_NAME,
                description=explanation.get("narrative", "")[:500],
                new_state=record,
            )
        except Exception as e:
            logger.warning(f"[{self.AGENT_NAME}] Audit write failed: {e}")

        return record
