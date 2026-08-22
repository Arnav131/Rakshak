# backend/simulation/test_generator.py
"""
Unit tests for the Rakshak Simulation Generator and Grok API integration.
"""

import json
import os
import unittest
from unittest.mock import MagicMock, patch

from simulation import generator


class GeneratorGrokTests(unittest.TestCase):
    def setUp(self):
        self.mock_readings_json = [
            {"ambient_temp": 28.5, "humidity": 55.0, "vibration_rms": 0.85, "gauge_width": 1676.0}
            for _ in range(16)
        ]

    @patch("simulation.generator.requests.post")
    def test_generate_grok_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(self.mock_readings_json)
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        readings, flavour_name, flavour_desc = generator._generate_grok(
            source="New Delhi",
            destination="Mumbai Central",
            api_key="xai-test-key-123",
            model="grok-2-latest",
        )

        self.assertEqual(len(readings), 16)
        self.assertEqual(readings[0]["ambient_temp"], 28.5)
        self.assertEqual(readings[0]["gauge_width"], 1676.0)
        self.assertTrue(len(flavour_name) > 0)
        self.assertTrue(len(flavour_desc) > 0)

        # Verify POST call details
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://api.x.ai/v1/chat/completions")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer xai-test-key-123")
        self.assertEqual(kwargs["json"]["model"], "grok-2-latest")
        self.assertEqual(len(kwargs["json"]["messages"]), 2)

    @patch("simulation.generator.requests.post")
    def test_generate_grok_handles_markdown_code_fences(self, mock_post):
        fenced_json = f"```json\n{json.dumps(self.mock_readings_json)}\n```"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": fenced_json}}]
        }
        mock_post.return_value = mock_response

        readings, flavour_name, flavour_desc = generator._generate_grok(
            source="Howrah",
            destination="Chennai Central",
            api_key="xai-test-key",
        )

        self.assertEqual(len(readings), 16)
        self.assertEqual(readings[0]["vibration_rms"], 0.85)

    @patch.dict(os.environ, {"GROK_API_KEY": "xai-test-key-123"}, clear=True)
    @patch("simulation.generator._generate_grok")
    def test_generate_journey_uses_grok_when_key_present(self, mock_gen_grok):
        mock_gen_grok.return_value = (self.mock_readings_json, "nominal", "test desc")

        readings, fn, fd, source_used = generator.generate_journey("Delhi", "Agra")

        self.assertEqual(source_used, "grok")
        self.assertEqual(len(readings), 16)
        mock_gen_grok.assert_called_once_with("Delhi", "Agra", "xai-test-key-123")

    @patch.dict(os.environ, {"GROK_API_KEY": "xai-invalid-key"}, clear=True)
    @patch("simulation.generator._generate_grok")
    def test_generate_journey_falls_back_when_grok_fails(self, mock_gen_grok):
        mock_gen_grok.side_effect = Exception("API connection timed out")

        # Without other LLM keys, it should fall back to physics_iot_rng
        readings, fn, fd, source_used = generator.generate_journey("Delhi", "Agra")

        self.assertEqual(source_used, "physics_iot_rng")
        self.assertEqual(len(readings), 16)

    @patch.dict(os.environ, {}, clear=True)
    def test_generate_journey_offline_physics_rng(self):
        readings, fn, fd, source_used = generator.generate_journey("Delhi", "Agra")

        self.assertEqual(source_used, "physics_iot_rng")
        self.assertEqual(len(readings), 16)
        for r in readings:
            self.assertIn("ambient_temp", r)
            self.assertIn("humidity", r)
            self.assertIn("vibration_rms", r)
            self.assertIn("gauge_width", r)
            self.assertTrue(15.0 <= r["ambient_temp"] <= 45.0)
            self.assertTrue(1670.0 <= r["gauge_width"] <= 1680.0)


if __name__ == "__main__":
    unittest.main()
