"""Story MSD426GXUST3-46: booking an in-clinic consultation."""
from datetime import date, time, timedelta

import pytest

from app.models import (
    CONSULTATION,
    STATUS_BOOKED,
    STATUS_CANCELLED,
    Animal,
    Appointment,
    Client,
    db,
)

def _next_weekday(weekday, earliest_offset=2):
    """Return the next date with ``weekday`` (0 = Monday), a few days out.

    The booking rules refuse dates in the past (story MSD426GXUST3-47), so the
    tests pick their dates relative to to-day instead of hard-coding one.
    """
    candidate = date.today() + timedelta(days=earliest_offset)
    return candidate + timedelta(days=(weekday - candidate.weekday()) % 7)


MONDAY_DATE = _next_weekday(0)
SUNDAY_DATE = _next_weekday(6)
MONDAY = MONDAY_DATE.isoformat()
SUNDAY = SUNDAY_DATE.isoformat()


@pytest.fixture
def biscuit(app):
    """Mrs Prosser's cat, straight from the case study appointment book."""
    with app.app_context():
        owner = Client(name="Mrs Prosser", phone="0417 552 118")
        animal = Animal(name="Biscuit", species="Cat", client=owner)
        db.session.add(animal)
        db.session.commit()
        return animal.id


def book(client, animal_id, day=MONDAY, start="09:00", room="1", reason="F3 vaccination"):
    return client.post(
        "/consultations/new",
        data={
            "animal_id": "" if animal_id is None else str(animal_id),
            "date": day,
            "start_time": start,
            "room": room,
            "reason": reason,
        },
    )


def test_booking_form_offers_the_day_and_its_slots(client, biscuit):
    response = client.get(f"/consultations/new?date={MONDAY}")
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Book an in-clinic consultation" in page
    assert 'value="08:30"' in page and "8:30 am" in page
    assert "Biscuit" in page


def test_sunday_offers_no_slots(client, biscuit):
    page = client.get(f"/consultations/new?date={SUNDAY}").get_data(as_text=True)
    assert "does not take consultations" in page


def test_booking_saves_the_consultation_then_shows_confirmation(app, client, biscuit):
    response = book(client, biscuit)
    assert response.status_code == 303

    confirmation = client.get(response.headers["Location"])
    page = confirmation.get_data(as_text=True)
    assert confirmation.status_code == 200
    assert "Consultation booked" in page
    assert "Biscuit" in page and "Room 1" in page

    with app.app_context():
        appointment = Appointment.query.one()
        assert appointment.kind == CONSULTATION
        assert appointment.status == STATUS_BOOKED
        assert appointment.animal_id == biscuit
        assert appointment.room == 1
        assert appointment.date == MONDAY_DATE
        assert appointment.start_time == time(9, 0)
        assert appointment.client.name == "Mrs Prosser"
        assert appointment.reason == "F3 vaccination"


def test_a_room_cannot_hold_two_live_consultations(app, client, biscuit):
    assert book(client, biscuit).status_code == 303
    second = book(client, biscuit)
    assert second.status_code == 200
    assert "already booked for that slot" in second.get_data(as_text=True)
    with app.app_context():
        assert Appointment.query.count() == 1


def test_the_second_room_can_take_the_same_slot(app, client, biscuit):
    assert book(client, biscuit, room="1").status_code == 303
    assert book(client, biscuit, room="2").status_code == 303
    with app.app_context():
        assert Appointment.query.count() == 2


def test_times_off_the_fifteen_minute_grid_are_rejected(app, client, biscuit):
    response = book(client, biscuit, start="09:07")
    assert "not a 15-minute slot" in response.get_data(as_text=True)
    with app.app_context():
        assert Appointment.query.count() == 0


def test_sunday_consultations_are_rejected(app, client, biscuit):
    response = book(client, biscuit, day=SUNDAY)
    assert "does not take consultations on this day" in response.get_data(as_text=True)
    with app.app_context():
        assert Appointment.query.count() == 0


def test_rooms_other_than_one_or_two_are_rejected(app, client, biscuit):
    response = book(client, biscuit, room="3")
    assert "consulting room 1 or 2" in response.get_data(as_text=True)
    with app.app_context():
        assert Appointment.query.count() == 0


def test_an_animal_is_required(app, client, biscuit):
    response = book(client, None)
    assert "must be booked for one animal" in response.get_data(as_text=True)
    with app.app_context():
        assert Appointment.query.count() == 0


def test_cancelled_bookings_do_not_block_the_slot(app, client, biscuit):
    with app.app_context():
        animal = db.session.get(Animal, biscuit)
        db.session.add(
            Appointment(
                kind=CONSULTATION,
                status=STATUS_CANCELLED,
                client=animal.client,
                animal=animal,
                date=MONDAY_DATE,
                start_time=time(9, 0),
                room=1,
            )
        )
        db.session.commit()

    assert book(client, biscuit).status_code == 303
    with app.app_context():
        assert Appointment.query.count() == 2


def test_an_unknown_consultation_is_a_404(client):
    assert client.get("/consultations/999").status_code == 404


def test_missing_choices_are_explained_in_english(client, biscuit):
    page = client.get(f"/consultations/new?date={MONDAY}").get_data(as_text=True)
    assert 'data-error="Please choose an animal."' in page
    assert 'data-error="Please choose a time slot."' in page
    assert 'data-error="Please choose a consulting room."' in page
    assert "js/form-validation.js" in page


def test_the_validation_script_is_served(client):
    response = client.get("/static/js/form-validation.js")
    assert response.status_code == 200
    assert b"setCustomValidity" in response.data
