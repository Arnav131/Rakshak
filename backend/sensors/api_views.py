"""
Prediction API — JSON endpoints for the AI inference pipeline.

Endpoints:
    POST /api/predict/         → Run inference on sensor readings
    GET  /api/predict/health/  → Pipeline health check
    POST /api/predict/batch/   → Batch inference on multiple readings

All endpoints return JSON. No template rendering.
The frontend (or any HTTP client) calls these to get AI predictions.
"""
import json
import logging
from decimal import Decimal

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache

from ai_integration.prediction_service import PredictionService
logger = logging.getLogger("rakshak.api.predict")

# Counter for generating unique alert codes within this process
_alert_counter = 0
_alert_counter_lock = __import__('threading').Lock()


def _generate_alert_code():
    """Generate a unique, collision-resistant alert code."""
    global _alert_counter
    with _alert_counter_lock:
        _alert_counter += 1
        counter_val = _alert_counter
    now = timezone.now()
    # Add process ID for multi-worker safety
    import os
    pid = os.getpid() % 10000
    return f"ALT-{now.strftime('%Y%m%d%H%M%S')}-{pid:04d}-{counter_val:04d}"


def _validate_sensor_input(data):
    """
    Validate sensor reading input.

    Returns (values_dict, error_string).
    On success error_string is None.
    """
    required = ["ambient_temp", "humidity", "vibration_rms", "gauge_width"]
    missing = [f for f in required if f not in data]
    if missing:
        return None, f"Missing required fields: {', '.join(missing)}"

    try:
        values = {
            "ambient_temp": float(data["ambient_temp"]),
            "humidity": float(data["humidity"]),
            "vibration_rms": float(data["vibration_rms"]),
            "gauge_width": float(data["gauge_width"]),
        }
    except (TypeError, ValueError) as e:
        return None, f"Invalid numeric value: {e}"

    # Basic range checks
    if not (-50 <= values["ambient_temp"] <= 80):
        return None, f"ambient_temp {values['ambient_temp']} out of range [-50, 80]"
    if not (0 <= values["humidity"] <= 100):
        return None, f"humidity {values['humidity']} out of range [0, 100]"
    if not (0 <= values["vibration_rms"] <= 50):
        return None, f"vibration_rms {values['vibration_rms']} out of range [0, 50]"
    if not (1500 <= values["gauge_width"] <= 1800):
        return None, f"gauge_width {values['gauge_width']} out of range [1500, 1800]"

    return values, None


def _maybe_create_alert(prediction, track_section_id=None, sensor_id=None):
    """
    Create an Alert record in the DB if the prediction is warning or critical.

    Returns the alert_code string if created, None otherwise.
    """
    alert_level = prediction.get("alert_level", "none")
    if alert_level == "none":
        return None

    if not track_section_id:
        return None

    try:
        from railway.models import Alert

        # Map pipeline alert levels to Alert severity
        severity_map = {
            "critical": "critical",
            "warning": "warning",
        }
        severity = severity_map.get(alert_level, "info")

        alert_code = _generate_alert_code()
        anomaly_score = prediction.get("anomaly_score", 0.0)
        fault_type = prediction.get("fault_type", "unknown")
        fault_confidence = prediction.get("fault_confidence", 0.0)
        explanation = prediction.get("metadata", {}).get("explanation", prediction.get("explanation", ""))

        alert = Alert.objects.create(
            alert_code=alert_code,
            track_section_id=track_section_id,
            sensor_id=sensor_id,
            alert_type="anomaly",
            severity=severity,
            title=f"AI Detection: {fault_type} (score: {anomaly_score:.2f})",
            description=(
                f"Pipeline prediction:\n"
                f"  Alert level: {alert_level}\n"
                f"  Anomaly score: {anomaly_score:.4f}\n"
                f"  Fault type: {fault_type} ({fault_confidence:.1%})\n"
                f"  Explanation: {explanation}\n"
                f"  Model: {prediction.get('provider_name', prediction.get('model_used', 'unknown'))}"
            ),
            confidence_score=Decimal(str(round(anomaly_score, 4))),
            generated_at=timezone.now(),
            generated_by="ml_model",
        )
        logger.info(f"Created alert {alert_code} (severity={severity})")
        return alert_code

    except Exception as e:
        logger.error(f"Failed to create alert: {e}", exc_info=True)
        return None


