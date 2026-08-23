# backend/railway/management/commands/seed_readiness_data.py
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from railway.models import (
    Station, TrackSection, MaintenanceTeam,
    OperationalReadinessCase, ReadinessChecklistItem, ReadinessAuditRecord
)

User = get_user_model()


class Command(BaseCommand):
    help = "Seed Flight-Deck Train Route Departure Clearance demonstration cases (Plan 4)."

    def handle(self, *args, **options):
        self.stdout.write("Seeding Flight-Deck Train Route Departure Clearance data...")

        # -------------------------------------------------------------
        # Ensure Users Exist (Controller & Field Worker)
        # -------------------------------------------------------------
        controller_user, created_c = User.objects.get_or_create(
            username="controller",
            defaults={"is_staff": True, "is_superuser": True, "first_name": "Chief", "last_name": "Dispatcher"}
        )
        if created_c or not controller_user.has_usable_password():
            controller_user.set_password("controller123")
            controller_user.is_staff = True
            controller_user.is_superuser = True
            controller_user.save()

        worker_user, created_w = User.objects.get_or_create(
            username="worker",
            defaults={"is_staff": False, "is_superuser": False, "first_name": "Field", "last_name": "Officer"}
        )
        if created_w or not worker_user.has_usable_password():
            worker_user.set_password("worker123")
            worker_user.save()

        # Find or create track sections
        trk_1 = TrackSection.objects.filter(section_code__icontains="NDL").first() or TrackSection.objects.first()
        trk_2 = TrackSection.objects.exclude(pk=getattr(trk_1, "pk", 0)).first() or trk_1

        team = MaintenanceTeam.objects.first()
        if not team:
            team = MaintenanceTeam.objects.create(
                team_name="Northern Quick Response Gang #4",
                specialization="track",
                contact_phone="+91-9876543210"
            )

        # -------------------------------------------------------------
        # CASE 1: Train #12951 (Rajdhani Express) -> CLEARED FOR DEPARTURE (GO)
        # -------------------------------------------------------------
        case1, _ = OperationalReadinessCase.objects.update_or_create(
            case_code="OPR-DEP-12951",
            defaults={
                "title": "Train #12951 (Rajdhani Express) Departure Clearance",
                "case_type": OperationalReadinessCase.CaseType.ROUTE_DEPARTURE,
                "train_number": "12951 New Delhi – Mumbai Central Rajdhani Express",
                "track_section": trk_1,
                "assigned_team": team,
                "description": "Pre-departure flight-deck route clearance and electronic interlocking check before green departure signal from Platform 1 (NDLS).",
                "workflow_status": OperationalReadinessCase.WorkflowStatus.COMPLETED,
                "readiness_decision": OperationalReadinessCase.ReadinessDecision.READY,
                "isolation_state": OperationalReadinessCase.IsolationState.RESTORED,
                "sensor_metrics": {
                    "vibration_rms": 1.12,
                    "temperature_celsius": 28.4,
                    "ai_risk_score": 0.04,
                    "route_health_alerts": 0,
                },
                "readiness_score": Decimal("98.50"),
                "cleared_speed_kmph": 130,
                "decision_taken_by": "Chief Train Dispatcher (NDLS Control)",
                "decision_taken_at": timezone.now(),
                "decision_reference": "DEP-AUTH-12951-GO",
                "decision_notes": "All 3 pre-flight pillars verified nominal: Route Health verified, Interlocking synced, Schedule Window clear. CLEARED FOR DEPARTURE (GO).",
                "is_overridden": False,
            }
        )

        c1_items = [
            (
                1,
                "ROUTE_HEALTH",
                "Route Health: All track sections along route have 0 critical unresolved alerts",
                ReadinessChecklistItem.Category.SAFETY,
                ReadinessChecklistItem.Status.PASSED,
                "R. K. Sharma (Field Track Inspector)",
                "Onboard IoT telemetry verified nominal (Vib 1.12 mm/s, Temp 28.4°C). Zero unresolved track alerts on NDLS-MMCT corridor."
            ),
            (
                2,
                "SIGNAL_INTERLOCKING",
                "Signal Interlocking: Section interlocking synced",
                ReadinessChecklistItem.Category.SIGNAL,
                ReadinessChecklistItem.Status.PASSED,
                "S. Gupta (Chief Signal Inspector)",
                "Electronic Interlocking (EI) locked from Platform 1 to Down Main Line. Section interlocking status synchronized 100%."
            ),
            (
                3,
                "SCHEDULE_WINDOW",
                "Schedule Window: No conflicting maintenance blocks on the schedule",
                ReadinessChecklistItem.Category.SAFETY,
                ReadinessChecklistItem.Status.PASSED,
                "A. Verma (Station Master NDLS)",
                "Timetable departure slot #2026-DEP-951 confirmed. Zero maintenance blocks or speed restriction conflicts active."
            ),
        ]
        for seq, code, title, cat, status, signed_by, notes in c1_items:
            ReadinessChecklistItem.objects.update_or_create(
                case=case1, sequence=seq,
                defaults={
                    "item_code": code, "title": title, "category": cat,
                    "status": status, "is_required": True,
                    "signed_off_by": signed_by,
                    "signed_off_at": timezone.now() if signed_by else None,
                    "sign_off_comments": notes,
                }
            )

        if not ReadinessAuditRecord.objects.filter(
            case=case1,
            record_type=ReadinessAuditRecord.RecordType.DECISION,
            decision_reference="DEP-AUTH-12951-GO",
        ).exists():
            ReadinessAuditRecord.objects.create(
                case=case1,
                record_type=ReadinessAuditRecord.RecordType.DECISION,
                actor_type=ReadinessAuditRecord.ActorType.USER,
                actor_identifier="Chief Train Dispatcher",
                decision=OperationalReadinessCase.ReadinessDecision.READY,
                decision_reference="DEP-AUTH-12951-GO",
                new_state={"decision": "ready", "speed_kmph": 130},
                decision_summary="CLEARED FOR DEPARTURE (GO) — Authorized green signal at full permissible speed 130 km/h.",
                notes="Flight-deck pre-departure clearance protocol completed successfully.",
            )

        # -------------------------------------------------------------
        # CASE 2: Train #12004 (Shatabdi Express) -> HOLD AT PLATFORM (NO-GO)
        # -------------------------------------------------------------
        case2, _ = OperationalReadinessCase.objects.update_or_create(
            case_code="OPR-DEP-12004",
            defaults={
                "title": "Train #12004 (Shatabdi Express) Departure Clearance",
                "case_type": OperationalReadinessCase.CaseType.ROUTE_DEPARTURE,
                "train_number": "12004 New Delhi – Lucknow Jn Shatabdi Express",
                "track_section": trk_2,
                "assigned_team": team,
                "description": "Pre-departure flight-deck route clearance and safety audit for Platform 4 (NDLS) departure to Lucknow.",
                "workflow_status": OperationalReadinessCase.WorkflowStatus.FIELD_VERIFICATION,
                "readiness_decision": OperationalReadinessCase.ReadinessDecision.NOT_READY,
                "isolation_state": OperationalReadinessCase.IsolationState.ISOLATED,
                "sensor_metrics": {
                    "vibration_rms": 3.85,
                    "temperature_celsius": 46.2,
                    "ai_risk_score": 0.72,
                    "route_health_alerts": 2,
                },
                "readiness_score": Decimal("33.00"),
                "cleared_speed_kmph": 0,
                "decision_taken_by": "Safety Officer (NDLS Control)",
                "decision_taken_at": timezone.now(),
                "decision_reference": "HOLD-PLATFORM-12004",
                "decision_notes": "HOLD AT PLATFORM: Conflicting track maintenance block on Ghaziabad downline and unresolved signal interlocking sync. Red departure signal enforced.",
                "is_overridden": False,
            }
        )

        c2_items = [
            (
                1,
                "ROUTE_HEALTH",
                "Route Health: All track sections along route have 0 critical unresolved alerts",
                ReadinessChecklistItem.Category.SAFETY,
                ReadinessChecklistItem.Status.FAILED,
                "K. L. Meena (P-Way Engineer)",
                "Critical ballast shift alert active at KM 42/6 (Ghaziabad section). Vibration spike 3.85 mm/s exceeds 2.5 mm/s threshold."
            ),
            (
                2,
                "SIGNAL_INTERLOCKING",
                "Signal Interlocking: Section interlocking synced",
                ReadinessChecklistItem.Category.SIGNAL,
                ReadinessChecklistItem.Status.PENDING,
                "",
                "Awaiting field sync verification from Signal Maintenance Team on turnout 14B."
            ),
            (
                3,
                "SCHEDULE_WINDOW",
                "Schedule Window: No conflicting maintenance blocks on the schedule",
                ReadinessChecklistItem.Category.SAFETY,
                ReadinessChecklistItem.Status.FAILED,
                "Operations Dispatch",
                "Conflicting emergency maintenance block #MB-402 active between Ghaziabad and Aligarh. Departure slot unavailable."
            ),
        ]
        for seq, code, title, cat, status, signed_by, notes in c2_items:
            ReadinessChecklistItem.objects.update_or_create(
                case=case2, sequence=seq,
                defaults={
                    "item_code": code, "title": title, "category": cat,
                    "status": status, "is_required": True,
                    "signed_off_by": signed_by,
                    "signed_off_at": timezone.now() if signed_by else None,
                    "sign_off_comments": notes,
                }
            )

        if not ReadinessAuditRecord.objects.filter(
            case=case2,
            record_type=ReadinessAuditRecord.RecordType.DECISION,
            decision_reference="HOLD-PLATFORM-12004",
        ).exists():
            ReadinessAuditRecord.objects.create(
                case=case2,
                record_type=ReadinessAuditRecord.RecordType.DECISION,
                actor_type=ReadinessAuditRecord.ActorType.SYSTEM,
                actor_identifier="Automated Safety Interlock",
                decision=OperationalReadinessCase.ReadinessDecision.NOT_READY,
                new_state={"decision": "not_ready", "speed_kmph": 0},
                decision_summary="HOLD AT PLATFORM (NO-GO) — Departure signal locked red due to Route Health failure & schedule block conflict.",
                notes="Safety interlock active.",
            )

        # -------------------------------------------------------------
        # CASE 3: Delhi–Mathura Main Line Track Re-Opening (Track Case)
        # -------------------------------------------------------------
        case3, _ = OperationalReadinessCase.objects.update_or_create(
            case_code="OPR-TRK-NDL-001",
            defaults={
                "title": "Delhi–Mathura Main Line Track Re-Opening & Speed Clearance",
                "case_type": OperationalReadinessCase.CaseType.TRACK_REOPENING,
                "track_section": trk_1,
                "assigned_team": team,
                "description": "Post-weld grinding inspection and line clearance verification following scheduled rail joint overhaul.",
                "workflow_status": OperationalReadinessCase.WorkflowStatus.COMPLETED,
                "readiness_decision": OperationalReadinessCase.ReadinessDecision.READY,
                "isolation_state": OperationalReadinessCase.IsolationState.RESTORED,
                "sensor_metrics": {
                    "vibration_rms": 1.25,
                    "temperature_celsius": 32.4,
                    "ai_risk_score": 0.06,
                },
                "readiness_score": Decimal("98.50"),
                "cleared_speed_kmph": 130,
                "decision_taken_by": "Senior Divisional Engineer (DLI)",
                "decision_taken_at": timezone.now(),
                "decision_reference": "LINE-BLOCK-CLR-9012",
                "decision_notes": "All track telemetry verified nominal. Line restored to normal speed 130 km/h.",
                "is_overridden": False,
            }
        )

        c3_items = [
            (1, "CREW_CLEAR", "Ground Crew & Equipment Cleared", ReadinessChecklistItem.Category.SAFETY, ReadinessChecklistItem.Status.PASSED, "R. K. Sharma (Field Safety Guard)", "All 8 track workers and grinding machines evacuated to safe cess."),
            (2, "OHE_POWER", "25kV Traction Power Energization", ReadinessChecklistItem.Category.OHE, ReadinessChecklistItem.Status.PASSED, "P. Verma (Traction Power Controller)", "Isolation removed. 25kV OHE feeder energized and synced."),
            (3, "INTERLOCKING", "Point Machine & Interlocking Synchronized", ReadinessChecklistItem.Category.SIGNAL, ReadinessChecklistItem.Status.PASSED, "S. Gupta (Chief Signal Inspector)", "Electronic Interlocking points tested. Route locking verified."),
            (4, "PW_MEMO", "Permanent Way Section Engineer Memo", ReadinessChecklistItem.Category.CIVIL, ReadinessChecklistItem.Status.PASSED, "A. Singh (Section Engineer P-Way)", "Visual track alignment and ultrasonic weld inspection signed off."),
        ]
        for seq, code, title, cat, status, signed_by, notes in c3_items:
            ReadinessChecklistItem.objects.update_or_create(
                case=case3, sequence=seq,
                defaults={
                    "item_code": code, "title": title, "category": cat,
                    "status": status, "is_required": True,
                    "signed_off_by": signed_by, "signed_off_at": timezone.now(),
                    "sign_off_comments": notes,
                }
            )

        # -------------------------------------------------------------
        # SEED LINKED GROUND PATROL INSPECTIONS
        # -------------------------------------------------------------
        from patrol.models import WorkerPatrolReport, PatrolCategoryRating

        # Patrol 1: Track Section 1 (Nominal / Cleared)
        p1, _ = WorkerPatrolReport.objects.update_or_create(
            patrol_code="PTR-2026-0001",
            defaults={
                "worker": worker_user,
                "track_section": trk_1,
                "patrol_started_at": timezone.now() - timezone.timedelta(hours=2),
                "patrol_completed_at": timezone.now() - timezone.timedelta(minutes=30),
                "worker_overall_score": Decimal("95.00"),
                "iot_overall_score": Decimal("96.00"),
                "composite_score": Decimal("95.40"),
                "worker_weight": Decimal("0.60"),
                "iot_weight": Decimal("0.40"),
                "conflict_detected": False,
                "status": WorkerPatrolReport.Status.DECIDED,
                "admin_decision": WorkerPatrolReport.AdminDecision.CLEARED,
                "admin_decision_by": "Chief Dispatcher",
                "admin_decision_at": timezone.now() - timezone.timedelta(minutes=15),
                "admin_notes": "Physical ground inspection verified 100% nominal across all 8 RDSO categories.",
            }
        )
        p1_ratings = [
            (PatrolCategoryRating.Category.RAIL_CONDITION, 5, "No surface defects, micro-cracks or head wear detected."),
            (PatrolCategoryRating.Category.TRACK_GEOMETRY, 5, "Gauge 1676.0mm exact, cross-levels nominal."),
            (PatrolCategoryRating.Category.SLEEPERS_FASTENINGS, 5, "All ERC clips and rubber pads intact."),
            (PatrolCategoryRating.Category.BALLAST_CONDITION, 4, "Cushion depth adequate, clean ballast shoulder."),
            (PatrolCategoryRating.Category.DRAINAGE, 5, "Side drains cleared of debris, zero waterlogging."),
            (PatrolCategoryRating.Category.POINTS_CROSSINGS, 5, "Switch tongue rail tight against stock rail."),
            (PatrolCategoryRating.Category.LEVEL_CROSSINGS, 5, "Lifting barrier locked, road surface smooth."),
            (PatrolCategoryRating.Category.FORMATION_EARTHWORK, 4, "Embankment stable, cess width compliant."),
        ]
        for cat, val, note in p1_ratings:
            PatrolCategoryRating.objects.update_or_create(
                patrol=p1, category=cat,
                defaults={"rating": val, "notes": note}
            )

        # Patrol 2: Track Section 2 (Defects / Hold)
        p2, _ = WorkerPatrolReport.objects.update_or_create(
            patrol_code="PTR-2026-0002",
            defaults={
                "worker": worker_user,
                "track_section": trk_2,
                "patrol_started_at": timezone.now() - timezone.timedelta(hours=1),
                "patrol_completed_at": timezone.now() - timezone.timedelta(minutes=10),
                "worker_overall_score": Decimal("42.50"),
                "iot_overall_score": Decimal("35.00"),
                "composite_score": Decimal("39.50"),
                "worker_weight": Decimal("0.60"),
                "iot_weight": Decimal("0.40"),
                "conflict_detected": False,
                "status": WorkerPatrolReport.Status.SUBMITTED,
                "admin_decision": WorkerPatrolReport.AdminDecision.BLOCKED,
                "admin_decision_by": "Safety Officer",
                "admin_decision_at": timezone.now() - timezone.timedelta(minutes=5),
                "admin_notes": "Defect report logged: Ballast settling & dynamic gauge deviation at KM 42/6.",
            }
        )
        p2_ratings = [
            (PatrolCategoryRating.Category.RAIL_CONDITION, 3, "Corrugation wear observed on high rail curve."),
            (PatrolCategoryRating.Category.TRACK_GEOMETRY, 2, "Dynamic gauge deviation +4.2mm under traffic."),
            (PatrolCategoryRating.Category.SLEEPERS_FASTENINGS, 2, "2 cracked concrete sleepers near turnout 14B."),
            (PatrolCategoryRating.Category.BALLAST_CONDITION, 1, "Critical ballast settling and mud pumping at KM 42/6."),
            (PatrolCategoryRating.Category.DRAINAGE, 3, "Side drain silt buildup requiring clearing."),
            (PatrolCategoryRating.Category.POINTS_CROSSINGS, 2, "Point machine throw slack detected."),
            (PatrolCategoryRating.Category.LEVEL_CROSSINGS, 4, "Gate mechanism operational."),
            (PatrolCategoryRating.Category.FORMATION_EARTHWORK, 2, "Cess erosion on down-slope side."),
        ]
        for cat, val, note in p2_ratings:
            PatrolCategoryRating.objects.update_or_create(
                patrol=p2, category=cat,
                defaults={"rating": val, "notes": note}
            )

        self.stdout.write(self.style.SUCCESS("Successfully seeded Flight-Deck Train Departure Clearance cases with Ground Patrol data!"))


