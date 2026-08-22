"""
patrol/services.py
Business logic for Worker Patrol System.
Every function is scoped to a single patrol_code — enforcing Separation Logic.
"""
import uuid
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from .models import WorkerPatrolReport, PatrolCategoryRating
from railway.models import TrackSection
from simulation import generator as sim_generator
from ai_integration.prediction_service import PredictionService


def generate_patrol_code():
    """Generate unique patrol code: PTR-2026-XXXX.
    Uses count + random suffix to mitigate race-condition duplicates.
    """
    year = timezone.now().year
    count = WorkerPatrolReport.objects.filter(
        patrol_code__startswith=f"PTR-{year}"
    ).count() + 1
    # Add random suffix to mitigate race-condition collisions
    import random
    suffix = random.randint(0, 99)
    return f"PTR-{year}-{count:04d}{suffix:02d}"[:30]


@transaction.atomic
def create_patrol_report(worker, track_section_id):
    """Create a new isolated patrol case. Returns the patrol object."""
    track_section = TrackSection.objects.get(pk=track_section_id)
    patrol = WorkerPatrolReport.objects.create(
        patrol_code=generate_patrol_code(),
        worker=worker,
        track_section=track_section,
        status=WorkerPatrolReport.Status.IN_PROGRESS,
    )
    return patrol


@transaction.atomic
def submit_worker_ratings(patrol_code, ratings_data):
    """
    Save 8 category ratings and compute worker_overall_score.
    ratings_data = [{"category": "rail_condition", "rating": 4, "notes": "..."}, ...]
    Scoped strictly to patrol_code.
    """
    patrol = WorkerPatrolReport.objects.select_for_update().get(patrol_code=patrol_code)
    # Clear existing ratings for this patrol (idempotent re-submission)
    patrol.category_ratings.all().delete()
    total = Decimal("0")
    count = 0
    for item in ratings_data:
        PatrolCategoryRating.objects.create(
            patrol=patrol,
            category=item["category"],
            rating=int(item["rating"]),
            notes=item.get("notes", ""),
            gps_latitude=item.get("gps_latitude"),
            gps_longitude=item.get("gps_longitude"),
        )
        total += Decimal(str(item["rating"]))
        count += 1

    # Normalize: avg of ratings (1-5) scaled to 0-100
    if count > 0:
        avg_rating = total / Decimal(str(count))
        patrol.worker_overall_score = (avg_rating / Decimal("5")) * Decimal("100")
    else:
        patrol.worker_overall_score = Decimal("0")

    patrol.patrol_completed_at = timezone.now()
    patrol.status = WorkerPatrolReport.Status.SUBMITTED
    patrol.save()
    return patrol


def generate_post_inspection_iot(patrol_code):
    """
    Generate 16 IoT sensor readings for the patrol's route using
    the simulation generator (30% chance of anomalous readings).
    Then feed through PredictionService. Scoped to patrol_code.
    """
    patrol = WorkerPatrolReport.objects.select_related(
        "track_section__start_station",
        "track_section__end_station",
    ).get(patrol_code=patrol_code)

    source = patrol.track_section.start_station.station_name if patrol.track_section and patrol.track_section.start_station else "Station A"
    destination = patrol.track_section.end_station.station_name if patrol.track_section and patrol.track_section.end_station else "Station B"

    # Use generator infrastructure in patrol mode
    readings, flavour_name, flavour_desc, backend_used = sim_generator.generate_journey(
        source, destination, patrol_mode=True
    )

    # Feed through the REAL PredictionService (same as simulation)
    sensor_id = f"PATROL-{uuid.uuid4().hex[:8]}"
    prediction_service = PredictionService()
    last_response = None
    for reading in readings:
        last_response = prediction_service.predict_for_sensor(
            sensor_id=sensor_id,
            ambient_temp=reading["ambient_temp"],
            humidity=reading["humidity"],
            vibration_rms=reading["vibration_rms"],
            gauge_width=reading["gauge_width"],
        )

    prediction = last_response.to_dict() if last_response else {}

    # Compute IoT health score (inverse of anomaly_score)
    anomaly_score = float(prediction.get("anomaly_score", 0.0) or 0.0)
    iot_score = Decimal(str(round((1.0 - anomaly_score) * 100, 2)))

    # Save to patrol (scoped — only touches this patrol)
    patrol.iot_readings = readings
    patrol.iot_generator_backend = backend_used
    patrol.iot_prediction = prediction
    patrol.iot_scenario_flavour = flavour_name
    patrol.iot_overall_score = iot_score
    patrol.status = WorkerPatrolReport.Status.IOT_GENERATED

    # Compute composite and detect conflicts
    _recompute_composite(patrol)
    patrol.save()
    return patrol


def _recompute_composite(patrol):
    """Compute weighted composite score and detect worker/IoT conflicts."""
    if patrol.worker_overall_score is not None and patrol.iot_overall_score is not None:
        w_score = patrol.worker_overall_score
        i_score = patrol.iot_overall_score
        patrol.composite_score = (
            patrol.worker_weight * w_score + patrol.iot_weight * i_score
        )
        # Conflict: worker and IoT disagree by more than 30 points
        patrol.conflict_detected = abs(w_score - i_score) > Decimal("30")


