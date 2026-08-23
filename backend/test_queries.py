import os


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "rakshak_project.settings")

    import django
    from django.db.models import Count, Q

    django.setup()

    from railway.models import Station, Ticket

    print("Testing Station query...")
    stations = (
        Station.objects
        .filter(is_active=True)
        .select_related("division__zone")
        .annotate(
            active_alerts_start=Count(
                "track_sections_starting__alerts",
                filter=Q(track_sections_starting__alerts__status="active"),
                distinct=True,
            ),
            active_alerts_end=Count(
                "track_sections_ending__alerts",
                filter=Q(track_sections_ending__alerts__status="active"),
                distinct=True,
            ),
            tracks_start=Count("track_sections_starting", distinct=True),
            tracks_end=Count("track_sections_ending", distinct=True),
        )
        .order_by("station_name")
    )

    try:
        station_list = list(stations)
        if station_list:
            station = station_list[0]
            print(f"Station: {station.station_name}")
            print(f"active_alerts_start: {station.active_alerts_start}")
            print(f"active_alerts_end: {station.active_alerts_end}")
            print(f"tracks_start: {station.tracks_start}")
            print(f"tracks_end: {station.tracks_end}")
    except Exception as exc:
        print("Error in station query:", exc)

    print("Testing Ticket query...")
    tickets = (
        Ticket.objects
        .exclude(status="closed")
        .select_related(
            "track_section__start_station__division__zone",
            "track_section__end_station",
            "assigned_team",
        )
        .order_by("-created_at")[:200]
    )

    try:
        ticket_list = list(tickets)
        if ticket_list:
            print("Ticket fetched successfully.")
    except Exception as exc:
        print("Error in ticket query:", exc)


if __name__ == "__main__":
    main()
