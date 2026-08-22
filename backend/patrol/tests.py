"""
patrol/tests.py
Unit and Integration Tests for Worker Patrol System.
"""
from decimal import Decimal
from django.contrib.auth.models import User, Group
from django.test import TestCase, Client
from django.urls import reverse
from railway.models import Zone, Division, Station, TrackSection
from patrol.models import WorkerPatrolReport, PatrolCategoryRating
from patrol import services


class WorkerPatrolTestCase(TestCase):
    def setUp(self):
        # 1. Setup geography and track sections
        self.zone = Zone.objects.create(code="NR", name="Northern Railway")
        self.division = Division.objects.create(code="DLI", name="Delhi Division", zone=self.zone)
        self.st_a = Station.objects.create(station_code="NDLS", station_name="New Delhi", division=self.division, latitude=Decimal("28.6139"), longitude=Decimal("77.2090"))
        self.st_b = Station.objects.create(station_code="GZB", station_name="Ghaziabad Junction", division=self.division, latitude=Decimal("28.6692"), longitude=Decimal("77.4538"))
        self.section = TrackSection.objects.create(
            section_code="TRK-NDL-GZB-01",
            start_station=self.st_a,
            end_station=self.st_b,
            length_km=Decimal("25.50"),
            max_speed_kmph=130,
            status=TrackSection.Status.ACTIVE,
        )

        # 2. Setup users and groups
        self.patrol_group = Group.objects.create(name="patrol_worker")

        self.worker = User.objects.create_user(username="testworker", password="password123", first_name="Ramesh", last_name="Kumar")
        self.worker.groups.add(self.patrol_group)

        self.admin = User.objects.create_superuser(username="testadmin", password="password123")
        self.viewer = User.objects.create_user(username="testviewer", password="password123")

        self.client = Client()

    def test_patrol_code_generation(self):
        code1 = services.generate_patrol_code()
        self.assertTrue(code1.startswith("PTR-"))
        p = WorkerPatrolReport.objects.create(
            patrol_code=code1,
            worker=self.worker,
            track_section=self.section,
        )
        code2 = services.generate_patrol_code()
        self.assertNotEqual(code1, code2)

    def test_create_patrol_and_submit_ratings(self):
        patrol = services.create_patrol_report(self.worker, self.section.pk)
        self.assertEqual(patrol.status, WorkerPatrolReport.Status.IN_PROGRESS)
        self.assertEqual(patrol.worker, self.worker)

        # Submit 8 ratings: 4, 5, 4, 5, 4, 5, 4, 5 -> avg = 4.5 -> score = 4.5/5 * 100 = 90.00
        ratings_data = [
            {"category": "rail_condition", "rating": 4, "notes": "Good"},
            {"category": "track_geometry", "rating": 5, "notes": "Perfect"},
            {"category": "sleepers_fastenings", "rating": 4, "notes": "All tight"},
            {"category": "ballast_condition", "rating": 5, "notes": "Clean"},
            {"category": "drainage", "rating": 4, "notes": "Clear"},
            {"category": "points_crossings", "rating": 5, "notes": "Nominal"},
            {"category": "level_crossings", "rating": 4, "notes": "Gates operational"},
            {"category": "formation_earthwork", "rating": 5, "notes": "Stable"},
        ]
        patrol = services.submit_worker_ratings(patrol.patrol_code, ratings_data)
        self.assertEqual(patrol.status, WorkerPatrolReport.Status.SUBMITTED)
        self.assertAlmostEqual(float(patrol.worker_overall_score), 90.00, places=1)
        self.assertEqual(patrol.category_ratings.count(), 8)

    def test_post_inspection_iot_and_composite_score(self):
        patrol = services.create_patrol_report(self.worker, self.section.pk)
        ratings_data = [
            {"category": cat.value, "rating": 5, "notes": "Optimal"}
            for cat in PatrolCategoryRating.Category
        ]
        services.submit_worker_ratings(patrol.patrol_code, ratings_data)
        patrol = services.generate_post_inspection_iot(patrol.patrol_code)

        self.assertEqual(patrol.status, WorkerPatrolReport.Status.IOT_GENERATED)
        self.assertEqual(len(patrol.iot_readings), 16)
        self.assertIsNotNone(patrol.iot_overall_score)
        self.assertIsNotNone(patrol.composite_score)

        # Composite score should follow worker_weight * worker_score + iot_weight * iot_score
        expected_composite = (patrol.worker_weight * patrol.worker_overall_score) + (patrol.iot_weight * patrol.iot_overall_score)
        self.assertAlmostEqual(float(patrol.composite_score), float(expected_composite), places=2)

    def test_conflict_detection(self):
        patrol = services.create_patrol_report(self.worker, self.section.pk)
        # Worker rates 5/5 everywhere -> 100.00 score
        ratings_data = [
            {"category": cat.value, "rating": 5, "notes": "Optimal"}
            for cat in PatrolCategoryRating.Category
        ]
        patrol = services.submit_worker_ratings(patrol.patrol_code, ratings_data)

        # Simulate poor IoT health score (e.g. 40.00)
        patrol.iot_overall_score = Decimal("40.00")
        services._recompute_composite(patrol)
        patrol.save()

        # abs(100 - 40) = 60 > 30 -> conflict_detected must be True
        self.assertTrue(patrol.conflict_detected)

    def test_admin_decision_and_track_sync(self):
        patrol = services.create_patrol_report(self.worker, self.section.pk)
        ratings_data = [
            {"category": cat.value, "rating": 3, "notes": "Fair"}
            for cat in PatrolCategoryRating.Category
        ]
        services.submit_worker_ratings(patrol.patrol_code, ratings_data)

        # Apply Speed Restriction of 45 km/h
        services.submit_admin_decision(
            patrol_code=patrol.patrol_code,
            user=self.admin,
            decision=WorkerPatrolReport.AdminDecision.RESTRICTED,
            notes="Reduced speed due to ballast settling",
            speed_restriction=45,
        )

        patrol.refresh_from_db()
        self.assertEqual(patrol.admin_decision, WorkerPatrolReport.AdminDecision.RESTRICTED)
        self.assertEqual(patrol.admin_speed_restriction, 45)
        self.assertEqual(patrol.status, WorkerPatrolReport.Status.DECIDED)

        # TrackSection max speed should be synced
        self.section.refresh_from_db()
        self.assertEqual(self.section.max_speed_kmph, 45)

        # Block route
        services.submit_admin_decision(
            patrol_code=patrol.patrol_code,
            user=self.admin,
            decision=WorkerPatrolReport.AdminDecision.BLOCKED,
            notes="Emergency maintenance needed",
        )
        self.section.refresh_from_db()
        self.assertEqual(self.section.status, TrackSection.Status.UNDER_MAINTENANCE)

    def test_api_workflow_end_to_end(self):
        # 1. Login as worker
        self.client.login(username="testworker", password="password123")

        # 2. Start patrol
        resp = self.client.post(
            "/api/patrol/start/",
            data={"track_section_id": self.section.pk},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        patrol_code = data["patrol_code"]

        # 3. Submit ratings
        ratings = [
            {"category": cat.value, "rating": 4, "notes": "Standard inspection"}
            for cat in PatrolCategoryRating.Category
        ]
        resp = self.client.post(
            f"/api/patrol/{patrol_code}/submit/",
            data={"ratings": ratings},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()["patrol"]
        self.assertEqual(payload["status"], "iot_generated")
        self.assertIsNotNone(payload["worker_overall_score"])
        self.assertIsNotNone(payload["iot_overall_score"])

        # 4. Worker cannot adjust weights or decide
        resp = self.client.post(
            f"/api/patrol/{patrol_code}/weights/",
            data={"worker_weight": 0.7, "iot_weight": 0.3},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)

        # 5. Login as admin
        self.client.login(username="testadmin", password="password123")

        # 6. Admin adjusts weights
        resp = self.client.post(
            f"/api/patrol/{patrol_code}/weights/",
            data={"worker_weight": 0.70, "iot_weight": 0.30},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["patrol"]["worker_weight"], 0.7)

        # 7. Admin submits decision
        resp = self.client.post(
            f"/api/patrol/{patrol_code}/decide/",
            data={"decision": "cleared", "notes": "Approved for full speed"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["patrol"]["admin_decision"], "cleared")
