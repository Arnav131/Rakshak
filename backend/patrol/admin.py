# backend/patrol/admin.py
from django.contrib import admin
from .models import WorkerPatrolReport, PatrolCategoryRating


class PatrolCategoryRatingInline(admin.TabularInline):
    model = PatrolCategoryRating
    extra = 0
    fields = ["category", "rating", "notes", "gps_latitude", "gps_longitude"]


@admin.register(WorkerPatrolReport)
class WorkerPatrolReportAdmin(admin.ModelAdmin):
    list_display = [
        "patrol_code", "worker", "track_section", "status",
        "worker_overall_score", "iot_overall_score", "composite_score",
        "conflict_detected", "admin_decision", "created_at"
    ]
    list_filter = ["status", "admin_decision", "conflict_detected", "created_at"]
    search_fields = ["patrol_code", "worker__username", "track_section__section_code"]
    inlines = [PatrolCategoryRatingInline]
    readonly_fields = [
        "patrol_code", "worker_overall_score", "iot_overall_score",
        "composite_score", "conflict_detected", "created_at", "updated_at"
    ]
