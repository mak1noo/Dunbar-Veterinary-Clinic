"""The day view for the consulting rooms (story MSD426GXUST3-50).

The clinic works from one appointment book, so reception needs to see the day
the way the book shows it: every fifteen-minute slot and both consulting
rooms, with each cell taken or free. The layout itself is built by
``app.services.scheduling.day_schedule``; this module is the HTTP layer that
picks the day and renders it.
"""
from datetime import date, timedelta

from flask import Blueprint, render_template, request

from app.services.scheduling import day_schedule

schedule_bp = Blueprint("schedule", __name__, url_prefix="/schedule")


def _parse_date(raw):
    """Return ``(day, error)`` for a raw ``YYYY-MM-DD`` query value."""
    if not raw:
        return date.today(), None
    try:
        return date.fromisoformat(raw), None
    except ValueError:
        return date.today(), "Date must be in YYYY-MM-DD format. Showing today instead."


@schedule_bp.get("/")
def day_view():
    """Show one consulting day as a grid of taken and free cells."""
    selected_date, date_error = _parse_date(request.args.get("date"))
    return render_template(
        "schedule/day.html",
        selected_date=selected_date,
        grid=day_schedule(selected_date),
        previous_date=selected_date - timedelta(days=1),
        next_date=selected_date + timedelta(days=1),
        date_error=date_error,
    )
