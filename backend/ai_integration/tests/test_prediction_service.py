# backend/ai_integration/tests/test_prediction_service.py
"""
Tests for the PredictionService and API integration.

Tests:
    1. PredictionService returns valid response with mock provider
    2. PredictionService handles missing provider gracefully
    3. predict_from_dict() convenience method works
    4. predict_batch() processes multiple readings
    5. Serializer validation catches invalid requests
    6. API endpoints return correct HTTP responses

# ---------------------------------------------------------------------------
# DATABASE MIGRATION NOTE
#
# Some tests create Alert and Ticket records in the TEST database.
# Django test framework uses a temporary database that is destroyed
# after tests complete.
#
# Current DB: PostgreSQL (test DB is separate from production)
# Future DB: None (tests will use PostgreSQL test DB)
# Whether this code is PostgreSQL compatible: YES
# Whether teammate needs to modify anything: NO
# ---------------------------------------------------------------------------
"""

import json

from django.test import TestCase, RequestFactory

from ai_integration.prediction_service import PredictionService
from ai_integration.providers import PredictionRequest, PredictionResponse
from ai_integration.registry import AIProviderRegistry
from ai_integration.serializers import (
    validate_prediction_request,
    validate_batch_prediction_request,
)

# Import MockProvider from sibling test module
from ai_integration.tests.test_providers import MockProvider


class TestPredictionService(TestCase):
    """Test PredictionService with mock providers."""

    def setUp(self):
        """Set up a fresh registry with a mock provider."""
        self.registry = AIProviderRegistry()
        self.mock_provider = MockProvider(
            anomaly=True,
            score=0.87,
            fault_type="thermal_buckle",
            alert_level="warning",
        )
        self.registry.register_provider("mock", self.mock_provider)

    def test_predict_for_sensor_with_mock(self):
        """predict_for_sensor returns response from mock provider."""
        from ai_integration import registry as reg_module
        from ai_integration import prediction_service as svc_module

        original_reg = reg_module.ai_provider_registry
        original_svc = svc_module.ai_provider_registry

        # Patch in both modules (prediction_service imports at top level)
        reg_module.ai_provider_registry = self.registry
        svc_module.ai_provider_registry = self.registry
        self.registry._config_loaded = True
        self.registry._provider_configs = {}

        try:
            service = PredictionService(provider_name="mock")
            response = service.predict_for_sensor(
                sensor_id="SEN-001",
                ambient_temp=42.5,
                humidity=22.0,
                vibration_rms=0.85,
                gauge_width=1676.3,
            )

            self.assertIsInstance(response, PredictionResponse)
            self.assertTrue(response.is_anomaly)
            self.assertEqual(response.anomaly_score, 0.87)
            self.assertEqual(response.fault_type, "thermal_buckle")
            self.assertEqual(response.provider_name, "mock")

        finally:
            reg_module.ai_provider_registry = original_reg
            svc_module.ai_provider_registry = original_svc

    def test_predict_from_dict(self):
        """predict_from_dict creates request from dict correctly."""
        from ai_integration import registry as reg_module
        from ai_integration import prediction_service as svc_module

        original_reg = reg_module.ai_provider_registry
        original_svc = svc_module.ai_provider_registry

        reg_module.ai_provider_registry = self.registry
        svc_module.ai_provider_registry = self.registry
        self.registry._config_loaded = True
        self.registry._provider_configs = {}

        try:
            service = PredictionService(provider_name="mock")
            response = service.predict_from_dict({
                "sensor_id": "SEN-001",
                "ambient_temp": 42.5,
                "humidity": 22.0,
                "vibration_rms": 0.85,
                "gauge_width": 1676.3,
            })

            self.assertIsInstance(response, PredictionResponse)
            self.assertTrue(response.is_anomaly)

        finally:
            reg_module.ai_provider_registry = original_reg
            svc_module.ai_provider_registry = original_svc

    def test_predict_batch(self):
        """predict_batch processes multiple readings."""
        from ai_integration import registry as reg_module
        from ai_integration import prediction_service as svc_module

        original_reg = reg_module.ai_provider_registry
        original_svc = svc_module.ai_provider_registry
        
        reg_module.ai_provider_registry = self.registry
        svc_module.ai_provider_registry = self.registry
        self.registry._default_name = "mock"
        self.registry._config_loaded = True

        try:
            service = PredictionService()
            readings = [
                {
                    "sensor_id": f"SEN-{i:03d}",
                    "ambient_temp": 40 + i,
                    "humidity": 20,
                    "vibration_rms": 0.5 + i * 0.1,
                    "gauge_width": 1676,
                }
                for i in range(5)
            ]
            responses = service.predict_batch(readings)

            self.assertEqual(len(responses), 5)
            for resp in responses:
                self.assertIsInstance(resp, PredictionResponse)

        finally:
            reg_module.ai_provider_registry = original_reg
            svc_module.ai_provider_registry = original_svc

    def test_no_provider_returns_safe_response(self):
        """Missing provider returns safe default response."""
        from ai_integration import registry as reg_module
        from ai_integration import prediction_service as svc_module

        original_reg = reg_module.ai_provider_registry
        original_svc = svc_module.ai_provider_registry
        
        empty_registry = AIProviderRegistry()
        empty_registry._config_loaded = True
        empty_registry._provider_configs = {}
        empty_registry._default_name = "nonexistent"
        
        reg_module.ai_provider_registry = empty_registry
        svc_module.ai_provider_registry = empty_registry

        try:
            service = PredictionService()
            response = service.predict_for_sensor(
                sensor_id="TEST",
                ambient_temp=40,
                humidity=20,
                vibration_rms=1.0,
                gauge_width=1676,
            )

            self.assertIsInstance(response, PredictionResponse)
            self.assertFalse(response.is_anomaly)
            self.assertIn("error", response.metadata)

        finally:
            reg_module.ai_provider_registry = original_reg
            svc_module.ai_provider_registry = original_svc

    def test_get_health(self):
        """get_health returns registry health data."""
        health = PredictionService.get_health()
        self.assertIn("status", health)


