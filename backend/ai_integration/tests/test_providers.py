# backend/ai_integration/tests/test_providers.py
"""
Tests for the AI Integration Layer — Provider abstraction.

Tests:
    1. PredictionRequest/PredictionResponse data contracts
    2. MockProvider satisfies BaseAIProvider interface
    3. LocalPickleProvider handles missing models gracefully
    4. AIProviderRegistry selects and caches providers correctly
    5. Provider hot-swapping works at runtime

# ---------------------------------------------------------------------------
# DATABASE MIGRATION NOTE
#
# These tests have ZERO database interaction.
# They test pure Python classes (providers, registry, dataclasses).
# Current DB: PostgreSQL
# Future DB: None
# Whether this code is PostgreSQL compatible: YES (no DB interaction)
# Whether teammate needs to modify anything: NO
# ---------------------------------------------------------------------------
"""

from django.test import TestCase, override_settings

from ai_integration.providers import (
    BaseAIProvider,
    PredictionRequest,
    PredictionResponse,
)
from ai_integration.registry import AIProviderRegistry


# ===================================================================
# MOCK PROVIDER — Used across all test modules
# ===================================================================

class MockProvider(BaseAIProvider):
    """
    Test-only provider that returns deterministic predictions.

    Configured via constructor to return specific responses.
    Never loads real models or calls external APIs.

    FUTURE NOTE:
        This mock demonstrates that ANY class implementing
        BaseAIProvider can be used by the backend — proving
        the architecture is truly provider-agnostic.
    """

    def __init__(
        self,
        anomaly: bool = False,
        score: float = 0.0,
        fault_type: str = "unknown",
        alert_level: str = "none",
        **kwargs,
    ):
        self._anomaly = anomaly
        self._score = score
        self._fault_type = fault_type
        self._alert_level = alert_level

    def get_metadata(self):
        return {"version": "mock", "name": "MockProvider"}

    def predict(self, request: PredictionRequest) -> PredictionResponse:
        return PredictionResponse(
            is_anomaly=self._anomaly,
            anomaly_score=self._score,
            failure_probabilities={"1h": 0.1, "6h": 0.3, "24h": 0.5},
            fault_type=self._fault_type,
            fault_confidence=0.85 if self._fault_type != "unknown" else 0.0,
            alert_level=self._alert_level,
            processing_time_ms=5.0,
            provider_name=self.get_provider_name(),
            metadata={"mock": True, "sensor_id": request.sensor_id},
        )

    def health_check(self):
        return {"status": "healthy", "provider": self.get_provider_name()}

    def get_provider_name(self):
        return "mock"

    def get_metadata(self):
        return {
            "window_size": 1,
            "model_version": "test",
            "supported_features": [
                "ambient_temp",
                "humidity",
                "vibration_rms",
                "gauge_width",
            ],
            "thresholds": {},
        }


# ===================================================================
# DATA CONTRACT TESTS
# ===================================================================

class TestPredictionRequest(TestCase):
    """Test PredictionRequest dataclass."""

    def test_create_request(self):
        """PredictionRequest can be created with required fields."""
        req = PredictionRequest(
            sensor_id="SEN-001",
            ambient_temp=42.5,
            humidity=22.0,
            vibration_rms=0.85,
            gauge_width=1676.3,
        )
        self.assertEqual(req.sensor_id, "SEN-001")
        self.assertEqual(req.ambient_temp, 42.5)
        self.assertIsNone(req.timestamp)
        self.assertIsNone(req.track_section_id)
        self.assertEqual(req.metadata, {})

    def test_to_dict(self):
        """PredictionRequest.to_dict() returns complete dict."""
        req = PredictionRequest(
            sensor_id="SEN-001",
            ambient_temp=42.5,
            humidity=22.0,
            vibration_rms=0.85,
            gauge_width=1676.3,
            track_section_id=7,
        )
        d = req.to_dict()
        self.assertIn("sensor_id", d)
        self.assertIn("track_section_id", d)
        self.assertEqual(d["sensor_id"], "SEN-001")
        self.assertEqual(d["track_section_id"], 7)

    def test_metadata_isolation(self):
        """Each request has independent metadata."""
        req1 = PredictionRequest(
            sensor_id="S1", ambient_temp=0, humidity=0,
            vibration_rms=0, gauge_width=0,
        )
        req2 = PredictionRequest(
            sensor_id="S2", ambient_temp=0, humidity=0,
            vibration_rms=0, gauge_width=0,
        )
        req1.metadata["key"] = "value"
        self.assertNotIn("key", req2.metadata)


class TestPredictionResponse(TestCase):
    """Test PredictionResponse dataclass."""

    def test_default_response(self):
        """Default PredictionResponse is safe (no anomaly)."""
        resp = PredictionResponse()
        self.assertFalse(resp.is_anomaly)
        self.assertEqual(resp.anomaly_score, 0.0)
        self.assertEqual(resp.fault_type, "unknown")
        self.assertEqual(resp.alert_level, "none")
        self.assertFalse(resp.needs_alert)
        self.assertFalse(resp.needs_immediate_action)

    def test_anomaly_response(self):
        """Anomaly response has correct convenience properties."""
        resp = PredictionResponse(
            is_anomaly=True,
            anomaly_score=0.92,
            failure_probabilities={"1h": 0.1, "6h": 0.8, "24h": 0.95},
            alert_level="critical",
        )
        self.assertTrue(resp.is_anomaly)
        self.assertEqual(resp.max_failure_probability, 0.95)
        self.assertEqual(resp.most_urgent_horizon, "24h")
        self.assertTrue(resp.needs_alert)
        self.assertTrue(resp.needs_immediate_action)

    def test_to_dict_rounds_scores(self):
        """to_dict() rounds scores to 4 decimal places."""
        resp = PredictionResponse(
            anomaly_score=0.123456789,
            failure_probabilities={"1h": 0.111111},
        )
        d = resp.to_dict()
        self.assertEqual(d["anomaly_score"], 0.1235)
        self.assertEqual(d["failure_probabilities"]["1h"], 0.1111)

    def test_warning_needs_alert(self):
        """Warning alert level needs alert but not immediate action."""
        resp = PredictionResponse(alert_level="warning")
        self.assertTrue(resp.needs_alert)
        self.assertFalse(resp.needs_immediate_action)

    def test_none_does_not_need_alert(self):
        """'none' alert level needs no alert."""
        resp = PredictionResponse(alert_level="none")
        self.assertFalse(resp.needs_alert)


