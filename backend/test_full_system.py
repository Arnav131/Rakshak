# backend/test_full_system.py
import os
import sys
import json
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rakshak_project.settings')
import django
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from railway.models import (
    Zone, Division, Station, TrackSection, MaintenanceTeam,
    Alert, Ticket, OperationalReadinessCase, ReadinessChecklistItem,
    ReadinessAuditRecord, Sensor
)
from readiness.services import (
    evaluate_case_telemetry, sign_off_checklist_item, submit_controller_decision, get_case_payload
)
from simulation.generator import generate_journey
from ai_integration.prediction_service import PredictionService

User = get_user_model()

def run_full_system_test():
    print("=" * 70)
    print("RAKSHAK - COMPREHENSIVE SYSTEM VERIFICATION & CHALLENGE #733 TEST")
    print("=" * 70)
    
    passed_tests = 0
    failed_tests = 0
    
    def log_result(name, passed, detail=""):
        nonlocal passed_tests, failed_tests
        status = "[PASS]" if passed else "[FAIL]"
        print(f" {status} {name}" + (f" -> {detail}" if detail else ""))
        if passed:
            passed_tests += 1
        else:
            failed_tests += 1

    client = Client()
    
    # -------------------------------------------------------------
    # 1. AUTHENTICATION & ROLE TEST
    # -------------------------------------------------------------
    print("\n[1] AUTHENTICATION & ROLE-BASED ACCESS CONTROL")
    controller_user = User.objects.filter(username="controller").first()
    if not controller_user:
        controller_user = User.objects.create_user(username="controller", password="admin123", is_staff=True, is_superuser=True)
    
    worker_user = User.objects.filter(username="worker").first()
    if not worker_user:
        worker_user = User.objects.create_user(username="worker", password="worker123", is_staff=False)
        
    client.force_login(controller_user)
    log_result("Controller Authentication", client.session.get('_auth_user_id') is not None, f"User: {controller_user.username}")

    # -------------------------------------------------------------
    # 2. PAGE RENDER TEST (ALL CORE VIEWS)
    # -------------------------------------------------------------
    print("\n[2] CORE PAGE RENDERING (HTTP 200)")
    urls_to_test = [
        ('/', 'Dashboard View'),
        ('/alerts/', 'Alerts View'),
        ('/tickets/', 'Tickets View'),
        ('/map/', 'Railway Map View'),
        ('/readiness/', 'Operational Readiness Control Center (Challenge #733)'),
        ('/simulation/', 'Live Simulation View'),
        ('/patrol/', 'Worker Patrol View'),
        ('/patrol/admin/', 'Patrol Admin Review View'),
    ]
    
    for url, label in urls_to_test:
        resp = client.get(url)
        log_result(f"Render {label} ({url})", resp.status_code == 200, f"Status: {resp.status_code}")

    # -------------------------------------------------------------
    # 3. REST API ENDPOINTS TEST
    # -------------------------------------------------------------
    print("\n[3] REST API ENDPOINTS VERIFICATION")
    api_endpoints = [
        ('/api/stations/', 'GET Stations API'),
        ('/api/routes/', 'GET Routes API'),
        ('/api/alerts/', 'GET Alerts API'),
        ('/api/tickets/', 'GET Tickets API'),
        ('/readiness/api/cases/', 'GET Readiness Cases API'),
        ('/tickets/api/search/', 'GET Tickets Search API'),
        ('/api/patrol/reports/', 'GET Patrol Reports API'),
    ]
    
    for url, label in api_endpoints:
        resp = client.get(url)
        is_ok = resp.status_code == 200
        is_json = resp.headers.get('Content-Type', '').startswith('application/json')
        log_result(f"{label} ({url})", is_ok and is_json, f"Status: {resp.status_code}")

    # -------------------------------------------------------------
    # 4. CHALLENGE #733: OPERATIONAL READINESS SEPARATION LOGIC
    # -------------------------------------------------------------
    print("\n[4] CHALLENGE #733: SEPARATION LOGIC & OPERATIONAL READINESS GATES")
    
    # Retrieve 3 test cases
    case_1 = OperationalReadinessCase.objects.filter(case_code="OPR-DEP-12951").first()
    case_2 = OperationalReadinessCase.objects.filter(case_code="OPR-DEP-12004").first()
    case_3 = OperationalReadinessCase.objects.filter(case_code="OPR-TRK-NDL-001").first()
    
    log_result("Cases Seeded in DB", bool(case_1 and case_2 and case_3), "OPR-DEP-12951, OPR-DEP-12004, OPR-TRK-NDL-001 found")
    
    if case_1 and case_2:
        # Check initial state separation
        c1_payload = get_case_payload(case_1)
        c2_payload = get_case_payload(case_2)
        
        log_result("Case Data Isolation", c1_payload["case_code"] != c2_payload["case_code"] and c1_payload["train_number"] != c2_payload["train_number"],
                   f"Case 1: {c1_payload['train_number']} vs Case 2: {c2_payload['train_number']}")
        
        # Telemetry Safety Gate check on Case 2 (Unready due to ballast vibration spike)
        eval_c2 = evaluate_case_telemetry(case_2)
        log_result("Case 2 Telemetry Safety Gate (Active Alert & High Vib Trigger)", not eval_c2["all_telemetry_passed"],
                   f"Vibration: {eval_c2['vibration_rms']} mm/s (Passed: {eval_c2['vibration_passed']}), Alerts: {eval_c2['active_critical_alerts']}")
        
        # Test Go/No-Go Decision Gate: Case 2 cannot be authorized for READY without override
        try:
            submit_controller_decision(
                case_code=case_2.case_code,
                user=controller_user,
                decision="ready",
                speed_kmph=130,
                is_override=False,
            )
            blocked_safely = False
        except ValueError:
            blocked_safely = True
            
        log_result("Pre-Action Safety Gate: Unsafe Track Authorization Blocked", blocked_safely,
                   "Blocked FULL GO because telemetry & checklist requirements failed")
        
        # Test Field Sign-off Separation: Signing off an item on Case 2 does NOT alter Case 1
        initial_c1_checklist_count = case_1.checklist_items.filter(status="passed").count()
        item_to_sign = case_2.checklist_items.filter(item_code="SIGNAL_INTERLOCKING").first()
        if item_to_sign:
            sign_off_checklist_item(
                case_code=case_2.case_code,
                item_id_or_code="SIGNAL_INTERLOCKING",
                user=worker_user,
                role_designation="Chief Signal Inspector",
                notes="Interlocking field check completed by unit 7.",
                status="passed"
            )
            
            case_1.refresh_from_db()
            case_2.refresh_from_db()
            item_to_sign.refresh_from_db()
            
            c1_unchanged = (case_1.checklist_items.filter(status="passed").count() == initial_c1_checklist_count)
            c2_updated = (item_to_sign.status == "passed")
            
            log_result("Field Sign-off Strict Separation Logic", c1_unchanged and c2_updated,
                       f"Case 2 Item Updated: {c2_updated} | Case 1 Checklist Untouched: {c1_unchanged}")
            
            # Check Audit Trail Isolation
            audit_records_c2 = ReadinessAuditRecord.objects.filter(case=case_2).count()
            audit_records_c1 = ReadinessAuditRecord.objects.filter(case=case_1).count()
            log_result("Immutable Audit Trail Separation", audit_records_c2 > 0 and audit_records_c1 > 0,
                       f"Case 2 Audits: {audit_records_c2}, Case 1 Audits: {audit_records_c1}")

    # -------------------------------------------------------------
    # 5. AI SIMULATION & ML INFERENCE PIPELINE TEST
    # -------------------------------------------------------------
    print("\n[5] AI ENGINE & LIVE TELEMETRY SIMULATION")
    readings, flavour, desc, source = generate_journey("NDLS", "AGC", condition="nominal")
    log_result("IoT Sensor Journey Generator", len(readings) == 16, f"16 readings generated via '{source}' ({flavour})")
    
    pred_service = PredictionService()
    last_resp = None
    for r in readings:
        last_resp = pred_service.predict_for_sensor(
            sensor_id="TEST-SIM-001",
            ambient_temp=r["ambient_temp"],
            humidity=r["humidity"],
            vibration_rms=r["vibration_rms"],
            gauge_width=r["gauge_width"],
        )
    log_result("AI Prediction Pipeline Inference", last_resp is not None and hasattr(last_resp, "is_anomaly"),
               f"Provider: {last_resp.provider_name}, Anomaly: {last_resp.is_anomaly}, Fault: {last_resp.fault_type}")

    # -------------------------------------------------------------
    # 6. SIMULATION END-TO-END API TEST (POST /api/simulation/run/)
    # -------------------------------------------------------------
    print("\n[6] SIMULATION END-TO-END API TEST")
    sim_post_resp = client.post(
        '/api/simulation/run/',
        data=json.dumps({"source": "NDLS", "destination": "AGC", "condition": "nominal"}),
        content_type="application/json"
    )
    sim_ok = sim_post_resp.status_code == 200
    sim_data = sim_post_resp.json() if sim_ok else {}
    log_result("POST /api/simulation/run/", sim_ok and sim_data.get("success") == True,
               f"Backend: {sim_data.get('generator_backend')}, Target Case: {sim_data.get('target_readiness_case')}")

    # -------------------------------------------------------------
    # SUMMARY
    # -------------------------------------------------------------
    print("\n" + "=" * 70)
    print(f"TEST SUMMARY: {passed_tests} PASSED | {failed_tests} FAILED")
    print("=" * 70)
    return failed_tests == 0

if __name__ == "__main__":
    success = run_full_system_test()
    sys.exit(0 if success else 1)
