# ===========================================================================
# ai_integration — Rakshak AI Integration Layer
# ===========================================================================
#
# This Django app provides the AI-agnostic abstraction layer for the
# Rakshak backend. It decouples business logic from AI model internals
# by defining a standardized provider interface.
#
# Architecture:
#     View / Agent
#         ↓
#     PredictionService (this app)
#         ↓
#     AIProviderRegistry → BaseAIProvider
#         ↓
#     Concrete Provider (LocalPickleProvider / future LLM / Cloud)
#         ↓
#     PredictionResponse (standardized dataclass)
#
# WHO SHOULD USE THIS APP:
#     - Agents (anomaly detection, failure prediction, etc.)
#     - Management commands that need predictions
#     - API views that expose prediction endpoints
#
# WHO SHOULD NEVER USE THIS APP DIRECTLY:
#     - Templates (they render data, not trigger predictions)
#     - Frontend JS (it hits API endpoints, not Python imports)
#
# DATABASE INTERACTION:
#     This package has NO models and creates NO tables.
#     The alert_service and ticket_service modules write to existing
#     railway.models tables (Alert, Ticket, AuditLog) — but those
#     models are defined elsewhere and require no schema changes.
#
# ---------------------------------------------------------------------------
# DATABASE MIGRATION NOTE
#
# This code does NOT interact with the database schema.
# Current DB: PostgreSQL
# Future DB: None
# Whether this code is PostgreSQL compatible: YES (no DB interaction)
# Whether teammate needs to modify anything: NO
# ---------------------------------------------------------------------------
