# backend/ai_integration/local_provider.py
"""
Rakshak AI Integration — Local Pickle/PyTorch Provider
=========================================================
Concrete provider that wraps the existing RakshakInferencePipeline.

This provider bridges the gap between the new AI-agnostic interface
(PredictionRequest → PredictionResponse) and the existing AI Engine
(process_reading() → PredictionResult).

RESPONSIBILITY:
    - Lazy-load the RakshakInferencePipeline from ai_engin/
    - Translate PredictionRequest → pipeline.process_reading() args
    - Translate PredictionResult → PredictionResponse
    - Handle all pipeline errors gracefully (never crash business logic)

WHO SHOULD USE THIS:
    - AIProviderRegistry (via settings configuration)

WHO SHOULD NEVER USE THIS:
    - Business logic (use PredictionService instead)
    - Views or agents (they don't know about specific providers)

FUTURE REPLACEMENT:
    When the team moves to a cloud AI model or LLM, this provider
    can be swapped out by changing one line in settings.py:
        RAKSHAK_AI['DEFAULT_PROVIDER'] = 'cloud'
    No business logic changes required.

# ---------------------------------------------------------------------------
# DATABASE MIGRATION NOTE
#
# This module has ZERO database interaction.
# It only calls the ai_engin inference pipeline (pure Python/ML code).
# Current DB: PostgreSQL
# Future DB: None
# Whether this code is PostgreSQL compatible: YES (no DB interaction)
# Whether teammate needs to modify anything: NO
# ---------------------------------------------------------------------------
"""

import logging
import os
import time
from typing import Any, Dict, Optional

from ai_integration.providers import (
    BaseAIProvider,
    PredictionRequest,
    PredictionResponse,
)

logger = logging.getLogger("rakshak.ai_integration.local")


