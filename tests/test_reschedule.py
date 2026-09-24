"""Tests for rescheduling appointments (MSD426GXUST3-53)."""
from datetime import date, time
from decimal import Decimal

from app.models import (
    CONSULTATION,
    FARM_VISIT,
    STATUS_BOOKED,
    STATUS_CANCELLED,
    Animal,
    Appointment,
    Client,
    Property,
    db,
)
from app.services.scheduling import reschedule_appointment


MONDAY = date(2026, 9, 21)
TUESDAY = date(2026, 9, 22)


def _booking_set():
    owner = Client(name="Bridie Callaghan", phone="0417 884 260")
    animal = Animal(client=owner, name="Moss", species="Dog")
    farm_property = Property(client=owner, name="Stony Creek", locality="Bunjurgen")
    first = Appointment(
        kind=CONSULTATION,
        status=STATUS_BOOKED,
        client=owner,
        animal=animal,
        date=MONDAY,
        start_time=time(8, 30),
        room=1,
        reason="Vaccination",
    )
    second = Appointment(
        kind=CONSULTATION,
        status=STATUS_BOOKED,
        client=owner,
        animal=animal,
        date=MONDAY,
        start_time=time(9, 0),
        room=2,
        reason="Recheck",
    )
    farm_visit = Appointment(
        kind=FARM_VISIT,
        status=STATUS_BOOKED,
        client=owner,
        farm_property=farm_property,
        date=TUESDAY,
        start_time=time(11, 15),
        estimated_hours=Decimal("1.5"),
        reason="Herd check",
    )
    db.session.add(owner)
    db.session.add_all([first, second, farm_visit])
    db.session.commit()
    return first, second, farm_visit


def test_consultation_reschedule_moves_only_the_selected_appointment(app):
    with app.app_context():
        first, second, _ = _booking_set()
        problems = reschedule_appointment(
            first,
            day=TUESDAY,
            start=time(10, 0),
            room=1,
        )
        assert problems == []
        db.session.commit()

        assert first.date == TUESDAY
        assert first.start_time == time(10, 0)
        assert second.date == MONDAY
        assert second.start_time == time(9, 0)


def test_consultation_reschedule_uses_new_booking_validation(app):
    with app.app_context():
        first, _, _ = _booking_set()
        problems = reschedule_appointment(
            first,
            day=MONDAY,
            start=time(9, 7),
            room=1,
        )

        assert "That time is not a 15-minute slot on the consulting timetable." in problems
        assert first.date == MONDAY
        assert first.start_time == time(8, 30)


def test_consultation_reschedule_rejects_double_booking(app):
    with app.app_context():
        first, _, _ = _booking_set()
        problems = reschedule_appointment(
            first,
            day=MONDAY,
            start=time(9, 0),
            room=2,
        )

        assert "That consulting room is already booked for that slot." in problems
        assert first.start_time == time(8, 30)
        assert first.room == 1


def test_farm_visit_moves_independently_of_consultations(app):
    with app.app_context():
        first, _, farm_visit = _booking_set()
        problems = reschedule_appointment(
            farm_visit,
            day=MONDAY,
            start=time(14, 45),
            estimated_hours=Decimal("2.0"),
        )
        assert problems == []
        db.session.commit()

        assert farm_visit.date == MONDAY
        assert farm_visit.start_time == time(14, 45)
        assert farm_visit.estimated_hours == Decimal("2.00")
        assert first.date == MONDAY
        assert first.start_time == time(8, 30)


def test_reschedule_page_renders_current_appointment(app, client):
    with app.app_context():
        first, _, _ = _booking_set()
        appointment_id = first.id

    response = client.get(f"/appointments/{appointment_id}/reschedule")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Reschedule appointment" in html
    assert "2026-09-21" in html
    assert "08:30" in html
    assert "Room 1" in html


def test_reschedule_post_updates_and_redirects(app, client):
    with app.app_context():
        first, _, _ = _booking_set()
        appointment_id = first.id

    response = client.post(
        f"/appointments/{appointment_id}/reschedule",
        data={"date": "2026-09-22", "time": "10:00", "room": "1"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("updated=1")
    with app.app_context():
        moved = db.session.get(Appointment, appointment_id)
        assert moved.date == TUESDAY
        assert moved.start_time == time(10, 0)


def test_reschedule_post_shows_validation_errors_without_moving(app, client):
    with app.app_context():
        first, _, _ = _booking_set()
        appointment_id = first.id

    response = client.post(
        f"/appointments/{appointment_id}/reschedule",
        data={"date": "2026-09-21", "time": "09:07", "room": "1"},
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "The appointment was not moved." in html
    assert "15-minute slot" in html
    with app.app_context():
        unchanged = db.session.get(Appointment, appointment_id)
        assert unchanged.start_time == time(8, 30)


def test_only_live_bookings_can_be_rescheduled(app, client):
    with app.app_context():
        first, _, _ = _booking_set()
        first.status = STATUS_CANCELLED
        db.session.commit()
        appointment_id = first.id

    page = client.get(f"/appointments/{appointment_id}/reschedule").get_data(as_text=True)
    assert "Only a live booking can be rescheduled." in page
    assert "Move appointment" not in page

    response = client.post(
        f"/appointments/{appointment_id}/reschedule",
        data={"date": "2026-09-22", "time": "10:00", "room": "1"},
    )
    assert response.status_code == 200
    with app.app_context():
        saved = db.session.get(Appointment, appointment_id)
        assert saved.status == STATUS_CANCELLED
        assert saved.date == MONDAY
        assert saved.start_time == time(8, 30)


def test_consultation_confirmation_links_to_reschedule(app, client):
    with app.app_context():
        first, _, _ = _booking_set()
        appointment_id = first.id

    page = client.get(f"/consultations/{appointment_id}").get_data(as_text=True)

    assert f"/appointments/{appointment_id}/reschedule" in page
    assert "Reschedule this appointment" in page


def test_client_history_links_booked_appointments_to_reschedule(app, client):
    with app.app_context():
        first, _, _ = _booking_set()
        client_id = first.client_id
        appointment_id = first.id

    page = client.get(f"/clients/{client_id}/appointments").get_data(as_text=True)

    assert f"/appointments/{appointment_id}/reschedule" in page
    assert "Reschedule this appointment" in page