@login_required
@require_POST
@never_cache  # ← Don't cache predictions
def api_predict(request):
    """
    POST /api/predict/

    Accept sensor readings, run inference, return prediction.

    Request body (JSON):
        {
            "ambient_temp": 42.0,
            "humidity": 40.0,
            "vibration_rms": 4.8,
            "gauge_width": 1689.0,
            "track_section_id": 1,   (optional — if provided, auto-creates alerts)
            "sensor_id": 5           (optional)
        }

    Response:
        {
            "success": true,
            "prediction": { ... pipeline output ... },
            "alert_created": false,
            "alert_id": null,
            "timestamp": "2024-01-01T00:00:00Z"
        }
    """
    if not request.user.is_staff:
        return JsonResponse(
            {"success": False, "error": "Prediction API is restricted to administrators."},
            status=403,
        )

    # Parse JSON body
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError) as e:
        return JsonResponse(
            {"success": False, "error": f"Invalid JSON: {e}"},
            status=400,
        )

    # Validate input
    values, error = _validate_sensor_input(data)
    if error:
        return JsonResponse(
            {"success": False, "error": error},
            status=400,
        )

    # AI TEAM NOTE: Predictions are now routed through the PredictionService
    # to support the new provider-agnostic architecture.
    prediction_service = PredictionService()

    # Optionally create alert
    track_section_id = data.get("track_section_id")
    sensor_id = data.get("sensor_id")

    # Run inference
    prediction_response = prediction_service.predict_for_sensor(
        sensor_id=str(sensor_id or "unknown"),
        track_section_id=track_section_id,
        **values
    )
    prediction = prediction_response.to_dict()
    alert_code = None

    create_alert = data.get("create_alert", True)
    if create_alert and track_section_id:
        alert_code = _maybe_create_alert(prediction, track_section_id, sensor_id)

    return JsonResponse({
        "success": True,
        "prediction": prediction,
        "alert_created": alert_code is not None,
        "alert_id": alert_code,
        "timestamp": timezone.now().isoformat(),  # ← Add timestamp
    })


@require_GET
@never_cache  # ← Don't cache health checks
def api_predict_health(request):
    """
    GET /api/predict/health/

    Return pipeline health status.

    Response:
        {
            "status": "ok",
            "risk_model_loaded": true,
            "fault_model_loaded": true,
            "config_loaded": true,
            "model_version": "1.0.0",
            "mode": "pytorch_mlp",
            "timestamp": "2024-01-01T00:00:00Z"
        }
    """
    # AI TEAM NOTE: Health check now polls the provider registry
    health_data = PredictionService.get_health()
    health_data["timestamp"] = timezone.now().isoformat()  # ← Add timestamp
    return JsonResponse(health_data)


@login_required
@require_POST
@never_cache  # ← Don't cache batch predictions
def api_predict_batch(request):
    """
    POST /api/predict/batch/

    Accept an array of sensor readings, return an array of predictions.

    Request body (JSON):
        {
            "readings": [
                {"ambient_temp": 34, "humidity": 55, "vibration_rms": 1.2, "gauge_width": 1676},
                {"ambient_temp": 42, "humidity": 40, "vibration_rms": 4.8, "gauge_width": 1689}
            ],
            "create_alerts": false
        }

    Response:
        {
            "success": true,
            "count": 2,
            "predictions": [ ... ],
            "timestamp": "2024-01-01T00:00:00Z"
        }
    """
    if not request.user.is_staff:
        return JsonResponse(
            {"success": False, "error": "Prediction API is restricted to administrators."},
            status=403,
        )

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError) as e:
        return JsonResponse(
            {"success": False, "error": f"Invalid JSON: {e}"},
            status=400,
        )

    readings = data.get("readings", [])
    if not isinstance(readings, list) or len(readings) == 0:
        return JsonResponse(
            {"success": False, "error": "Request must contain a non-empty 'readings' array"},
            status=400,
        )

    if len(readings) > 100:
        return JsonResponse(
            {"success": False, "error": "Maximum 100 readings per batch"},
            status=400,
        )

    # AI TEAM NOTE: Batch predictions are now routed through PredictionService
    prediction_service = PredictionService()
    create_alerts = data.get("create_alerts", False)
    results = []

    for i, reading in enumerate(readings):
        values, error = _validate_sensor_input(reading)
        if error:
            results.append({
                "index": i,
                "success": False,
                "error": error,
            })
            continue

        track_section_id = reading.get("track_section_id")
        sensor_id = reading.get("sensor_id")

        prediction_response = prediction_service.predict_for_sensor(
            sensor_id=str(sensor_id or "unknown"),
            track_section_id=track_section_id,
            **values
        )
        prediction = prediction_response.to_dict()

        entry = {
            "index": i,
            "success": True,
            "prediction": prediction,
        }

        if create_alerts:
            alert_code = _maybe_create_alert(prediction, track_section_id, sensor_id)
            entry["alert_created"] = alert_code is not None
            entry["alert_id"] = alert_code

        results.append(entry)

    return JsonResponse({
        "success": True,
        "count": len(results),
        "predictions": results,
        "timestamp": timezone.now().isoformat(),  # ← Add timestamp
    })