class LocalPickleProvider(BaseAIProvider):
    """
    AI provider that wraps the local RakshakInferencePipeline.

    Loads trained models from the ai_engin/trained_models/ directory.
    Supports PyTorch (.pt) and joblib (.joblib) model files.

    This is the DEFAULT provider for the Rakshak prototype.

    Lazy initialization:
        The pipeline is NOT loaded at __init__ time. It is loaded on
        the first predict() call. This avoids import errors when:
        - Models haven't been trained yet
        - PyTorch is not installed in the environment
        - Running in a testing environment

    Thread safety:
        The underlying RakshakInferencePipeline is documented as
        thread-safe for Django request handling. This provider
        inherits that property.

    Graceful degradation:
        If the pipeline fails to load or any prediction fails, this
        provider returns a safe PredictionResponse with is_anomaly=False
        and anomaly_score=0.0. It NEVER raises exceptions into the
        caller.
    """

    def __init__(
        self,
        model_dir: str,
        window_size: int = 64,
        alert_threshold: float = 0.7,
        critical_threshold: float = 0.9,
    ):
        """
        Initialize the local provider configuration.

        NOTE: This does NOT load models. Models are lazy-loaded on
        first predict() call via _ensure_pipeline().

        Args:
            model_dir:           Path to the trained_models/ directory.
                                 Typically: <project_root>/ai_engin/trained_models/
            window_size:         Sliding window size for sequence models.
                                 Must match training configuration (default: 64).
            alert_threshold:     Failure probability threshold for 'warning' alerts.
            critical_threshold:  Failure probability threshold for 'critical' alerts.
        """
        self._model_dir = str(model_dir)
        self._window_size = window_size
        self._alert_threshold = alert_threshold
        self._critical_threshold = critical_threshold

        # Cache for metadata to prevent repeated disk reads
        self._cached_metadata: Optional[Dict[str, Any]] = None

        # Pipeline instance — lazy-loaded
        self._pipeline = None
        self._pipeline_loaded = False
        self._pipeline_error: Optional[str] = None

        logger.info(
            f"LocalPickleProvider configured "
            f"(model_dir={self._model_dir}, window_size={window_size})"
        )

    def _ensure_pipeline(self) -> bool:
        """
        Lazy-load the AI Engine inference pipeline.

        Returns:
            True if pipeline is ready, False if loading failed.
        """
        if self._pipeline is not None:
            return True

        if self._pipeline_loaded:
            return False

        self._pipeline_loaded = True

        try:
            if not os.path.exists(self._model_dir):
                raise FileNotFoundError(f"Model directory not found: {self._model_dir}")

            from ai_models.simple_pipeline import SimpleRakshakInferencePipeline

            self._pipeline = SimpleRakshakInferencePipeline(
                model_dir=self._model_dir,
            )

            if not self._pipeline.models_loaded:
                self._pipeline_error = f"Model directory {self._model_dir} contains no trained models."
                logger.warning(f"LocalPickleProvider: {self._pipeline_error}")
                return False

            logger.info(
                f"LocalPickleProvider: AI Engine pipeline loaded successfully from {self._model_dir}"
            )
            return True

        except FileNotFoundError as e:
            self._pipeline_error = (
                f"Model directory not found: {self._model_dir}. "
                f"Train models first. Error: {e}"
            )
            logger.warning(f"LocalPickleProvider: {self._pipeline_error}")
            return False

        except Exception as e:
            self._pipeline_error = f"Failed to load AI pipeline: {e}"
            logger.error(f"LocalPickleProvider: {self._pipeline_error}", exc_info=True)
            return False

    def predict(self, request: PredictionRequest) -> PredictionResponse:
        """
        Run prediction using the local AI Engine pipeline.
        """
        t0 = time.time()

        # --- Ensure pipeline is loaded ---
        if not self._ensure_pipeline():
            return PredictionResponse(
                is_anomaly=False,
                anomaly_score=0.0,
                provider_name=self.get_provider_name(),
                processing_time_ms=(time.time() - t0) * 1000,
                metadata={"error": self._pipeline_error or "Pipeline not loaded", "status": "degraded"},
            )

        # --- Run prediction through the AI Engine ---
        try:
            result = self._pipeline.predict(
                ambient_temp=request.ambient_temp,
                humidity=request.humidity,
                vibration_rms=request.vibration_rms,
                gauge_width=request.gauge_width,
            )

            elapsed_ms = (time.time() - t0) * 1000
            return self._translate_result(result, elapsed_ms)

        except Exception as e:
            elapsed_ms = (time.time() - t0) * 1000
            logger.error(
                f"LocalPickleProvider: Prediction failed for sensor "
                f"{request.sensor_id}: {e}",
                exc_info=True,
            )
            return PredictionResponse(
                is_anomaly=False,
                anomaly_score=0.0,
                provider_name=self.get_provider_name(),
                processing_time_ms=elapsed_ms,
                metadata={"error": str(e), "status": "degraded"},
            )

    def _translate_result(self, result: Dict[str, Any], elapsed_ms: float) -> PredictionResponse:
        """
        Translate the SimpleRakshakInferencePipeline dict into PredictionResponse.
        """
        is_anomaly = bool(result.get("is_anomaly", False))
        anomaly_score = float(result.get("anomaly_score", 0.0))
        alert_level = result.get("alert_level", "none")
        fault_type = result.get("fault_type", "none")
        fault_confidence = float(result.get("fault_confidence", 0.0))

        metadata = {
            "explanation": result.get("explanation", ""),
            "model_used": result.get("model_used", "rules_only"),
            "rule_triggers": result.get("rule_triggers", []),
            "top_features": result.get("top_features", {}),
            "fault_top_k": result.get("fault_top_k", {}),
        }

        return PredictionResponse(
            is_anomaly=is_anomaly,
            anomaly_score=anomaly_score,
            failure_probabilities={"24h": anomaly_score},
            fault_type=fault_type,
            fault_confidence=fault_confidence,
            alert_level=alert_level,
            processing_time_ms=elapsed_ms,
            provider_name=self.get_provider_name(),
            raw_result=result,
            metadata=metadata,
        )

    def health_check(self) -> Dict[str, Any]:
        """
        Check if the local AI pipeline is ready.
        """
        base = {
            "status": "unhealthy",
            "provider": self.get_provider_name(),
            "model_dir": self._model_dir,
            "model_dir_exists": os.path.isdir(self._model_dir),
        }

        if self._pipeline_error:
            base["error"] = self._pipeline_error
            return base

        if not self._ensure_pipeline():
            base["error"] = self._pipeline_error or "Pipeline not initialized"
            return base

        try:
            pipeline_health = self._pipeline.health_check()
            base.update({
                "status": "healthy" if pipeline_health.get("status") == "ok" else "degraded",
                "models": {
                    "anomaly": pipeline_health.get("risk_model_loaded", False),
                    "fault": pipeline_health.get("fault_model_loaded", False),
                },
                "device": "cpu",
                "mode": pipeline_health.get("mode", "unknown"),
                "model_version": pipeline_health.get("model_version", "unknown"),
            })
        except Exception as e:
            base["status"] = "degraded"
            base["error"] = f"Health check failed: {e}"

        return base

    def get_provider_name(self) -> str:
        """Return the stable identifier for this provider."""
        return "local_pickle"

    def get_metadata(self) -> Dict[str, Any]:
        """
        Return model metadata and configuration by reading model_config.json.
        Reads from disk only once and caches the result.
        """
        if self._cached_metadata is not None:
            return self._cached_metadata

        config_path = os.path.join(self._model_dir, "model_config.json")
        try:
            import json
            with open(config_path, 'r') as f:
                data = json.load(f)
                self._cached_metadata = {
                    "window_size": data.get("window_size", self._window_size),
                    "model_version": data.get("version", "unknown"),
                    "supported_features": data.get("feature_order", []),
                    "alert_threshold": self._alert_threshold,
                    "critical_threshold": self._critical_threshold
                }
        except Exception as e:
            logger.warning(f"LocalPickleProvider: Failed to read model metadata: {e}")
            self._cached_metadata = {
                "window_size": self._window_size,
                "model_version": "unknown",
                "supported_features": [],
                "alert_threshold": self._alert_threshold,
                "critical_threshold": self._critical_threshold
            }
            
        return self._cached_metadata

    def reset(self):
        """
        Force re-initialization of the pipeline.

        Use this after:
            - Deploying new model files
            - Fixing a model loading error
            - Changing model configuration
        """
        self._pipeline = None
        self._pipeline_loaded = False
        self._pipeline_error = None
        logger.info("LocalPickleProvider: Reset — pipeline will reload on next predict()")
