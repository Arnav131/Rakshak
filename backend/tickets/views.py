# backend/tickets/views.py
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.timesince import timesince

from railway.models import Ticket


def _ticket_queryset():
    return Ticket.objects.select_related(
        "alert",
        "track_section__start_station__division__zone",
        "track_section__end_station",
        "assigned_team",
    )


def _choice_values(choices):
    return [value for value, _label in choices]


def _display_label(value):
    return value.replace("_", " ").title() if value else ""


def _format_duration(hours):
    if not hours:
        return "TBD"
    hours_float = float(hours)
    if hours_float.is_integer():
        return f"{int(hours_float)}h"
    return f"{hours_float:.1f}h"


def _ticket_has_missing_data(ticket):
    return ticket.assigned_team_id is None or ticket.estimated_duration_hours is None


def _serialize_ticket(ticket):
    track = ticket.track_section
    start = track.start_station
    end = track.end_station
    team = ticket.assigned_team.team_name if ticket.assigned_team else "Unassigned"
    created_at = ticket.created_at or timezone.now()
    age = timesince(created_at, timezone.now()).split(",")[0]
    has_missing_data = _ticket_has_missing_data(ticket)

    return {
        "id": ticket.ticket_code,
        "linked_alert": ticket.alert.alert_code if ticket.alert else "Manual",
        "track_id": track.section_code,
        "section": f"{start.station_name} - {end.station_name}",
        "station": start.station_name,
        "zone": start.division.zone.name,
        "zone_code": start.division.zone.code,
        "issue": ticket.title,
        "description": ticket.description,
        "team": team,
        "team_raw": team,
        "priority": ticket.priority,
        "priority_label": _display_label(ticket.priority),
        "status": ticket.status,
        "status_label": _display_label(ticket.status),
        "eta": _format_duration(ticket.estimated_duration_hours),
        "scheduled_for": (
            ticket.scheduled_for.strftime("%Y-%m-%d %H:%M")
            if ticket.scheduled_for
            else "Not scheduled"
        ),
        "time_ago": f"{age} ago",
        "has_missing_data": has_missing_data,
        "is_ready_for_ai": not has_missing_data,
        "issue_raw": ticket.title,
        "section_raw": track.section_code,
    }


def _filter_options(qs):
    return {
        "sections": list(
            qs.order_by("track_section__section_code")
            .values_list("track_section__section_code", flat=True)
            .distinct()
        ),
        "statuses": _choice_values(Ticket.Status.choices),
        "teams": list(
            qs.exclude(assigned_team__isnull=True)
            .order_by("assigned_team__team_name")
            .values_list("assigned_team__team_name", flat=True)
            .distinct()
        ),
    }


def _apply_ticket_filters(qs, params):
    search = params.get("search", "").strip()
    section = params.get("section", "").strip()
    status = params.get("status", "").strip()
    team = params.get("team", "").strip()
    missing_data = params.get("missing_data", "").strip().lower()

    valid_statuses = set(_choice_values(Ticket.Status.choices))
    if status and status not in valid_statuses:
        return None, f"Invalid status: {status}"

    if missing_data and missing_data not in {"true", "false"}:
        return None, f"Invalid missing_data value: {missing_data}"

    if search:
        qs = qs.filter(
            Q(ticket_code__icontains=search)
            | Q(title__icontains=search)
            | Q(description__icontains=search)
            | Q(alert__alert_code__icontains=search)
            | Q(track_section__section_code__icontains=search)
            | Q(track_section__start_station__station_name__icontains=search)
            | Q(track_section__end_station__station_name__icontains=search)
            | Q(assigned_team__team_name__icontains=search)
        )
    if section:
        qs = qs.filter(track_section__section_code=section)
    if status:
        qs = qs.filter(status=status)
    if team:
        qs = qs.filter(assigned_team__team_name=team)

    missing_q = Q(assigned_team__isnull=True) | Q(estimated_duration_hours__isnull=True)
    if missing_data == "true":
        qs = qs.filter(missing_q)
    elif missing_data == "false":
        qs = qs.exclude(missing_q)

    return qs, None


@login_required
def tickets_page(request):
    status_filter = request.GET.get("status", "all")
    base_qs = _ticket_queryset()

    summary = {
        "total": base_qs.count(),
        "open": base_qs.filter(status=Ticket.Status.OPEN).count(),
        "assigned": base_qs.filter(status=Ticket.Status.ASSIGNED).count(),
        "in_progress": base_qs.filter(status=Ticket.Status.IN_PROGRESS).count(),
        "scheduled": base_qs.filter(status=Ticket.Status.SCHEDULED).count(),
        "resolved": base_qs.filter(status=Ticket.Status.RESOLVED).count(),
        "critical_priority": base_qs.filter(priority=Ticket.Priority.CRITICAL).count(),
    }

    display_qs = base_qs
    if status_filter != "all":
        display_qs = display_qs.filter(status=status_filter)

    filters = _filter_options(base_qs)
    display_total = display_qs.count()
    visible_tickets = list(display_qs[:80])
    context = {
        "page_title": "Maintenance Tickets",
        "tickets": [_serialize_ticket(ticket) for ticket in visible_tickets],
        "summary": summary,
        "current_filter": status_filter,
        "display_total": display_total,
        "filter_sections": filters["sections"],
        "filter_statuses": filters["statuses"],
        "filter_teams": filters["teams"],
    }
    return render(request, "tickets.html", context)


@login_required
def tickets_search(request):
    base_qs = _ticket_queryset()
    filtered_qs, error = _apply_ticket_filters(base_qs, request.GET)
    if error:
        return JsonResponse({"error": error}, status=400)

    total = filtered_qs.count()
    tickets = [_serialize_ticket(ticket) for ticket in filtered_qs[:80]]
    return JsonResponse(
        {
            "tickets": tickets,
            "total": total,
            "shown": len(tickets),
            "filters": _filter_options(base_qs),
        }
    )
