# backend/readiness/services.py
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model
from railway.models import (
    OperationalReadinessCase,
    ReadinessChecklistItem,
    ReadinessAuditRecord,
    TrackSection,
    Alert,
)

User = get_user_model()

# Safety Threshold Standards (Indian Railways RDSO Specs)
MAX_SAFE_VIBRATION_RMS = Decimal("2.50")  # mm/s
MIN_SAFE_TEMPERATURE = Decimal("15.00")   # deg C
MAX_SAFE_TEMPERATURE = Decimal("45.00")   # deg C
MAX_SAFE_AI_RISK_SCORE = 0.25             # 25% anomaly probability


def evaluate_case_telemetry(case: OperationalReadinessCase) -> dict:
    """
    Evaluates sensor telemetry thresholds and active alerts for an operational case.
    Enforces separation logic: runs strictly against the passed case entity.
    """
    metrics = case.sensor_metrics or {}
    
    # Extract vibration, temperature, AI score
    vib = Decimal(str(metrics.get("vibration_rms", metrics.get("vibration_rms_avg", "1.20"))))
    temp = Decimal(str(metrics.get("temperature_celsius", metrics.get("temperature_max", "32.00"))))
    ai_risk = float(metrics.get("ai_risk_score", metrics.get("anomaly_probability", 0.05)))
    
    # Check threshold passes
    vib_passed = vib <= MAX_SAFE_VIBRATION_RMS
    temp_passed = MIN_SAFE_TEMPERATURE <= temp <= MAX_SAFE_TEMPERATURE
    ai_passed = ai_risk <= MAX_SAFE_AI_RISK_SCORE
    
    # Check section active critical alerts
    active_alerts_count = 0
    if case.track_section:
        active_alerts_count = Alert.objects.filter(
            track_section=case.track_section,
            status="active",
            severity__in=["critical", "warning"]
        ).count()
        
    alerts_passed = active_alerts_count == 0
    all_telemetry_passed = vib_passed and temp_passed and ai_passed and alerts_passed
    
    # Calculate checklist progress
    checklist_items = case.checklist_items.all()
    total_items = checklist_items.count()
    passed_items = checklist_items.filter(status="passed").count()
    failed_items = checklist_items.filter(status="failed").count()
    pending_items = checklist_items.filter(status="pending").count()
    
    checklist_score = (passed_items / total_items * 60.0) if total_items > 0 else 0.0
    telemetry_score = 40.0 if all_telemetry_passed else (20.0 if (vib_passed and temp_passed) else 0.0)
    composite_score = Decimal(str(round(checklist_score + telemetry_score, 2)))
    
    # Update case readiness score if changed
    if case.readiness_score != composite_score:
        case.readiness_score = composite_score
        case.save(update_fields=["readiness_score", "updated_at"])
        
    return {
        "vibration_rms": float(vib),
        "vibration_passed": vib_passed,
        "vibration_threshold": float(MAX_SAFE_VIBRATION_RMS),
        "temperature_celsius": float(temp),
        "temperature_passed": temp_passed,
        "temperature_min": float(MIN_SAFE_TEMPERATURE),
        "temperature_max": float(MAX_SAFE_TEMPERATURE),
        "ai_risk_score": round(ai_risk * 100, 1),
        "ai_risk_passed": ai_passed,
        "active_critical_alerts": active_alerts_count,
        "alerts_passed": alerts_passed,
        "all_telemetry_passed": all_telemetry_passed,
        "total_checklist_items": total_items,
        "passed_checklist_items": passed_items,
        "failed_checklist_items": failed_items,
        "pending_checklist_items": pending_items,
        "checklist_percentage": round((passed_items / total_items * 100) if total_items > 0 else 0),
        "composite_score": float(composite_score),
    }


