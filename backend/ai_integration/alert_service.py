# backend/ai_integration/alert_service.py
"""
Rakshak AI Integration — Alert Service
==========================================
Centralizes alert creation from AI predictions.

Extracted from AnomalyDetectionAgent._create_alert() to enable
reuse across agents, API views, and management commands.

WHO SHOULD USE THIS:
    - PredictionService (when auto-alert is enabled)
    - API views (POST /api/ai/predict/ with auto_alert=true)
    - Management commands that process sensor data in bulk
    - Any code that needs to create alerts from PredictionResponse

WHO SHOULD NEVER USE THIS:
    - Code that creates manual/system alerts (use Alert.objects.create)
    - Templates or frontend code

# ---------------------------------------------------------------------------
# DATABASE MIGRATION NOTE
#
# This module creates records in:
#   - rakshak_alert (via Alert.objects.create)
#   - rakshak_audit_log (via AuditLog.objects.create)
#
# Current DB: PostgreSQL
# Future DB: None
#
# Why this code exists:
#   Centralizes AI-driven alert creation logic that was previously
#   duplicated across agents. Uses transaction.atomic() for consistency.
#
# PostgreSQL compatible: YES
#   - transaction.atomic() is fully supported
#   - DecimalField for confidence_score is native PostgreSQL NUMERIC
#   - CharField(unique=True) for alert_code uses PostgreSQL unique index
#   - DateTimeField for generated_at uses PostgreSQL TIMESTAMPTZ
#   - All ORM operations are database-agnostic
#
# Whether teammate needs to modify anything: NO
#   No schema changes. Uses existing Alert and AuditLog models.
# ---------------------------------------------------------------------------
"""

import logging
from decimal import Decimal
from typing import Optional

from django.db import transaction
from django.utils import timezone

from ai_integration.providers import PredictionResponse
from ai_integration.severity import score_to_alert_level

logger = logging.getLogger("rakshak.ai_integration.alert_service")

# Minimum delay between duplicate alerts for the same section + type.
# Prevents one persistent fault from flooding the alert queue when
# predictions repeat inside a short window.
DEDUP_WINDOW_MINUTES = 30


def has_recent_duplicate_alert(
    track_section_id: int,
    alert_type: str,
    window_minutes: int = DEDUP_WINDOW_MINUTES,
) -> bool:
    """
    Return True if an active alert of the same type already exists for
    this track section within the dedup window.
    """
    from datetime import timedelta

    from railway.models import Alert

    since = timezone.now() - timedelta(minutes=window_minutes)
    return Alert.objects.filter(
        track_section_id=track_section_id,
        alert_type=alert_type,
        created_at__gte=since,
    ).exclude(status=Alert.Status.DISMISSED).exists()


