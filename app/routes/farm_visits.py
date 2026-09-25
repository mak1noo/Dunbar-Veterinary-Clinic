"""Booking a farm visit.

Story MSD426GXUST3-48: a farm visit is booked against a property, with a start
time and an estimated duration in hours. It is not a slot and it is not booked
for an animal (case study section 4), so it gets its own form rather than
being squeezed into the consulting timetable. The rules live in
``app.services.scheduling``; this module is the HTTP layer that turns the green
diary page into an ``Appointment``.
"""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, abort, redirect, render_template, request, url_for

from app.models import FARM_VISIT, STATUS_BOOKED, Appointment, Property, db
from app.services.scheduling import validate_farm_visit

farm_visits_bp = Blueprint("farm_visits", __name__, url_prefix="/farm-visits")

DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M"
HALF_HOUR = Decimal("0.5")
MAX_ESTIMATED_HOURS = Decimal("8.0")


def _parse_date(raw, fallback):
    try:
        return datetime.strptime(raw, DATE_FORMAT).date()
    except (TypeError, ValueError):
        return fallback


def _parse_time(raw):
    try:
        return datetime.strptime(raw, TIME_FORMAT).time()
    except (TypeError, ValueError):
        return None


def _parse_int(raw):
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _parse_hours(raw):
    try:
        return Decimal(str(raw).strip())
    except (InvalidOperation, TypeError, ValueError, AttributeError):
        return None


def _hours_label(value):
    """Write a duration the way the diary writes it: 1 hour, 1.5 hours."""
    if value == 1:
        return "1 hour"
    if value == value.to_integral_value():
        return f"{int(value)} hours"
    return f"{value} hours"


def _hour_choices():
    """Half-hour steps from 30 minutes up to a working day of visits."""
    steps = int(MAX_ESTIMATED_HOURS / HALF_HOUR)
    return [
        {"value": str(HALF_HOUR * (step + 1)), "label": _hours_label(HALF_HOUR * (step + 1))}
        for step in range(steps)
    ]


def _property_groups():
    """Active farm properties grouped under their client, for the form."""
    properties = Property.query.filter_by(active=True).all()
    properties.sort(key=lambda record: (record.client.name.lower(), record.name.lower()))
    groups = []
    for record in properties:
        if not groups or groups[-1][0] != record.client.name:
            groups.append((record.client.name, []))
        groups[-1][1].append(record)
    return groups


def _form_context(day, chosen):
    return {
        "day": day,
        "hour_choices": _hour_choices(),
        "property_groups": _property_groups(),
        "chosen": chosen,
        "problems": [],
    }


def _problems(day, start, farm_property, hours):
    """What is wrong with a proposed farm visit, in the order to fix it."""
    problems = []
    if start is None:
        problems.append("Enter the time the vet leaves for the property, for example 11:15.")
    problems.extend(
        validate_farm_visit(
            day=day,
            start=start,
            farm_property=farm_property,
            estimated_hours=hours,
            today=date.today(),
        )
    )
    return problems


@farm_visits_bp.get("/new")
def new_farm_visit():
    """Show the farm visit form for one day (today by default)."""
    day = _parse_date(request.args.get("date"), date.today())
    return render_template("farm_visits/new.html", **_form_context(day, {}))


@farm_visits_bp.post("/new")
def create_farm_visit():
    """Create the farm visit, or hand the form back with the problems."""
    day = _parse_date(request.form.get("date"), date.today())
    start = _parse_time(request.form.get("start_time"))
    farm_property = db.session.get(Property, _parse_int(request.form.get("property_id")) or 0)
    hours = _parse_hours(request.form.get("estimated_hours"))
    chosen = {
        "property_id": request.form.get("property_id", ""),
        "start_time": request.form.get("start_time", ""),
        "estimated_hours": request.form.get("estimated_hours", ""),
        "reason": request.form.get("reason", ""),
    }

    problems = _problems(day, start, farm_property, hours)
    if problems:
        context = _form_context(day, chosen)
        context["problems"] = problems
        return render_template("farm_visits/new.html", **context)

    appointment = Appointment(
        kind=FARM_VISIT,
        status=STATUS_BOOKED,
        client=farm_property.client,
        farm_property=farm_property,
        date=day,
        start_time=start,
        estimated_hours=hours,
        reason=chosen["reason"].strip() or None,
    )
    db.session.add(appointment)
    db.session.commit()

    return redirect(
        url_for("farm_visits.show_farm_visit", appointment_id=appointment.id),
        code=303,
    )


@farm_visits_bp.get("/<int:appointment_id>")
def show_farm_visit(appointment_id):
    """Confirmation page for one farm visit."""
    appointment = db.session.get(Appointment, appointment_id)
    if appointment is None or appointment.kind != FARM_VISIT:
        abort(404)
    return render_template(
        "farm_visits/show.html",
        appointment=appointment,
        hours_label=_hours_label(appointment.estimated_hours),
    )
