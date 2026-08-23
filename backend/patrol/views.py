"""
patrol/views.py
Page views for Worker Patrol (worker) and Patrol Review (admin).
"""
import json
from django.shortcuts import render
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_http_methods
from railway.models import TrackSection
from .models import WorkerPatrolReport, PatrolCategoryRating
from . import services


def _is_patrol_worker(user):
    """Check if user is in the 'patrol_worker' Django Group."""
    return user.is_authenticated and user.groups.filter(name="patrol_worker").exists()


@login_required
def patrol_page(request):
    """GET /patrol/ — Worker patrol inspection page."""
    if not (request.user.is_staff or _is_patrol_worker(request.user)):
        return HttpResponseForbidden("Access restricted to patrol workers and administrators.")

    # Get available track sections for the route selector
    sections = TrackSection.objects.select_related(
        "start_station", "end_station"
    ).filter(status="active").order_by("section_code")

    sections_data = []
    for s in sections:
        sections_data.append({
            "id": s.pk,
            "code": s.section_code,
            "start": s.start_station.station_name if s.start_station else "Unknown",
            "end": s.end_station.station_name if s.end_station else "Unknown",
            "length_km": float(s.length_km) if s.length_km else 0,
            "max_speed": s.max_speed_kmph or 120,
        })

    # Worker's own patrol history (or all for staff preview)
    if request.user.is_staff:
        patrols = WorkerPatrolReport.objects.select_related(
            "worker", "track_section__start_station", "track_section__end_station"
        ).prefetch_related("category_ratings").order_by("-created_at")[:15]
    else:
        patrols = WorkerPatrolReport.objects.filter(
            worker=request.user
        ).select_related(
            "worker", "track_section__start_station", "track_section__end_station"
        ).prefetch_related("category_ratings").order_by("-created_at")[:15]

    my_patrols = [services.get_patrol_payload(p) for p in patrols]

    categories_info = [
        {"value": PatrolCategoryRating.Category.RAIL_CONDITION, "label": "Rail Condition", "desc": "Cracks, fractures, wear, corrosion, head wear"},
        {"value": PatrolCategoryRating.Category.TRACK_GEOMETRY, "label": "Track Geometry", "desc": "Alignment, cross-level, gauge, super-elevation"},
        {"value": PatrolCategoryRating.Category.SLEEPERS_FASTENINGS, "label": "Sleepers & Fastenings", "desc": "Cracked sleepers, loose bolts, missing clips, fishplates"},
        {"value": PatrolCategoryRating.Category.BALLAST_CONDITION, "label": "Ballast Condition", "desc": "Ballast adequacy, fouling, vegetation, shoulder width"},
        {"value": PatrolCategoryRating.Category.DRAINAGE, "label": "Drainage", "desc": "Side drains, catch water drains, waterlogging"},
        {"value": PatrolCategoryRating.Category.POINTS_CROSSINGS, "label": "Points & Crossings", "desc": "Tongue rails, check rails, switch condition"},
        {"value": PatrolCategoryRating.Category.LEVEL_CROSSINGS, "label": "Level Crossings", "desc": "Gate condition, road surface, visibility, signage"},
        {"value": PatrolCategoryRating.Category.FORMATION_EARTHWORK, "label": "Formation & Earthwork", "desc": "Embankment stability, cutting slopes, erosion"},
    ]

    context = {
        "page_title": "Worker Patrol",
        "sections_json": json.dumps(sections_data),
        "my_patrols_json": json.dumps(my_patrols),
        "is_patrol_worker": _is_patrol_worker(request.user),
        "categories": categories_info,
        "categories_json": json.dumps(categories_info),
    }
    return render(request, "patrol.html", context)


@login_required
def patrol_admin_page(request):
    """GET /patrol/admin/ — Admin patrol review dashboard."""
    if not request.user.is_staff:
        return HttpResponseForbidden("Access restricted to controllers.")

    patrols = WorkerPatrolReport.objects.select_related(
        "worker", "track_section__start_station", "track_section__end_station",
    ).prefetch_related("category_ratings").order_by("-created_at")

    patrols_payload = [services.get_patrol_payload(p) for p in patrols]

    context = {
        "page_title": "Patrol Review",
        "patrols_json": json.dumps(patrols_payload),
        "patrols": patrols_payload,
    }
    return render(request, "patrol_admin.html", context)


# === API ENDPOINTS ===

