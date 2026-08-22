# backend/ai_integration/serializers.py
"""
Rakshak AI Integration — Request/Response Serializers
========================================================
Input validation and output formatting for API views.

Uses plain Python (no Django REST Framework dependency) to
validate JSON request bodies and format API responses.

# ---------------------------------------------------------------------------
# DATABASE MIGRATION NOTE
#
# This module has ZERO database interaction.
# It only validates and transforms data structures.
# Current DB: PostgreSQL
# Future DB: None
# Whether this code is PostgreSQL compatible: YES (no DB interaction)
# Whether teammate needs to modify anything: NO
# ---------------------------------------------------------------------------
"""

from typing import Any, Dict, List, Optional, Tuple


def validate_prediction_request(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate an incoming prediction API request body.

    Required fields:
        sensor_id (str), ambient_temp (number), humidity (number),
        vibration_rms (number), gauge_width (number)

    Optional fields:
        timestamp (str), track_section_id (int), metadata (dict)

    Args:
        data: Parsed JSON request body.

    Returns:
        (is_valid, error_message) — error_message is None if valid.
    """
    required_fields = {
        "sensor_id": str,
        "ambient_temp": (int, float),
        "humidity": (int, float),
        "vibration_rms": (int, float),
        "gauge_width": (int, float),
    }

    for field_name, expected_type in required_fields.items():
        if field_name not in data:
            return False, f"Missing required field: '{field_name}'"

        value = data[field_name]
        if not isinstance(value, expected_type):
            return False, (
                f"Invalid type for '{field_name}': "
                f"expected {expected_type}, got {type(value).__name__}"
            )

    # Validate optional fields
    if "track_section_id" in data:
        if not isinstance(data["track_section_id"], int):
            return False, "track_section_id must be an integer"

    if "metadata" in data:
        if not isinstance(data["metadata"], dict):
            return False, "metadata must be a dictionary"

    return True, None


def validate_batch_prediction_request(
    data: Dict[str, Any],
) -> Tuple[bool, Optional[str]]:
    """
    Validate a batch prediction request body.

    Expected shape:
        {
            "readings": [
                {"sensor_id": ..., "ambient_temp": ..., ...},
                {"sensor_id": ..., "ambient_temp": ..., ...},
            ],
            "track_section_id": 7  (optional, applied to all)
        }
    """
    if "readings" not in data:
        return False, "Missing required field: 'readings'"

    if not isinstance(data["readings"], list):
        return False, "'readings' must be a list"

    if len(data["readings"]) == 0:
        return False, "'readings' must not be empty"

    if len(data["readings"]) > 1000:
        return False, "'readings' must not exceed 1000 items"

    for i, reading in enumerate(data["readings"]):
        if not isinstance(reading, dict):
            return False, f"readings[{i}] must be a dictionary"

        is_valid, error = validate_prediction_request(reading)
        if not is_valid:
            return False, f"readings[{i}]: {error}"

    return True, None


def format_prediction_response(response) -> Dict[str, Any]:
    """
    Format a PredictionResponse for API output.

    Converts the internal PredictionResponse dataclass into a
    JSON-serializable dict suitable for JsonResponse.
    """
    return {
        "success": True,
        "prediction": response.to_dict(),
    }


def format_batch_prediction_response(
    responses: List,
) -> Dict[str, Any]:
    """Format a list of PredictionResponses for API output."""
    return {
        "success": True,
        "count": len(responses),
        "predictions": [r.to_dict() for r in responses],
    }


def format_error_response(
    error: str,
    status_code: int = 400,
) -> Dict[str, Any]:
    """Format an error response."""
    return {
        "success": False,
        "error": error,
        "status_code": status_code,
    }


def format_health_response(health_data: Dict[str, Any]) -> Dict[str, Any]:
    """Format a health check response."""
    return {
        "success": True,
        "health": health_data,
    }
