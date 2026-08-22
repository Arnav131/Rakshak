"""
Rakshak Agent System — Maintenance Dispatch Agent
====================================================
Automatically creates maintenance tickets and assigns teams
based on anomaly severity and team availability.
"""

import logging
from decimal import Decimal
from typing import Any, Dict, Optional

from django.db import transaction
from django.utils import timezone

from agents.shared.base_agent import BaseAgent
from agents.shared.events import MaintenanceDispatchEvent

logger = logging.getLogger("rakshak.agents.dispatch")


class MaintenanceDispatchAgent(BaseAgent):
    """
    Automated maintenance ticket creation and team dispatch.

    Responsibilities:
    - Creates Ticket from confirmed anomaly alerts
    - Assigns nearest available MaintenanceTeam
    - Sets priority based on fault urgency + anomaly score
    - Estimates cost and duration from fault type

    From agents_README:
        Autonomy: Semi-auto (L1) / Full-auto (L2)
        Target: Ticket auto-generation < 60s from confirmed event
    """

    AGENT_NAME = "maintenance_dispatch"
    AGENT_VERSION = "1.0.0"

    # Urgency → ticket priority mapping
    URGENCY_TO_PRIORITY = {
        "critical": "critical",
        "high": "high",
        "medium": "medium",
        "low": "low",
        "none": "low",
    }

    # Fault type → estimated cost (INR)
    COST_ESTIMATES = {
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
    }

    def __init__(self, config: Optional[Dict] = None):
        super().__init__(config)
        self._ticket_counter = 0

    def _generate_ticket_code(self) -> str:
        self._ticket_counter += 1
        now = timezone.now()
        return f"TKT-{now.strftime('%Y%m%d')}-{self._ticket_counter:04d}"

    def process(self, data: Any) -> Dict:
        """
        Create a maintenance ticket from a root cause analysis.

        Args:
            data: Dict from RootCauseAgent with fault_type, urgency,
                  track_section_id, alert_id, estimated_repair_hours

        Returns:
            Dict with ticket_id, assigned_team, priority
        """
        fault_type = data.get("fault_type", "unknown")
        urgency = data.get("urgency", "medium")
        track_section_id = data.get("track_section_id")
        alert_id = data.get("alert_id")
        estimated_hours = data.get("estimated_repair_hours", 8.0)
        explanation = data.get("explanation", "")
        recommended_action = data.get("recommended_action", "")

        if not track_section_id:
            return {"success": False, "error": "No track_section_id provided"}

        priority = self.URGENCY_TO_PRIORITY.get(urgency, "medium")
        cost_estimate = self.COST_ESTIMATES.get(fault_type, 100000)

        # Find available team
        assigned_team_id = self._find_available_team(track_section_id, priority)

        # Create ticket
        from railway.models import Ticket

        with transaction.atomic():
            ticket = Ticket.objects.create(
                ticket_code=self._generate_ticket_code(),
                alert_id=alert_id,
                track_section_id=track_section_id,
                assigned_team_id=assigned_team_id,
                title=f"{fault_type.replace('_', ' ').title()} — {urgency.upper()} Priority",
                description=(
                    f"Auto-generated maintenance ticket.\n\n"
                    f"Fault Type: {fault_type}\n"
                    f"Urgency: {urgency}\n"
                    f"Estimated Duration: {estimated_hours} hours\n\n"
                    f"Root Cause Analysis:\n{explanation}\n\n"
                    f"Recommended Action:\n{recommended_action}"
                ),
                priority=priority,
                status=Ticket.Status.ASSIGNED if assigned_team_id else Ticket.Status.OPEN,
                estimated_duration_hours=Decimal(str(estimated_hours)),
                cost_estimate_inr=Decimal(str(cost_estimate)),
            )

        self.log_event("create", "ticket", ticket.pk, f"Auto-dispatch: {fault_type}")

        logger.info(
            f"[{self.AGENT_NAME}] Created ticket {ticket.ticket_code} "
            f"(priority={priority}, team={assigned_team_id})"
        )

        # Emit event
        event = MaintenanceDispatchEvent(
            ticket_id=ticket.pk,
            alert_id=alert_id or 0,
            track_section_id=track_section_id,
            assigned_team_id=assigned_team_id,
            priority=priority,
        )

        return {
            "success": True,
            "ticket_id": ticket.pk,
            "ticket_code": ticket.ticket_code,
            "priority": priority,
            "assigned_team_id": assigned_team_id,
            "cost_estimate_inr": cost_estimate,
            "event": event,
        }

    def _find_available_team(self, track_section_id: int, priority: str) -> Optional[int]:
        """
        Find the nearest available maintenance team.

        Simple strategy for Phase 1:
        - Find teams in the same division as the track section
        - Prefer teams with fewer open tickets
        - Return the best match or None
        """
        try:
            from railway.models import MaintenanceTeam, TrackSection, Ticket

            section = TrackSection.objects.select_related(
                "start_station__division"
            ).get(pk=track_section_id)

            division = section.start_station.division if section.start_station else None
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
                    status__in=[Ticket.Status.OPEN, Ticket.Status.ASSIGNED, Ticket.Status.IN_PROGRESS],
                ).count()

                if open_count < min_tickets:
                    min_tickets = open_count
                    best_team = team

            return best_team.pk if best_team else None

        except Exception as e:
            logger.warning(f"[{self.AGENT_NAME}] Team lookup failed: {e}")
            return None