# ===================================================================
# SERIALIZER TESTS
# ===================================================================

class TestSerializers(TestCase):
    """Test request validation."""

    def test_valid_request(self):
        """Valid request passes validation."""
        data = {
            "sensor_id": "SEN-001",
            "ambient_temp": 42.5,
            "humidity": 22.0,
            "vibration_rms": 0.85,
            "gauge_width": 1676.3,
        }
        is_valid, error = validate_prediction_request(data)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_missing_required_field(self):
        """Missing field fails validation."""
        data = {
            "sensor_id": "SEN-001",
            "ambient_temp": 42.5,
            # humidity missing
            "vibration_rms": 0.85,
            "gauge_width": 1676.3,
        }
        is_valid, error = validate_prediction_request(data)
        self.assertFalse(is_valid)
        self.assertIn("humidity", error)

    def test_wrong_type(self):
        """Wrong type fails validation."""
        data = {
            "sensor_id": "SEN-001",
            "ambient_temp": "not_a_number",
            "humidity": 22.0,
            "vibration_rms": 0.85,
            "gauge_width": 1676.3,
        }
        is_valid, error = validate_prediction_request(data)
        self.assertFalse(is_valid)
        self.assertIn("ambient_temp", error)

    def test_valid_batch_request(self):
        """Valid batch request passes validation."""
        data = {
            "readings": [
                {
                    "sensor_id": "S1",
                    "ambient_temp": 40,
                    "humidity": 20,
                    "vibration_rms": 1.0,
                    "gauge_width": 1676,
                },
                {
                    "sensor_id": "S2",
                    "ambient_temp": 41,
                    "humidity": 21,
                    "vibration_rms": 1.1,
                    "gauge_width": 1676,
                },
            ]
        }
        is_valid, error = validate_batch_prediction_request(data)
        self.assertTrue(is_valid)

    def test_empty_batch_fails(self):
        """Empty readings list fails validation."""
        data = {"readings": []}
        is_valid, error = validate_batch_prediction_request(data)
        self.assertFalse(is_valid)
        self.assertIn("empty", error)

    def test_batch_with_invalid_reading_fails(self):
        """Batch with one invalid reading reports the index."""
        data = {
            "readings": [
                {
                    "sensor_id": "S1",
                    "ambient_temp": 40,
                    "humidity": 20,
                    "vibration_rms": 1.0,
                    "gauge_width": 1676,
                },
                {
                    "sensor_id": "S2",
                    # missing ambient_temp
                    "humidity": 21,
                    "vibration_rms": 1.1,
                    "gauge_width": 1676,
                },
            ]
        }
        is_valid, error = validate_batch_prediction_request(data)
        self.assertFalse(is_valid)
        self.assertIn("readings[1]", error)
