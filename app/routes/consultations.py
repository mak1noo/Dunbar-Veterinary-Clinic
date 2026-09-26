"""Booking in-clinic consultations.

Story MSD426GXUST3-46: one animal, one 15-minute slot, one of the two
consulting rooms, on the clinic's consulting timetable. Story MSD426GXUST3-47
adds the timetable rules around it: nothing in the past, and the form shows
which rooms are still free for each slot. The rules themselves live in
``app.services.scheduling``; this module is the HTTP layer that turns the
reception desk's form into an ``Appointment``.
"""
from datetime import date, datetime

from flask import Blueprint, abort, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from app.models import CONSULTATION, STATUS_BOOKED, Animal, Appointment, db
from app.services.scheduling import (
    CONSULTING_ROOMS,
    free_rooms_by_slot,
    slots_for_day,
    validate_consultation,
)

consultations_bp = Blueprint("consultations", __name__, url_prefix="/consultations")

DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M"


def _slot_label(value):
    """Format a slot the way the appointment book writes it: 8:30 am."""
    hour = value.hour % 12 or 12
    suffix = "am" if value.hour < 12 else "pm"
    return f"{hour}:{value.minute:02d} {suffix}"


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


def _animal_groups():
    """Active animals grouped under their owner, for the form's select."""
    animals = Animal.query.filter_by(active=True).all()
    animals.sort(key=lambda animal: (animal.client.name.lower(), animal.name.lower()))
    groups = []
    for animal in animals:
        if not groups or groups[-1][0] != animal.client.name:
            groups.append((animal.client.name, []))
        groups[-1][1].append(animal)
    return groups


def _booked_consultations(day):
    """Live consultations on ``day``, used for the double-booking check."""
    return Appointment.query.filter_by(
        kind=CONSULTATION, date=day, status=STATUS_BOOKED
    ).all()


def _availability_label(free_rooms):
    """Short hint for one slot, the way the front desk would say it."""
    if not free_rooms:
        return "fully booked"
    if len(free_rooms) == 1:
        return f"only room {free_rooms[0]} free"
    return "both rooms free"


def _form_context(day, chosen):
    free_rooms = free_rooms_by_slot(day, _booked_consultations(day))
    slots = []
    for slot in slots_for_day(day):
        rooms_free = free_rooms.get(slot, list(CONSULTING_ROOMS))
        slots.append(
            {
                "value": slot.strftime(TIME_FORMAT),
                "label": _slot_label(slot),
                "free_rooms": len(rooms_free),
                "availability": _availability_label(rooms_free),
            }
        )
    return {
        "day": day,
        "slots": slots,
        "rooms": CONSULTING_ROOMS,
        "animal_groups": _animal_groups(),
        "chosen": chosen,
        "problems": [],
    }


def _problems(day, start, animal, room):
    if start is None:
        return ["Choose a time from the day's 15-minute slots."]
    return validate_consultation(
        day=day,
        start=start,
        animal=animal,
        room=room,
        existing_bookings=_booked_consultations(day),
        today=date.today(),
        now=datetime.now().time(),
    )


@consultations_bp.get("/new")
def new_consultation():
    """Show the booking form for one consulting day (today by default)."""
    day = _parse_date(request.args.get("date"), date.today())
    return render_template("consultations/new.html", **_form_context(day, {}))


@consultations_bp.post("/new")
def create_consultation():
    """Create the consultation, or send the form back with the problems."""
    day = _parse_date(request.form.get("date"), date.today())
    start = _parse_time(request.form.get("start_time"))
    animal = db.session.get(Animal, _parse_int(request.form.get("animal_id")) or 0)
    room = _parse_int(request.form.get("room"))
    chosen = {
        "animal_id": request.form.get("animal_id", ""),
        "start_time": request.form.get("start_time", ""),
        "room": request.form.get("room", ""),
        "reason": request.form.get("reason", ""),
    }

    problems = _problems(day, start, animal, room)
    if problems:
        context = _form_context(day, chosen)
        context["problems"] = problems
        return render_template("consultations/new.html", **context)

    appointment = Appointment(
        kind=CONSULTATION,
        status=STATUS_BOOKED,
        client=animal.client,
        animal=animal,
        date=day,
        start_time=start,
        room=room,
        reason=chosen["reason"].strip() or None,
    )
    db.session.add(appointment)
    try:
        db.session.commit()
    except IntegrityError:
        # The other reception desk booked the same room and slot a moment ago.
        db.session.rollback()
        context = _form_context(day, chosen)
        context["problems"] = [
            "That consulting room was booked a moment ago. Pick another slot."
        ]
        return render_template("consultations/new.html", **context)

    return redirect(
        url_for("consultations.show_consultation", appointment_id=appointment.id),
        code=303,
    )


@consultations_bp.get("/<int:appointment_id>")
def show_consultation(appointment_id):
    """Confirmation page for one consultation."""
    appointment = db.session.get(Appointment, appointment_id)
    if appointment is None or appointment.kind != CONSULTATION:
        abort(404)
    return render_template("consultations/show.html", appointment=appointment)
