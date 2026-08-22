# backend/ai_integration/providers.py
"""
Rakshak AI Integration — Provider Abstraction Layer
======================================================
Defines the abstract interface and data contracts for ALL AI providers.

This is the SINGLE MOST IMPORTANT file in the AI integration layer.

It defines:
    1. PredictionRequest  — Standardized input (what the backend sends)
    2. PredictionResponse  — Standardized output (what the backend receives)
    3. BaseAIProvider      — Abstract interface (what every provider must implement)

DESIGN PRINCIPLES:
    - Backend ONLY knows PredictionRequest and PredictionResponse.
    - Backend NEVER imports from ai_engin/ directly.
    - Backend NEVER loads pickle files, .pt files, or any model artifacts.
    - Backend NEVER knows about PyTorch, joblib, sklearn, or any ML library.
    - All of that is encapsulated inside concrete providers.

FUTURE PROVIDERS (add by implementing BaseAIProvider):
    - LocalPickleProvider  — Current: loads trained models from disk
    - LLMProvider          — Future: sends sensor data to an LLM for analysis
    - CloudAIProvider      — Future: calls a remote AI API (e.g., Vertex AI)
    - EnsembleProvider     — Future: combines multiple providers' predictions
    - MockProvider         — Testing: returns deterministic predictions

WHO SHOULD USE THIS MODULE:
    - PredictionService (ai_integration/prediction_service.py)
    - Provider implementations (local_provider.py, future cloud_provider.py)
    - Tests (to create mock providers)

WHO SHOULD NEVER USE THIS MODULE:
    - Views (they go through PredictionService)
    - Templates
    - Frontend code

# ---------------------------------------------------------------------------
# DATABASE MIGRATION NOTE
#
# This module has ZERO database interaction.
# It defines pure Python dataclasses and an abstract base class.
# Current DB: PostgreSQL
# Future DB: None
# Whether this code is PostgreSQL compatible: YES (no DB interaction)
# Whether teammate needs to modify anything: NO
# ---------------------------------------------------------------------------
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("rakshak.ai_integration")


# ===================================================================
# DATA CONTRACTS — The ONLY shapes backend code ever sees
# ===================================================================

@dataclass
class PredictionRequest:
    """
    Standardized prediction input — provider-agnostic.

    Every AI provider receives this exact shape, regardless of whether
    it's a local pickle model, a cloud API, or an LLM.

    The four sensor fields match the Rakshak sensor schema:
        - ambient_temp:  Ambient temperature in °C
        - humidity:      Relative humidity in %
        - vibration_rms: RMS vibration in mm/s
        - gauge_width:   Track gauge width in mm

    These correspond to the four features the AI Engine was trained on
    (see ai_engin/inference/pipeline.py, line 164).

    Fields:
        sensor_id:        Hardware identifier for the source sensor.
                          Maps to railway.models.Sensor.sensor_code.
        ambient_temp:     Current ambient temperature reading.
        humidity:         Current humidity reading.
        vibration_rms:    Current vibration RMS reading.
        gauge_width:      Current gauge width reading.
        timestamp:        ISO 8601 timestamp of when reading was taken.
                          Optional; providers may use current time if None.
        track_section_id: Django PK of the TrackSection this sensor belongs to.
                          Used by downstream alert/ticket services — NOT by the
                          AI model itself.
        metadata:         Extensible key-value bag for provider-specific
                          parameters. Examples:
                            {'use_uncertainty': True}
                            {'model_version': '2.1.0'}
                            {'priority': 'high'}
    """

    sensor_id: str
    ambient_temp: float
    humidity: float
    vibration_rms: float
    gauge_width: float
    timestamp: Optional[str] = None
    track_section_id: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for logging, caching, or API transmission."""
        return {
            "sensor_id": self.sensor_id,
            "ambient_temp": self.ambient_temp,
            "humidity": self.humidity,
            "vibration_rms": self.vibration_rms,
            "gauge_width": self.gauge_width,
            "timestamp": self.timestamp,
            "track_section_id": self.track_section_id,
            "metadata": self.metadata,
        }


