# backend/ai_integration/api_urls.py
"""
Rakshak AI Integration — API URL Configuration
==================================================
Maps AI prediction endpoints under /api/ai/.

Endpoints:
    POST /api/ai/predict/        — Single sensor prediction
    POST /api/ai/predict/batch/  — Batch predictions
    GET  /api/ai/health/         — AI subsystem health check
    GET  /api/ai/providers/      — List registered providers

# ---------------------------------------------------------------------------
# DATABASE MIGRATION NOTE
#
# This module defines URL patterns only — zero database interaction.
# Current DB: PostgreSQL
# Future DB: None
# Whether this code is PostgreSQL compatible: YES (no DB interaction)
# Whether teammate needs to modify anything: NO
# ---------------------------------------------------------------------------
"""

from django.urls import path

from ai_integration.api_views import (
    health_view,
    predict_batch_view,
    predict_view,
    providers_view,
)

urlpatterns = [
    path('predict/', predict_view, name='ai-predict'),
    path('predict/batch/', predict_batch_view, name='ai-predict-batch'),
    path('health/', health_view, name='ai-health'),
    path('providers/', providers_view, name='ai-providers'),
]