@login_required
@require_POST
def api_start_patrol(request):
    """POST /api/patrol/start/ — Worker starts a new patrol."""
    if not (request.user.is_staff or _is_patrol_worker(request.user)):
        return JsonResponse({"status": "error", "message": "Not authorized"}, status=403)

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"status": "error", "message": "Invalid JSON"}, status=400)

    track_section_id = data.get("track_section_id")
    if not track_section_id:
        return JsonResponse({"status": "error", "message": "track_section_id required"}, status=400)

    try:
        patrol = services.create_patrol_report(request.user, track_section_id)
        payload = services.get_patrol_payload(patrol)
        return JsonResponse({
            "status": "success",
            "patrol_code": patrol.patrol_code,
            "patrol": payload,
            "message": f"Patrol {patrol.patrol_code} started.",
        })
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@login_required
@require_POST
def api_submit_ratings(request, patrol_code):
    """POST /api/patrol/<code>/submit/ — Worker submits 8 category ratings."""
    # Role guard: only patrol workers (or admins reviewing on their behalf)
    if not (request.user.is_staff or _is_patrol_worker(request.user)):
        return JsonResponse({"status": "error", "message": "Not authorized"}, status=403)

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"status": "error", "message": "Invalid JSON"}, status=400)

    ratings = data.get("ratings", [])
    if len(ratings) < 1:
        return JsonResponse({"status": "error", "message": "At least one rating required"}, status=400)

    try:
        # Ownership + state guards before any side effects run.
        patrol = WorkerPatrolReport.objects.get(patrol_code=patrol_code)
    except WorkerPatrolReport.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Patrol not found"}, status=404)

    if not request.user.is_staff and patrol.worker != request.user:
        return JsonResponse({"status": "error", "message": "You can only submit ratings for your own patrols"}, status=403)

    if patrol.status in (
        WorkerPatrolReport.Status.SUBMITTED,
        WorkerPatrolReport.Status.IOT_GENERATED,
        WorkerPatrolReport.Status.DECIDED,
    ):
        return JsonResponse({
            "status": "error",
            "message": f"Patrol {patrol_code} has already been submitted and can no longer be edited",
        }, status=409)

    try:
        # 1. Save worker ratings and calculate worker score
        patrol = services.submit_worker_ratings(patrol_code, ratings)
        # 2. Auto-trigger IoT generation and ML prediction pipeline
        patrol = services.generate_post_inspection_iot(patrol_code)
        payload = services.get_patrol_payload(patrol)
        return JsonResponse({"status": "success", "patrol": payload})
    except WorkerPatrolReport.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Patrol not found"}, status=404)
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@login_required
@require_http_methods(["GET"])
def api_get_patrol_detail(request, patrol_code):
    """GET /api/patrol/<code>/ — Get single patrol detail (separated)."""
    try:
        patrol = WorkerPatrolReport.objects.select_related(
            "worker", "track_section__start_station", "track_section__end_station",
        ).prefetch_related("category_ratings").get(patrol_code=patrol_code)

        # Workers can only view their own patrols unless staff
        if not request.user.is_staff and patrol.worker != request.user:
            return JsonResponse({"status": "error", "message": "Access denied"}, status=403)

        return JsonResponse({"status": "success", "patrol": services.get_patrol_payload(patrol)})
    except WorkerPatrolReport.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Patrol not found"}, status=404)


@login_required
@require_http_methods(["GET"])
def api_list_patrols(request):
    """GET /api/patrol/reports/ — List all patrols (admin) or own patrols (worker)."""
    if request.user.is_staff:
        patrols = WorkerPatrolReport.objects.all()
    else:
        patrols = WorkerPatrolReport.objects.filter(worker=request.user)

    patrols = patrols.select_related(
        "worker", "track_section__start_station", "track_section__end_station",
    ).prefetch_related("category_ratings").order_by("-created_at")

    payload = [services.get_patrol_payload(p) for p in patrols]
    return JsonResponse({"status": "success", "patrols": payload})


@login_required
@require_POST
def api_update_weights(request, patrol_code):
    """POST /api/patrol/<code>/weights/ — Admin adjusts worker/IoT weights."""
    if not request.user.is_staff:
        return JsonResponse({"status": "error", "message": "Admin only"}, status=403)

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"status": "error", "message": "Invalid JSON"}, status=400)

    try:
        worker_weight = float(data.get("worker_weight", 0.60))
        iot_weight = float(data.get("iot_weight", 0.40))
    except (ValueError, TypeError):
        return JsonResponse({"status": "error", "message": "Invalid weight values"}, status=400)

    # Validate weights sum to 1.0 (with tolerance for floating point)
    if abs((worker_weight + iot_weight) - 1.0) > 0.02:
        return JsonResponse({"status": "error", "message": "Weights must sum to 1.0 (100%)"}, status=400)

    try:
        patrol = services.update_weights_and_recompute(patrol_code, worker_weight, iot_weight)
        return JsonResponse({"status": "success", "patrol": services.get_patrol_payload(patrol)})
    except WorkerPatrolReport.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Patrol not found"}, status=404)
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@login_required
@require_POST
def api_submit_decision(request, patrol_code):
    """POST /api/patrol/<code>/decide/ — Admin submits Go/No-Go decision."""
    if not request.user.is_staff:
        return JsonResponse({"status": "error", "message": "Admin only"}, status=403)

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"status": "error", "message": "Invalid JSON"}, status=400)

    decision = data.get("decision")
    notes = data.get("notes", "")
    try:
        speed = int(data.get("speed_restriction", 0))
    except (ValueError, TypeError):
        speed = 0

    if decision not in [
        WorkerPatrolReport.AdminDecision.CLEARED,
        WorkerPatrolReport.AdminDecision.RESTRICTED,
        WorkerPatrolReport.AdminDecision.BLOCKED,
    ]:
        return JsonResponse({"status": "error", "message": "Invalid decision"}, status=400)

    try:
        patrol = services.submit_admin_decision(patrol_code, request.user, decision, notes, speed)
        return JsonResponse({
            "status": "success",
            "message": f"Decision '{decision.upper()}' recorded.",
            "patrol": services.get_patrol_payload(patrol),
        })
    except WorkerPatrolReport.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Patrol not found"}, status=404)
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)
