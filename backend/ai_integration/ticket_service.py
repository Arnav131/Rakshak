# backend/ai_integration/ticket_service.py
"""
Rakshak AI Integration — Ticket Service
===========================================
Centralizes maintenance ticket creation from AI predictions.

Extracted from MaintenanceDispatchAgent.process() to enable
reuse across agents, API views, and management commands.

WHO SHOULD USE THIS:
    - AlertService (when auto-ticketing is enabled)
    - API views (for manual ticket creation from predictions)
    - Management commands that process alerts in bulk
    - Any code that needs to create tickets from PredictionResponse

WHO SHOULD NEVER USE THIS:
    - Code that creates manual tickets (use Ticket.objects.create)
    - Templates or frontend code

# ---------------------------------------------------------------------------
# DATABASE MIGRATION NOTE
#
# This module creates records in:
#   - rakshak_ticket (via Ticket.objects.create)
#   - rakshak_audit_log (via AuditLog.objects.create)
#
# Current DB: PostgreSQL
# Future DB: None
#
# Why this code exists:
#   Centralizes AI-driven ticket creation that was previously only
#   available through the MaintenanceDispatchAgent.
#
# PostgreSQL compatible: YES
#   - transaction.atomic() is fully supported
#   - DecimalField for cost_estimate_inr is native PostgreSQL NUMERIC
#   - CharField(unique=True) for ticket_code uses PostgreSQL unique index
#   - ForeignKey fields use standard integer references
#   - All ORM operations are database-agnostic
#
# Whether teammate needs to modify anything: NO
#   No schema changes. Uses existing Ticket and AuditLog models.
# ---------------------------------------------------------------------------
"""

import logging
from decimal import Decimal
from typing import Dict, Optional

from django.db import transaction
from django.utils import timezone

from ai_integration.providers import PredictionResponse
from ai_integration.severity import score_to_ticket_priority

logger = logging.getLogger("rakshak.ai_integration.ticket_service")

# Minimum delay before a duplicate ticket may be opened again for the
# same section + fault type. Mirrors AlertService.DEDUP_WINDOW_MINUTES.
DEDUP_WINDOW_MINUTES = 30


# Fault type → estimated repair cost (INR)
# Mirrors MaintenanceDispatchAgent.COST_ESTIMATES
COST_ESTIMATES: Dict[str, int] = {
    "thermal_buckle": 250000,
    "rail_fracture": 500000,
    "gauge_widening": 180000,
    "ballast_degradation": 120000,
    "joint_wear": 80000,
    "corrugation": 200000,
    "fastener_failure": 50000,
    "subgrade_settlement": 800000,
    "weld_defect": 150000,
    "drainage_failure": 100000,
    "vegetation_encroachment": 30000,
    "buckle_precursor": 100000,
    "ballast_washout": 150000,
    "subgrade_failure": 600000,
}

# Fault type → estimated repair duration (hours)
DURATION_ESTIMATES: Dict[str, float] = {
    "thermal_buckle": 12.0,
    "rail_fracture": 24.0,
    "gauge_widening": 8.0,
    "ballast_degradation": 6.0,
    "joint_wear": 4.0,
    "corrugation": 16.0,
    "fastener_failure": 3.0,
    "subgrade_settlement": 48.0,
    "weld_defect": 8.0,
    "drainage_failure": 6.0,
    "vegetation_encroachment": 4.0,
    "buckle_precursor": 8.0,
    "ballast_washout": 10.0,
    "subgrade_failure": 36.0,
}


