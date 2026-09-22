"""Consulting timetable rules and booking validation helpers.

Rules taken from the case study and the photocopied appointment book page
(Document A):

* Monday, Wednesday, Friday: consulting 8:30am - 5:30pm, last booking 5:15pm.
* Tuesday, Thursday: consults only until 10:30am (no consults after 10:15am),
  the vets are on the road from 10:30am.
* Saturday: short consulting morning, 8:00am - 11:00am.
* Sunday: closed.
* A consultation is one 15-minute slot and occupies one consulting room.
* A farm visit is booked against a property and has a start time plus an
  estimated duration in hours; it never occupies a consulting slot.
"""
from datetime import date, datetime, time, timedelta

SLOT_MINUTES = 15
CONSULTING_ROOMS = (1, 2)

# date.weekday() -> (first bookable slot, last bookable slot); None = closed
CONSULTING_WINDOWS = {
    0: (time(8, 30), time(17, 15)),  # Monday
    1: (time(8, 30), time(10, 15)),  # Tuesday
    2: (time(8, 30), time(17, 15)),  # Wednesday
    3: (time(8, 30), time(10, 15)),  # Thursday
    4: (time(8, 30), time(17, 15)),  # Friday
    5: (time(8, 0), time(10, 45)),   # Saturday
    6: None,                          # Sunday
}

FARM_VISIT_STEP_HOURS = 0.5


def is_consulting_day(day):
    """Return True when the clinic takes consultations on ``day``."""
    return CONSULTING_WINDOWS.get(day.weekday()) is not None


def slots_for_day(day):
    """Return every bookable consultation start time for ``day``."""
    window = CONSULTING_WINDOWS.get(day.weekday())
    if window is None:
        return []
    first, last = window
    slots = []
    cursor = first
    while cursor <= last:
        slots.append(cursor)
        cursor = (datetime.combine(date.min, cursor) + timedelta(minutes=SLOT_MINUTES)).time()
    return slots


def slot_is_on_grid(day, start):
    """Return True when ``start`` is a consulting slot on ``day``."""
    return start in slots_for_day(day)


def validate_consultation(*, day, start, animal, room, existing_bookings=(), today=None, now=None):
    """Return the problems with a proposed consultation.

    An empty list means the booking is valid. ``existing_bookings`` is any
    iterable of appointment-like objects with ``status``, ``room`` and
    ``start_time`` attributes (used for the double-booking check).

    ``today`` (a date) and ``now`` (a time) are optional so the caller stays in
    charge of the clock: pass them to keep the booking out of the past.
    """
    problems = []
    if today is not None:
        if day < today:
            problems.append("That day is in the past. Pick a later day.")
        elif day == today and now is not None and start < now:
            problems.append("That time has already passed today.")
    if not is_consulting_day(day):
        problems.append("The clinic does not take consultations on this day.")
    elif not slot_is_on_grid(day, start):
        problems.append("That time is not a 15-minute slot on the consulting timetable.")
    if animal is None:
        problems.append("A consultation must be booked for one animal.")
    if room not in CONSULTING_ROOMS:
        problems.append("A consultation must be booked into consulting room 1 or 2.")
    if any(
        booking.status == "booked" and booking.room == room and booking.start_time == start
        for booking in existing_bookings
    ):
        problems.append("That consulting room is already booked for that slot.")
    return problems


def validate_farm_visit(*, day, start, farm_property, estimated_hours, today=None):
    """Return the problems with a proposed farm visit (empty list = valid).

    ``today`` is optional, like in :func:`validate_consultation`, so the rules
    can be reused by the booking form, the reschedule form and the tests.
    """
    problems = []
    if today is not None and day is not None and day < today:
        problems.append("That day is in the past. Pick a later day.")
    if farm_property is None:
        problems.append("A farm visit must be booked against a property.")
    if estimated_hours is None:
        problems.append("A farm visit needs an estimated duration in hours.")
    else:
        try:
            hours = float(estimated_hours)
        except (TypeError, ValueError):
            problems.append("The estimated duration must be a number of hours.")
        else:
            if hours <= 0:
                problems.append("The estimated duration must be greater than zero.")
            elif abs(hours / FARM_VISIT_STEP_HOURS - round(hours / FARM_VISIT_STEP_HOURS)) > 1e-9:
                    problems.append("The estimated duration must be in half-hour steps.")
    return problems


def free_rooms_by_slot(day, existing_bookings, rooms=CONSULTING_ROOMS):
    """Return the consulting rooms that are still free for every slot of ``day``.

    ``existing_bookings`` holds appointment-like objects with ``status``,
    ``room`` and ``start_time`` attributes. Cancelled bookings do not block a
    room, matching the rule used when a consultation is booked.
    """
    taken = {}
    for booking in existing_bookings:
        if booking.status == "booked" and booking.room in rooms:
            taken.setdefault(booking.start_time, set()).add(booking.room)
    return {
        slot: [room for room in rooms if room not in taken.get(slot, set())]
        for slot in slots_for_day(day)
    }