@transaction.atomic
def sign_off_checklist_item(
    case_code: str,
    item_id_or_code: str,
    user=None,
    role_designation: str = "",
    notes: str = "",
    status: str = "passed",
    lat: Decimal = None,
    lon: Decimal = None,
) -> ReadinessChecklistItem:
    """
    Field sign-off logic.
    A field officer (Safety Guard, Traction Controller, Signal Inspector, Section Engineer)
    signs off an individual checklist item.
    Enforces Separation Logic: modifies strictly the checklist item belonging to case_code.
    """
    case = OperationalReadinessCase.objects.select_for_update().get(case_code=case_code)
    
    # Find item by pk or item_code
    if str(item_id_or_code).isdigit():
        item = case.checklist_items.get(pk=int(item_id_or_code))
    else:
        item = case.checklist_items.get(item_code=item_id_or_code)
        
    prev_status = item.status
    item.status = status
    item.signed_off_by = user.username if user and getattr(user, "username", None) else (role_designation or "Field Officer")
    item.signed_off_at = timezone.now()
    item.sign_off_designation = role_designation or (getattr(user, "role", "Field Officer") if user else "Field Officer")
    item.sign_off_comments = notes
    if lat is not None:
        item.signed_off_latitude = lat
    if lon is not None:
        item.signed_off_longitude = lon
    item.save()
    
    # Log immutable audit record
    ReadinessAuditRecord.objects.create(
        case=case,
        checklist_item=item,
        record_type=ReadinessAuditRecord.RecordType.CHECKLIST_SIGNOFF,
        actor_type=ReadinessAuditRecord.ActorType.FIELD_TEAM if not user else ReadinessAuditRecord.ActorType.USER,
        actor_identifier=item.signed_off_by,
        occurred_at=timezone.now(),
        previous_state={"status": prev_status, "item_code": item.item_code},
        new_state={"status": status, "item_code": item.item_code, "notes": notes},
        notes=f"Field sign-off '{item.title}' marked as {status.upper()} by {item.signed_off_by}.",
    )
    
    # Advance workflow status if in draft
    if case.workflow_status in [OperationalReadinessCase.WorkflowStatus.DRAFT, OperationalReadinessCase.WorkflowStatus.FIELD_VERIFICATION]:
        total_req = case.checklist_items.filter(is_required=True).count()
        passed_req = case.checklist_items.filter(is_required=True, status="passed").count()
        if passed_req == total_req and total_req > 0:
            case.workflow_status = OperationalReadinessCase.WorkflowStatus.AWAITING_DECISION
        else:
            case.workflow_status = OperationalReadinessCase.WorkflowStatus.FIELD_VERIFICATION
        case.save(update_fields=["workflow_status", "updated_at"])
        
    return item


@transaction.atomic
def submit_controller_decision(
    case_code: str,
    user,
    decision: str,  # 'ready', 'conditionally_ready', 'not_ready'
    speed_kmph: int = 0,
    notes: str = "",
    conditions: str = "",
    is_override: bool = False,
    override_reason: str = "",
) -> OperationalReadinessCase:
    """
    Controller Go/No-Go Decision Gate.
    Enforces pre-action safety check before granting track reopening or departure clearance.
    """
    case = OperationalReadinessCase.objects.select_for_update().get(case_code=case_code)
    eval_result = evaluate_case_telemetry(case)
    
    # Validate preconditions if ready without override
    if decision == OperationalReadinessCase.ReadinessDecision.READY and not is_override:
        if not eval_result["all_telemetry_passed"]:
            raise ValueError("Cannot authorize FULL GO: IoT sensor telemetry threshold checks failed.")
        if eval_result["pending_checklist_items"] > 0 or eval_result["failed_checklist_items"] > 0:
            raise ValueError("Cannot authorize FULL GO: Mandatory safety checklist items are incomplete or failed.")

    prev_decision = case.readiness_decision
    prev_speed = case.cleared_speed_kmph
    
    case.readiness_decision = decision
    case.workflow_status = OperationalReadinessCase.WorkflowStatus.COMPLETED
    case.decision_taken_by = user.username if user and getattr(user, "username", None) else "Operations Controller"
    case.decision_taken_at = timezone.now()
    case.decision_notes = notes or override_reason
    case.decision_conditions = conditions
    case.cleared_speed_kmph = speed_kmph
    case.is_overridden = is_override
    case.isolation_state = (
        OperationalReadinessCase.IsolationState.RESTORED
        if decision in [OperationalReadinessCase.ReadinessDecision.READY, OperationalReadinessCase.ReadinessDecision.CONDITIONALLY_READY]
        else OperationalReadinessCase.IsolationState.ISOLATED
    )
    case.save()
    
    # Sync with TrackSection if applicable
    if case.track_section:
        sec = case.track_section
        if decision == OperationalReadinessCase.ReadinessDecision.READY:
            sec.status = TrackSection.Status.ACTIVE
            if speed_kmph > 0:
                sec.max_speed_kmph = speed_kmph
            sec.save()
        elif decision == OperationalReadinessCase.ReadinessDecision.CONDITIONALLY_READY:
            sec.status = TrackSection.Status.ACTIVE
            if speed_kmph > 0:
                sec.max_speed_kmph = speed_kmph
            sec.save()
        elif decision == OperationalReadinessCase.ReadinessDecision.NOT_READY:
            sec.status = TrackSection.Status.UNDER_MAINTENANCE
            sec.save()

    # Log immutable audit record
    ReadinessAuditRecord.objects.create(
        case=case,
        record_type=ReadinessAuditRecord.RecordType.DECISION,
        actor_type=ReadinessAuditRecord.ActorType.USER,
        actor_identifier=case.decision_taken_by,
        occurred_at=timezone.now(),
        previous_state={"decision": prev_decision, "speed_kmph": prev_speed},
        new_state={"decision": decision, "speed_kmph": speed_kmph, "is_overridden": is_override},
        decision=decision,
        decision_reference=case.case_code,
        decision_summary=f"Readiness decision '{decision.upper()}' recorded with speed limit {speed_kmph} km/h.",
        notes=notes or override_reason,
    )
    
    return case


