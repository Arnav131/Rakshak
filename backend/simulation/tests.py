from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from core.context_processors import navigation

User = get_user_model()


class SimulationAccessTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.non_staff = User.objects.create_user(username="viewer", password="secret123")
        self.staff = User.objects.create_user(username="admin", password="secret123", is_staff=True)

    def test_anonymous_simulation_page_redirects_to_login(self):
        response = self.client.get('/simulation/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_non_staff_simulation_page_returns_forbidden(self):
        self.client.force_login(self.non_staff)
        response = self.client.get('/simulation/')
        self.assertEqual(response.status_code, 403)

    def test_staff_simulation_page_renders(self):
        self.client.force_login(self.staff)
        response = self.client.get('/simulation/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Live Simulation')

    def test_non_staff_simulation_api_returns_forbidden(self):
        self.client.force_login(self.non_staff)
        response = self.client.post(
            '/api/simulation/run/',
            data='{"source": "Delhi", "destination": "Mumbai"}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn('Simulation is restricted to administrators.', response.json()['error'])

    def test_navigation_hides_simulation_for_non_staff(self):
        request = type('Req', (), {'user': self.non_staff, 'path': '/'} )()
        context = navigation(request)
        self.assertNotIn('Simulation', [item['name'] for item in context['nav_items']])

    def test_navigation_includes_simulation_for_staff(self):
        request = type('Req', (), {'user': self.staff, 'path': '/simulation/'} )()
        context = navigation(request)
        self.assertIn('Simulation', [item['name'] for item in context['nav_items']])

    def test_anonymous_simulation_api_returns_401_json(self):
        response = self.client.post(
            '/api/simulation/run/',
            data='{"source": "Delhi", "destination": "Mumbai"}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json().get('error'), 'Authentication required')

    def test_staff_simulation_run_successful(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            '/api/simulation/run/',
            data='{"source": "Akola Junction (AK)", "destination": "Alipurduar Junction (APDJ)"}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get('success'))
        self.assertEqual(len(data.get('readings', [])), 16)
        self.assertIn('prediction', data)
        self.assertIn('suggestions', data)

