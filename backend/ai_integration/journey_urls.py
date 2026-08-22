# backend/ai_integration/journey_urls.py
"""
URL routing for Journey Simulation API endpoints.

Routes:
    POST /api/journey/start/       → Start a journey simulation
    GET  /api/journey/scenarios/    → List available scenarios
"""

from django.urls import path

from ai_integration import journey_views

app_name = "journey_api"

urlpatterns = [
    path("start/", journey_views.api_journey_start, name="start"),
    path("scenarios/", journey_views.api_journey_scenarios, name="scenarios"),
]
