"""Story MSD426GXUST3-48: booking a farm visit."""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models import FARM_VISIT, STATUS_BOOKED, Appointment, Client, Property, db


def _next_weekday(weekday, earliest_offset=2):
    """The next date with ``weekday`` (0 = Monday), a few days out.

    The rules refuse dates in the past, so the tests pick their day relative to
    to-day rather than hard-coding one.
    """
    candidate = date.today() + timedelta(days=earliest_offset)
    return candidate + timedelta(days=(weekday - candidate.weekday()) % 7)


TUESDAY_DATE = _next_weekday(1)
TUESDAY = TUESDAY_DATE.isoformat()


@pytest.fixture
def stony_creek(app):
    """The Callaghans' place, straight from the case study farm run sheet."""
    with app.app_context():
        owner = Client(name="Bridie & Tom Callaghan", phone="0417 884 260")
        farm = Property(
            client=owner,
            name="Stony Creek",
            locality="Bunjurgen",
            access_notes="3 gates; the last one has a chain and no code.",
        )
        db.session.add(farm)
        db.session.commit()
        return farm.id


def book(client, property_id, day=TUESDAY, start="11:15", hours="3.0", reason="Preg test, 120 head"):
    return client.post(
        "/farm-visits/new",
        data={
            "property_id": "" if property_id is None else str(property_id),
            "date": day,
            "start_time": start,
            "estimated_hours": hours,
            "reason": reason,
        },
    )


def test_the_form_lists_the_properties_under_their_client(client, stony_creek):
    response = client.get(f"/farm-visits/new?date={TUESDAY}")
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Book a farm visit" in page
    assert "Bridie &amp; Tom Callaghan" in page
    assert "Stony Creek (Bunjurgen)" in page


def test_the_form_offers_half_hour_steps(client, stony_creek):
    page = client.get(f"/farm-visits/new?date={TUESDAY}").get_data(as_text=True)
    assert 'value="0.5"' in page
    assert 'value="3.0"' in page
    assert "1 hour</option>" in page
    assert 'value="1.25"' not in page
    assert "Please choose an estimated duration." in page


def test_booking_a_visit_saves_it_then_shows_confirmation(app, client, stony_creek):
    response = book(client, stony_creek)
    assert response.status_code == 303

    confirmation = client.get(response.headers["Location"])
    page = confirmation.get_data(as_text=True)
    assert confirmation.status_code == 200
    assert "Farm visit booked" in page
    assert "Stony Creek" in page
    assert "3 hours on the road" in page
    assert "3 gates; the last one has a chain and no code." in page

    with app.app_context():
        appointment = Appointment.query.one()
        assert appointment.kind == FARM_VISIT
        assert appointment.status == STATUS_BOOKED
        assert appointment.property_id == stony_creek
        assert appointment.animal_id is None
        assert appointment.room is None
        assert appointment.date == TUESDAY_DATE
        assert appointment.start_time.strftime("%H:%M") == "11:15"
        assert appointment.estimated_hours == Decimal("3.0")
        assert appointment.client.name == "Bridie & Tom Callaghan"
        assert appointment.reason == "Preg test, 120 head"


def test_a_visit_needs_a_property(app, client, stony_creek):
    response = book(client, None)
    assert "must be booked against a property" in response.get_data(as_text=True)
    with app.app_context():
        assert Appointment.query.count() == 0


def test_a_visit_needs_a_start_time(app, client, stony_creek):
    response = book(client, stony_creek, start="")
    assert "Enter the time the vet leaves for the property" in response.get_data(as_text=True)
    with app.app_context():
        assert Appointment.query.count() == 0


def test_a_visit_needs_an_estimated_duration(app, client, stony_creek):
    response = book(client, stony_creek, hours="")
    assert "needs an estimated duration" in response.get_data(as_text=True)
    with app.app_context():
        assert Appointment.query.count() == 0


def test_the_duration_must_be_in_half_hour_steps(app, client, stony_creek):
    response = book(client, stony_creek, hours="1.25")
    assert "half-hour steps" in response.get_data(as_text=True)
    with app.app_context():
        assert Appointment.query.count() == 0


def test_an_unknown_visit_is_a_404(client):
    assert client.get("/farm-visits/999").status_code == 404
