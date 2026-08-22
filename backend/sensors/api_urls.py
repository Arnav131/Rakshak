# backend/sensors/api_urls.py
"""
API URL routing for the AI prediction endpoints.

All endpoints return JSON and are consumed by the frontend
or any HTTP client for AI inference.
"""

from django.urls import path

from . import api_views

app_name = "predict_api"

urlpatterns = [
    path("", api_views.api_predict, name="predict"),
    path("health/", api_views.api_predict_health, name="health"),
    path("batch/", api_views.api_predict_batch, name="batch"),
]
