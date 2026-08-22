from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from unittest.mock import patch

User = get_user_model()


class SensorsApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.non_staff = User.objects.create_user(username="viewer", password="secret123")
        self.staff = User.objects.create_user(username="admin", password="secret123", is_staff=True)

    def test_predict_non_staff_forbidden(self):
        self.client.force_login(self.non_staff)
        response = self.client.post('/api/predict/', data='{}', content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_predict_invalid_json_returns_400(self):
        self.client.force_login(self.staff)
        response = self.client.post('/api/predict/', data='not-a-json', content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_predict_missing_fields_returns_400(self):
        self.client.force_login(self.staff)
        response = self.client.post('/api/predict/', data='{}', content_type='application/json')
        self.assertEqual(response.status_code, 400)

    @patch('ai_integration.prediction_service.PredictionService')
    def test_predict_staff_success(self, MockService):
        # Stub the prediction service to return a simple predictable response
        class DummyResponse:
            def __init__(self):
                self.is_anomaly = False
                self.anomaly_score = 0.0
                self.fault_type = 'normal'
                self.alert_level = 'none'

            def to_dict(self):
                return {
                    'is_anomaly': self.is_anomaly,
                    'anomaly_score': self.anomaly_score,
                    'fault_type': self.fault_type,
                    'alert_level': self.alert_level,
                }

        instance = MockService.return_value
        instance.predict_for_sensor.return_value = DummyResponse()

        self.client.force_login(self.staff)
        payload = {
            "ambient_temp": 25.0,
            "humidity": 40.0,
            "vibration_rms": 1.2,
            "gauge_width": 1676.0
        }
        import json
        response = self.client.post('/api/predict/', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get('success'))
        self.assertIn('prediction', data)

    @patch('ai_integration.prediction_service.PredictionService')
    def test_batch_predict_staff_success(self, MockService):
        class DummyResponse:
            def __init__(self):
                self.is_anomaly = False
                self.anomaly_score = 0.0
                self.fault_type = 'normal'
                self.alert_level = 'none'

            def to_dict(self):
                return {
                    'is_anomaly': self.is_anomaly,
                    'anomaly_score': self.anomaly_score,
                    'fault_type': self.fault_type,
                    'alert_level': self.alert_level,
                }

        instance = MockService.return_value
        instance.predict_for_sensor.return_value = DummyResponse()

        self.client.force_login(self.staff)
        import json
        payload = {
            "readings": [
                {"ambient_temp": 25.0, "humidity": 40.0, "vibration_rms": 1.2, "gauge_width": 1676.0},
                {"ambient_temp": 26.0, "humidity": 41.0, "vibration_rms": 1.3, "gauge_width": 1677.0}
            ]
        }
        response = self.client.post('/api/predict/batch/', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get('success'))
        self.assertEqual(data.get('count'), 2)

    def test_health_endpoint_accessible(self):
        response = self.client.get('/api/predict/health/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('status', data)