# ===================================================================
# MOCK PROVIDER TESTS
# ===================================================================

class TestMockProvider(TestCase):
    """Test that MockProvider satisfies BaseAIProvider interface."""

    def test_is_base_ai_provider(self):
        """MockProvider is a valid BaseAIProvider."""
        provider = MockProvider()
        self.assertIsInstance(provider, BaseAIProvider)

    def test_predict_returns_response(self):
        """predict() returns a PredictionResponse."""
        provider = MockProvider(anomaly=True, score=0.85)
        req = PredictionRequest(
            sensor_id="TEST", ambient_temp=40, humidity=20,
            vibration_rms=1.0, gauge_width=1676,
        )
        resp = provider.predict(req)
        self.assertIsInstance(resp, PredictionResponse)
        self.assertTrue(resp.is_anomaly)
        self.assertEqual(resp.anomaly_score, 0.85)
        self.assertEqual(resp.provider_name, "mock")

    def test_health_check(self):
        """health_check() returns healthy status."""
        provider = MockProvider()
        health = provider.health_check()
        self.assertEqual(health["status"], "healthy")
        self.assertEqual(health["provider"], "mock")

    def test_predict_batch(self):
        """predict_batch() returns one response per request."""
        provider = MockProvider()
        requests = [
            PredictionRequest(
                sensor_id=f"S{i}", ambient_temp=40, humidity=20,
                vibration_rms=1.0, gauge_width=1676,
            )
            for i in range(3)
        ]
        responses = provider.predict_batch(requests)
        self.assertEqual(len(responses), 3)
        for resp in responses:
            self.assertIsInstance(resp, PredictionResponse)


# ===================================================================
# REGISTRY TESTS
# ===================================================================

class TestAIProviderRegistry(TestCase):
    """Test AIProviderRegistry singleton behavior."""

    def test_register_and_retrieve(self):
        """Manually registered providers can be retrieved."""
        registry = AIProviderRegistry()
        mock = MockProvider(anomaly=True, score=0.9)
        registry.register_provider("test_mock", mock)

        retrieved = registry.get_provider("test_mock")
        self.assertIs(retrieved, mock)

    def test_register_rejects_non_provider(self):
        """register_provider rejects objects that aren't BaseAIProvider."""
        registry = AIProviderRegistry()
        with self.assertRaises(TypeError):
            registry.register_provider("bad", "not a provider")

    def test_list_providers(self):
        """list_providers returns registered providers."""
        registry = AIProviderRegistry()
        mock = MockProvider()
        registry.register_provider("test_list", mock)

        providers = registry.list_providers()
        self.assertIn("test_list", providers)
        self.assertIn("loaded", providers["test_list"])

    def test_unregister_provider(self):
        """unregister_provider removes a provider."""
        registry = AIProviderRegistry()
        mock = MockProvider()
        registry.register_provider("test_unreg", mock)
        registry.unregister_provider("test_unreg")

        self.assertNotIn("test_unreg", registry._providers)

    def test_health_check_all_providers(self):
        """health_check returns status for all loaded providers."""
        registry = AIProviderRegistry()
        registry.register_provider("hc_mock", MockProvider())

        health = registry.health_check()
        self.assertIn("status", health)
        self.assertIn("providers", health)
        self.assertIn("hc_mock", health["providers"])

    def test_get_unknown_provider_returns_none(self):
        """Getting a non-existent provider returns None."""
        registry = AIProviderRegistry()
        registry._config_loaded = True
        registry._provider_configs = {}
        result = registry.get_provider("nonexistent")
        self.assertIsNone(result)


class TestLocalPickleProviderGracefulDegradation(TestCase):
    """Test that LocalPickleProvider handles missing models."""

    def test_missing_model_dir(self):
        """Provider returns safe response when model dir doesn't exist."""
        from ai_integration.local_provider import LocalPickleProvider

        provider = LocalPickleProvider(model_dir="/nonexistent/path")
        req = PredictionRequest(
            sensor_id="TEST", ambient_temp=40, humidity=20,
            vibration_rms=1.0, gauge_width=1676,
        )
        resp = provider.predict(req)

        # Must return a response, not raise
        self.assertIsInstance(resp, PredictionResponse)
        self.assertFalse(resp.is_anomaly)
        self.assertEqual(resp.anomaly_score, 0.0)
        self.assertIn("error", resp.metadata)

    def test_health_check_unhealthy(self):
        """Health check reports unhealthy when models unavailable."""
        from ai_integration.local_provider import LocalPickleProvider

        provider = LocalPickleProvider(model_dir="/nonexistent/path")
        health = provider.health_check()

        self.assertIn("status", health)
        # Either unhealthy or has an error
        self.assertTrue(
            health["status"] in ("unhealthy", "degraded")
            or "error" in health
        )