@transaction.atomic
def update_weights_and_recompute(patrol_code, worker_weight, iot_weight):
    """Admin adjusts weights and recomputes composite. Scoped to patrol_code."""
    patrol = WorkerPatrolReport.objects.select_for_update().get(patrol_code=patrol_code)
    patrol.worker_weight = Decimal(str(worker_weight))
    patrol.iot_weight = Decimal(str(iot_weight))
    _recompute_composite(patrol)
    patrol.save()
    return patrol


@transaction.atomic
def submit_admin_decision(patrol_code, user, decision, notes="", speed_restriction=0):
    """Admin Go/No-Go decision. Scoped strictly to patrol_code."""
    patrol = WorkerPatrolReport.objects.select_for_update().get(patrol_code=patrol_code)
    patrol.admin_decision = decision
    patrol.admin_decision_by = user.username
    patrol.admin_decision_at = timezone.now()
    patrol.admin_notes = notes
    patrol.admin_speed_restriction = speed_restriction
    patrol.status = WorkerPatrolReport.Status.DECIDED

    # Sync with TrackSection
    if patrol.track_section:
        ts = patrol.track_section
        if decision == WorkerPatrolReport.AdminDecision.CLEARED:
            ts.status = TrackSection.Status.ACTIVE
        elif decision == WorkerPatrolReport.AdminDecision.RESTRICTED:
            ts.status = TrackSection.Status.ACTIVE
            if speed_restriction > 0:
                ts.max_speed_kmph = speed_restriction
        elif decision == WorkerPatrolReport.AdminDecision.BLOCKED:
            ts.status = TrackSection.Status.UNDER_MAINTENANCE
        ts.save()

    patrol.save()
    return patrol


def get_patrol_payload(patrol):
    """Serialize a single patrol report for API/template consumption."""
    ratings = []
    for r in patrol.category_ratings.all().order_by("category"):
        ratings.append({
            "category": r.category,
            "category_display": r.get_category_display(),
            "rating": r.rating,
            "rating_label": {1: "Critical", 2: "Poor", 3: "Fair", 4: "Good", 5: "Excellent"}.get(r.rating, "?"),
            "notes": r.notes,
        })

    section_name = "N/A"
    start_station_name = "N/A"
    end_station_name = "N/A"
    if patrol.track_section:
        s = patrol.track_section.start_station.station_name if patrol.track_section.start_station else "?"
        e = patrol.track_section.end_station.station_name if patrol.track_section.end_station else "?"
        start_station_name = s
        end_station_name = e
        section_name = f"{s} → {e}"

    return {
        "patrol_code": patrol.patrol_code,
        "worker": patrol.worker.username if patrol.worker else "Unknown",
        "worker_name": f"{patrol.worker.first_name} {patrol.worker.last_name}".strip() if patrol.worker and (patrol.worker.first_name or patrol.worker.last_name) else (patrol.worker.username if patrol.worker else "Unknown"),
        "track_section_id": patrol.track_section.pk if patrol.track_section else None,
        "track_section_code": patrol.track_section.section_code if patrol.track_section else "N/A",
        "section_name": section_name,
        "start_station": start_station_name,
        "end_station": end_station_name,
        "status": patrol.status,
        "status_display": patrol.get_status_display(),
        "patrol_started_at": patrol.patrol_started_at.strftime("%Y-%m-%d %H:%M") if patrol.patrol_started_at else None,
        "patrol_completed_at": patrol.patrol_completed_at.strftime("%Y-%m-%d %H:%M") if patrol.patrol_completed_at else None,
        "worker_overall_score": float(patrol.worker_overall_score) if patrol.worker_overall_score is not None else None,
        "iot_overall_score": float(patrol.iot_overall_score) if patrol.iot_overall_score is not None else None,
        "composite_score": float(patrol.composite_score) if patrol.composite_score is not None else None,
        "worker_weight": float(patrol.worker_weight),
        "iot_weight": float(patrol.iot_weight),
        "conflict_detected": patrol.conflict_detected,
        "iot_readings": patrol.iot_readings or [],
        "iot_generator_backend": patrol.iot_generator_backend,
        "iot_prediction": patrol.iot_prediction or {},
        "iot_scenario_flavour": patrol.iot_scenario_flavour,
        "admin_decision": patrol.admin_decision,
        "admin_decision_display": patrol.get_admin_decision_display(),
        "admin_decision_by": patrol.admin_decision_by,
        "admin_decision_at": patrol.admin_decision_at.strftime("%Y-%m-%d %H:%M") if patrol.admin_decision_at else None,
        "admin_notes": patrol.admin_notes,
        "admin_speed_restriction": patrol.admin_speed_restriction,
        "category_ratings": ratings,
        "created_at": patrol.created_at.strftime("%Y-%m-%d %H:%M") if patrol.created_at else None,
    }