class TicketService:
    """
    Service for creating maintenance tickets from AI predictions.

    Provides a clean interface for converting PredictionResponse
    + Alert data into Ticket database records with auto-assignment.

    Usage:
        from ai_integration.ticket_service import TicketService

        service = TicketService()
        ticket_id = service.create_ticket_from_prediction(
            response=prediction_response,
            track_section_id=7,
            alert_id=123,
        )
    """

    def __init__(self):
        pass

    def _generate_ticket_code(self) -> str:
        """
        Generate a globally unique, collision-resistant ticket code (<= 20 chars).
        Format: TKT-YYYYMMDD-XXXXXX (e.g. TKT-20260823-A1B2C3) -> 19 chars.
        """
        import uuid
        now = timezone.now()
        unique_suffix = uuid.uuid4().hex[:6].upper()
        return f"TKT-{now.strftime('%Y%m%d')}-{unique_suffix}"

    def create_ticket_from_prediction(
        self,
        response: PredictionResponse,
        track_section_id: int,
        alert_id: Optional[int] = None,
    ) -> Optional[int]:
        """
        Create a maintenance ticket from a PredictionResponse.

        Automatically determines priority, cost estimate, duration,
        and assigns the nearest available team.

        Args:
            response:         PredictionResponse from any AI provider.
            track_section_id: TrackSection PK where maintenance is needed.
            alert_id:         Alert PK that triggered this ticket (optional).

        Returns:
            Ticket PK if created, None on failure.

        # ---------------------------------------------------------------
        # DATABASE MIGRATION NOTE
        #
        # Inserts into: rakshak_ticket, rakshak_audit_log
        # Reads from: rakshak_maintenance_team, rakshak_ticket (for counts),
        #             rakshak_track_section (for division lookup)
        # Uses: transaction.atomic()
        #
        # Current DB: PostgreSQL
        # Future DB: None
        # PostgreSQL compatible: YES
        #   - All queries use standard Django ORM
        #   - Count aggregations work identically
        #   - ForeignKey lookups work identically
        # Teammate action: NONE
        # ---------------------------------------------------------------
        """
        from railway.models import Ticket, AuditLog

        fault_type = response.fault_type
        if fault_type == "unknown":
            fault_type = "unclassified"

        # Dedup: don't open a second open/assigned ticket for the same
        # section + fault type while one is already being worked on.
        from datetime import timedelta

        since = timezone.now() - timedelta(minutes=DEDUP_WINDOW_MINUTES)
        duplicate = Ticket.objects.filter(
            track_section_id=track_section_id,
            created_at__gte=since,
        ).exclude(status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED])
        if fault_type != "unclassified":
            duplicate = duplicate.filter(title__icontains=fault_type.replace("_", " "))
        if duplicate.exists():
            logger.info(
                f"TicketService: Suppressing duplicate ticket for "
                f"section={track_section_id} fault={fault_type} within "
                f"{DEDUP_WINDOW_MINUTES}min window"
            )
            return None

        # Determine priority from score + alert level via centralized
        # thresholds (severity.py) so alert severity and ticket priority
        # always tell the same story for one event.
        priority = getattr(
            Ticket.Priority, score_to_ticket_priority(
                response.anomaly_score, response.alert_level
            ).upper(),
            Ticket.Priority.MEDIUM,
        )

        # Estimate cost and duration
        cost_estimate = COST_ESTIMATES.get(fault_type, 100000)
        duration_estimate = DURATION_ESTIMATES.get(fault_type, 8.0)

        # Find available team
        assigned_team_id = self._find_available_team(track_section_id)

        try:
            with transaction.atomic():
                ticket = Ticket.objects.create(
                    ticket_code=self._generate_ticket_code(),
                    alert_id=alert_id,
                    track_section_id=track_section_id,
                    assigned_team_id=assigned_team_id,
                    title=(
                        f"{fault_type.replace('_', ' ').title()} — "
                        f"{response.alert_level.upper()} Priority"
                    ),
                    description=(
                        f"Auto-generated from AI prediction.\n\n"
                        f"Fault Type: {fault_type}\n"
                        f"Anomaly Score: {response.anomaly_score:.4f}\n"
                        f"Alert Level: {response.alert_level}\n"
                        f"Estimated Duration: {duration_estimate} hours\n"
                        f"Provider: {response.provider_name}\n\n"
                        f"Failure Probabilities:\n"
                        + "\n".join(
                            f"  {h}: {p:.1%}"
                            for h, p in response.failure_probabilities.items()
                        )
                    ),
                    priority=priority,
                    status=(
                        Ticket.Status.ASSIGNED
                        if assigned_team_id
                        else Ticket.Status.OPEN
                    ),
                    estimated_duration_hours=Decimal(str(duration_estimate)),
                    cost_estimate_inr=Decimal(str(cost_estimate)),
                )

                AuditLog.objects.create(
                    event_type=AuditLog.EventType.CREATE,
                    entity_type="ticket",
                    entity_id=ticket.pk,
                    actor_type=AuditLog.ActorType.ML_PIPELINE,
                    actor_identifier=f"ticket_service/{response.provider_name}",
                    description=(
                        f"Auto-ticket: {fault_type} "
                        f"priority={priority} "
                        f"provider={response.provider_name}"
                    ),
                )

            logger.info(
                f"TicketService: Created ticket {ticket.ticket_code} "
                f"(priority={priority}, team={assigned_team_id})"
            )
            return ticket.pk

        except Exception as e:
            logger.error(
                f"TicketService: Failed to create ticket: {e}",
                exc_info=True,
            )
            return None

    def _find_available_team(self, track_section_id: int) -> Optional[int]:
        """
        Find the nearest available maintenance team.

        Strategy:
            1. Find teams in the same division as the track section
            2. Pick the team with fewest open tickets
            3. Fallback to any active team if none in division

        # ---------------------------------------------------------------
        # DATABASE MIGRATION NOTE
        #
        # Reads from: rakshak_track_section, rakshak_maintenance_team,
        #             rakshak_ticket
        # Uses: select_related(), filter(), count()
        #
        # Current DB: PostgreSQL
        # Future DB: None
        # PostgreSQL compatible: YES
        #   - All queries use standard Django ORM
        #   - select_related() generates JOIN which works in both DBs
        #   - Count aggregation is standard SQL
        # Teammate action: NONE
        # ---------------------------------------------------------------
        """
        try:
            from railway.models import MaintenanceTeam, TrackSection, Ticket

            section = TrackSection.objects.select_related(
                "start_station__division"
            ).get(pk=track_section_id)

            division = (
                section.start_station.division
                if section.start_station
                else None
            )
            if not division:
                return None

            # Find teams in the division
            teams = MaintenanceTeam.objects.filter(
                division=division,
                is_active=True,
            )

            if not teams.exists():
                # Fallback: any active team
                teams = MaintenanceTeam.objects.filter(is_active=True)

            if not teams.exists():
                return None

            # Pick the team with fewest open tickets
            best_team = None
            min_tickets = float("inf")

            for team in teams:
                open_count = Ticket.objects.filter(
                    assigned_team=team,
                    status__in=[
                        Ticket.Status.OPEN,
                        Ticket.Status.ASSIGNED,
                        Ticket.Status.IN_PROGRESS,
                    ],
                ).count()

                if open_count < min_tickets:
                    min_tickets = open_count
                    best_team = team

            return best_team.pk if best_team else None

        except Exception as e:
            logger.warning(f"TicketService: Team lookup failed: {e}")
            return None
