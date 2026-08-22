# backend/ai_integration/journey_views.py
"""
Rakshak AI Integration — Journey Simulation API Views
========================================================
JSON endpoints for simulating train journeys during the hackathon demo.

Endpoints:
    POST /api/journey/start/      → Start a journey simulation
    GET  /api/journey/scenarios/   → List available simulation scenarios

All endpoints return JSON. No template rendering.

AI TEAM NOTE:
    Purpose:     HTTP interface for the JourneyService.
    How it works: Accepts station IDs and scenario, delegates to JourneyService,
                  returns journey results as JSON.
    Why introduced: Frontend needs API to trigger journey simulations.
    Future LLM compatibility: These views call JourneyService, which calls
                              PredictionService. Swapping providers is transparent.

CHANGE SUMMARY:
    Reason: Hackathon demo requires journey simulation API.
    Architecture impact: New views module. Only calls JourneyService.
    Future migration notes: May need authentication when moving to production.
    Backward compatibility: N/A — new endpoints, no existing callers affected.

# ---------------------------------------------------------------------------
# DATABASE MIGRATION NOTE
#
# This module has ZERO direct database interaction.
# It delegates all DB operations to JourneyService → AlertService/TicketService.
# Current DB: PostgreSQL
# Future DB: None
# Whether this code is PostgreSQL compatible: YES (no direct DB interaction)
# Whether teammate needs to modify anything: NO
# Migration required: NO
# ---------------------------------------------------------------------------
"""

import json
import logging

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.cache import never_cache

from ai_integration.journey_service import JourneyService

logger = logging.getLogger("rakshak.api.journey")


@csrf_exempt
@require_POST
@never_cache
def api_journey_start(request):
    """
    POST /api/journey/start/

    Start a simulated train journey.

    Request body (JSON):
        {
            "start_station_id": 1,
            "end_station_id": 5,
            "scenario": "gauge_widening",
            "sensor_id": "SIM-001",
            "seed": 42
        }

    Required fields: start_station_id, end_station_id
    Optional fields: scenario (default: "healthy"), sensor_id (default: "SIM-001"),
                     seed (default: None)

    Response:
        {
            "success": true,
            "journey": {
                "start_station": "New Delhi",
                "end_station": "Mumbai Central",
                "scenario": "gauge_widening",
                "sensor_id": "SIM-001",
                "readings_sent": 16,
                "prediction": { ... },
                "alert_created": true,
                "alert_id": 42,
                "ticket_created": false,
                "ticket_id": null,
                "buffering_responses": 15
            },
            "timestamp": "2026-08-08T..."
        }
    """
    # Parse JSON body
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError) as e:
        return JsonResponse(
            {"success": False, "error": f"Invalid JSON: {e}"},
            status=400,
        )

    # Validate required fields
    start_station_id = data.get("start_station_id")
    end_station_id = data.get("end_station_id")

    if not start_station_id or not end_station_id:
        return JsonResponse(
            {
                "success": False,
                "error": "Both 'start_station_id' and 'end_station_id' are required.",
            },
            status=400,
        )

    try:
        start_station_id = int(start_station_id)
        end_station_id = int(end_station_id)
    except (TypeError, ValueError):
        return JsonResponse(
            {"success": False, "error": "Station IDs must be integers."},
            status=400,
        )

    scenario = data.get("scenario", "healthy")
    sensor_id = data.get("sensor_id", "SIM-001")
    seed = data.get("seed")

    if seed is not None:
        try:
            seed = int(seed)
        except (TypeError, ValueError):
            seed = None

    # Execute journey
    service = JourneyService()

    try:
        result = service.start_journey(
            start_station_id=start_station_id,
            end_station_id=end_station_id,
            scenario=scenario,
            sensor_id=sensor_id,
            seed=seed,
        )
    except Exception as e:
        logger.error(f"Journey simulation failed: {e}", exc_info=True)
        return JsonResponse(
            {"success": False, "error": f"Journey simulation failed: {e}"},
            status=500,
        )

    return JsonResponse({
        "success": True,
        "journey": result.to_dict(),
        "timestamp": timezone.now().isoformat(),
    })


@require_GET
@never_cache
def api_journey_scenarios(request):
    """
    GET /api/journey/scenarios/

    List available simulation scenarios.

    Response:
        {
            "scenarios": [
                {
                    "id": "healthy",
                    "name": "Normal Journey",
                    "description": "All sensors within normal operating range."
                },
                ...
            ]
        }
    """
    scenarios = JourneyService.get_scenarios()
    return JsonResponse({"scenarios": scenarios})
