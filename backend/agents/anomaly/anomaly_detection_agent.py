"""
Rakshak Agent System — Anomaly Detection Agent
=================================================
3-tier anomaly detection pipeline that uses the AI Integration Layer
to run predictions and writes results to Django models.
#Hello World

ARCHITECTURE:
    SensorValidatedEvent
        ↓
    AnomalyDetectionAgent.process()
        ↓
    PredictionService.predict_for_sensor()     ← AI-agnostic service
        ↓
    AIProviderRegistry → BaseAIProvider         ← Provider abstraction
        ↓
    PredictionResponse                          ← Standardized result
        ↓
    Alert creation (if anomaly detected)
    Predictive alert (if failure predicted)

PREVIOUS ARCHITECTURE (before Sprint 2):
    This agent previously imported directly from:
        ai_engin.inference.pipeline.RakshakInferencePipeline
    That created a hard coupling to the local pickle model.

CURRENT ARCHITECTURE (after Sprint 2):
    This agent now uses:
        ai_integration.prediction_service.PredictionService
    The backend can now switch AI providers by changing settings.py
    without touching this agent.

Tier 1: Z-score + IQR (< 5ms) → fast statistical screen
Tier 2: Isolation Forest (< 50ms) → multivariate
Tier 3: VAE reconstruction (< 150ms) → deep learning
Meta:   GBM combining all tiers → calibrated probability

# ---------------------------------------------------------------------------
# DATABASE MIGRATION NOTE
#
# This agent creates Alert records via Alert.objects.create()
# and writes AuditLog entries via self.log_event().
#
# Current DB: PostgreSQL
# Future DB: PostgreSQL
#
# Why this code exists:
#   Creates anomaly and predictive alerts from AI predictions.
#
# PostgreSQL compatible: YES
#   - transaction.atomic() works identically in PostgreSQL
#   - DecimalField for confidence_score is native PostgreSQL
#   - CharField with unique=True for alert_code works identically
#   - DateTimeField for generated_at works identically
#
# Whether teammate needs to modify anything: NO
# ---------------------------------------------------------------------------
"""

import logging
from decimal import Decimal
from typing import Any, Dict, Optional

from django.db import transaction
from django.utils import timezone

from agents.shared.base_agent import BaseAgent
from agents.shared.events import AnomalyEvent, SensorValidatedEvent

logger = logging.getLogger("rakshak.agents.anomaly")