def get_case_payload(case: OperationalReadinessCase) -> dict:
    """Serializes complete case information for API and template consumption."""
    eval_result = evaluate_case_telemetry(case)
    
    checklist_data = []
    for item in case.checklist_items.all().order_by("sequence"):
        checklist_data.append({
            "id": item.pk,
            "sequence": item.sequence,
            "item_code": item.item_code,
            "title": item.title,
            "description": item.description,
            "category": item.category,
            "category_display": item.get_category_display(),
            "is_required": item.is_required,
            "status": item.status,
            "status_display": item.get_status_display(),
            "signed_off_by": item.signed_off_by,
            "signed_off_at": item.signed_off_at.strftime("%H:%M:%S (%d %b)") if item.signed_off_at else None,
            "sign_off_designation": item.sign_off_designation,
            "sign_off_comments": item.sign_off_comments,
        })
        
    audit_data = []
    for aud in case.audit_records.all().order_by("-occurred_at")[:8]:
        audit_data.append({
            "id": aud.pk,
            "record_type": aud.record_type,
            "actor_identifier": aud.actor_identifier,
            "time_str": aud.occurred_at.strftime("%H:%M:%S"),
            "decision": aud.decision or "—",
            "notes": aud.notes or aud.decision_summary or f"Record {aud.record_type}",
        })

    section_name = "N/A"
    track_code = "N/A"
    latest_patrol = None
    if case.track_section:
        track_code = case.track_section.section_code
        start = case.track_section.start_station.station_name if case.track_section.start_station else "?"
        end = case.track_section.end_station.station_name if case.track_section.end_station else "?"
        section_name = f"{start} — {end}"
        try:
            from patrol.models import WorkerPatrolReport
            from patrol.services import get_patrol_payload
            patrol_obj = WorkerPatrolReport.objects.filter(
                track_section=case.track_section
            ).select_related(
                "worker", "track_section__start_station", "track_section__end_station"
            ).prefetch_related("category_ratings").order_by("-created_at").first()
            if patrol_obj:
                latest_patrol = get_patrol_payload(patrol_obj)
        except Exception:
            latest_patrol = None

    return {
        "id": case.pk,
        "case_code": case.case_code,
        "case_type": case.case_type,
        "case_type_display": case.get_case_type_display() if hasattr(case, "get_case_type_display") else case.case_type,
        "title": case.title,
        "description": case.description,
        "track_id": track_code,
        "section_name": section_name,
        "train_number": case.train_number,
        "workflow_status": case.workflow_status,
        "workflow_status_display": case.get_workflow_status_display(),
        "readiness_decision": case.readiness_decision,
        "readiness_decision_display": case.get_readiness_decision_display(),
        "isolation_state": case.isolation_state,
        "cleared_speed_kmph": case.cleared_speed_kmph,
        "decision_taken_by": case.decision_taken_by,
        "decision_taken_at": case.decision_taken_at.strftime("%Y-%m-%d %H:%M:%S") if case.decision_taken_at else None,
        "decision_notes": case.decision_notes,
        "is_overridden": case.is_overridden,
        "telemetry": eval_result,
        "checklist": checklist_data,
        "audit_trail": audit_data,
        "latest_patrol": latest_patrol,
    }
