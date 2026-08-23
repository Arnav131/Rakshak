# backend/ai_integration/prediction_service.py
"""
Rakshak AI Integration — Prediction Service
===============================================
High-level business-logic-facing prediction service.

This is the ONLY class that agents, views, and management commands
should call for AI predictions. It handles:
    - Provider selection via the registry
    - Error handling and graceful degradation
    - Request construction from raw sensor values
    - Logging and diagnostics

ARCHITECTURE POSITION:
    View / Agent
        ↓
    PredictionService  ← YOU ARE HERE
        ↓
    AIProviderRegistry
        ↓
    BaseAIProvider (LocalPickleProvider / Cloud / LLM)
        ↓
    PredictionResponse

WHO SHOULD USE THIS:
    - AnomalyDetectionAgent
    - FailurePredictionAgent
    - API views (POST /api/ai/predict/)
    - Management commands
    - Any future code that needs predictions

WHO SHOULD NEVER USE THIS:
    - Templates
    - Frontend JavaScript (use API endpoints)
    - Database models

WHY THIS EXISTS (instead of calling registry directly):
    1. Encapsulates provider selection logic
    2. Provides a simpler API (raw values → PredictionResponse)
    3. Centralizes error handling
    4. Single place to add cross-cutting concerns (logging, metrics, caching)
    5. Easier to mock in tests (mock one service, not the whole registry)

# ---------------------------------------------------------------------------
# DATABASE MIGRATION NOTE
#
# This module has ZERO direct database interaction.
# It constructs PredictionRequest objects and calls AI providers.
# Downstream consumers (AlertService, TicketService) write to the DB,
# but this module does not.
#
# Current DB: PostgreSQL
# Future DB: None
# Whether this code is PostgreSQL compatible: YES (no DB interaction)
# Whether teammate needs to modify anything: NO
# ---------------------------------------------------------------------------
"""

import logging
from typing import Any, Dict, List, Optional

from ai_integration.providers import PredictionRequest, PredictionResponse
from ai_integration.registry import ai_provider_registry

logger = logging.getLogger("rakshak.ai_integration.service")


