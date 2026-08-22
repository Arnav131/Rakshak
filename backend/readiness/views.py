# backend/readiness/views.py
import json
from decimal import Decimal
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib.auth.decorators import login_required
from railway.models import OperationalReadinessCase
from .services import (
    get_case_payload,
    sign_off_checklist_item,
    submit_controller_decision,
    evaluate_case_telemetry,
)


@login_required
@ensure_csrf_cookie
def readiness_page(request):
    """
    Renders the main Operational Readiness Control Center dashboard.
    """
    cases = OperationalReadinessCase.objects.select_related(
        "track_section__start_station",
        "track_section__end_station",
        "assigned_team",
    ).prefetch_related("checklist_items", "audit_records").all().order_by("-created_at")

    cases_payload = [get_case_payload(c) for c in cases]
    
    # Calculate summary metrics
    total_cases = len(cases_payload)
    ready_count = sum(1 for c in cases_payload if c["readiness_decision"] == "ready")
    caution_count = sum(1 for c in cases_payload if c["readiness_decision"] == "conditionally_ready")
    hold_count = sum(1 for c in cases_payload if c["readiness_decision"] in ["not_ready", "pending"])

    context = {
        "page_title": "Operational Readiness Center",
        "cases_json": json.dumps(cases_payload),
        "cases": cases_payload,
        "summary": {
            "total": total_cases,
            "ready": ready_count,
            "caution": caution_count,
            "hold": hold_count,
        },
    }
    return render(request, "readiness.html", context)


@login_required
@require_http_methods(["GET"])
def api_get_cases(request):
    """
    JSON API: returns list of all readiness cases.
    """
    cases = OperationalReadinessCase.objects.select_related(
        "track_section__start_station",
        "track_section__end_station",
    ).prefetch_related("checklist_items", "audit_records").all().order_by("-created_at")

    payload = [get_case_payload(c) for c in cases]
    return JsonResponse({"status": "success", "cases": payload})


@login_required
@require_http_methods(["GET"])
def api_get_case_detail(request, case_code):
    """
    JSON API: returns full detail and telemetry evaluation for a single case.
    Strictly isolated by case_code.
    """
    try:
        case = OperationalReadinessCase.objects.select_related(
            "track_section__start_station",
            "track_section__end_station",
            "assigned_team",
        ).prefetch_related("checklist_items", "audit_records").get(case_code=case_code)
    except OperationalReadinessCase.DoesNotExist:
        return JsonResponse({"status": "error", "message": f"Case {case_code} not found"}, status=404)

    return JsonResponse({"status": "success", "case": get_case_payload(case)})


@login_required
@require_http_methods(["POST"])
def api_sign_off_item(request, case_code):
    """
    JSON API: Field Safety Guard / Officer signs off an individual checklist item.
    Enforces separation logic: modifies only the item under case_code.
    """
    try:
        data = json.loads(request.body.decode("utf-8")) if request.body else request.POST
    except Exception:
        data = request.POST

    item_id_or_code = data.get("item_id") or data.get("item_code")
    status = data.get("status", "passed")
    notes = data.get("notes", "")
    role_designation = data.get("role_designation", "")

    if not item_id_or_code:
        return JsonResponse({"status": "error", "message": "item_id or item_code is required"}, status=400)

    try:
        item = sign_off_checklist_item(
            case_code=case_code,
            item_id_or_code=item_id_or_code,
            user=request.user,
            role_designation=role_designation,
            notes=notes,
            status=status,
        )
        case = OperationalReadinessCase.objects.get(case_code=case_code)
        return JsonResponse({
            "status": "success",
            "message": f"Checklist item '{item.title}' updated to {status.upper()}.",
            "case": get_case_payload(case),
        })
    except OperationalReadinessCase.DoesNotExist:
        return JsonResponse({"status": "error", "message": f"Case {case_code} not found"}, status=404)
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def api_submit_decision(request, case_code):
    """
    JSON API: Controller authorizes Go (Ready) / Caution / No-Go (Hold).
    Enforces pre-action safety checks before clearance.
    """
    try:
        data = json.loads(request.body.decode("utf-8")) if request.body else request.POST
    except Exception:
        data = request.POST

    decision = data.get("decision")  # 'ready', 'conditionally_ready', 'not_ready'
    try:
        speed_kmph = int(data.get("speed_kmph", 0))
    except (ValueError, TypeError):
        return JsonResponse({"status": "error", "message": "speed_kmph must be an integer"}, status=400)
    notes = data.get("notes", "")
    conditions = data.get("conditions", "")
    is_override = bool(data.get("is_override", False))
    override_reason = data.get("override_reason", "")

    if not decision:
        return JsonResponse({"status": "error", "message": "Decision value is required"}, status=400)

    try:
        case = submit_controller_decision(
            case_code=case_code,
            user=request.user,
            decision=decision,
            speed_kmph=speed_kmph,
            notes=notes,
            conditions=conditions,
            is_override=is_override,
            override_reason=override_reason,
        )
        return JsonResponse({
            "status": "success",
            "message": f"Operational decision '{decision.upper()}' authorized successfully.",
            "case": get_case_payload(case),
        })
    except OperationalReadinessCase.DoesNotExist:
        return JsonResponse({"status": "error", "message": f"Case {case_code} not found"}, status=404)
    except ValueError as ve:
        return JsonResponse({"status": "error", "message": str(ve), "requires_override": True}, status=422)
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)