@dataclass
class PredictionResponse:
    """
    Standardized prediction output — provider-agnostic.

    This is the ONLY result type the backend ever sees from any AI provider.
    It contains everything needed for:
        - Anomaly detection  → is_anomaly, anomaly_score
        - Failure prediction → failure_probabilities, alert_level
        - Fault classification → fault_type, fault_confidence

    Design notes:
        - All scores are normalized to [0.0, 1.0].
        - failure_probabilities uses horizon keys: {"1h", "6h", "24h"}.
        - alert_level is derived by the provider: "none", "warning", "critical".
        - raw_result preserves the full provider response for debugging.
          It is NEVER used by business logic — only for logging/diagnostics.

    Fields:
        is_anomaly:             Whether an anomaly was detected.
        anomaly_score:          Anomaly confidence score, 0.0 (normal) to 1.0 (certain).
        failure_probabilities:  Per-horizon failure probability. Keys are time horizons
                                (e.g., "1h", "6h", "24h"). Values are probabilities [0, 1].
        fault_type:             Predicted fault category string (e.g., "rail_fracture",
                                "thermal_buckle"). "unknown" if no fault classified.
        fault_confidence:       Confidence in fault_type prediction, [0.0, 1.0].
        alert_level:            Provider-recommended alert level:
                                  "none"     — no action needed
                                  "warning"  — monitor closely
                                  "critical" — immediate attention required
        processing_time_ms:     Wall-clock time for the prediction in milliseconds.
        provider_name:          Name of the provider that generated this response.
                                Used for audit trails and debugging.
        raw_result:             Full unprocessed provider output. Business logic
                                MUST NOT depend on this field. It is for debugging
                                and advanced diagnostics only.
        metadata:               Extensible output metadata. Examples:
                                  {'tier_scores': {'stat': 0.2, 'iforest': 0.5, 'vae': 0.8}}
                                  {'model_version': '1.0.0'}
                                  {'uncertainty': {'1h': 0.05, '6h': 0.12, '24h': 0.20}}
    """

    is_anomaly: bool = False
    anomaly_score: float = 0.0
    failure_probabilities: Dict[str, float] = field(default_factory=dict)
    fault_type: str = "unknown"
    fault_confidence: float = 0.0
    alert_level: str = "none"
    processing_time_ms: float = 0.0
    provider_name: str = "unknown"
    raw_result: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for API responses, logging, or caching."""
        return {
            "is_anomaly": self.is_anomaly,
            "anomaly_score": round(self.anomaly_score, 4),
            "failure_probabilities": {
                k: round(v, 4) for k, v in self.failure_probabilities.items()
            },
            "fault_type": self.fault_type,
            "fault_confidence": round(self.fault_confidence, 4),
            "alert_level": self.alert_level,
            "processing_time_ms": round(self.processing_time_ms, 2),
            "provider_name": self.provider_name,
            "metadata": self.metadata,
        }

    @property
    def max_failure_probability(self) -> float:
        """Convenience: highest failure probability across all horizons."""
        if not self.failure_probabilities:
            return 0.0
        return max(self.failure_probabilities.values())

    @property
    def most_urgent_horizon(self) -> Optional[str]:
        """Convenience: horizon with the highest failure probability."""
        if not self.failure_probabilities:
            return None
        return max(self.failure_probabilities, key=self.failure_probabilities.get)

    @property
    def needs_alert(self) -> bool:
        """Whether this prediction should trigger an alert."""
        return self.alert_level in ("warning", "critical")

    @property
    def needs_immediate_action(self) -> bool:
        """Whether this prediction requires immediate attention."""
        return self.alert_level == "critical"


# ===================================================================
# ABSTRACT PROVIDER INTERFACE
# ===================================================================

class BaseAIProvider(ABC):
    """
    Abstract base class for ALL Rakshak AI providers.

    Every AI backend — whether local pickle, cloud API, LLM, or
    ensemble — MUST implement this interface.

    The backend ONLY communicates through:
        response = provider.predict(request)

    It never knows what happens inside predict(). That's the entire
    point of this abstraction.

    Contract:
        1. predict() MUST return a PredictionResponse, even on failure.
           On failure, return a response with is_anomaly=False and
           anomaly_score=0.0 — never raise exceptions into business logic.

        2. health_check() MUST return a dict with at least:
           {"status": "healthy"|"degraded"|"unhealthy", "provider": "..."}

        3. get_provider_name() MUST return a stable string identifier.

    Implementation guide for NEW providers:

        class MyCloudProvider(BaseAIProvider):
            def predict(self, request: PredictionRequest) -> PredictionResponse:
                # Call cloud API with request.to_dict()
                # Parse response into PredictionResponse
                return PredictionResponse(...)

            def health_check(self) -> dict:
                # Ping cloud API
                return {"status": "healthy", "provider": "my_cloud"}

            def get_provider_name(self) -> str:
                return "my_cloud"

    FUTURE LLM INTEGRATION NOTE:
        An LLM provider would receive the sensor data as a structured
        prompt, ask the LLM to analyze it, and parse the LLM's response
        into a PredictionResponse. The backend doesn't care that it's
        an LLM — it just sees PredictionResponse.

    FUTURE MULTI-MODEL INTEGRATION NOTE:
        An ensemble provider would internally call multiple providers
        (e.g., local + cloud), combine their PredictionResponses
        (e.g., weighted average of anomaly scores), and return a
        single unified PredictionResponse.
    """

    @abstractmethod
    def predict(self, request: PredictionRequest) -> PredictionResponse:
        """
        Run a prediction on the given sensor data.

        This is the PRIMARY method. Everything flows through here.

        Args:
            request: Standardized prediction input.

        Returns:
            PredictionResponse — ALWAYS. Never raise into caller.
            On internal failure, return a safe default response with
            is_anomaly=False, anomaly_score=0.0.
        """
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """
        Check if this provider is ready to serve predictions.

        Returns:
            Dict with at least:
                status:   "healthy" | "degraded" | "unhealthy"
                provider: Provider name string
            May include additional provider-specific diagnostics.
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """
        Return the stable identifier for this provider.

        Used in PredictionResponse.provider_name, audit logs, and
        health check dashboards.

        Examples: "local_pickle", "vertex_ai", "openai_gpt4", "ensemble"
        """
        pass

    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """
        Return model metadata, capabilities, and configuration.
        Must include window_size, model_version, supported_features,
        and any available threshold values.
        """
        pass

    def predict_batch(
        self, requests: List[PredictionRequest]
    ) -> List[PredictionResponse]:
        """
        Run predictions on a batch of inputs.

        Default implementation calls predict() in a loop.
        Concrete providers may override this for batch-optimized
        inference (e.g., GPU batching, bulk API calls).

        Args:
            requests: List of prediction inputs.

        Returns:
            List of PredictionResponses, one per request, in order.
        """
        return [self.predict(req) for req in requests]