class PredictionService:
    """
    Business-logic-facing prediction service.

    Provides a clean, simple API for running AI predictions without
    knowing anything about providers, model loading, or ML internals.

    Usage:
        service = PredictionService()

        # Simple prediction from raw values
        response = service.predict_for_sensor(
            sensor_id="SEN-VIB-001",
            ambient_temp=42.5,
            humidity=22.0,
            vibration_rms=0.85,
            gauge_width=1676.3,
            track_section_id=7,
        )

        if response.is_anomaly:
            print(f"Anomaly! Score: {response.anomaly_score}")
            print(f"Fault: {response.fault_type}")

        # Or from a dict (for agent compatibility)
        response = service.predict_from_dict({
            "sensor_id": "SEN-VIB-001",
            "ambient_temp": 42.5,
            "humidity": 22.0,
            "vibration_rms": 0.85,
            "gauge_width": 1676.3,
        })
    """

    def __init__(self, provider_name: Optional[str] = None):
        """
        Initialize the prediction service.

        Args:
            provider_name: Specific provider to use. None = use default
                           from settings.RAKSHAK_AI['DEFAULT_PROVIDER'].
        """
        self._provider_name = provider_name

    def _get_provider(self):
        """
        Get the AI provider instance from the registry.

        Returns:
            BaseAIProvider instance, or None if unavailable.
        """
        provider = ai_provider_registry.get_provider(self._provider_name)
        if provider is None:
            logger.error(
                f"PredictionService: No provider available "
                f"(requested: {self._provider_name or 'default'})"
            )
        return provider

    def predict_for_sensor(
        self,
        sensor_id: str,
        ambient_temp: float,
        humidity: float,
        vibration_rms: float,
        gauge_width: float,
        timestamp: Optional[str] = None,
        track_section_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PredictionResponse:
        """
        Run a prediction for a single sensor reading.

        This is the primary entry point for predictions.

        Args:
            sensor_id:        Sensor identifier (e.g., "SEN-VIB-001").
            ambient_temp:     Ambient temperature in °C.
            humidity:         Relative humidity in %.
            vibration_rms:    RMS vibration in mm/s.
            gauge_width:      Track gauge width in mm.
            timestamp:        ISO 8601 timestamp. None = current time.
            track_section_id: TrackSection PK for downstream alert/ticket creation.
            metadata:         Optional provider-specific parameters.

        Returns:
            PredictionResponse — always. Never raises exceptions.
            On failure, returns a safe default with is_anomaly=False.
        """
        provider = self._get_provider()
        if provider is None:
            return PredictionResponse(
                is_anomaly=False,
                anomaly_score=0.0,
                provider_name="none",
                metadata={
                    "error": "No AI provider available",
                    "status": "degraded",
                },
            )

        request = PredictionRequest(
            sensor_id=sensor_id,
            ambient_temp=ambient_temp,
            humidity=humidity,
            vibration_rms=vibration_rms,
            gauge_width=gauge_width,
            timestamp=timestamp,
            track_section_id=track_section_id,
            metadata=metadata or {},
        )

        try:
            response = provider.predict(request)

            # Log significant predictions
            if response.is_anomaly:
                logger.info(
                    f"PredictionService: Anomaly detected — "
                    f"sensor={sensor_id}, score={response.anomaly_score:.4f}, "
                    f"fault={response.fault_type}, alert={response.alert_level}"
                )

            return response

        except Exception as e:
            # This should NEVER happen (providers must catch their own errors),
            # but defense in depth.
            logger.error(
                f"PredictionService: Unexpected error from provider: {e}",
                exc_info=True,
            )
            return PredictionResponse(
                is_anomaly=False,
                anomaly_score=0.0,
                provider_name=provider.get_provider_name(),
                metadata={
                    "error": f"Unexpected provider error: {e}",
                    "status": "degraded",
                },
            )

    def predict_from_dict(
        self,
        data: Dict[str, Any],
        track_section_id: Optional[int] = None,
    ) -> PredictionResponse:
        """
        Run a prediction from a dictionary of sensor values.

        Convenience method for agent compatibility. Agents often
        pass data as dicts rather than individual kwargs.

        Args:
            data: Dict with keys matching PredictionRequest fields.
                  Required: sensor_id, ambient_temp, humidity,
                            vibration_rms, gauge_width.
            track_section_id: Override track section (optional).

        Returns:
            PredictionResponse — always.
        """
        return self.predict_for_sensor(
            sensor_id=str(data.get("sensor_id", "unknown")),
            ambient_temp=float(data.get("ambient_temp", 0)),
            humidity=float(data.get("humidity", 0)),
            vibration_rms=float(data.get("vibration_rms", 0)),
            gauge_width=float(data.get("gauge_width", 0)),
            timestamp=data.get("timestamp"),
            track_section_id=track_section_id or data.get("track_section_id"),
            metadata=data.get("metadata", {}),
        )

    def predict_batch(
        self,
        readings: List[Dict[str, Any]],
        track_section_id: Optional[int] = None,
    ) -> List[PredictionResponse]:
        """
        Run predictions on a batch of sensor readings.

        Args:
            readings: List of dicts with sensor values.
            track_section_id: Common track section for all readings.

        Returns:
            List of PredictionResponses, one per reading.
        """
        provider = self._get_provider()
        if provider is None:
            return [
                PredictionResponse(
                    is_anomaly=False,
                    anomaly_score=0.0,
                    provider_name="none",
                    metadata={
                        "error": "No AI provider available",
                        "status": "degraded",
                    },
                )
                for _ in readings
            ]

        requests = [
            PredictionRequest(
                sensor_id=str(r.get("sensor_id", "unknown")),
                ambient_temp=float(r.get("ambient_temp", 0)),
                humidity=float(r.get("humidity", 0)),
                vibration_rms=float(r.get("vibration_rms", 0)),
                gauge_width=float(r.get("gauge_width", 0)),
                timestamp=r.get("timestamp"),
                track_section_id=track_section_id or r.get("track_section_id"),
                metadata=r.get("metadata", {}),
            )
            for r in readings
        ]

        try:
            return provider.predict_batch(requests)
        except Exception as e:
            logger.error(
                f"PredictionService: Batch prediction failed: {e}",
                exc_info=True,
            )
            return [
                PredictionResponse(
                    is_anomaly=False,
                    anomaly_score=0.0,
                    provider_name=provider.get_provider_name(),
                    metadata={"error": str(e), "status": "degraded"},
                )
                for _ in requests
            ]

    @staticmethod
    def get_health() -> Dict[str, Any]:
        """
        Get health status of the AI subsystem.

        Returns:
            Dict with overall status and per-provider health.
        """
        return ai_provider_registry.health_check()

    def health_check(self) -> Dict[str, Any]:
        """Instance method alias for get_health()."""
        return self.get_health()

    def get_provider_metadata(self) -> Dict[str, Any]:
        """
        Get capabilities and metadata from the active provider.
        """
        provider = self._get_provider()
        if provider:
            return provider.get_metadata()
        return {}
