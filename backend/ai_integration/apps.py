# backend/ai_integration/apps.py
"""
Django AppConfig for the AI Integration Layer.

This app has NO models, NO migrations, NO database tables.
It is a pure Python service layer that provides:
  - Abstract AI provider interface
  - Concrete provider implementations
  - Provider registry for hot-swapping AI backends
  - Prediction service for business logic consumption

# ---------------------------------------------------------------------------
# DATABASE MIGRATION NOTE
#
# This app creates NO database tables.
# Current DB: PostgreSQL
# Future DB: None
# Whether this code is PostgreSQL compatible: YES (no DB interaction)
# Whether teammate needs to modify anything: NO
# ---------------------------------------------------------------------------
"""

from django.apps import AppConfig


class AiIntegrationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ai_integration'
    verbose_name = 'AI Integration Layer'

    def ready(self):
        """
        Called when Django starts. We do NOT auto-initialize providers here
        because model files may not be available in all environments (e.g.,
        CI, testing, frontend-only development).

        Providers are lazy-loaded on first prediction request via the
        AIProviderRegistry.
        """
        pass