class AlertService:
    """
    Service for creating alerts from AI prediction results.

    Provides a clean interface for converting PredictionResponse
    objects into Alert database records.

    Usage:
        from ai_integration.alert_service import AlertService

        service = AlertService()
        alert_id = service.create_anomaly_alert(
            response=prediction_response,
            track_section_id=7,
            sensor_id=42,
        )
    """

    def __init__(self):
        pass

    def _generate_alert_code(self) -> str:
        """
        Generate a globally unique, collision-resistant alert code (<= 20 chars).
        Format: ALT-YYYYMMDD-XXXXXX (e.g. ALT-20260823-A1B2C3) -> 19 chars.
        """
        import uuid
        now = timezone.now()
        unique_suffix = uuid.uuid4().hex[:6].upper()
        return f"ALT-{now.strftime('%Y%m%d')}-{unique_suffix}"

    def create_anomaly_alert(
        self,
        response: PredictionResponse,
        track_section_id: int,
        sensor_id: Optional[int] = None,
        reading_id: Optional[int] = None,
    ) -> Optional[int]:
        """
        Create an anomaly alert from a PredictionResponse.

        Only creates an alert if the response indicates an anomaly.

        Args:
            response:         PredictionResponse from any AI provider.
            track_section_id: TrackSection PK where the anomaly was detected.
            sensor_id:        Sensor PK that produced the reading (optional).
            reading_id:       SensorReading PK that triggered the alert (optional).

        Returns:
            Alert PK if created, None if no anomaly.

        # ---------------------------------------------------------------
        # DATABASE MIGRATION NOTE
        #
        # Inserts into: rakshak_alert, rakshak_audit_log
        # Uses: transaction.atomic()
        #
        # Current DB: PostgreSQL
        # Future DB: None
        # PostgreSQL compatible: YES
        # Teammate action: NONE
        # ---------------------------------------------------------------
        """
        if not response.is_anomaly:
            return None

        from railway.models import Alert, AuditLog

        score = response.anomaly_score

        # Dedup: collapse repeat predictions of the same fault on the same
        # section inside the window instead of flooding the alert queue.
        if has_recent_duplicate_alert(track_section_id, Alert.AlertType.ANOMALY):
            logger.info(
                f"AlertService: Suppressing duplicate anomaly alert for "
                f"section={track_section_id} within {DEDUP_WINDOW_MINUTES}min window"
            )
            return None

        # Map score → severity via centralized thresholds (severity.py)
        level = score_to_alert_level(score)
        if level == "critical":
            severity = Alert.Severity.CRITICAL
        elif level == "warning":
            severity = Alert.Severity.WARNING
        else:
            severity = Alert.Severity.INFO

        # Build description
        fault_info = ""
        if response.fault_type != "unknown":
            fault_info = (
                f" | Fault: {response.fault_type} "
                f"({response.fault_confidence:.1%})"
            )

        tier_scores = response.metadata.get("tier_scores", {})

        try:
            with transaction.atomic():
                alert = Alert.objects.create(
                    alert_code=self._generate_alert_code(),
                    track_section_id=track_section_id,
                    sensor_id=sensor_id,
                    trigger_reading_id=reading_id,
                    alert_type=Alert.AlertType.ANOMALY,
                    severity=severity,
                    title=f"Anomaly Detected (score: {score:.2f})",
                    description=(
                        f"AI anomaly detection triggered.\n"
                        f"Score: {score:.4f}\n"
                        f"Tier scores: {tier_scores}{fault_info}\n"
                        f"Provider: {response.provider_name}"
                    ),
                    confidence_score=Decimal(str(round(score, 4))),
                    generated_at=timezone.now(),
                    generated_by=Alert.GeneratedBy.ML_MODEL,
                )

                # Audit trail
                AuditLog.objects.create(
                    event_type=AuditLog.EventType.CREATE,
                    entity_type="alert",
                    entity_id=alert.pk,
                    actor_type=AuditLog.ActorType.ML_PIPELINE,
                    actor_identifier=f"alert_service/{response.provider_name}",
                    description=(
                        f"Anomaly alert created: score={score:.4f} "
                        f"provider={response.provider_name}"
                    ),
                )

            logger.info(
                f"AlertService: Created anomaly alert {alert.alert_code} "
                f"(severity={severity}, provider={response.provider_name})"
            )
            return alert.pk

        except Exception as e:
            logger.error(f"AlertService: Failed to create anomaly alert: {e}", exc_info=True)
            return None

    def create_predictive_alert(
        self,
        response: PredictionResponse,
        track_section_id: int,
        sensor_id: Optional[int] = None,
    ) -> Optional[int]:
        """
        Create a predictive failure alert from a PredictionResponse.

        Only creates an alert if the response indicates a warning or
        critical failure prediction.

        Args:
            response:         PredictionResponse from any AI provider.
            track_section_id: TrackSection PK.
            sensor_id:        Sensor PK (optional).

        Returns:
            Alert PK if created, None if no alert needed.

        # ---------------------------------------------------------------
        # DATABASE MIGRATION NOTE
        #
        # Inserts into: rakshak_alert, rakshak_audit_log
        # Uses: transaction.atomic()
        #
        # Current DB: PostgreSQL
        # Future DB: None
        # PostgreSQL compatible: YES
        # Teammate action: NONE
        # ---------------------------------------------------------------
        """
        if not response.needs_alert:
            return None

        from railway.models import Alert, AuditLog

        probs = response.failure_probabilities
        max_horizon = response.most_urgent_horizon or "unknown"
        max_prob = response.max_failure_probability

        severity = (
            Alert.Severity.CRITICAL
            if response.alert_level == "critical"
            else Alert.Severity.WARNING
        )

        try:
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

                AuditLog.objects.create(
                    event_type=AuditLog.EventType.CREATE,
                    entity_type="alert",
                    entity_id=alert.pk,
                    actor_type=AuditLog.ActorType.ML_PIPELINE,
                    actor_identifier=f"alert_service/{response.provider_name}",
                    description=(
                        f"Predictive alert: {max_horizon}={max_prob:.4f} "
                        f"provider={response.provider_name}"
                    ),
                )

            logger.info(
                f"AlertService: Created predictive alert {alert.alert_code} "
                f"(severity={severity})"
            )
            return alert.pk

        except Exception as e:
            logger.error(
                f"AlertService: Failed to create predictive alert: {e}",
                exc_info=True,
            )
            return None
