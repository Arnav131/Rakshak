"""
patrol/models.py
Worker Patrol Report & Category Rating models.
Each patrol is an isolated case (Separation Logic).
"""
import uuid
from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone
from railway.models import TimeStampedModel, TrackSection


class WorkerPatrolReport(TimeStampedModel):
    """
    A single worker patrol of a track section (Station A → Station B).
    Each patrol is an independent, isolated case — no data leaks between patrols.
    """
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In Progress"
        SUBMITTED = "submitted", "Worker Report Submitted"
        IOT_GENERATED = "iot_generated", "IoT Data Generated"
        UNDER_REVIEW = "under_review", "Under Admin Review"
        DECIDED = "decided", "Decision Made"

    class AdminDecision(models.TextChoices):
        PENDING = "pending", "Pending"
        CLEARED = "cleared", "Cleared for Operations"
        RESTRICTED = "restricted", "Speed Restriction Applied"
        BLOCKED = "blocked", "Route Blocked"

    # --- Identity ---
    patrol_code = models.CharField(
        max_length=30, unique=True,
        help_text="Unique patrol code, e.g. 'PTR-2026-0001'.",
    )
    worker = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="patrol_reports",
        help_text="Worker who performed the patrol.",
    )
    track_section = models.ForeignKey(
        TrackSection, on_delete=models.PROTECT,
        related_name="patrol_reports",
        help_text="Track section inspected (Station A → Station B).",
    )

    # --- Timing ---
    patrol_started_at = models.DateTimeField(default=timezone.now)
    patrol_completed_at = models.DateTimeField(null=True, blank=True)

    # --- Worker Score (computed from 8 category ratings) ---
    worker_overall_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
        help_text="Worker inspection score (0-100), avg of 8 category ratings × 20.",
    )

    # --- IoT Score (computed from generated sensor data + ML pipeline) ---
    iot_overall_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
        help_text="IoT health score (0-100), derived from ML anomaly prediction.",
    )
    iot_readings = models.JSONField(
        default=list, blank=True,
        help_text="16-reading IoT sensor window generated post-inspection.",
    )
    iot_generator_backend = models.CharField(
        max_length=30, blank=True, default="",
        help_text="Which backend generated IoT data: gemini, anthropic, physics_iot_rng, etc.",
    )
    iot_prediction = models.JSONField(
        default=dict, blank=True,
        help_text="Full ML prediction result from the PredictionService pipeline.",
    )
    iot_scenario_flavour = models.CharField(
        max_length=100, blank=True, default="",
    )

    # --- Composite Score (admin-adjustable weights) ---
    worker_weight = models.DecimalField(
        max_digits=3, decimal_places=2, default=Decimal("0.60"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("1"))],
        help_text="Weight given to worker score in composite. Default 0.60 (60%).",
    )
    iot_weight = models.DecimalField(
        max_digits=3, decimal_places=2, default=Decimal("0.40"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("1"))],
        help_text="Weight given to IoT score in composite. Default 0.40 (40%).",
    )
    composite_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
        help_text="Weighted composite: (worker_weight × worker_score) + (iot_weight × iot_score).",
    )
    conflict_detected = models.BooleanField(
        default=False,
        help_text="True when worker score and IoT score disagree by > 30 points.",
    )

    # --- Status & Decision ---
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.IN_PROGRESS,
    )
    admin_decision = models.CharField(
        max_length=20, choices=AdminDecision.choices, default=AdminDecision.PENDING,
    )
    admin_decision_by = models.CharField(max_length=150, blank=True, default="")
    admin_decision_at = models.DateTimeField(null=True, blank=True)
    admin_notes = models.TextField(blank=True, default="")
    admin_speed_restriction = models.PositiveIntegerField(
        default=0,
        help_text="Speed restriction applied by admin (km/h). 0 = no restriction.",
    )

    class Meta:
        db_table = "rakshak_worker_patrol_report"
        ordering = ["-created_at"]
        verbose_name = "Worker Patrol Report"
        verbose_name_plural = "Worker Patrol Reports"
        indexes = [
            models.Index(fields=["status"], name="idx_patrol_status"),
            models.Index(fields=["worker", "status"], name="idx_patrol_worker_st"),
            models.Index(fields=["admin_decision"], name="idx_patrol_decision"),
        ]

    def __str__(self):
        return self.patrol_code


class PatrolCategoryRating(TimeStampedModel):
    """
    Per-category worker inspection rating.
    8 categories based on Indian Railways RDSO Keyman Patrol Manual.
    """
    class Category(models.TextChoices):
        RAIL_CONDITION = "rail_condition", "Rail Condition"
        TRACK_GEOMETRY = "track_geometry", "Track Geometry"
        SLEEPERS_FASTENINGS = "sleepers_fastenings", "Sleepers & Fastenings"
        BALLAST_CONDITION = "ballast_condition", "Ballast Condition"
        DRAINAGE = "drainage", "Drainage"
        POINTS_CROSSINGS = "points_crossings", "Points & Crossings"
        LEVEL_CROSSINGS = "level_crossings", "Level Crossings"
        FORMATION_EARTHWORK = "formation_earthwork", "Formation & Earthwork"

    patrol = models.ForeignKey(
        WorkerPatrolReport, on_delete=models.CASCADE,
        related_name="category_ratings",
    )
    category = models.CharField(max_length=30, choices=Category.choices)
    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="1=Critical, 2=Poor, 3=Fair, 4=Good, 5=Excellent",
    )
    notes = models.TextField(
        blank=True, default="",
        help_text="Worker's observation notes for this category.",
    )
    gps_latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
    )
    gps_longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
    )

    class Meta:
        db_table = "rakshak_patrol_category_rating"
        ordering = ["patrol", "category"]
        verbose_name = "Patrol Category Rating"
        verbose_name_plural = "Patrol Category Ratings"
        constraints = [
            models.UniqueConstraint(
                fields=["patrol", "category"],
                name="uniq_patrol_category",
            ),
        ]

    def __str__(self):
        return f"{self.patrol.patrol_code}:{self.get_category_display()} = {self.rating}/5"
