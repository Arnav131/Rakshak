"""
Rakshak Agent System — Failure Prediction Agent
==================================================
Wraps the TCN + Transformer + BiLSTM multi-horizon failure
prediction model with Monte Carlo Dropout uncertainty.
"""

import logging
from typing import Any, Dict, Optional

from agents.shared.base_agent import BaseAgent
from agents.shared.events import FailurePredictionEvent

logger = logging.getLogger("rakshak.agents.prediction")


class FailurePredictionAgent(BaseAgent):
    """
    Multi-horizon failure prediction with uncertainty estimation.

    Runs on validated sensor events and produces:
    - 1h / 6h / 24h failure probabilities
    - Calibrated uncertainty bounds (via MC Dropout)
    - Alert level classification (none / warning / critical)

    From agents_README:
        Autonomy: Event-driven
        Target: AUROC ≥ 0.95
        Refresh: Every 5 minutes per section
    """

    AGENT_NAME = "failure_prediction"
    AGENT_VERSION = "1.0.0"

    def __init__(self, config: Optional[Dict] = None):
        super().__init__(config)
        self._alert_threshold = self.config.get("alert_threshold", 0.7)
        self._critical_threshold = self.config.get("critical_threshold", 0.9)

    def process(self, data: Any) -> Dict:
        """
        Process failure prediction.

        This agent is typically invoked by the AnomalyDetectionAgent
        as part of the full pipeline. It can also run independently
        on a scheduled basis.

        Args:
            data: Dict with track_section_id and prediction results
                  from the AI Engine, OR raw sensor window

        Returns:
            Dict with failure probabilities, uncertainty, and alert level
        """
        track_section_id = data.get("track_section_id")
        probabilities = data.get("probabilities", {})
        uncertainty = data.get("uncertainty", {})

        if not probabilities:
            return {
                "track_section_id": track_section_id,
                "status": "no_prediction",
                "reason": "No probability data provided",
            }

        # Determine alert level
        max_prob = max(probabilities.values()) if probabilities else 0
        if max_prob >= self._critical_threshold:
            alert_level = "critical"
        elif max_prob >= self._alert_threshold:
            alert_level = "warning"
        else:
            alert_level = "none"

        # Create event
        event = FailurePredictionEvent(
            track_section_id=track_section_id,
            probabilities=probabilities,
            uncertainty=uncertainty,
            alert_level=alert_level,
        )

        # If critical or warning, create predictive alert
        if alert_level != "none" and track_section_id:
            self._escalate_prediction(track_section_id, probabilities, alert_level)

        return {
            "track_section_id": track_section_id,
            "probabilities": probabilities,
            "uncertainty": uncertainty,
            "alert_level": alert_level,
            "max_probability": max_prob,
            "event": event,
        }

    def _escalate_prediction(
        self,
        track_section_id: int,
        probabilities: Dict[str, float],
        alert_level: str,
    ):
        """Log and escalate concerning predictions."""
        max_horizon = max(probabilities, key=probabilities.get)
        max_prob = probabilities[max_horizon]

        logger.warning(
            f"[{self.AGENT_NAME}] FAILURE PREDICTION — "
            f"Section {track_section_id}: {alert_level.upper()} "
            f"({max_horizon}={max_prob:.1%})"
        )

        self.log_event(
            "create", "prediction", track_section_id,
            f"Failure prediction: {alert_level} — {max_horizon}={max_prob:.4f}",
        )