class AnomalyDetectionAgent(BaseAgent):
    """
    Anomaly detection agent backed by SimpleRakshakInferencePipeline.

    Receives SensorValidatedEvents from the ingestion agent,
    runs predictions through the AI Integration Layer, and
    creates Alert objects for detected anomalies.

    IMPORTANT:
        This agent does NOT directly import or use the AI Engine.
        It calls PredictionService, which calls the provider registry,
        which calls the configured AI provider (local, cloud, LLM, etc.).

    From agents_README:
        Autonomy: Event-driven
        Latency: < 200ms (p99)
    """

    AGENT_NAME = "anomaly_detection"
    AGENT_VERSION = "2.0.0"  # Bumped: now uses AI Integration Layer

    def __init__(self, config: Optional[Dict] = None):
        super().__init__(config)
        self._prediction_service = None

    def _ensure_prediction_service(self):
        """
        Lazy-initialize the PredictionService.

        PREVIOUS: Directly loaded RakshakInferencePipeline from ai_engin/
        NOW: Creates a PredictionService that delegates to the configured
             AI provider via the registry.

        The import is deferred to avoid circular imports and to allow
        the agent to be instantiated even when AI dependencies are
        not installed.
        """
        if self._prediction_service is not None:
            return

        try:
            from ai_integration.prediction_service import PredictionService
            self._prediction_service = PredictionService()
            logger.info(f"[{self.AGENT_NAME}] PredictionService initialized")
        except Exception as e:
            logger.error(
                f"[{self.AGENT_NAME}] Failed to initialize PredictionService: {e}"
            )
            self._prediction_service = None

    def _generate_alert_code(self) -> str:
        """Generate a unique, collision-resistant alert code.

        Uses a UUID suffix instead of an in-memory counter: counters
        restart at 0001 on process restart and collide with the unique
        alert_code constraint.
        """
        import uuid

        now = timezone.now()
        unique_suffix = uuid.uuid4().hex[:6].upper()
        return f"ALT-{now.strftime('%Y%m%d')}-{unique_suffix}"

    def process(self, data: Any) -> Dict:
        """
        Process a sensor event through the AI-agnostic prediction pipeline.

        FLOW:
            1. Extract sensor values from event/dict
            2. Call PredictionService.predict_for_sensor()
            3. If anomaly → create Alert
            4. If failure prediction → create predictive Alert
            5. Return structured response

        Args:
            data: SensorValidatedEvent or dict with sensor values:
                  {ambient_temp, humidity, vibration_rms, gauge_width,
                   sensor_id?, track_section_id?, reading_id?}

        Returns:
            Dict with anomaly detection results and optional alert_id

        # ---------------------------------------------------------------
        # DATABASE MIGRATION NOTE
        #
        # This method creates Alert objects (via _create_alert and
        # _create_predictive_alert) which INSERT into rakshak_alert.
        #
        # Current DB: PostgreSQL
        # Future DB: PostgreSQL
        # PostgreSQL compatible: YES
        # Teammate action: NONE
        # ---------------------------------------------------------------
        """
        self._ensure_prediction_service()

        # --- Extract sensor values ---
        if isinstance(data, SensorValidatedEvent):
            sensor_id = data.sensor_id
            track_section_id = data.track_section_id
            reading_id = data.reading_id
            values = {
                "ambient_temp": data.ambient_temp,
                "humidity": data.humidity,
                "vibration_rms": data.vibration_rms,
                "gauge_width": data.gauge_width,
            }
        else:
            sensor_id = data.get("sensor_id")
            track_section_id = data.get("track_section_id")
            reading_id = data.get("reading_id")
            values = {
                "ambient_temp": data.get("ambient_temp", 0),
                "humidity": data.get("humidity", 0),
                "vibration_rms": data.get("vibration_rms", 0),
                "gauge_width": data.get("gauge_width", 0),
            }

        # --- Run prediction through AI Integration Layer ---
        if self._prediction_service is None:
            return {
                "anomaly_detected": False,
                "error": "PredictionService not available",
                "sensor_id": sensor_id,
            }

        # This is the key decoupling point:
        # We call predict_for_sensor() instead of pipeline.process_reading().
        # The PredictionService handles provider selection, error handling,
        # and returns a PredictionResponse regardless of which AI backend
        # is configured (local pickle, cloud API, LLM, etc.).
        response = self._prediction_service.predict_for_sensor(
            sensor_id=str(sensor_id or "default"),
            ambient_temp=values["ambient_temp"],
            humidity=values["humidity"],
            vibration_rms=values["vibration_rms"],
            gauge_width=values["gauge_width"],
            track_section_id=track_section_id,
        )

        # --- Handle buffering state ---
        # When the provider is accumulating readings into a window,
        # it returns a response with metadata["status"] == "buffering".
        if response.metadata.get("status") == "buffering":
            return {
                "anomaly_detected": False,
                "buffering": True,
                "sensor_id": sensor_id,
            }

        # --- Handle errors ---
        if response.metadata.get("error"):
            return {
                "anomaly_detected": False,
                "error": response.metadata["error"],
                "sensor_id": sensor_id,
            }

        # --- Build response dict ---
        result = {
            "anomaly_detected": response.is_anomaly,
            "anomaly_score": response.anomaly_score,
            "tier_scores": response.metadata.get("tier_scores", {}),
            "failure_prediction": {
                "probabilities": response.failure_probabilities,
                "uncertainty": response.metadata.get("uncertainty", {}),
                "alert_level": response.alert_level,
            },
            "processing_time_ms": response.processing_time_ms,
            "sensor_id": sensor_id,
            "provider": response.provider_name,
        }

        # --- If anomaly detected → create Alert ---
        if response.is_anomaly and track_section_id:
            alert_id = self._create_alert_from_response(
                track_section_id=track_section_id,
                sensor_id=sensor_id,
                reading_id=reading_id,
                response=response,
            )
            result["alert_id"] = alert_id

            # Add fault classification
            if response.fault_type != "unknown":
                result["fault_type"] = response.fault_type
                result["fault_confidence"] = response.fault_confidence
                result["fault_top_k"] = response.metadata.get("fault_top_k", [])

            # Emit event for downstream agents
            result["event"] = AnomalyEvent(
                alert_id=alert_id,
                track_section_id=track_section_id,
                sensor_id=sensor_id,
                anomaly_score=response.anomaly_score,
                is_anomaly=True,
                tier_scores=response.metadata.get("tier_scores", {}),
                fault_type=response.fault_type,
                fault_confidence=response.fault_confidence,
                detected_at=timezone.now().isoformat(),
            )

        # --- If failure prediction is concerning → create predictive alert ---
        if response.needs_alert and track_section_id:
            self._create_predictive_alert_from_response(
                track_section_id=track_section_id,
                sensor_id=sensor_id,
                response=response,
            )

        return result

    def _create_alert_from_response(
        self,
        track_section_id: int,
        sensor_id: Optional[int],
        reading_id: Optional[int],
        response,
    ) -> int:
        """
        Create an Alert record from a PredictionResponse.

        PREVIOUS: Accepted raw PredictionResult from ai_engin.
        NOW: Accepts PredictionResponse from the AI Integration Layer.

        # ---------------------------------------------------------------
        # DATABASE MIGRATION NOTE
        #
        # Inserts into: rakshak_alert
        # Uses: transaction.atomic(), Alert.objects.create()
        #
        # Current DB: PostgreSQL
        # Future DB: PostgreSQL
        # PostgreSQL compatible: YES
        # Teammate action: NONE
        # ---------------------------------------------------------------
        """
        from railway.models import Alert
        from ai_integration.severity import score_to_alert_level

        # Determine severity from anomaly score via centralized thresholds
        score = response.anomaly_score
        level = score_to_alert_level(score)
        if level == "critical":
            severity = Alert.Severity.CRITICAL
        elif level == "warning":
            severity = Alert.Severity.WARNING
        else:
            severity = Alert.Severity.INFO

        fault_info = ""
        if response.fault_type != "unknown":
            fault_info = (
                f" | Fault: {response.fault_type} "
                f"({response.fault_confidence:.1%})"
            )

        tier_scores = response.metadata.get("tier_scores", {})

        with transaction.atomic():
            alert = Alert.objects.create(
                alert_code=self._generate_alert_code(),
                track_section_id=track_section_id,
                sensor_id=sensor_id,
                trigger_reading_id=reading_id,
                alert_type="anomaly",
                severity=severity,
                title=f"Anomaly Detected: {response.fault_type} (score: {score:.2f})",
                description=(
                    f"AI anomaly detection triggered.\n"
                    f"Score: {score:.4f}\n"
                    f"Tier scores: {tier_scores}{fault_info}\n"
                    f"Provider: {response.provider_name}"
                ),
                confidence_score=Decimal(str(round(score, 4))),
                generated_at=timezone.now(),
                generated_by="ml_model",
            )

        self.log_event(
            "create", "alert", alert.pk,
            f"Anomaly alert: score={score:.4f} provider={response.provider_name}",
        )
        logger.info(
            f"[{self.AGENT_NAME}] Created alert {alert.alert_code} "
            f"(severity={severity}, provider={response.provider_name})"
        )

        return alert.pk

    def _create_predictive_alert_from_response(
        self,
        track_section_id: int,
        sensor_id: Optional[int],
        response,
    ):
        """
        Create a predictive alert from a PredictionResponse.

        PREVIOUS: Accepted raw PredictionResult from ai_engin.
        NOW: Accepts PredictionResponse from the AI Integration Layer.

        # ---------------------------------------------------------------
        # DATABASE MIGRATION NOTE
        #
        # Inserts into: rakshak_alert
        # Uses: transaction.atomic(), Alert.objects.create()
        #
        # Current DB: PostgreSQL
        # Future DB: PostgreSQL
        # PostgreSQL compatible: YES
        # Teammate action: NONE
        # ---------------------------------------------------------------
        """
        from railway.models import Alert

        probs = response.failure_probabilities
        max_horizon = response.most_urgent_horizon or "unknown"
        max_prob = response.max_failure_probability

        severity = (
            Alert.Severity.CRITICAL
            if response.alert_level == "critical"
            else Alert.Severity.WARNING
        )

        with transaction.atomic():
            alert = Alert.objects.create(
                alert_code=self._generate_alert_code(),
                track_section_id=track_section_id,
                sensor_id=sensor_id,
                alert_type=Alert.AlertType.PREDICTION,
                severity=severity,
                title=f"Failure Predicted within {max_horizon} (P={max_prob:.1%})",
                description=(
                    f"Multi-horizon failure prediction:\n"
                    + "\n".join(f"  {h}: {p:.1%}" for h, p in probs.items())
                    + f"\nAlert level: {response.alert_level}"
                    + f"\nProvider: {response.provider_name}"
                ),
                confidence_score=Decimal(str(round(max_prob, 4))),
                generated_at=timezone.now(),
                generated_by=Alert.GeneratedBy.ML_MODEL,
            )

        self.log_event(
            "create", "alert", alert.pk,
            f"Predictive alert: {max_horizon}={max_prob:.4f} "
            f"provider={response.provider_name}",
        )
