"""Story MSD426GXUST3-47: timetable rules around a booking.

The service layer stays in charge of the rules (``app.services.scheduling``);
this file covers the clock rules and the availability helper that lets the
booking form grey out slots that cannot take another consultation.
"""
from datetime import date, time, timedelta
from types import SimpleNamespace

import pytest

from app.models import CONSULTATION, STATUS_BOOKED, Animal, Appointment, Client, db
from app.services.scheduling import (
    free_rooms_by_slot,
    slots_for_day,
    validate_consultation,
    validate_farm_visit,
)

MONDAY = date(2026, 9, 21)
TUESDAY = date(2026, 9, 22)


def _next_weekday(weekday, earliest_offset=2):
    candidate = date.today() + timedelta(days=earliest_offset)
    return candidate + timedelta(days=(weekday - candidate.weekday()) % 7)


@pytest.fixture
def biscuit(app):
    """Mrs Prosser's cat, straight from the case study appointment book."""
    with app.app_context():
        owner = Client(name="Mrs Prosser", phone="0417 552 118")
        animal = Animal(name="Biscuit", species="Cat", client=owner)
        db.session.add(animal)
        db.session.commit()
        return animal.id


def test_a_date_in_the_past_is_rejected():
    problems = validate_consultation(
        day=MONDAY, start=time(9, 0), animal=object(), room=1, today=TUESDAY
    )
    assert "That day is in the past. Pick a later day." in problems


def test_a_time_that_has_already_passed_today_is_rejected():
    problems = validate_consultation(
        day=TUESDAY,
        start=time(9, 0),
        animal=object(),
        room=1,
        today=TUESDAY,
        now=time(10, 0),
    )
    assert "That time has already passed today." in problems


def test_a_later_time_today_is_still_allowed():
    problems = validate_consultation(
        day=TUESDAY,
        start=time(10, 15),
        animal=object(),
        room=1,
        today=TUESDAY,
        now=time(10, 0),
    )
    assert problems == []


def test_without_a_clock_the_rules_are_unchanged():
    problems = validate_consultation(day=MONDAY, start=time(9, 0), animal=object(), room=1)
    assert problems == []


def test_a_farm_visit_in_the_past_is_rejected():
    problems = validate_farm_visit(
        day=MONDAY, start=time(11, 15), farm_property=object(), estimated_hours=2, today=TUESDAY
    )
    assert "That day is in the past. Pick a later day." in problems


def test_free_rooms_by_slot_ignores_cancelled_bookings():
    bookings = [
        SimpleNamespace(status="booked", room=1, start_time=time(8, 30)),
        SimpleNamespace(status="cancelled", room=2, start_time=time(8, 30)),
    ]
    availability = free_rooms_by_slot(MONDAY, bookings)
    assert availability[time(8, 30)] == [2]
    assert availability[time(8, 45)] == [1, 2]
    assert len(availability) == len(slots_for_day(MONDAY))


def test_free_rooms_by_slot_marks_a_fully_booked_slot():
    bookings = [
        SimpleNamespace(status="booked", room=1, start_time=time(9, 0)),
        SimpleNamespace(status="booked", room=2, start_time=time(9, 0)),
    ]
    availability = free_rooms_by_slot(MONDAY, bookings)
    assert availability[time(9, 0)] == []


def test_the_form_disables_slots_where_both_rooms_are_taken(app, client, biscuit):
    day = _next_weekday(0)
    with app.app_context():
        animal = db.session.get(Animal, biscuit)
        for start, room in ((time(8, 30), 1), (time(9, 0), 1), (time(9, 0), 2)):
            db.session.add(
                Appointment(
                    kind=CONSULTATION,
                    status=STATUS_BOOKED,
                    client=animal.client,
                    animal=animal,
                    date=day,
                    start_time=start,
                    room=room,
                )
            )
        db.session.commit()

    page = client.get(f"/consultations/new?date={day.isoformat()}").get_data(as_text=True)
    assert "9:00 am — fully booked" in page
    assert 'value="09:00" disabled' in page
    assert "8:45 am — both rooms free" in page
    assert "8:30 am — only room 2 free" in page


def test_posting_a_past_date_is_rejected(app, client, biscuit):
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    response = client.post(
        "/consultations/new",
        data={
            "animal_id": str(biscuit),
            "date": yesterday,
            "start_time": "09:00",
            "room": "1",
            "reason": "",
        },
    )
    assert "in the past" in response.get_data(as_text=True)
    with app.app_context():
        assert Appointment.query.count() == 0
